#!/usr/bin/env bash
# Run once on the Pi after cloning the repo.
# Usage: bash scripts/install.sh
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_USER="${SUDO_USER:-$USER}"

echo "==> Installing system packages"
sudo apt update -q
sudo apt install -y python3-pip python3-venv autossh libusb-1.0-0 cups unclutter

echo "==> Creating Python virtual environment"
python3 -m venv "$REPO_DIR/venv"
"$REPO_DIR/venv/bin/pip" install --quiet --upgrade pip
"$REPO_DIR/venv/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

echo "==> Setting up .env"
if [ ! -f "$REPO_DIR/.env" ]; then
  cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
  echo "    Created .env from example — edit it before starting the service"
fi

echo "==> Installing systemd services"
sudo cp "$REPO_DIR/systemd/orderbox-pi.service"     /etc/systemd/system/
sudo cp "$REPO_DIR/systemd/orderbox-tunnel.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orderbox-pi.service

echo "==> Configuring kiosk autostart"
AUTOSTART_DIR="/home/$INSTALL_USER/.config/lxsession/rpd-x"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/autostart" <<EOF
@xset s off
@xset -dpms
@xset s noblank
@unclutter -idle 0.5 -root
@chromium --kiosk --noerrdialogs --disable-infobars --no-first-run --window-size=800,480 http://localhost:5000
EOF

echo ""
echo "Done. Next steps:"
echo "  1. Edit $REPO_DIR/.env with your API URL, subdomain, and printer IP"
echo "  2. Fill in your GCP IP in systemd/orderbox-tunnel.service, then:"
echo "       sudo systemctl enable orderbox-tunnel.service"
echo "       sudo systemctl start  orderbox-tunnel.service"
echo "  3. Start the dashboard:"
echo "       sudo systemctl start orderbox-pi.service"
echo "  4. Reboot and confirm Chromium opens automatically"
