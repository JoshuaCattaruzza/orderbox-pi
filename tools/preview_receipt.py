#!/usr/bin/env python3
"""Render a receipt as plain text for layout review without a physical printer.

Usage (from orderbox-pi/):
    python3 tools/preview_receipt.py [--reprint] [order.json]

Reuses printer.py's real _print() formatting logic unmodified — this only
stubs the driver surface (set/text/cut/close), not any layout/wrapping code.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from printer import _print  # noqa: E402

SAMPLE_ORDER = {
    "woo_order_id": 3507,
    "customer_name": "Joshua Cattaruzza",
    "customer_phone": "07881682468",
    "delivery_type": "delivery",
    "total_amount": "50.25",
    "payment_method": "cod",
    "metadata": {
        "payment_method": "cod",
        "customer_note": "Extra napkins please",
        "shipping": {
            "address_1": "5 Poplar View",
            "address_2": "",
            "city": "Haverhill",
            "postcode": "CB9 7JE",
        },
        "shipping_total": "6.00",
        "meta_data": [
            {"key": "Delivery Date", "value": "25 July, 2026"},
            {"key": "_orddd_time_slot", "value": "As Soon As Possible."},
        ],
        "line_items": [
            {"quantity": 6, "name": "Plain Popadom", "total": "5.70"},
            {"quantity": 2, "name": "Lime Pickle", "total": "1.90"},
            {"quantity": 2, "name": "Mango Chutney", "total": "1.90"},
            {"quantity": 1, "name": "Vindaloo: Chicken", "total": "9.95"},
            {"quantity": 1, "name": "Pathia: Chicken", "total": "9.95"},
            {"quantity": 1, "name": "Bombay Potato", "total": "5.95"},
            {"quantity": 1, "name": "Pilau Rice", "total": "3.95"},
            {"quantity": 1, "name": "Special Rice", "total": "4.95"},
        ],
    },
}

SAMPLE_TENANT_INFO = {
    "restaurant_name": "The Raj Mahal",
    "restaurant_address": "61 High Street, Haverhill, Cambridge, CB9 8AH",
    "restaurant_phone": "01440 713009",
}


class PreviewPrinter:
    """Stubs only the driver surface _print() calls — no formatting logic here."""

    def __init__(self):
        self.lines = []
        self._bold = False
        self._big = False

    def set(self, align=None, bold=None, double_height=None, double_width=None, font=None):
        if bold is not None:
            self._bold = bold
        if double_height is not None or double_width is not None:
            self._big = bool(double_height) or bool(double_width)

    def text(self, txt):
        for line in txt.split("\n"):
            if not line:
                continue
            rendered = line
            if self._big:
                rendered = f"=={rendered}=="
            elif self._bold:
                rendered = f"**{rendered}**"
            self.lines.append(rendered)

    def cut(self):
        self.lines.append("--- CUT ---")

    def close(self):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("order_json", nargs="?", help="Path to a JSON file with {order, tenant_info}")
    parser.add_argument("--reprint", action="store_true")
    args = parser.parse_args()

    if args.order_json:
        with open(args.order_json) as f:
            data = json.load(f)
        order = data["order"]
        tenant_info = data.get("tenant_info", {})
    else:
        order = SAMPLE_ORDER
        tenant_info = SAMPLE_TENANT_INFO

    p = PreviewPrinter()
    _print(p, order, tenant_info, reprint=args.reprint)
    output = "\n".join(p.lines)

    print(output)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "receipt_preview.txt")
    with open(out_path, "w") as f:
        f.write(output + "\n")
    print(f"\n(also written to {out_path})", file=sys.stderr)


if __name__ == "__main__":
    main()
