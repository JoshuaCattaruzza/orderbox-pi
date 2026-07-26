import logging
import os
import subprocess
from flask import Flask, render_template, jsonify, request
from requests.exceptions import HTTPError
from poller import OrderPoller
from printer import print_order
from notifier import play_notification
import api_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
poller = OrderPoller()


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response

_tenant_info = {}
_wc_auth_error = False
try:
    _tenant_info = api_client.get_tenant_info()
    _wc_auth_error = bool(_tenant_info.get("wc_auth_error", False))
    if _tenant_info.get("pi_was_offline"):
        poller.note_reconnect()
    log.info("Tenant info loaded: %s, wc_auth_error=%s", _tenant_info.get("restaurant_name"), _wc_auth_error)
except Exception:
    log.warning("Failed to fetch tenant info — receipt header will be empty")

_paused = False
try:
    _paused = api_client.get_pause_status()
    log.info("Pause state on startup: %s", _paused)
except Exception:
    log.warning("Failed to fetch pause state — defaulting to unpaused")


@poller.on_new_order
def _on_new_order(order):
    log.info("New order: #%s from %s", order["woo_order_id"], order.get("customer_name"))


@poller.on_pending_new_orders
def _on_pending_new_orders():
    play_notification()


poller.start()


KIOSK_MODE = os.environ.get("KIOSK_MODE", "false").lower() == "true"


@app.route("/")
def dashboard():
    return render_template("dashboard.html", kiosk=KIOSK_MODE)


@app.route("/api/orders")
def orders():
    all_orders = poller.get_orders()
    return jsonify({
        "NEW":          [o for o in all_orders if o["status"] == "NEW"],
        "ACCEPTED":     [o for o in all_orders if o["status"] == "ACCEPTED"],
        "PRINTED":      [o for o in all_orders if o["status"] == "PRINTED"],
        "paused":       _paused,
        "wc_auth_error": _wc_auth_error,
        "reconnect_notice": poller.get_reconnect_notice(),
    })


@app.route("/api/orders/<int:order_id>/accept", methods=["POST"])
def accept(order_id):
    data = request.get_json(silent=True) or {}
    eta = data.get("eta_minutes", 20)
    result = api_client.accept_order(order_id, eta)

    # Print immediately after accepting and mark as printed
    order = next((o for o in poller.get_orders() if o["id"] == order_id), None)
    print_ok = False
    if order:
        try:
            print_order(order, _tenant_info)
            print_ok = True
        except Exception:
            log.exception("Print failed for order %s", order_id)

    if print_ok:
        try:
            api_client.mark_printed(order_id)
        except Exception:
            log.exception("mark_printed failed for order %s", order_id)

    return jsonify({**result, "print_ok": print_ok})


@app.route("/api/orders/<int:order_id>/decline", methods=["POST"])
def decline(order_id):
    try:
        return jsonify(api_client.decline_order(order_id))
    except HTTPError as e:
        try:
            body = e.response.json()
        except Exception:
            body = {"error": str(e)}
        return jsonify(body), e.response.status_code


@app.route("/api/orders/<int:order_id>/complete", methods=["POST"])
def complete(order_id):
    try:
        return jsonify(api_client.complete_order(order_id))
    except HTTPError as e:
        return jsonify({"error": str(e)}), e.response.status_code


@app.route("/api/orders/history")
def history():
    try:
        orders, _ = api_client.get_orders(["COMPLETED", "CANCELLED"])
        return jsonify({"orders": orders})
    except Exception as e:
        log.exception("Failed to fetch history")
        return jsonify({"error": str(e)}), 500


def _refresh_tenant_info():
    global _tenant_info, _wc_auth_error
    import threading
    try:
        info = api_client.get_tenant_info()
        _tenant_info = info
        _wc_auth_error = bool(info.get("wc_auth_error", False))
        if info.get("pi_was_offline"):
            poller.note_reconnect()
    except Exception:
        log.warning("Background tenant info refresh failed")
    threading.Timer(60, _refresh_tenant_info).start()

_refresh_tenant_info()


@app.route("/api/pause", methods=["POST"])
def pause():
    global _paused
    try:
        result = api_client.pause()
        _paused = True
        return jsonify(result)
    except Exception as e:
        log.exception("Pause failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/resume", methods=["POST"])
def resume():
    global _paused
    try:
        result = api_client.resume()
        _paused = False
        return jsonify(result)
    except Exception as e:
        log.exception("Resume failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/orders/<int:order_id>/reprint", methods=["POST"])
def reprint(order_id):
    order = request.get_json(silent=True)
    if not order:
        order = next((o for o in poller.get_orders() if o["id"] == order_id), None)
    if not order:
        return jsonify({"error": "order not found"}), 404
    try:
        print_order(order, _tenant_info, reprint=True)
        return jsonify({"ok": True})
    except Exception as e:
        log.exception("Reprint failed for order %s", order_id)
        return jsonify({"error": str(e)}), 500


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/api/wifi/status")
def wifi_status():
    try:
        r = subprocess.run(
            ["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "dev"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split("\n"):
            parts = line.split(":")
            if len(parts) >= 3 and parts[0] == "wifi":
                conn = parts[2] if parts[2] not in ("--", "") else None
                return jsonify({"state": parts[1], "connection": conn})
        return jsonify({"state": "unknown", "connection": None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/wifi/networks")
def wifi_networks():
    try:
        r = subprocess.run(
            ["sudo", "nmcli", "--escape", "yes", "-t", "-f", "SSID,SIGNAL,SECURITY",
             "dev", "wifi", "list", "--rescan", "yes"],
            capture_output=True, text=True, timeout=20
        )
        networks = []
        seen = set()
        for line in r.stdout.strip().split("\n"):
            if not line:
                continue
            # SSID may contain ':'; SIGNAL and SECURITY never do — split from right
            parts = line.split(":")
            if len(parts) < 3:
                continue
            security = parts[-1]
            signal_str = parts[-2]
            ssid = ":".join(parts[:-2])
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try:
                signal = int(signal_str)
            except ValueError:
                signal = 0
            networks.append({"ssid": ssid, "signal": signal, "security": security})
        networks.sort(key=lambda x: x["signal"], reverse=True)
        return jsonify({"networks": networks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/wifi/connect", methods=["POST"])
def wifi_connect():
    data = request.get_json(silent=True) or {}
    ssid = data.get("ssid", "").strip()
    password = data.get("password", "").strip()
    if not ssid:
        return jsonify({"error": "SSID required"}), 400
    try:
        cmd = ["sudo", "nmcli", "dev", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return jsonify({"ok": True})
        else:
            msg = (r.stderr or r.stdout).strip()
            return jsonify({"ok": False, "error": msg}), 400
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Connection timed out"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
