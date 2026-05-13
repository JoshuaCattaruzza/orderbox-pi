import os
from dotenv import load_dotenv

load_dotenv()

API_URL      = os.getenv("ORDERBOX_API_URL", "http://localhost:3000")
SUBDOMAIN    = os.getenv("ORDERBOX_SUBDOMAIN", "demo")
PI_API_KEY   = os.getenv("ORDERBOX_PI_API_KEY", "")
PRINTER_DEV  = os.getenv("PRINTER_DEV", "/dev/usb/lp0")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
