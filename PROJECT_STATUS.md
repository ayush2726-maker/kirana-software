# Kirana Software — v0.4.0

Status: Working professional mobile-first build.

## Completed in v0.4.0

- Purchase screen redesigned to match the compact professional Sale workspace
- Separate supplier balance, Credit/Cash toggle, invoice reference, due and fixed save actions
- Item-wise Sale Return and Purchase Return
- Automatic stock reversal and customer/supplier outstanding adjustment on returns
- Sale, purchase and return invoice printing in A4, 80 mm and 58 mm formats
- Separate Item Name and Size columns throughout billing and printing
- Variant-safe import for same-name packs such as Barik Souff 100 and Barik Souff 500
- Net sales/net purchases reports after returns
- Size-wise top-selling item report
- Items, Parties, Sales and Purchases CSV export
- One-tap full SQLite database backup
- Existing databases remain compatible; update script backs up `kirana.db`
- Static assets use v0.4.0 cache key to avoid stale PWA UI
- 10/10 automated tests passing

## Native Android shell v0.2.0 patch

- Compact native toolbar
- Refresh, OTA check and server URL controls
- Automatic silent EAS Update check
- Correct EAS project ID, preview/production channels and runtime compatibility
- Same-phone Termux, LAN and cloud server URL support

## Next high-priority work

- Item-wise quotation/order/challan/proforma editor
- One-tap document-to-invoice conversion
- Multiple godowns
- Batch and expiry stock
- Multi-company switching and hosted cloud authentication
- Direct Bluetooth thermal-printer integration
- Role/permission controls for staff users
