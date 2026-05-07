import requests
from config import API_URL, SUBDOMAIN, PI_API_KEY

TIMEOUT = 5


def _headers():
    h = {"Content-Type": "application/json"}
    if PI_API_KEY:
        h["X-Api-Key"] = PI_API_KEY
    return h


def _url(path):
    return f"{API_URL}/pi/{SUBDOMAIN}{path}"


def get_orders(statuses=None):
    if statuses is None:
        statuses = ["NEW", "ACCEPTED", "PRINTED"]
    resp = requests.get(
        _url("/orders"),
        params={"status": ",".join(statuses)},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["orders"]


def accept_order(order_id, eta_minutes=20):
    resp = requests.post(
        _url(f"/orders/{order_id}/accept"),
        json={"eta_minutes": eta_minutes},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def decline_order(order_id):
    resp = requests.post(
        _url(f"/orders/{order_id}/decline"),
        json={},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def mark_printed(order_id):
    resp = requests.post(
        _url(f"/orders/{order_id}/print"),
        json={},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def complete_order(order_id):
    resp = requests.post(
        _url(f"/orders/{order_id}/complete"),
        json={},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()
