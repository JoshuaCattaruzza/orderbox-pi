import logging
from config import PRINTER_DEV

log = logging.getLogger(__name__)

PAPER_WIDTH   = 24  # Font A confirmed on physical printer
PAPER_WIDTH_B = 32  # Font B estimate (smaller chars, more per line)
LINE   = "─" * PAPER_WIDTH
LINE_B = "─" * PAPER_WIDTH_B


def _blen(s):
    return len(s.encode('utf-8'))

def format_line(left, right, width=PAPER_WIDTH):
    max_left = width - _blen(right) - 1
    while _blen(left) > max_left and left:
        left = left[:-1]
    if _blen(left) == max_left:
        left = left[:-1] + "~"
    gap = width - _blen(left) - _blen(right)
    if gap < 1:
        gap = 1
    return left + " " * gap + right


def _extract_delivery_time(metadata):
    meta_data = metadata.get("meta_data") or []
    time_slot = next((m["value"] for m in meta_data if m.get("key") == "_orddd_time_slot"), None)
    date      = next((m["value"] for m in meta_data if m.get("key") == "Delivery Date"), None)
    if date and time_slot: return f"{date} - {time_slot}"
    return time_slot or date or None


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
        p.set(align="center", bold=True)
        p.text(f"{name}\n")
        p.set(bold=False)
    if address:
        p.set(align="center")
        for part in address.split(","):
            part = part.strip()
            if part:
                p.text(f"{part}\n")
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
    p.text("[CUSTOMER]\n")
    p.text(f"{order.get('customer_name') or 'Unknown'}\n")
    p.set(bold=False)
    if order.get("customer_phone"):
        p.text(f"{order['customer_phone']}\n")

    # Delivery type
    p.text("\n")
    p.set(bold=True)
    p.text(f"[{delivery_type}]\n")
    p.set(bold=False)
    if delivery_type == "DELIVERY":
        shipping = metadata.get("shipping") or {}
        addr_parts = [
            shipping.get("address_1", ""),
            shipping.get("address_2", ""),
            shipping.get("city", ""),
            shipping.get("postcode", ""),
        ]
        for part in addr_parts:
            if part:
                p.text(f"{part}\n")

    meta_data = metadata.get("meta_data") or []
    delivery_date = next((m["value"] for m in meta_data if m.get("key") == "Delivery Date"), None)
    delivery_slot = next((m["value"] for m in meta_data if m.get("key") == "_orddd_time_slot"), None)
    if delivery_date or delivery_slot:
        p.text("\n")
    if delivery_date:
        p.set(bold=True)
        p.text(f"{delivery_date}\n")
        p.set(bold=False)
    if delivery_slot:
        p.set(bold=True)
        p.text(f"{delivery_slot}\n")
        p.set(bold=False)

    p.text(f"{LINE}\n")

    # Items — Font B for smaller text so more of the dish name is readable
    p.set(font="b", align="left", bold=False)
    if line_items:
        for item in line_items:
            qty = item.get("quantity", 1)
            item_name = item.get("name", "Item")
            total = item.get("total", "")
            left = f"{qty}x {item_name}"
            right = f"£{total}" if total else ""
            p.text(format_line(left, right, width=PAPER_WIDTH_B) + "\n")
            p.text("\n")
    else:
        p.text("(no item details)\n")

    p.text(f"{LINE_B}\n")

    # Total — stay in Font B to match item list width
    p.set(font="b", bold=True)
    p.text(format_line("TOTAL", f"£{order.get('total_amount') or '0.00'}", width=PAPER_WIDTH_B) + "\n")
    p.set(font="b", bold=False)

    # Payment method
    payment = (order.get("payment_method") or metadata.get("payment_method") or "").lower()
    p.text(f"{LINE_B}\n")
    p.set(font="a", bold=True, align="center")
    if payment in ("stripe", "woocommerce_payments"):
        p.text("** PAID ONLINE **\n")
        p.set(bold=False, align="center")
        p.text("Do not collect payment\n")
    elif payment == "cod":
        p.text("** CASH ON DELIVERY **\n")
        p.set(bold=False, align="center")
        p.text(f"Collect £{order.get('total_amount') or '0.00'}\n")
        p.text("at door\n")
    p.set(bold=False, align="left")

    # Customer note
    note = metadata.get("customer_note", "").strip()
    if note:
        p.text(f"\nNote: {note}\n")

    p.text("\n\n\n")
    p.cut()
