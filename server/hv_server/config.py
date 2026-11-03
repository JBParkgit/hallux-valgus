"""Server settings, read from environment variables (see server/.env.example)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# server/.env (next to this package) — on the Vultr box: /opt/hv-server/.env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


DATABASE_URL = _env("DATABASE_URL")

# X-ray storage directory (raw images, one file per case)
XRAY_DIR = Path(_env("XRAY_DIR", "/var/lib/hv-server/xray"))
MAX_XRAY_BYTES = int(_env("MAX_XRAY_MB", "25")) * 1024 * 1024

# Login sessions
TOKEN_TTL_HOURS = int(_env("TOKEN_TTL_HOURS", "12"))

# Public report page base URL; the case's reportHash is appended
REPORT_BASE_URL = _env("REPORT_BASE_URL", "https://hallux-valgus.vercel.app/report").rstrip("/")

# Alimtalk — sent through the existing relay server (it forwards to Biztalk as-is)
RELAY_URL = _env("ALIMTALK_RELAY_URL", "http://203.245.41.19:5003/send-alimtalk")
ALIMTALK_SENDER_KEY = _env("ALIMTALK_SENDER_KEY")
ALIMTALK_TEMPLATE_CODE = _env("ALIMTALK_TEMPLATE_CODE")
ALIMTALK_PF_ID = _env("ALIMTALK_PF_ID", "@달려라병원")
# Optional shared secret header for the relay (once the relay checks it)
ALIMTALK_RELAY_SECRET = _env("ALIMTALK_RELAY_SECRET")
