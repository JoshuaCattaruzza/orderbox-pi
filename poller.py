import threading
import time
import logging
from api_client import get_orders

log = logging.getLogger(__name__)


RECONNECT_NOTICE_SECONDS = 300


class OrderPoller:
    def __init__(self, interval=10):
        self.interval = interval
        self._orders = {}
        self._lock = threading.Lock()
        self._new_order_callbacks = []
        self._pending_new_callbacks = []
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._reconnect_notice_until = 0

    def start(self):
        self._thread.start()

    def on_new_order(self, callback):
        self._new_order_callbacks.append(callback)

    def on_pending_new_orders(self, callback):
        # Fires every poll tick (not just on arrival) as long as at least one
        # order is still in NEW status — drives a repeating alert until the
        # restaurant accepts (-> ACCEPTED) or declines (-> CANCELLED, drops
        # out of the fetched list) it.
        self._pending_new_callbacks.append(callback)

    def get_orders(self):
        with self._lock:
            return list(self._orders.values())

    def get_reconnect_notice(self):
        return time.time() < self._reconnect_notice_until

    def note_reconnect(self):
        log.info("Pi reconnected after being auto-paused for lost connectivity")
        self._reconnect_notice_until = time.time() + RECONNECT_NOTICE_SECONDS

    def _run(self):
        while True:
            try:
                orders, pi_was_offline = get_orders(["NEW", "ACCEPTED", "PRINTED"])
                if pi_was_offline:
                    self.note_reconnect()

                with self._lock:
                    existing_ids = set(self._orders.keys())
                    self._orders = {o["id"]: o for o in orders}

                for order in orders:
                    if order["id"] not in existing_ids:
                        log.info("New order arrived: #%s", order["woo_order_id"])
                        for cb in self._new_order_callbacks:
                            try:
                                cb(order)
                            except Exception:
                                log.exception("Error in new-order callback")

                if any(o["status"] == "NEW" for o in orders):
                    for cb in self._pending_new_callbacks:
                        try:
                            cb()
                        except Exception:
                            log.exception("Error in pending-new-orders callback")

            except Exception:
                log.exception("Polling error")

            time.sleep(self.interval)
