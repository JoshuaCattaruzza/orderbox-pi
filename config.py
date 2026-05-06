import os
from dotenv import load_dotenv

load_dotenv()

API_URL      = os.getenv("ORDERBOX_API_URL", "http://localhost:3000")
SUBDOMAIN    = os.getenv("ORDERBOX_SUBDOMAIN", "demo")
PI_API_KEY   = os.getenv("ORDERBOX_PI_API_KEY", "")
PRINTER_IP   = os.getenv("PRINTER_IP", "")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
