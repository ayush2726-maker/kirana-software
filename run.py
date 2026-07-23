import os
import uvicorn

# Registers advanced settings, reminders, users and injected settings assets.
import backend.settings_ext  # noqa: F401
# Groups repeated product names into one item card with separate size variants.
import backend.items_ext  # noqa: F401
# Fixes Vyapar header detection, annual invoice-number collisions and wrong party imports.
import backend.import_fix_ext  # noqa: F401
# Reads SaleReport item-detail sheets and blocks/removes invalid zero-value imports.
import backend.sale_import_ext  # noqa: F401
# Exact parser for the uploaded Party/Sale/Purchase reports, including blank purchase invoice grouping.
import backend.vyapar_exact_ext  # noqa: F401
# Shows sale/purchase/other entries in a date-wise mixed timeline and fixes menu navigation.
import backend.activity_navigation_ext  # noqa: F401
# Groups every invoice's item rows, detects old item-wise duplicate imports and adds the Sale item picker.
import backend.sale_workflow_ext  # noqa: F401
# Always exposes a strict manual cleanup for old SaleReport item-wise invoice imports.
import backend.manual_sale_cleanup_ext  # noqa: F401

# The barcode/theme extension is temporarily disabled because its injected
# browser bundle caused a blank screen on some Android Chrome/WebView builds.
# The source files remain in the repository and will be re-enabled after the
# frontend bundle is made compatible and tested.
# import backend.features_ext  # noqa: F401

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
