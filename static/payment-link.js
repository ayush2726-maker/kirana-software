(() => {
  'use strict';

  const paymentState = {
    type: 'received',
    party: null,
    bills: [],
    allocations: new Map(),
    loading: false,
    saving: false,
  };

  const style = document.createElement('style');
  style.textContent = `
    #linked-payment-dialog{
      width:min(100vw,760px);max-width:100vw;height:100dvh;max-height:100dvh;
      margin:0 auto;border:0;padding:0;background:#f4f5f7;color:#292d36;
    }
    #linked-payment-dialog::backdrop{background:rgba(20,27,36,.48)}
    .linked-payment-shell{min-height:100%;display:flex;flex-direction:column;background:#f4f5f7}
    .linked-payment-head{
      position:sticky;top:0;z-index:20;display:grid;grid-template-columns:48px 1fr 48px;
      align-items:center;min-height:68px;padding:8px 12px;background:#fff;border-bottom:1px solid #e0e3e8;
    }
    .linked-payment-head h2{margin:0;text-align:center;font-size:22px}
    .linked-payment-head button{border:0;background:transparent;padding:10px;color:#56606d}
    .linked-payment-head svg{width:26px;height:26px}
    .linked-payment-body{padding:14px 14px 110px;display:grid;gap:13px}
    .linked-payment-card{background:#fff;border:1px solid #e1e4e9;border-radius:14px;padding:14px;box-shadow:0 3px 10px rgba(28,43,58,.04)}
    .linked-payment-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .linked-payment-field{display:flex;flex-direction:column;gap:6px;min-width:0}
    .linked-payment-field.full{grid-column:1/-1}
    .linked-payment-field span{font-size:12px;color:#737b88;font-weight:700}
    .linked-payment-field input,.linked-payment-field select,.linked-payment-field textarea{
      width:100%;border:1px solid #cfd5dd;border-radius:10px;background:#fff;color:#2c3139;
      min-height:48px;padding:10px 12px;font-size:16px;outline:none;
    }
    .linked-payment-field textarea{min-height:72px;resize:vertical}
    .linked-payment-field input:focus,.linked-payment-field select:focus,.linked-payment-field textarea:focus{border-color:#087bc1;box-shadow:0 0 0 2px rgba(8,123,193,.09)}
    .linked-payment-party-summary{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}
    .linked-payment-party-summary div{background:#f6f8fa;border-radius:10px;padding:10px}
    .linked-payment-party-summary small{display:block;color:#7a828e;font-size:11px;margin-bottom:3px}
    .linked-payment-party-summary strong{font-size:15px;word-break:break-word}
    .linked-payment-section-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}
    .linked-payment-section-head h3{margin:0;font-size:17px}
    .linked-payment-section-head small{color:#777f8a}
    .linked-payment-tools{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
    .linked-payment-tools button{border:1px solid #cfd6df;border-radius:9px;background:#fff;padding:8px 11px;font-weight:700;color:#087bc1}
    .linked-payment-bills{display:grid;gap:9px}
    .linked-payment-bill{
      display:grid;grid-template-columns:28px minmax(0,1fr) 112px;gap:10px;align-items:center;
      border:1px solid #e0e4e9;border-radius:12px;padding:11px;background:#fff;
    }
    .linked-payment-bill.selected{border-color:#087bc1;background:#f4fbff}
    .linked-payment-bill input[type="checkbox"]{width:20px;height:20px;accent-color:#087bc1}
    .linked-payment-bill-main b{display:block;font-size:15px}
    .linked-payment-bill-main small{display:block;color:#7b828e;margin-top:3px;line-height:1.35}
    .linked-payment-bill-amount{text-align:right}
    .linked-payment-bill-amount small{display:block;color:#777f8b;font-size:10px;margin-bottom:3px}
    .linked-payment-bill-amount strong{display:block;color:#d83252;font-size:15px;margin-bottom:5px}
    .linked-payment-bill-amount input{width:100%;height:38px;border:1px solid #cbd2db;border-radius:8px;padding:6px 8px;text-align:right;font-size:15px}
    .linked-payment-empty{padding:26px 12px;text-align:center;color:#7d8490;background:#f8fafb;border-radius:12px}
    .linked-payment-total-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .linked-payment-total-box{border-radius:12px;padding:12px;background:#f5f7f9}
    .linked-payment-total-box small{display:block;color:#747d88;margin-bottom:4px}
    .linked-payment-total-box strong{font-size:18px}
    .linked-payment-total-box.positive strong{color:#087bc1}
    .linked-payment-total-box.warning strong{color:#d83252}
    .linked-payment-sticky{
      position:fixed;left:50%;bottom:0;transform:translateX(-50%);z-index:30;width:min(100vw,760px);
      display:grid;grid-template-columns:1fr 1.4fr;background:#fff;border-top:1px solid #dfe3e8;
      padding:10px 12px calc(10px + env(safe-area-inset-bottom));gap:10px;
    }
    .linked-payment-sticky button{min-height:54px;border-radius:11px;font-size:17px;font-weight:800}
    .linked-payment-cancel{border:1px solid #ccd3dc;background:#fff;color:#626b77}
    .linked-payment-save{border:0;background:#087bc1;color:#fff}
    .linked-payment-shell.payment-out .linked-payment-save{background:#f51f46}
    .linked-payment-shell.payment-out .linked-payment-tools button{color:#e1264a}
    .linked-payment-loading{padding:24px;text-align:center;color:#727b87}
    @media(max-width:520px){
      .linked-payment-body{padding:10px 10px 106px}
      .linked-payment-grid{grid-template-columns:1fr}
      .linked-payment-field.full{grid-column:auto}
      .linked-payment-bill{grid-template-columns:24px minmax(0,1fr) 96px;padding:9px;gap:8px}
      .linked-payment-bill-main b{font-size:14px}
      .linked-payment-bill-amount input{font-size:14px;padding:5px}
    }
  `;
  document.head.appendChild(style);

  document.body.insertAdjacentHTML('beforeend', `
    <dialog id="linked-payment-dialog">
      <div id="linked-payment-shell" class="linked-payment-shell">
        <header class="linked-payment-head">
          <button id="linked-payment-back" type="button" aria-label="Back">${icon('back')}</button>
          <h2 id="linked-payment-title">Payment In</h2>
          <button id="linked-payment-close" type="button" aria-label="Close">${icon('close')}</button>
        </header>

        <main class="linked-payment-body">
          <section class="linked-payment-card">
            <div class="linked-payment-grid">
              <label class="linked-payment-field full">
                <span id="linked-payment-party-label">Received From</span>
                <select id="linked-payment-party"><option value="">Select Party</option></select>
              </label>
              <label class="linked-payment-field">
                <span>Payment Date</span>
                <input id="linked-payment-date" type="date" />
              </label>
              <label class="linked-payment-field">
                <span>Receipt / Payment No.</span>
                <input id="linked-payment-number" value="Auto generated" readonly />
              </label>
            </div>
            <div id="linked-payment-party-summary" class="linked-payment-party-summary hidden">
              <div><small>Phone</small><strong id="linked-payment-phone">-</strong></div>
              <div><small>Party Outstanding</small><strong id="linked-payment-party-balance">₹0.00</strong></div>
            </div>
          </section>

          <section class="linked-payment-card">
            <div class="linked-payment-grid">
              <label class="linked-payment-field">
                <span>Payment Mode</span>
                <select id="linked-payment-mode">
                  <option value="cash">Cash</option>
                  <option value="upi">UPI</option>
                  <option value="bank">Bank Transfer</option>
                  <option value="card">Card</option>
                  <option value="cheque">Cheque</option>
                </select>
              </label>
              <label class="linked-payment-field">
                <span>Cash / Bank Account</span>
                <select id="linked-payment-account"><option value="">Default Account</option></select>
              </label>
              <label class="linked-payment-field full">
                <span>Description / Reference</span>
                <textarea id="linked-payment-note" placeholder="Optional note"></textarea>
              </label>
            </div>
          </section>

          <section class="linked-payment-card">
            <div class="linked-payment-section-head">
              <div><h3 id="linked-payment-bills-title">Pending Sale Bills</h3><small id="linked-payment-bills-subtitle">Party select karne ke baad bills dikhenge</small></div>
              <strong id="linked-payment-total-due">₹0.00</strong>
            </div>
            <div class="linked-payment-tools">
              <button id="linked-payment-select-all" type="button">Select All Pending</button>
              <button id="linked-payment-clear-all" type="button">Clear Selection</button>
            </div>
            <div id="linked-payment-bills" class="linked-payment-bills">
              <div class="linked-payment-empty">Party select karein</div>
            </div>
          </section>

          <section class="linked-payment-card">
            <div class="linked-payment-grid">
              <label class="linked-payment-field full">
                <span id="linked-payment-amount-label">Amount Received</span>
                <input id="linked-payment-amount" type="number" min="0.01" step="0.01" inputmode="decimal" value="0" />
              </label>
            </div>
            <div class="linked-payment-tools" style="margin-top:10px">
              <button id="linked-payment-auto-adjust" type="button">Auto Adjust Oldest Bills</button>
            </div>
            <div class="linked-payment-total-row">
              <div class="linked-payment-total-box positive"><small>Allocated to Bills</small><strong id="linked-payment-allocated">₹0.00</strong></div>
              <div class="linked-payment-total-box warning"><small>On Account / Unallocated</small><strong id="linked-payment-unallocated">₹0.00</strong></div>
            </div>
          </section>
        </main>

        <footer class="linked-payment-sticky">
          <button id="linked-payment-cancel" class="linked-payment-cancel" type="button">Cancel</button>
          <button id="linked-payment-save" class="linked-payment-save" type="button">Save Payment In</button>
        </footer>
      </div>
    </dialog>
  `);

  const dialog = $('#linked-payment-dialog');
  const shell = $('#linked-payment-shell');
  const partySelect = $('#linked-payment-party');
  const billHost = $('#linked-payment-bills');
  const amountInput = $('#linked-payment-amount');

  function expectedPartyTypes() {
    return paymentState.type === 'received' ? ['customer', 'both'] : ['supplier', 'both'];
  }

  function fillPaymentParties() {
    const allowed = expectedPartyTypes();
    const rows = (state.parties || []).filter(party => allowed.includes(party.type));
    partySelect.innerHTML = '<option value="">Select Party</option>' + rows
      .map(party => `<option value="${party.id}">${esc(party.name)} · ${money(party.balance)}</option>`)
      .join('');
  }

  function fillPaymentAccounts() {
    const selected = $('#linked-payment-account').value;
    $('#linked-payment-account').innerHTML = '<option value="">Default Account</option>' + (state.accounts || [])
      .map(account => `<option value="${account.id}">${esc(account.name)} · ${money(account.balance)}</option>`)
      .join('');
    if ([...$('#linked-payment-account').options].some(option => option.value === selected)) {
      $('#linked-payment-account').value = selected;
    }
  }

  function paymentLabels() {
    const incoming = paymentState.type === 'received';
    shell.classList.toggle('payment-out', !incoming);
    $('#linked-payment-title').textContent = incoming ? 'Payment In' : 'Payment Out';
    $('#linked-payment-party-label').textContent = incoming ? 'Received From' : 'Paid To';
    $('#linked-payment-amount-label').textContent = incoming ? 'Amount Received' : 'Amount Paid';
    $('#linked-payment-bills-title').textContent = incoming ? 'Pending Sale Bills' : 'Pending Purchase Bills';
    $('#linked-payment-save').textContent = incoming ? 'Save Payment In' : 'Save Payment Out';
  }

  function allocationTotal() {
    return [...paymentState.allocations.values()].reduce((sum, value) => sum + num(value), 0);
  }

  function updatePaymentSummary(syncAmount = false) {
    const allocated = Math.round(allocationTotal() * 100) / 100;
    if (syncAmount) amountInput.value = allocated.toFixed(2);
    const amount = Math.max(0, num(amountInput.value));
    $('#linked-payment-allocated').textContent = money(allocated);
    $('#linked-payment-unallocated').textContent = money(Math.max(0, amount - allocated));
    $('#linked-payment-save').disabled = paymentState.saving || !paymentState.party || amount <= 0 || allocated > amount + 0.01;
  }

  function billMarkup(bill) {
    const allocated = num(paymentState.allocations.get(Number(bill.id)) || 0);
    const selected = allocated > 0;
    return `
      <article class="linked-payment-bill ${selected ? 'selected' : ''}" data-payment-bill="${bill.id}">
        <input data-payment-check="${bill.id}" type="checkbox" ${selected ? 'checked' : ''} aria-label="Select ${esc(bill.invoice_no)}" />
        <div class="linked-payment-bill-main">
          <b>${esc(bill.invoice_no || 'Invoice')}</b>
          <small>${niceDate(bill.invoice_date)} · Total ${money(bill.total)} · Paid ${money(bill.paid)}</small>
          <small>${bill.status === 'partial' ? 'Partly Paid' : 'Unpaid'}</small>
        </div>
        <div class="linked-payment-bill-amount">
          <small>Balance</small>
          <strong>${money(bill.due)}</strong>
          <input data-payment-allocation="${bill.id}" type="number" min="0" max="${num(bill.due)}" step="0.01" inputmode="decimal" value="${selected ? allocated.toFixed(2) : '0'}" />
        </div>
      </article>
    `;
  }

  function renderBills() {
    if (paymentState.loading) {
      billHost.innerHTML = '<div class="linked-payment-loading">Pending bills load ho rahe hain…</div>';
      return;
    }
    if (!paymentState.party) {
      billHost.innerHTML = '<div class="linked-payment-empty">Party select karein</div>';
      return;
    }
    if (!paymentState.bills.length) {
      billHost.innerHTML = '<div class="linked-payment-empty">Is party ka koi pending bill nahi hai. Opening balance ho to payment On Account save kar sakte hain.</div>';
      return;
    }
    billHost.innerHTML = paymentState.bills.map(billMarkup).join('');
  }

  function resetPaymentState() {
    paymentState.party = null;
    paymentState.bills = [];
    paymentState.allocations.clear();
    paymentState.loading = false;
    paymentState.saving = false;
    partySelect.value = '';
    amountInput.value = '0';
    $('#linked-payment-date').value = today();
    $('#linked-payment-number').value = 'Auto generated';
    $('#linked-payment-mode').value = 'cash';
    $('#linked-payment-account').value = '';
    $('#linked-payment-note').value = '';
    $('#linked-payment-party-summary').classList.add('hidden');
    $('#linked-payment-total-due').textContent = money(0);
    $('#linked-payment-bills-subtitle').textContent = 'Party select karne ke baad bills dikhenge';
    renderBills();
    updatePaymentSummary();
  }

  async function loadPartyBills() {
    const partyId = Number(partySelect.value || 0);
    paymentState.allocations.clear();
    amountInput.value = '0';
    if (!partyId) {
      paymentState.party = null;
      paymentState.bills = [];
      $('#linked-payment-party-summary').classList.add('hidden');
      $('#linked-payment-total-due').textContent = money(0);
      renderBills();
      updatePaymentSummary();
      return;
    }

    paymentState.loading = true;
    renderBills();
    updatePaymentSummary();
    try {
      const data = await api(`/api/parties/${partyId}/open-bills?payment_type=${paymentState.type}`);
      paymentState.party = data.party;
      paymentState.bills = data.bills || [];
      $('#linked-payment-phone').textContent = data.party.phone || '-';
      $('#linked-payment-party-balance').textContent = money(data.party.balance);
      $('#linked-payment-party-summary').classList.remove('hidden');
      $('#linked-payment-total-due').textContent = money(data.total_due);
      $('#linked-payment-bills-subtitle').textContent = `${data.bill_count} pending bill${data.bill_count === 1 ? '' : 's'} · Oldest first`;
    } catch (error) {
      paymentState.party = null;
      paymentState.bills = [];
      toast(error.message, true);
    } finally {
      paymentState.loading = false;
      renderBills();
      updatePaymentSummary();
    }
  }

  function setAllocation(id, value, syncAmount = true) {
    const bill = paymentState.bills.find(row => Number(row.id) === Number(id));
    if (!bill) return;
    const safe = Math.max(0, Math.min(num(value), num(bill.due)));
    if (safe > 0) paymentState.allocations.set(Number(id), Math.round(safe * 100) / 100);
    else paymentState.allocations.delete(Number(id));
    renderBills();
    updatePaymentSummary(syncAmount);
  }

  function selectAllBills() {
    paymentState.allocations.clear();
    paymentState.bills.forEach(bill => paymentState.allocations.set(Number(bill.id), num(bill.due)));
    renderBills();
    updatePaymentSummary(true);
  }

  function clearAllocations() {
    paymentState.allocations.clear();
    renderBills();
    updatePaymentSummary(false);
  }

  function autoAdjust() {
    let remaining = Math.max(0, num(amountInput.value));
    if (!remaining) return toast('Pehle payment amount daalein', true);
    paymentState.allocations.clear();
    for (const bill of paymentState.bills) {
      if (remaining <= 0) break;
      const value = Math.min(num(bill.due), remaining);
      if (value > 0) paymentState.allocations.set(Number(bill.id), Math.round(value * 100) / 100);
      remaining = Math.round((remaining - value) * 100) / 100;
    }
    renderBills();
    updatePaymentSummary(false);
  }

  async function openLinkedPayment(type) {
    paymentState.type = type;
    paymentLabels();
    fillPaymentParties();
    fillPaymentAccounts();
    resetPaymentState();
    closeIfOpen($('#txn-launcher'));
    dialog.showModal();
  }

  async function saveLinkedPayment() {
    if (paymentState.saving) return;
    const partyId = Number(partySelect.value || 0);
    const amount = Math.round(num(amountInput.value) * 100) / 100;
    if (!partyId) return toast('Party select karein', true);
    if (amount <= 0) return toast('Payment amount daalein', true);
    const allocated = Math.round(allocationTotal() * 100) / 100;
    if (allocated > amount + 0.01) return toast('Bill allocation payment amount se zyada hai', true);

    const referenceType = paymentState.type === 'received' ? 'sale' : 'purchase';
    const allocations = [...paymentState.allocations.entries()]
      .filter(([, value]) => num(value) > 0)
      .map(([referenceId, value]) => ({
        reference_type: referenceType,
        reference_id: Number(referenceId),
        amount: Math.round(num(value) * 100) / 100,
      }));

    paymentState.saving = true;
    updatePaymentSummary();
    try {
      const saved = await api('/api/payments/linked', {
        method: 'POST',
        body: {
          payment_type: paymentState.type,
          party_id: partyId,
          payment_date: $('#linked-payment-date').value,
          amount,
          mode: $('#linked-payment-mode').value,
          account_id: Number($('#linked-payment-account').value) || null,
          note: $('#linked-payment-note').value,
          allocations,
        },
      });
      dialog.close();
      toast(`${saved.receipt_no} saved · ${allocations.length} bill linked`);
      await refreshAll();
      if (typeof loadTransactions === 'function' && $('#page-transactions')?.classList.contains('active')) {
        await loadTransactions();
      }
    } catch (error) {
      toast(error.message, true);
    } finally {
      paymentState.saving = false;
      updatePaymentSummary();
    }
  }

  document.addEventListener('click', event => {
    const entry = event.target.closest('[data-entry-type]');
    if (!entry || !['cash_in', 'cash_out'].includes(entry.dataset.entryType)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openLinkedPayment(entry.dataset.entryType === 'cash_in' ? 'received' : 'paid');
  }, true);

  partySelect.addEventListener('change', loadPartyBills);
  amountInput.addEventListener('input', () => updatePaymentSummary(false));
  $('#linked-payment-select-all').addEventListener('click', selectAllBills);
  $('#linked-payment-clear-all').addEventListener('click', clearAllocations);
  $('#linked-payment-auto-adjust').addEventListener('click', autoAdjust);
  $('#linked-payment-back').addEventListener('click', () => dialog.close());
  $('#linked-payment-close').addEventListener('click', () => dialog.close());
  $('#linked-payment-cancel').addEventListener('click', () => dialog.close());
  $('#linked-payment-save').addEventListener('click', saveLinkedPayment);

  billHost.addEventListener('change', event => {
    const check = event.target.closest('[data-payment-check]');
    if (check) {
      const bill = paymentState.bills.find(row => Number(row.id) === Number(check.dataset.paymentCheck));
      if (bill) setAllocation(bill.id, check.checked ? bill.due : 0, true);
      return;
    }
    const input = event.target.closest('[data-payment-allocation]');
    if (input) setAllocation(input.dataset.paymentAllocation, input.value, false);
  });

  billHost.addEventListener('input', event => {
    const input = event.target.closest('[data-payment-allocation]');
    if (!input) return;
    const bill = paymentState.bills.find(row => Number(row.id) === Number(input.dataset.paymentAllocation));
    if (!bill) return;
    const safe = Math.max(0, Math.min(num(input.value), num(bill.due)));
    if (safe > 0) paymentState.allocations.set(Number(bill.id), Math.round(safe * 100) / 100);
    else paymentState.allocations.delete(Number(bill.id));
    input.closest('.linked-payment-bill')?.classList.toggle('selected', safe > 0);
    const checkbox = input.closest('.linked-payment-bill')?.querySelector('[data-payment-check]');
    if (checkbox) checkbox.checked = safe > 0;
    updatePaymentSummary(false);
  });
})();
