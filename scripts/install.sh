#!/usr/bin/env bash
# Run once on the Pi after cloning the repo.
# Usage: sudo bash scripts/install.sh
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_USER="${SUDO_USER:-$USER}"
SSH_KEY="/home/$INSTALL_USER/.ssh/orderbox_tunnel"

echo "==> Enabling SSH"
sudo systemctl enable ssh
sudo systemctl start ssh

echo "==> Enabling desktop auto-login for $INSTALL_USER"
sudo raspi-config nonint do_boot_behaviour B4

echo "==> Installing system packages"
sudo apt update -q
sudo apt install -y python3-pip python3-venv autossh libusb-1.0-0 cups unclutter \
  xserver-xorg-video-fbdev xserver-xorg-legacy at \
  alsa-utils espeak sox mpg123

echo "==> Creating Python virtual environment"
python3 -m venv "$REPO_DIR/venv"
"$REPO_DIR/venv/bin/pip" install --quiet --upgrade pip
"$REPO_DIR/venv/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

echo "==> Setting up .env"
if [ ! -f "$REPO_DIR/.env" ]; then
  cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
  echo "    Created .env from example — edit it before starting the service"
fi

echo "==> Adding $INSTALL_USER to lp group (printer access)"
sudo usermod -a -G lp "$INSTALL_USER"

echo "==> Configuring audio boot overlay (MAX98357A I2S DAC)"
CONFIG_TXT="/boot/firmware/config.txt"
REBOOT_REQUIRED=""
if [ -f "$CONFIG_TXT" ]; then
  sudo cp "$CONFIG_TXT" "$CONFIG_TXT.orderbox-bak"
  # Remove any conflicting onboard-audio-enable line before adding audio=off
  sudo sed -i '/^dtparam=audio=on/d' "$CONFIG_TXT"
  ADDED=""
  for line in "dtoverlay=vc4-kms-v3d" "dtoverlay=hifiberry-dac" "dtparam=audio=off"; do
    if ! grep -qxF "$line" "$CONFIG_TXT"; then
      echo "$line" | sudo tee -a "$CONFIG_TXT" > /dev/null
      ADDED="$ADDED $line;"
    fi
  done
  if [ -n "$ADDED" ]; then
    echo "    Added to config.txt:$ADDED"
    echo "    (backup saved at $CONFIG_TXT.orderbox-bak)"
    REBOOT_REQUIRED=1
  else
    echo "    Already configured"
  fi
else
  echo "    WARNING: $CONFIG_TXT not found — configure the hifiberry-dac and vc4-kms-v3d overlays manually"
fi

echo "==> Installing systemd services"
sudo cp "$REPO_DIR/systemd/orderbox-pi.service"          /etc/systemd/system/
sudo cp "$REPO_DIR/systemd/orderbox-tunnel.service"      /etc/systemd/system/
sudo cp "$REPO_DIR/systemd/orderbox-audio-setup.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orderbox-pi.service
sudo systemctl enable orderbox-audio-setup.service

echo "==> Detecting audio card now (best-effort — only works if the overlay is already active)"
sudo bash "$REPO_DIR/scripts/detect-audio-card.sh" || true

echo "==> Detecting SPI display framebuffer device"
FB_DEV=""
for fb in /sys/class/graphics/fb*; do
  name=$(cat "$fb/name" 2>/dev/null || true)
  if [ "$name" = "fb_ili9486" ]; then
    FB_DEV="/dev/$(basename "$fb")"
    break
  fi
done

if [ -z "$FB_DEV" ]; then
  echo "    WARNING: fb_ili9486 not found — defaulting to /dev/fb1"
  echo "    If the display is blank, check: cat /sys/class/graphics/fb*/name"
  FB_DEV="/dev/fb1"
else
  echo "    Found ILI9486 display at $FB_DEV"
fi

echo "==> Writing /etc/X11/Xwrapper.config"
sudo tee /etc/X11/Xwrapper.config > /dev/null <<EOF
allowed_users=anybody
needs_root_rights=yes
EOF

echo "==> Writing /etc/X11/xorg.conf (using $FB_DEV)"
sudo tee /etc/X11/xorg.conf > /dev/null <<EOF
Section "Device"
    Identifier "SPI Display"
    Driver "fbdev"
    Option "fbdev" "$FB_DEV"
EndSection
Section "Monitor"
    Identifier "Monitor0"
EndSection
Section "Screen"
    Identifier "Screen0"
    Device "SPI Display"
    Monitor "Monitor0"
    DefaultDepth 16
    SubSection "Display"
        Depth 16
        Modes "480x320"
    EndSubSection
EndSection
EOF

echo "==> Configuring autostart (kiosk + unclutter)"
AUTOSTART_DIR="/home/$INSTALL_USER/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/orderbox-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OrderBox Kiosk
Exec=chromium --kiosk --noerrdialogs --disable-infobars --no-first-run --window-size=800,480 --force-renderer-accessibility --password-store=basic http://localhost:5000
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

cat > "$AUTOSTART_DIR/unclutter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Unclutter
Exec=unclutter -idle 1 -root
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

echo "==> Granting passwordless nmcli for WiFi management"
echo "$INSTALL_USER ALL=(ALL) NOPASSWD: /usr/bin/nmcli" | sudo tee /etc/sudoers.d/orderbox-nmcli > /dev/null
sudo chmod 440 /etc/sudoers.d/orderbox-nmcli

echo "==> Generating SSH tunnel key"
mkdir -p "/home/$INSTALL_USER/.ssh"
chmod 700 "/home/$INSTALL_USER/.ssh"
if [ ! -f "$SSH_KEY" ]; then
  ssh-keygen -t ed25519 -f "$SSH_KEY" -N "" -C "orderbox-pi-tunnel"
  echo "    Key generated at $SSH_KEY"
else
  echo "    Key already exists at $SSH_KEY — skipping"
fi
chown "$INSTALL_USER:$INSTALL_USER" "$SSH_KEY" "$SSH_KEY.pub"

echo "==> Enabling tunnel service (will start once key is on the VM)"
sudo systemctl enable orderbox-tunnel.service

PUBKEY=$(cat "$SSH_KEY.pub")

echo ""
echo "======================================================"
echo " NEXT STEPS"
echo "======================================================"
echo ""
echo "1. Edit $REPO_DIR/.env with your API URL, subdomain, printer IP and API key"
echo ""
echo "2. Run this ONE command from your dev machine to authorise the tunnel:"
echo ""
echo "   gcloud compute ssh orderbox-wp-vm --zone=europe-west2-b --project=orderbox-487000 --command=\"echo '$PUBKEY' >> ~/.ssh/authorized_keys\""
echo ""
echo "3. Then on the Pi:"
echo "       sudo systemctl start orderbox-tunnel.service"
echo "       sudo systemctl start orderbox-pi.service"
echo ""
echo "4. Wire the MAX98357A I2S amp breakout to the GPIO header before first boot:"
echo "       VIN->5V(pin2/4)  GND->any GND  BCLK->GPIO18(pin12)"
echo "       LRC->GPIO19(pin35)  DIN->GPIO21(pin40)  GAIN->3.3V(pin1)  SD->3.3V(pin17)"
echo ""
if [ -n "$REBOOT_REQUIRED" ]; then
  echo "5. REBOOT REQUIRED — audio overlay lines were just added to config.txt"
  echo "       sudo reboot"
else
  echo "5. Reboot and confirm Chromium opens automatically"
fi
