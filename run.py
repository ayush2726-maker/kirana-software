import os
import uvicorn

# Public health endpoint used by Railway deployments.
import backend.health_ext  # noqa: F401
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
# Stores Payment In/Out receipts and invoice-wise allocations.
import backend.payment_link_ext  # noqa: F401
# Explicit owner-confirmed removal of a selected imported Sales batch.
import backend.import_batch_remove_ext  # noqa: F401
# Secure current-user password change and logout of old sessions.
import backend.password_change_ext  # noqa: F401
# Customer self-ordering, customer-specific rates and order-to-bill conversion.
import backend.order_portal_ext  # noqa: F401
# Deletes corrupt imported items containing x00 control markers and blocks them in future imports.
import backend.corrupt_x00_item_cleanup_ext  # noqa: F401
# Multi-business SaaS signup, trial plans and unique shop links.
import backend.saas_ext  # noqa: F401
# Enforces trial expiry and seller-controlled suspension.
import backend.saas_guard_ext  # noqa: F401
# Existing database customers register only after owner-sent WhatsApp OTP verification.
import backend.customer_self_register_ext  # noqa: F401
# Merges duplicate name/size/unit rows before showing products to customers.
import backend.customer_catalog_dedupe_ext  # noqa: F401
# Product visibility feature is temporarily disabled while its runtime conflict is fixed.
# import backend.customer_catalog_visibility_ext  # noqa: F401
# Redirects old /customer links and resolves the primary shop safely.
import backend.customer_link_fix_ext  # noqa: F401
# Forces the latest product-card quantity UI and hides stock from customers.
import backend.customer_product_ui_ext  # noqa: F401
# Final browser shell: billing controls, security, customer orders and SaaS UI.
import backend.ui_shell_v2_ext  # noqa: F401
# Outermost stable responses for / and /customer, bypassing middleware conflicts.
import backend.frontend_rescue_ext  # noqa: F401

# The barcode/theme extension is temporarily disabled because its injected
# browser bundle caused a blank screen on some Android Chrome/WebView builds.
# The source files remain in the repository and will be re-enabled after the
# frontend bundle is made compatible and tested.
# import backend.features_ext  # noqa: F401

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
