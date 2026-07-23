# Kirana Software 0.4.0

Mobile-first billing, inventory, khata and business management software. The same FastAPI/SQLite backend serves Android, laptop browser and installable PWA clients.

## Working modules

- Compact professional Sale and Purchase workspaces
- Credit/Cash billing, party balance, invoice metadata and fixed save/print actions
- Item master with separate Name and Size/Pack variants
- Variant-safe Vyapar CSV/XLS/XLSX import: same item name can keep 100/500/1 kg as separate sizes
- Sale/Purchase stock movements and customer/supplier ledgers
- Item-wise Sale Return and Purchase Return with automatic stock reversal and party adjustment
- A4, 80 mm and 58 mm invoice/return print layouts with separate Size column
- Payment-In, Payment-Out, expenses and P2P account transfer
- Cash, bank, loan and fixed-asset registers
- Home, dashboard, item cards, transaction launcher and reports
- Net sales/purchases after returns, tax movement, stock value and size-wise top items
- Export Items, Parties, Sales and Purchases to CSV
- Downloadable full SQLite database backup
- Vyapar import preview/history and clearer file errors
- Offline sale/purchase queue and installable PWA
- Quantity/rate/discount editing keeps Android keyboard focus

## Important scope note

Estimate, quotation, proforma invoice, sale order, purchase order and delivery challan currently work as header/amount registers. Item-wise editors and one-tap conversion between these documents and invoices remain planned. Multiple godowns, batch/expiry inventory and direct Bluetooth printer integration also remain pending.

## Termux start

```bash
cd ~/kirana-software
source ~/.kirana-venv/bin/activate
python run.py
```

Open `http://127.0.0.1:8000`.

## Tests

```bash
source ~/.kirana-venv/bin/activate
cd ~/kirana-software
pytest -q
```

Version 0.4.0 includes 10 automated API tests covering setup/login, sale/purchase, stock and ledger effects, variant-safe Vyapar imports, name/size cleanup, accounts, expenses, transfers, item-wise returns, reports, CSV exports and database backup.
