import logging
from config import PRINTER_DEV

log = logging.getLogger(__name__)

PAPER_WIDTH = 32  # 58mm paper, Font A
LINE = "─" * PAPER_WIDTH


def format_line(left, right, width=PAPER_WIDTH):
    max_left = width - len(right) - 1
    if len(left) > max_left:
        left = left[:max_left - 1] + "~"
    gap = width - len(left) - len(right)
    return left + " " * gap + right


def print_order(order, tenant_info=None, reprint=False):
    from escpos.printer import File

    p = File(PRINTER_DEV)
    try:
        _print(p, order, tenant_info or {}, reprint=reprint)
    finally:
        p.close()


def _print(p, order, tenant_info, reprint=False):
    metadata = order.get("metadata") or {}
    line_items = metadata.get("line_items") or []
    delivery_type = (order.get("delivery_type") or "collection").upper()

    # Restaurant header
    name    = (tenant_info.get("restaurant_name")    or "").strip()
    address = (tenant_info.get("restaurant_address") or "").strip()
    phone   = (tenant_info.get("restaurant_phone")   or "").strip()

    if name:
        p.set(align="center", bold=True, double_height=True, double_width=False)
        p.text(f"{name}\n")
        p.set(bold=False, double_height=False)
    if address:
        p.set(align="center")
        p.text(f"{address}\n")
    if phone:
        p.set(align="center")
        p.text(f"{phone}\n")
    if name or address or phone:
        p.text(f"{LINE}\n")

    # Order header
    p.set(align="center", bold=True, double_height=True, double_width=True)
    p.text("REPRINT\n" if reprint else "NEW ORDER\n")
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
    p.set(font="a", align="left", bold=False, double_height=False, double_width=False)
    if line_items:
        for item in line_items:
            qty = item.get("quantity", 1)
            item_name = item.get("name", "Item")
            total = item.get("total", "")
            left = f"{qty}x {item_name}"
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
