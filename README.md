# orderbox-pi

Python/Flask kiosk dashboard for OrderBox. Runs on a Raspberry Pi connected to a thermal printer. Polls the OrderBox API for orders and lets the operator accept, decline, and complete them.

## Architecture

```
orderbox-api  ←→  Flask (main.py)  ←→  Browser (dashboard.js)
                       ↓
                 Thermal printer (printer.py)
```

## Pi Setup

### 1. Flash the SD card

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) with these OS Customisation settings:

| Setting | Value |
|---|---|
| OS | Raspberry Pi OS (64-bit) — Desktop |
| Hostname | `orderbox` |
| Username | `pi` |
| Timezone | `Europe/London` |
| Keyboard | `gb` |
| SSH | Enabled (password auth) |

### 2. Boot and SSH in

```bash
ssh pi@orderbox.local
```

### 3. Clone and run the install script

```bash
git clone <repo-url> ~/orderbox-pi
cd ~/orderbox-pi
sudo bash scripts/install.sh
```

The script installs system packages, sets up the Python venv, auto-detects the SPI display framebuffer (ILI9486, falls back to `/dev/fb1`), writes Xorg config, configures Chromium kiosk autostart via XDG, grants passwordless `nmcli` for WiFi management, generates the SSH tunnel key at `~/.ssh/orderbox_tunnel`, and enables both systemd services.

At the end it prints a single `gcloud` command to authorise the tunnel key — copy it.

### 4. Authorise the tunnel key on the VM

Run the printed command from your dev machine:

```bash
gcloud compute ssh orderbox-wp-vm --zone=europe-west2-b --project=orderbox-487000 \
  --command="echo 'ssh-ed25519 AAAA...' >> ~/.ssh/authorized_keys"
```

### 5. Edit `.env`

```bash
nano ~/orderbox-pi/.env
```

| Variable | Description |
|---|---|
| `ORDERBOX_API_URL` | API base URL (e.g. `https://orderbox-api-xxx.a.run.app`) |
| `ORDERBOX_SUBDOMAIN` | Restaurant subdomain (must match `tenants.subdomain` in the DB) |
| `ORDERBOX_PI_API_KEY` | Pi API key (must match `tenants.pi_api_key` in the DB) |
| `PRINTER_DEV` | Printer device path (default `/dev/usb/lp0`) |
| `POLL_INTERVAL` | Seconds between order polls (default `10`) |
| `KIOSK_MODE` | Set to `true` on the Pi — disables cursor and text selection |

### 6. Start services and reboot

```bash
sudo systemctl start orderbox-tunnel.service
sudo systemctl start orderbox-pi.service
sudo reboot
```

Chromium opens `http://localhost:5000` automatically on the touchscreen after reboot.

---

## Local dev

```bash
pip install -r requirements.txt
ORDERBOX_API_URL=http://localhost:3000 ORDERBOX_SUBDOMAIN=demo python main.py
```

Dashboard at `http://localhost:5000`.

---

## Module-level state in Flask (`main.py`)

Two flags are initialised at startup and included in every `/api/orders` response, keeping the dashboard JS in sync without extra round trips:

**`_paused`** — whether ordering is paused. Loaded from `GET /public/:subdomain/status` on startup, updated immediately when the operator hits Pause/Resume.

**`_wc_auth_error`** — whether WooCommerce credentials are failing. Loaded from `GET /pi/:subdomain/info` on startup, then refreshed every 60 seconds via a background `threading.Timer`. The 60s poll ensures the banner clears shortly after the operator fixes the API keys, without waiting for the next order action.

**`_tenant_info`** — restaurant name, address, phone. Also refreshed every 60s. Used as the receipt header.

---

## Dashboard behaviours

### Live tab
Two columns: Incoming (NEW orders) and In Prep (ACCEPTED + PRINTED). The dashboard polls `/api/orders` every 5 seconds.

### History tab
Fetches COMPLETED and CANCELLED orders from the API on tab switch. Each card shows status badge, timestamps, line items, and a Reprint button.

