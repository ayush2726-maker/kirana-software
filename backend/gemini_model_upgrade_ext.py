from __future__ import annotations

import os

import backend.handwritten_bill_ai_ext as handwriting


VERSION = "138"
CURRENT_DEFAULT = "gemini-3.6-flash"
OLD_BLOCKED_MODELS = {
    "gemini-2.5-flash-lite",
    "models/gemini-2.5-flash-lite",
}

configured = str(os.getenv("GEMINI_MODEL", "") or "").strip()
if not configured or configured in OLD_BLOCKED_MODELS:
    configured = CURRENT_DEFAULT
if configured.startswith("models/"):
    configured = configured.split("/", 1)[1]

# handwritten_bill_ai_ext reads GEMINI_MODEL dynamically from this module-level
# value on each request. Replacing it here lets existing deployments migrate
# without requiring the user to add/change a GEMINI_MODEL Railway variable.
handwriting.GEMINI_MODEL = configured
handwriting.VERSION = VERSION
