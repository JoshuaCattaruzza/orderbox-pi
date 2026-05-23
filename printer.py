import logging
from config import PRINTER_DEV

log = logging.getLogger(__name__)

PAPER_WIDTH = 32  # 58mm paper = 32 chars; change to 48 for 80mm paper
LINE = "─" * PAPER_WIDTH


def format_line(left, right, width=PAPER_WIDTH):
    gap = width - len(left) - len(right)
    if gap < 1:
        gap = 1
    return left + " " * gap + right


def print_order(order):
    from escpos.printer import File

    p = File(PRINTER_DEV)
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
            left = f"{qty}x {name}"
            right = f"£{total}" if total else ""
            p.text(format_line(left, right) + "\n")
            p.text("\n")
    else:
        p.text("(no item details)\n")

    p.text(f"{LINE}\n")

    # Total
    p.set(bold=True)
    p.text(format_line("TOTAL", f"£{order.get('total_amount') or '0.00'}") + "\n")
    p.set(bold=False)

    # Customer note
    note = metadata.get("customer_note", "").strip()
    if note:
        p.text(f"\nNote: {note}\n")

    p.text("\n\n\n")
    p.cut()
