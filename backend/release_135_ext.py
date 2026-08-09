from __future__ import annotations

# Final smart-tools Android/runtime repair is loaded here so it is registered
# after the original Photo Bill & Barcode module and can safely intercept the
# standalone smart-tools page.
import backend.smart_tools_runtime_fix_ext  # noqa: F401
# Local OCR helpers remain available as a fallback, but Gemini Vision must be
# the final /api/photo-bill/ocr interceptor because it reads handwriting far
# better than OCR character guessing.
import backend.local_handwriting_ai_ext  # noqa: F401
import backend.local_handwriting_process_ext  # noqa: F401
import backend.handwriting_review_ext  # noqa: F401
import backend.handwritten_bill_ai_ext  # noqa: F401
import backend.gemini_model_upgrade_ext  # noqa: F401
# Allows high-resolution phone photos up to 25 MB.
import backend.photo_upload_limit_25mb_ext  # noqa: F401
# Hindi/English Quick Write billing.
import backend.quick_write_bill_ext  # noqa: F401
# Build 152: larger pencil canvas, append-more flow, correct bare-number quantity parsing,
# dedicated Gemini Quick Write prompt, and saved/last-billed rate fallback.
import backend.quick_write_canvas_fix_ext  # noqa: F401
# Build 153: delete any wrong draft row and recalculate total instantly.
import backend.quick_write_delete_ext  # noqa: F401
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "153"
native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION
