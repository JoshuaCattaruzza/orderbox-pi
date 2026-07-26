import logging
import os
import subprocess
import threading

from config import NOTIFICATION_SOUND_ENABLED

log = logging.getLogger(__name__)

SOUND_FILE = os.path.join(os.path.dirname(__file__), "static", "audio", "notification.wav")


def play_notification():
    if not NOTIFICATION_SOUND_ENABLED:
        return
    threading.Thread(target=_play, daemon=True).start()


def _play():
    try:
        subprocess.run(
            ["aplay", "-q", SOUND_FILE],
            check=True, capture_output=True, timeout=10,
        )
    except Exception:
        log.exception("Failed to play notification sound")
