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
# Safe customer catalog visibility, default rates and customer-specific rate management.
import backend.customer_catalog_manager_ext  # noqa: F401
# Old allow-list implementation remains disabled; the safe manager above replaces it.
# import backend.customer_catalog_visibility_ext  # noqa: F401
# Redirects old /customer links and resolves the primary shop safely.
import backend.customer_link_fix_ext  # noqa: F401
# Forces the latest product-card quantity UI and hides stock from customers.
import backend.customer_product_ui_ext  # noqa: F401
# Legacy browser assets remain available for compatibility.
import backend.ui_shell_v2_ext  # noqa: F401
# One-time secure recovery for a forgotten owner PIN.
import backend.owner_recovery_ext  # noqa: F401
# Legacy root/customer rescue routes.
import backend.frontend_rescue_ext  # noqa: F401
# Standalone owner login and secure cookie session.
import backend.owner_session_ext  # noqa: F401
# Legacy owner bundle repair kept only as a fallback.
import backend.owner_core_fix_ext  # noqa: F401
# Legacy inline fallback kept only as a fallback.
import backend.owner_inline_navigation_ext  # noqa: F401
# Transactional bulk item edit and delete APIs.
import backend.bulk_items_ext  # noqa: F401
# Final owner route: isolated stable HTML/CSS/JS app.
import backend.stable_owner_app_ext  # noqa: F401
# Adds the customer catalog manager assets to the isolated owner app.
import backend.customer_catalog_owner_ui_ext  # noqa: F401
# Fixes catalog API route order and uses only the latest bill from the last 15 days.
import backend.customer_catalog_15day_fix_ext  # noqa: F401
# Scopes customer login to the shared shop and adds owner WhatsApp link sharing.
import backend.customer_login_share_fix_ext  # noqa: F401
# Prevents an expired request from clearing a newly completed customer login.
import backend.customer_login_race_fix_ext  # noqa: F401
# Registration/reset OTP flow plus owner OTP request alerts and WhatsApp sending.
import backend.customer_registration_reset_ext  # noqa: F401

# Disabled: these layered owner recovery middlewares duplicated/replaced the
# stable owner bundle and left Android WebView in a half-loaded state.
# import backend.owner_boot_recovery_ext  # noqa: F401
# import backend.owner_self_contained_ext  # noqa: F401
# Disabled: this response-rewrapping middleware caused Railway upstream errors.
# import backend.owner_dashboard_session_ext  # noqa: F401
# Disabled: old barcode/theme browser injection caused blank screens on Android.
# import backend.features_ext  # noqa: F401

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
