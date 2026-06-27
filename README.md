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

Insert the SD card, power on, then from your dev machine:

```bash
ssh pi@orderbox.local
```

### 3. Clone and run the install script

```bash
git clone <repo-url> ~/orderbox-pi
cd ~/orderbox-pi
sudo bash scripts/install.sh
```

The script will:
- Install all system packages (autossh, cups, unclutter, xserver-xorg-video-fbdev, etc.)
- Set up the Python venv
- Auto-detect the SPI display framebuffer device (ILI9486)
- Write `/etc/X11/xorg.conf` and `Xwrapper.config`
- Configure the Chromium kiosk autostart
- Generate the SSH tunnel key at `~/.ssh/orderbox_tunnel`
- Enable the `orderbox-pi` and `orderbox-tunnel` systemd services

At the end it will print a single `gcloud` command — copy it.

### 4. Authorise the tunnel key on the VM

Run the command printed by the install script on your dev machine. It looks like:

```bash
gcloud compute ssh orderbox-wp-vm --zone=europe-west2-b --project=orderbox-487000 --command="echo 'ssh-ed25519 AAAA...' >> ~/.ssh/authorized_keys"
```

### 5. Edit `.env`

```bash
nano ~/orderbox-pi/.env
```

Fill in:
- `ORDERBOX_API_URL` — API base URL
- `ORDERBOX_SUBDOMAIN` — restaurant subdomain
- `ORDERBOX_PI_API_KEY` — Pi API key
- `PRINTER_DEV` — printer device path (default `/dev/usb/lp0`)

### 6. Start services and reboot

```bash
sudo systemctl start orderbox-tunnel.service
sudo systemctl start orderbox-pi.service
sudo reboot
```

Chromium should open automatically on the touchscreen after reboot.

---

## Local dev

```bash
pip install -r requirements.txt
ORDERBOX_API_URL=http://localhost:3000 ORDERBOX_SUBDOMAIN=demo python main.py
```

Dashboard at `http://localhost:5000`.

## Configuration

All config is via environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `ORDERBOX_API_URL` | `http://localhost:3000` | OrderBox API base URL. In Docker, use the container name e.g. `http://host.docker.internal:3000` |
| `ORDERBOX_SUBDOMAIN` | `demo` | Tenant subdomain — must match the `subdomain` column in the API's `tenants` table |
| `ORDERBOX_PI_API_KEY` | _(empty)_ | Optional. If the tenant has a `pi_api_key` set, include it here as `X-Api-Key` |
| `PRINTER_DEV` | `/dev/usb/lp0` | USB device path for the thermal printer |
| `POLL_INTERVAL` | `10` | Seconds between order polls |
| `KIOSK_MODE` | `false` | Set to `true` on the Pi — disables cursor, text selection, and enables touch scroll |

## State managed in Flask (`main.py`)

Flask maintains two module-level flags that are included in every `/api/orders` response so the dashboard JS stays in sync on every 5-second poll:

### `_paused`
Whether ordering is currently paused. Initialised from `GET /public/:subdomain/status` on startup. Updated when the operator hits the Pause/Resume button. Included in `/api/orders` as `paused`.

### `_wc_auth_error`
Whether the API's WooCommerce credentials are failing. Initialised from `GET /pi/:subdomain/info` on startup, then refreshed every 60 seconds via a background timer. Included in `/api/orders` as `wc_auth_error`.

**Why poll every 60s for the auth error?** The flag is set by the API when a WC call returns 401, but it's cleared by the API when a subsequent WC call succeeds. Since successful WC calls happen on order actions (accept, decline, complete), they're infrequent. The 60s background poll ensures the banner clears within a minute of the keys being fixed — without waiting for the next order action.

## Dashboard behaviours

### Pause / resume
The header contains a Pause button. Tapping it shows a confirm modal (pausing affects all customers). Resume is immediate with no confirm — it's always safe. Both actions call `/api/pause` and `/api/resume` on Flask, which proxy to the API.

### WooCommerce auth error banner
When `wc_auth_error` is `true`, a red banner appears below the header:
> ⚠ WooCommerce connection error — API keys may be invalid. Update them in WooCommerce → Settings → Advanced → REST API.

The banner is **non-dismissable** — it stays until the API clears the flag. This is intentional: a silent WC auth failure means order status updates, notes, and refunds are all failing. The operator must fix the keys.

To fix: go to WooCommerce → Settings → Advanced → REST API, revoke the old key, create a new one, and update `woo_consumer_key` / `woo_consumer_secret` in the `tenants` table on the API's Postgres instance.

### Decline flow
Tapping Decline opens a confirm modal (irreversible, triggers a refund). On confirm, the API attempts a WooCommerce refund:
- Card payments: Stripe refund via `api_refund: true`
- COD: falls back to plain cancel (no money to refund)
- If the refund fails: Flask receives a 502 and the dashboard shows an error modal — **the operator must not decline until the refund issue is resolved**

### Accept flow
Tapping Accept opens an ETA picker (10 / 15 / 20 / 25 / 30 / 45 min). On selection, the API sends the ETA as a customer-facing WooCommerce order note, then the Pi prints the receipt. If printing fails, a modal prompts the operator to reprint manually.

### print_ok
Every accept response includes `print_ok: true/false`. If `false`, the order is still accepted on the API side — only the print failed. A modal directs the operator to use the Reprint button on the card.

## Printer

`printer.py` writes ESC/POS commands directly to `PRINTER_DEV`. If the device is absent (local dev), printing fails gracefully — `print_ok` is `false` and the order still transitions. The Reprint button on every In Prep card re-sends the print job.
