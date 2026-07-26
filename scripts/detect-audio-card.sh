#!/usr/bin/env bash
# Detects the HifiBerry DAC (MAX98357A I2S amp) ALSA card number and writes
# /etc/asound.conf accordingly. Card numbers can shift after OS/kernel updates
# (HDMI outputs registering before/after it), so this runs on every boot rather
# than assuming a fixed card number.
set -e

CARD=$(aplay -l 2>/dev/null | awk -F'[ :]+' '/sndrpihifiberry/ {print $2; exit}')

if [ -z "$CARD" ]; then
  echo "orderbox-audio-setup: sndrpihifiberry card not found — leaving /etc/asound.conf untouched" >&2
  exit 0
fi

cat > /etc/asound.conf <<EOF
pcm.!default {
    type plug
    slave.pcm "hw:$CARD,0"
}

ctl.!default {
    type hw
    card $CARD
}
EOF

echo "orderbox-audio-setup: /etc/asound.conf set to card $CARD (sndrpihifiberry)"
