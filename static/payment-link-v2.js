(() => {
  'use strict';

  const model = {
    type: 'received',
    party: null,
    bills: [],
    allocations: new Map(),
    loading: false,
    saving: false,
    shown: 250,
  };

  const css = document.createElement('style');
  css.textContent = `
    #payment-main-v2,#payment-adjust-v2{width:min(100vw,760px);max-width:100vw;height:100dvh;max-height:100dvh;margin:0 auto;border:0;padding:0;background:#f4f5f7;color:#282d36}
    #payment-main-v2::backdrop,#payment-adjust-v2::backdrop{background:rgba(20,28,38,.48)}
    .payv2-shell{min-height:100%;display:flex;flex-direction:column;background:#f4f5f7}
    .payv2-head{position:sticky;top:0;z-index:20;display:grid;grid-template-columns:48px 1fr 48px;align-items:center;min-height:70px;padding:8px 12px;background:#fff;border-bottom:1px solid #dfe3e8}
    .payv2-head h2{margin:0;text-align:center;font-size:24px}.payv2-head button{border:0;background:transparent;padding:10px;color:#596472}.payv2-head svg{width:27px;height:27px}
    .payv2-body{padding:13px 13px 112px;display:grid;gap:13px}.payv2-card{background:#fff;border:1px solid #e0e4e9;border-radius:14px;padding:14px;box-shadow:0 3px 12px rgba(25,38,52,.04)}
    .payv2-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.payv2-field{display:flex;flex-direction:column;gap:6px;min-width:0}.payv2-field.full{grid-column:1/-1}.payv2-field span{font-size:12px;color:#747d89;font-weight:700}
    .payv2-field input,.payv2-field select,.payv2-field textarea{width:100%;min-height:50px;border:1px solid #cdd4dd;border-radius:10px;background:#fff;padding:10px 12px;font-size:16px;color:#2c3139;outline:none}.payv2-field textarea{min-height:76px;resize:vertical}.payv2-field input:focus,.payv2-field select:focus,.payv2-field textarea:focus{border-color:#087dc2;box-shadow:0 0 0 2px rgba(8,125,194,.1)}
    .payv2-party-info{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.payv2-party-info div{background:#f5f7f9;border-radius:10px;padding:10px}.payv2-party-info small{display:block;color:#79818d;font-size:11px;margin-bottom:3px}.payv2-party-info strong{font-size:16px}.payv2-negative{color:#d82f50}
    .payv2-amount-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:end}.payv2-link-btn{min-height:50px;border:1px solid #087dc2;border-radius:10px;background:#f2fbff;color:#087dc2;font-weight:800;padding:10px 16px;white-space:nowrap}.payv2-link-btn:disabled{opacity:.45}
    .payv2-link-summary{margin-top:11px;padding:11px;border-radius:10px;background:#f4f7fa;display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}.payv2-link-summary div{text-align:center}.payv2-link-summary small{display:block;color:#7a828e;font-size:10px}.payv2-link-summary strong{display:block;margin-top:3px;font-size:14px}
    .payv2-sticky{position:fixed;left:50%;bottom:0;transform:translateX(-50%);z-index:30;width:min(100vw,760px);display:grid;grid-template-columns:1fr 1.4fr;gap:10px;background:#fff;border-top:1px solid #dfe3e8;padding:10px 12px calc(10px + env(safe-area-inset-bottom))}.payv2-sticky button{min-height:56px;border-radius:11px;font-size:18px;font-weight:800}.payv2-cancel{border:1px solid #cbd2db;background:#fff;color:#616a76}.payv2-save{border:0;background:#087dc2;color:#fff}.payv2-out .payv2-save{background:#f42048}
    .payv2-adjust-total{background:#fff;padding:16px 18px;border-bottom:1px solid #e0e4e8;display:flex;justify-content:space-between;align-items:center}.payv2-adjust-total small{display:block;color:#727b87}.payv2-adjust-total strong{font-size:26px}.payv2-adjust-tools{position:sticky;top:70px;z-index:15;background:#f4f5f7;padding:10px 12px;border-bottom:1px solid #e1e4e8}.payv2-adjust-tools-row{display:flex;gap:8px;margin-top:8px}.payv2-adjust-tools input{flex:1;min-width:0;height:44px;border:1px solid #cbd2db;border-radius:10px;padding:8px 11px;font-size:15px}.payv2-adjust-tools button{border:1px solid #cbd2db;border-radius:10px;background:#fff;padding:8px 11px;font-weight:750;color:#087dc2}
    .payv2-bill-list{padding:10px 10px 120px;display:grid;gap:9px}.payv2-bill{display:grid;grid-template-columns:28px minmax(0,1fr) 118px;gap:9px;align-items:center;background:#eaf4f8;border:1px solid #d8e3e8;padding:12px;border-radius:6px}.payv2-bill.active{border-color:#087dc2;background:#f0fbff}.payv2-bill input[type=checkbox]{width:21px;height:21px;accent-color:#087dc2}.payv2-bill-main b{display:flex;justify-content:space-between;gap:8px;font-size:16px}.payv2-bill-main small{display:block;color:#6f7884;margin-top:5px;line-height:1.35}.payv2-bill-link small{display:block;color:#6f7884;font-size:11px;margin-bottom:4px}.payv2-bill-link strong{display:block;color:#d72f50;margin-bottom:5px}.payv2-bill-link input{width:100%;height:42px;border:1px solid #7c858e;background:#fff;border-radius:4px;padding:6px 8px;text-align:right;font-size:16px}
    .payv2-empty{padding:30px;text-align:center;color:#747d88;background:#fff;border-radius:10px}.payv2-more{width:100%;min-height:46px;border:1px solid #087dc2;border-radius:9px;background:#fff;color:#087dc2;font-weight:800}.payv2-unused{position:fixed;left:max(12px,calc(50% - 360px));bottom:83px;z-index:31;background:#2482a5;color:#fff;border-radius:0 42px 42px 0;padding:10px 30px 10px 18px;box-shadow:0 5px 16px rgba(0,0,0,.18)}.payv2-unused small{display:block}.payv2-unused strong{font-size:22px}.payv2-adjust-sticky{grid-template-columns:1fr 1fr}.payv2-done{border:0;background:#087dc2;color:#fff}
    @media(max-width:520px){.payv2-body{padding:10px 10px 108px}.payv2-grid{grid-template-columns:1fr}.payv2-field.full{grid-column:auto}.payv2-amount-row{grid-template-columns:1fr}.payv2-link-summary{grid-template-columns:1fr 1fr 1fr}.payv2-bill{grid-template-columns:24px minmax(0,1fr) 100px;padding:10px 8px}.payv2-bill-main b{font-size:14px}.payv2-adjust-tools-row{flex-wrap:wrap}.payv2-adjust-tools input{flex-basis:100%}.payv2-unused{left:0}}
  `;
  document.head.appendChild(css);

  document.body.insertAdjacentHTML('beforeend', `
    <dialog id="payment-main-v2">
      <div id="payment-shell-v2" class="payv2-shell">
        <header class="payv2-head"><button id="payment-back-v2" type="button">${icon('back')}</button><h2 id="payment-title-v2">Payment In</h2><button id="payment-close-v2" type="button">${icon('close')}</button></header>
        <main class="payv2-body">
          <section class="payv2-card">
            <div class="payv2-grid">
              <label class="payv2-field full"><span id="payment-party-label-v2">Customer / Received From</span><select id="payment-party-v2"><option value="">Select Party</option></select></label>
              <label class="payv2-field"><span>Date</span><input id="payment-date-v2" type="date"></label>
              <label class="payv2-field"><span>Receipt / Payment No.</span><input value="Auto generated" readonly></label>
            </div>
            <div id="payment-party-info-v2" class="payv2-party-info hidden"><div><small>Phone</small><strong id="payment-phone-v2">-</strong></div><div><small>Party Balance</small><strong id="payment-balance-v2" class="payv2-negative">₹0.00</strong></div></div>
          </section>
          <section class="payv2-card">
            <div class="payv2-amount-row">
              <label class="payv2-field"><span id="payment-amount-label-v2">Received Amount</span><input id="payment-amount-v2" type="number" min="0.01" step="0.01" inputmode="decimal" value="0"></label>
              <button id="payment-link-bills-v2" class="payv2-link-btn" type="button" disabled>🔗 Link / Adjust Bills</button>
            </div>
            <div class="payv2-link-summary"><div><small>Pending Bills</small><strong id="payment-pending-count-v2">0</strong></div><div><small>Linked Amount</small><strong id="payment-linked-v2">₹0.00</strong></div><div><small>Unused Amount</small><strong id="payment-unused-v2">₹0.00</strong></div></div>
          </section>
          <section class="payv2-card"><div class="payv2-grid"><label class="payv2-field"><span>Payment Mode</span><select id="payment-mode-v2"><option value="cash">Cash</option><option value="upi">UPI</option><option value="bank">Bank Transfer</option><option value="card">Card</option><option value="cheque">Cheque</option></select></label><label class="payv2-field"><span>Cash / Bank Account</span><select id="payment-account-v2"><option value="">Default Account</option></select></label><label class="payv2-field full"><span>Payment Ref. / Description</span><textarea id="payment-note-v2" placeholder="Optional reference or note"></textarea></label></div></section>
        </main>
        <footer class="payv2-sticky"><button id="payment-cancel-v2" class="payv2-cancel" type="button">Cancel</button><button id="payment-save-v2" class="payv2-save" type="button">Save Payment In</button></footer>
      </div>
    </dialog>

    <dialog id="payment-adjust-v2">
      <div class="payv2-shell">
        <header class="payv2-head"><button id="adjust-back-v2" type="button">${icon('back')}</button><h2>Link Payment To Txns</h2><button id="adjust-close-v2" type="button">${icon('close')}</button></header>
        <div class="payv2-adjust-total"><div><small>Total Payment</small><strong id="adjust-total-v2">₹0.00</strong></div><div><small>Party</small><b id="adjust-party-v2">-</b></div></div>
        <div class="payv2-adjust-tools"><div id="adjust-status-v2">Pending bills</div><div class="payv2-adjust-tools-row"><input id="adjust-search-v2" placeholder="Search invoice no. or date"><button id="adjust-auto-v2" type="button">Auto Adjust Oldest</button><button id="adjust-clear-v2" type="button">Clear</button></div></div>
        <div id="adjust-bills-v2" class="payv2-bill-list"></div>
        <div class="payv2-unused"><small>Unused Amount</small><strong id="adjust-unused-v2">₹0.00</strong></div>
        <footer class="payv2-sticky payv2-adjust-sticky"><button id="adjust-cancel-v2" class="payv2-cancel" type="button">Cancel</button><button id="adjust-done-v2" class="payv2-done" type="button">Done</button></footer>
      </div>
    </dialog>
  `);

  const mainDialog = $('#payment-main-v2');
  const adjustDialog = $('#payment-adjust-v2');
  const partySelect = $('#payment-party-v2');
  const amountInput = $('#payment-amount-v2');
  const billHost = $('#adjust-bills-v2');

  const round2 = value => Math.round(num(value) * 100) / 100;
  const totalAllocated = () => round2([...model.allocations.values()].reduce((sum, value) => sum + num(value), 0));
  const paymentAmount = () => Math.max(0, round2(amountInput.value));
  const unusedAmount = () => Math.max(0, round2(paymentAmount() - totalAllocated()));

  function labels() {
    const incoming = model.type === 'received';
    $('#payment-shell-v2').classList.toggle('payv2-out', !incoming);
    $('#payment-title-v2').textContent = incoming ? 'Payment In' : 'Payment Out';
    $('#payment-party-label-v2').textContent = incoming ? 'Customer / Received From' : 'Supplier / Paid To';
    $('#payment-amount-label-v2').textContent = incoming ? 'Received Amount' : 'Paid Amount';
    $('#payment-save-v2').textContent = incoming ? 'Save Payment In' : 'Save Payment Out';
  }

  function fillParties() {
    const expected = model.type === 'received' ? ['customer','both'] : ['supplier','both'];
    partySelect.innerHTML = '<option value="">Select Party</option>' + (state.parties || []).filter(p => expected.includes(p.type)).map(p => `<option value="${p.id}">${esc(p.name)} · ${money(p.balance)}</option>`).join('');
  }

  function fillAccounts() {
    $('#payment-account-v2').innerHTML = '<option value="">Default Account</option>' + (state.accounts || []).map(a => `<option value="${a.id}">${esc(a.name)} · ${money(a.balance)}</option>`).join('');
  }

  function updateSummary() {
    const allocated = totalAllocated();
    const amount = paymentAmount();
    const unused = Math.max(0, round2(amount - allocated));
    $('#payment-pending-count-v2').textContent = model.bills.length;
    $('#payment-linked-v2').textContent = money(allocated);
    $('#payment-unused-v2').textContent = money(unused);
    $('#adjust-total-v2').textContent = money(amount);
    $('#adjust-unused-v2').textContent = money(unused);
    $('#payment-link-bills-v2').disabled = !model.party || amount <= 0;
    $('#payment-save-v2').disabled = model.saving || !model.party || amount <= 0 || allocated > amount + .01;
  }

  function reset() {
    model.party = null; model.bills = []; model.allocations.clear(); model.loading = false; model.saving = false; model.shown = 250;
    partySelect.value = ''; amountInput.value = '0'; $('#payment-date-v2').value = today(); $('#payment-mode-v2').value = 'cash'; $('#payment-account-v2').value = ''; $('#payment-note-v2').value = '';
    $('#payment-party-info-v2').classList.add('hidden'); $('#adjust-search-v2').value = ''; updateSummary();
  }

  async function loadBills() {
    const partyId = Number(partySelect.value || 0);
    model.allocations.clear(); model.bills = []; model.party = null; model.shown = 250;
    if (!partyId) { $('#payment-party-info-v2').classList.add('hidden'); updateSummary(); return; }
    model.loading = true; updateSummary();
    try {
      const data = await api(`/api/parties/${partyId}/open-bills?payment_type=${model.type}`);
      model.party = data.party; model.bills = data.bills || [];
      $('#payment-phone-v2').textContent = data.party.phone || '-'; $('#payment-balance-v2').textContent = money(data.party.balance); $('#payment-party-info-v2').classList.remove('hidden');
    } catch (error) { toast(error.message, true); partySelect.value = ''; }
    finally { model.loading = false; updateSummary(); }
  }

  function matchingBills() {
    const q = ($('#adjust-search-v2').value || '').trim().toLowerCase();
    return model.bills.filter(b => !q || `${b.invoice_no} ${b.invoice_date}`.toLowerCase().includes(q));
  }

  function billHtml(bill) {
    const value = round2(model.allocations.get(Number(bill.id)) || 0); const active = value > 0;
    return `<article class="payv2-bill ${active ? 'active' : ''}" data-bill-card-v2="${bill.id}"><input data-bill-check-v2="${bill.id}" type="checkbox" ${active ? 'checked' : ''}><div class="payv2-bill-main"><b><span>${model.type === 'received' ? 'Sale' : 'Purchase'}</span><span>${niceDate(bill.invoice_date)}</span></b><small>Invoice Number: ${esc(bill.invoice_no)}</small><small>Total ${money(bill.total)} · Paid ${money(bill.paid)} · Current Balance ${money(bill.due)}</small></div><div class="payv2-bill-link"><small>Link Amount</small><strong>${money(bill.due)}</strong><input data-bill-amount-v2="${bill.id}" type="number" min="0" max="${num(bill.due)}" step="0.01" inputmode="decimal" value="${active ? value.toFixed(2) : ''}" placeholder="0"></div></article>`;
  }

  function renderBills() {
    if (model.loading) { billHost.innerHTML = '<div class="payv2-empty">Bills load ho rahe hain…</div>'; return; }
    const rows = matchingBills();
    if (!rows.length) { billHost.innerHTML = '<div class="payv2-empty">Koi pending bill nahi mila</div>'; return; }
    const shown = rows.slice(0, model.shown);
    billHost.innerHTML = shown.map(billHtml).join('') + (shown.length < rows.length ? `<button id="adjust-more-v2" class="payv2-more" type="button">Load More (${rows.length - shown.length} remaining)</button>` : '');
    $('#adjust-status-v2').textContent = `${rows.length} pending bills · Oldest first`;
  }

  function setAllocation(id, value, rerender = false) {
    const bill = model.bills.find(b => Number(b.id) === Number(id)); if (!bill) return;
    const safe = Math.max(0, Math.min(round2(value), round2(bill.due)));
    if (safe > 0) model.allocations.set(Number(id), safe); else model.allocations.delete(Number(id));
    if (rerender) renderBills(); updateSummary();
  }

  function autoAdjust() {
    let left = paymentAmount(); if (left <= 0) return toast('Pehle payment amount daalein', true);
    model.allocations.clear();
    for (const bill of model.bills) { if (left <= 0) break; const value = Math.min(round2(bill.due), left); if (value > 0) model.allocations.set(Number(bill.id), value); left = round2(left - value); }
    renderBills(); updateSummary();
  }

  function openAdjust() {
    if (!model.party) return toast('Party select karein', true); if (paymentAmount() <= 0) return toast('Pehle payment amount daalein', true);
    $('#adjust-party-v2').textContent = model.party.name; model.shown = 250; renderBills(); updateSummary(); adjustDialog.showModal();
  }

  async function openPayment(type) {
    model.type = type; labels(); fillParties(); fillAccounts(); reset(); closeIfOpen($('#txn-launcher')); mainDialog.showModal();
  }

  async function savePayment() {
    if (model.saving) return;
    const amount = paymentAmount(); const allocated = totalAllocated();
    if (!model.party) return toast('Party select karein', true); if (amount <= 0) return toast('Payment amount daalein', true); if (allocated > amount + .01) return toast('Linked amount payment se zyada hai', true);
    const referenceType = model.type === 'received' ? 'sale' : 'purchase';
    const allocations = [...model.allocations.entries()].filter(([,v]) => num(v) > 0).map(([id,v]) => ({reference_type: referenceType, reference_id: Number(id), amount: round2(v)}));
    model.saving = true; updateSummary();
    try {
      const saved = await api('/api/payments/linked',{method:'POST',body:{payment_type:model.type,party_id:model.party.id,payment_date:$('#payment-date-v2').value,amount,mode:$('#payment-mode-v2').value,account_id:Number($('#payment-account-v2').value)||null,note:$('#payment-note-v2').value,allocations}});
      mainDialog.close(); toast(`${saved.receipt_no} saved · ${allocations.length} bill adjusted`); await refreshAll();
    } catch (error) { toast(error.message,true); }
    finally { model.saving = false; updateSummary(); }
  }

  document.addEventListener('click', event => {
    const entry = event.target.closest('[data-entry-type]');
    if (!entry || !['cash_in','cash_out'].includes(entry.dataset.entryType)) return;
    event.preventDefault(); event.stopImmediatePropagation(); openPayment(entry.dataset.entryType === 'cash_in' ? 'received' : 'paid');
  }, true);

  partySelect.addEventListener('change', loadBills); amountInput.addEventListener('input', updateSummary); $('#payment-link-bills-v2').addEventListener('click', openAdjust); $('#payment-save-v2').addEventListener('click', savePayment);
  ['#payment-back-v2','#payment-close-v2','#payment-cancel-v2'].forEach(sel => $(sel).addEventListener('click',()=>mainDialog.close()));
  ['#adjust-back-v2','#adjust-close-v2','#adjust-cancel-v2'].forEach(sel => $(sel).addEventListener('click',()=>adjustDialog.close()));
  $('#adjust-done-v2').addEventListener('click',()=>{adjustDialog.close();updateSummary()}); $('#adjust-auto-v2').addEventListener('click',autoAdjust); $('#adjust-clear-v2').addEventListener('click',()=>{model.allocations.clear();renderBills();updateSummary()}); $('#adjust-search-v2').addEventListener('input',()=>{model.shown=250;renderBills()});
  billHost.addEventListener('click',event=>{const more=event.target.closest('#adjust-more-v2');if(more){model.shown+=250;renderBills();return}const check=event.target.closest('[data-bill-check-v2]');if(check){const bill=model.bills.find(b=>Number(b.id)===Number(check.dataset.billCheckV2));if(!bill)return;const current=unusedAmount();setAllocation(bill.id,check.checked?Math.min(num(bill.due),current):0,true)}});
  billHost.addEventListener('input',event=>{const input=event.target.closest('[data-bill-amount-v2]');if(!input)return;setAllocation(input.dataset.billAmountV2,input.value,false);const card=input.closest('[data-bill-card-v2]');card?.classList.toggle('active',num(input.value)>0);const check=card?.querySelector('[data-bill-check-v2]');if(check)check.checked=num(input.value)>0});
})();
