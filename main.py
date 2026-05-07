import logging
from flask import Flask, render_template, jsonify, request
from requests.exceptions import HTTPError
from poller import OrderPoller
from printer import print_order
import api_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
poller = OrderPoller()


@poller.on_new_order
def _on_new_order(order):
    log.info("New order: #%s from %s", order["woo_order_id"], order.get("customer_name"))


poller.start()


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/orders")
def orders():
    all_orders = poller.get_orders()
    return jsonify({
        "NEW":      [o for o in all_orders if o["status"] == "NEW"],
        "ACCEPTED": [o for o in all_orders if o["status"] == "ACCEPTED"],
        "PRINTED":  [o for o in all_orders if o["status"] == "PRINTED"],
    })


@app.route("/api/orders/<int:order_id>/accept", methods=["POST"])
def accept(order_id):
    data = request.get_json(silent=True) or {}
    eta = data.get("eta_minutes", 20)
    result = api_client.accept_order(order_id, eta)

    # Print immediately after accepting and mark as printed
    order = next((o for o in poller.get_orders() if o["id"] == order_id), None)
    if order:
        try:
            print_order(order)
        except Exception:
            log.exception("Print failed for order %s", order_id)
    api_client.mark_printed(order_id)

    return jsonify(result)


@app.route("/api/orders/<int:order_id>/decline", methods=["POST"])
def decline(order_id):
    try:
        return jsonify(api_client.decline_order(order_id))
    except HTTPError as e:
        return jsonify({"error": str(e)}), e.response.status_code


@app.route("/api/orders/<int:order_id>/complete", methods=["POST"])
def complete(order_id):
    try:
        return jsonify(api_client.complete_order(order_id))
    except HTTPError as e:
        return jsonify({"error": str(e)}), e.response.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
