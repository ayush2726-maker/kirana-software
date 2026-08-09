from __future__ import annotations

# Final smart-tools Android/runtime repair is loaded here so it is registered
# after the original Photo Bill & Barcode module and can safely intercept the
# standalone smart-tools page.
import backend.smart_tools_runtime_fix_ext  # noqa: F401
# Existing local handwriting engine + learning store.
import backend.local_handwriting_ai_ext  # noqa: F401
import backend.local_handwriting_process_ext  # noqa: F401
import backend.handwriting_review_ext  # noqa: F401
import backend.handwritten_bill_ai_ext  # noqa: F401
import backend.gemini_model_upgrade_ext  # noqa: F401
# Allows high-resolution phone photos up to 25 MB.
import backend.photo_upload_limit_25mb_ext  # noqa: F401
# Hindi/English Quick Write billing.
import backend.quick_write_bill_ext  # noqa: F401
# Core pencil canvas + quantity parsing.
import backend.quick_write_canvas_fix_ext  # noqa: F401
# Delete wrong draft rows.
import backend.quick_write_delete_ext  # noqa: F401
# Pack handling + particular-stroke eraser.
import backend.quick_write_grams_eraser_ext  # noqa: F401
# LEFT qty, MIDDLE item, RIGHT rate layout.
import backend.quick_write_column_format_ext  # noqa: F401
# Build 157: local Kirana AI becomes primary Quick Write reader, uses spatial
# qty-item-rate parsing, handwritten rates, and learns corrected item aliases.
import backend.quick_write_local_ai_ext  # noqa: F401
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "157"
native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION
