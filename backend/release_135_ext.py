from __future__ import annotations

# Final smart-tools Android/runtime repair is loaded here so it is registered
# after the original Photo Bill & Barcode module and can safely intercept the
# standalone smart-tools page.
import backend.smart_tools_runtime_fix_ext  # noqa: F401
# Adds AI Vision handwriting reading and blocks garbage OCR drafts safely.
import backend.handwritten_bill_ai_ext  # noqa: F401
import backend.native_owner_app_ext as native_owner
import backend.owner_final_inline_ext as final_owner
import backend.stable_owner_app_ext as stable_owner


VERSION = "137"
native_owner.BUILD = VERSION
final_owner.BUILD = VERSION
stable_owner.VERSION = VERSION
