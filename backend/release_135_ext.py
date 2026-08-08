from __future__ import annotations

# Final smart-tools Android/runtime repair is loaded here so it is registered
# after the original Photo Bill & Barcode module and can safely intercept the
# standalone smart-tools page.
import backend.smart_tools_runtime_fix_ext  # noqa: F401
# Legacy Gemini reader remains available in code only for rollback compatibility.
import backend.handwritten_bill_ai_ext  # noqa: F401
import backend.gemini_model_upgrade_ext  # noqa: F401
# Allows high-resolution phone photos up to 25 MB.
import backend.photo_upload_limit_25mb_ext  # noqa: F401
# Local learning/matching rules and learned handwriting aliases.
import backend.local_handwriting_ai_ext  # noqa: F401
# Final primary reader: PP-OCRv5 Hindi/Devanagari runs in an isolated local
# worker, with dual-pass preprocessing and strict catalog-match quality checks.
import backend.local_handwriting_process_ext  # noqa: F401
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "144"
native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION
