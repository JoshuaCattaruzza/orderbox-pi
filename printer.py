import logging
from config import PRINTER_IP, PRINTER_PORT

log = logging.getLogger(__name__)

LINE = "─" * 32


def print_order(order):
    if not PRINTER_IP:
        log.warning("No PRINTER_IP configured — skipping print for order #%s", order["woo_order_id"])
        return

    from escpos.printer import Network

    p = Network(PRINTER_IP, port=PRINTER_PORT)
    try:
        _print(p, order)
    finally:
        p.close()


def _print(p, order):
    metadata = order.get("metadata") or {}
    line_items = metadata.get("line_items") or []
    delivery_type = (order.get("delivery_type") or "collection").upper()

    # Header
    p.set(align="center", bold=True, double_height=True, double_width=True)
    p.text("NEW ORDER\n")
    p.set(align="center", bold=False, double_height=False, double_width=False)
    p.text(f"Order #{order['woo_order_id']}\n")
    p.text(f"{LINE}\n")

    # Customer
    p.set(align="left", bold=True)
    p.text(f"{order.get('customer_name') or 'Unknown'}\n")
    p.set(bold=False)
    if order.get("customer_phone"):
        p.text(f"{order['customer_phone']}\n")

    # Delivery type
    p.text("\n")
    p.set(bold=True)
    p.text(f"[{delivery_type}]\n")
    p.set(bold=False)
    if delivery_type == "DELIVERY" and order.get("delivery_address"):
        p.text(f"{order['delivery_address']}\n")

    p.text(f"{LINE}\n")

    # Items
    if line_items:
        for item in line_items:
            qty = item.get("quantity", 1)
            name = item.get("name", "Item")
            total = item.get("total", "")
            price_str = f" £{total}" if total else ""
            p.text(f"{qty}x {name}{price_str}\n")
    else:
        p.text("(no item details)\n")

    p.text(f"{LINE}\n")

    # Total
    p.set(bold=True)
    p.text(f"TOTAL: £{order.get('total_amount') or '0.00'}\n")
    p.set(bold=False)

    # Customer note
    note = metadata.get("customer_note", "").strip()
    if note:
        p.text(f"\nNote: {note}\n")

    p.text("\n\n\n")
    p.cut()