### Accept flow
Tapping Accept opens an ETA picker (10 / 15 / 20 / 25 / 30 / 45 min). On selection:
1. API transitions `NEW → ACCEPTED` and posts an ETA note to the WooCommerce order (customer-visible)
2. Flask immediately prints the receipt
3. Flask calls `mark_printed` to transition `ACCEPTED → PRINTED`
4. If printing fails, `print_ok: false` is returned and a modal prompts the operator to use the Reprint button

### Decline flow
Opens a confirm modal (irreversible — triggers a refund). On confirm:
- Card payments: Stripe refund via WooCommerce `api_refund: true`
- COD orders: plain WooCommerce cancel (no money to refund)
- If the refund call fails: Flask receives 502 and shows an error modal — **the operator must not proceed until the issue is resolved**

### Complete flow
Opens a confirm modal, then transitions `PRINTED → COMPLETED` and marks the order completed in WooCommerce.

### Reprint
Available on every In Prep card and History card. Uses cached order data from `_orderData` (populated during polling). Calls `printer.py` with `reprint=True`, which prints `REPRINT` instead of `NEW ORDER` as the header.

### Pause / resume
Pause shows a confirm modal (affects all customers). Resume is immediate with no confirm. Both proxy to the OrderBox API, which propagates to WordPress within 30s.

### WooCommerce auth error banner
When `wc_auth_error` is true, a non-dismissable red banner appears below the header. It clears automatically once the API keys are fixed and any WC call succeeds.

To fix: WooCommerce → Settings → Advanced → REST API → revoke the old key, generate a new one, update `woo_consumer_key` and `woo_consumer_secret` in the `tenants` table.

### WiFi settings (`/settings`)
A separate page (accessible via the gear icon) lets the operator scan for networks, select one, enter a password via the embedded on-screen keyboard, and connect — all without a physical keyboard. Uses `nmcli` via Flask API endpoints (`/api/wifi/status`, `/api/wifi/networks`, `/api/wifi/connect`). The `pi` user has passwordless `nmcli` via `/etc/sudoers.d/orderbox-nmcli`.

---

## Printer (`printer.py`)

Writes ESC/POS directly to `PRINTER_DEV` via `python-escpos`. The receipt layout:

1. **Restaurant header** — name (bold, centred), address (split by comma, one line each), phone, separator line
2. **Order header** — `NEW ORDER` or `REPRINT` (double height/width), order number
3. **Customer** — name and phone
4. **Order type** — `[COLLECTION]` or `[DELIVERY]`. For delivery: full shipping address (line 1, line 2, city, postcode)
5. **Delivery time** — if present, date and time slot printed on separate bold lines (from WooCommerce meta keys `Delivery Date` and `_orddd_time_slot`)
6. **Items** — Font B (smaller, fits more dish name). Each item: `qty x name` right-aligned to `£price`. One blank line between items.
7. **Total** — Font B bold, right-aligned
8. **Payment** — `** PAID ONLINE **` (card) or `** CASH ON DELIVERY **` with collect amount
9. **Customer note** — if present
10. Three blank lines + cut

Constants: `PAPER_WIDTH = 24` (Font A), `PAPER_WIDTH_B = 32` (Font B). `_blen()` is used for byte-length calculations (£ = 2 UTF-8 bytes).

If `PRINTER_DEV` is absent (local dev), printing fails gracefully — `print_ok` is false but the order still transitions.

---

## SSH tunnel

The Pi maintains a persistent reverse SSH tunnel to the VM:

```
Pi → autossh → josh@34.89.22.14 port 2222 → Pi SSH port 22
```

This lets you SSH to the Pi from anywhere by hopping through the VM:

```bash
gcloud compute ssh orderbox-wp-vm --zone=europe-west2-b -- \
  ssh -p 2222 pi@localhost
```

The tunnel is managed by `systemd/orderbox-tunnel.service` using `autossh` with keepalives every 30s.
