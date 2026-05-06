import threading
import time
import logging
from api_client import get_orders

log = logging.getLogger(__name__)


class OrderPoller:
    def __init__(self, interval=10):
        self.interval = interval
        self._orders = {}
        self._lock = threading.Lock()
        self._new_order_callbacks = []
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def on_new_order(self, callback):
        self._new_order_callbacks.append(callback)

    def get_orders(self):
        with self._lock:
            return list(self._orders.values())

    def _run(self):
        while True:
            try:
                orders = get_orders(["NEW", "ACCEPTED", "PRINTED"])

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

            except Exception:
                log.exception("Polling error")

            time.sleep(self.interval)
