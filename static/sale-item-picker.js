(() => {
  'use strict';

  const pickerStyle = document.createElement('style');
  pickerStyle.textContent = `
    .sale-picker-open-row{
      display:grid;
      grid-template-columns:minmax(0,1fr) 58px;
      gap:12px;
      margin-top:14px;
    }
    .sale-picker-open{
      min-height:58px;
      border:1px solid #d8dde5;
      border-radius:12px;
      background:#fff;
      color:#087bc1;
      font-size:18px;
      font-weight:800;
      display:flex;
      align-items:center;
      justify-content:center;
      gap:9px;
      cursor:pointer;
    }
    .sale-picker-open small{color:#a0a5af;font-size:15px;font-weight:500}
    .sale-picker-open .plus-circle{
      width:26px;height:26px;border-radius:50%;background:#087bc1;color:#fff;
      display:grid;place-items:center;font-size:22px;line-height:1;
    }
    .sale-picker-barcode{
      border:1px solid #d8dde5;border-radius:12px;background:#fff;color:#087bc1;
      display:grid;place-items:center;cursor:pointer;
    }
    .sale-picker-barcode svg{width:29px;height:29px}
    #sale-item-picker-dialog{
      width:min(100vw,720px);
      max-width:100vw;
      height:100dvh;
      max-height:100dvh;
      margin:0 auto;
      border:0;
      padding:0;
      background:#f7f7f8;
      color:#272a32;
    }
    #sale-item-picker-dialog::backdrop{background:rgba(20,27,36,.46)}
    .sale-picker-shell{min-height:100%;display:flex;flex-direction:column;background:#f7f7f8}
    .sale-picker-head{
      position:sticky;top:0;z-index:4;
      min-height:76px;padding:10px 20px;
      display:grid;grid-template-columns:50px 1fr 50px;align-items:center;
      background:#fff;border-bottom:1px solid #e4e6ea;
    }
    .sale-picker-head h2{font-size:25px;margin:0;font-weight:750}
    .sale-picker-icon-btn{border:0;background:transparent;color:#59606b;padding:10px;cursor:pointer}
    .sale-picker-icon-btn svg{width:28px;height:28px}
    .sale-picker-body{padding:28px 30px 120px;flex:1;background:#fff}
    .sale-picker-search-wrap{position:relative;margin-bottom:22px}
    .sale-picker-floating-label{
      position:absolute;left:16px;top:-11px;background:#fff;padding:0 7px;
      color:#087bc1;font-size:15px;z-index:2;
    }
    .sale-picker-search-wrap input{
      width:100%;height:88px;border:2px solid #087bc1;border-radius:10px;
      padding:20px 22px;font-size:22px;outline:none;background:#fff;
    }
    .sale-picker-results{
      position:absolute;left:0;right:0;top:92px;z-index:10;
      background:#fff;border:1px solid #dce1e8;border-radius:12px;
      box-shadow:0 14px 36px rgba(35,50,65,.18);max-height:42vh;overflow:auto;
    }
    .sale-picker-result{
      width:100%;border:0;border-bottom:1px solid #edf0f3;background:#fff;
      padding:14px 16px;display:flex;justify-content:space-between;gap:12px;text-align:left;
      cursor:pointer;color:#252a33;
    }
    .sale-picker-result:last-child{border-bottom:0}
    .sale-picker-result b{display:block;font-size:16px}
    .sale-picker-result small{display:block;color:#8d929c;margin-top:4px}
    .sale-picker-result strong{white-space:nowrap;font-size:17px}
    .sale-picker-grid-three{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:20px}
    .sale-picker-grid-two{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:28px}
    .sale-picker-field{display:flex;flex-direction:column;gap:7px}
    .sale-picker-field span{font-size:14px;color:#777e89;font-weight:650}
    .sale-picker-field input,.sale-picker-field select{
      width:100%;height:60px;border:1.5px solid #aeb5c0;border-radius:9px;
      background:#fff;padding:0 16px;font-size:19px;color:#30343c;outline:none;
    }
    .sale-picker-field input:focus,.sale-picker-field select:focus{border-color:#087bc1;box-shadow:0 0 0 2px rgba(8,123,193,.08)}
    .sale-picker-batch-title{margin:0 -30px 18px;padding:26px 30px 15px;border-top:18px solid #f2f2f3;border-bottom:1px solid #dfe2e7;font-size:20px}
    .sale-picker-selected{
      margin-top:18px;padding:14px 16px;border-radius:10px;background:#eff8fe;color:#116e9f;
      display:flex;justify-content:space-between;gap:12px;align-items:center;
    }
    .sale-picker-selected strong{font-size:15px}
    .sale-picker-selected small{display:block;color:#6f8796;margin-top:3px}
    .sale-picker-new-item{border:0;background:transparent;color:#087bc1;font-weight:800;cursor:pointer;padding:8px}
    .sale-picker-actions{
      position:fixed;left:50%;bottom:0;transform:translateX(-50%);
      width:min(100vw,720px);height:92px;display:grid;grid-template-columns:1fr 1fr;
      background:#fff;border-top:1px solid #e0e2e6;z-index:6;
      padding-bottom:env(safe-area-inset-bottom);
    }
    .sale-picker-actions button{border:0;font-size:21px;cursor:pointer}
    .sale-picker-save-new{background:#fff;color:#6e7480}
    .sale-picker-save{background:#f51f46;color:#fff}
    .sale-picker-cart-count{
      position:absolute;right:14px;top:5px;min-width:24px;height:24px;border-radius:12px;
      background:#f51f46;color:#fff;font-size:12px;font-weight:800;display:grid;place-items:center;padding:0 6px;
    }
    .import-duplicate-banner{
      margin-bottom:12px;padding:14px;border:1px solid #ef476f;border-radius:12px;background:#fff5f7;
    }
    .import-duplicate-banner b{display:block;color:#c51f45;margin-bottom:5px}
    .import-duplicate-banner p{margin:0 0 10px;color:#666f7a;font-size:13px}
    @media (max-width:520px){
      .sale-picker-body{padding:24px 20px 118px}
      .sale-picker-grid-three{grid-template-columns:1fr 1fr 1fr;gap:10px}
      .sale-picker-grid-two{grid-template-columns:1fr 1fr;gap:12px}
      .sale-picker-field input,.sale-picker-field select{padding:0 12px;font-size:17px}
      .sale-picker-batch-title{margin-left:-20px;margin-right:-20px;padding-left:20px;padding-right:20px}
      .sale-picker-head h2{font-size:23px}
    }
  `;
  document.head.appendChild(pickerStyle);

  function pickerMarkup() {
    return `
      <dialog id="sale-item-picker-dialog">
        <div class="sale-picker-shell">
          <header class="sale-picker-head">
            <button id="sale-picker-back" type="button" class="sale-picker-icon-btn" aria-label="Back">${icon('back')}</button>
            <h2>Add Items to Sale</h2>
            <button id="sale-picker-settings" type="button" class="sale-picker-icon-btn" aria-label="Item settings">${icon('settings')}</button>
          </header>
          <div class="sale-picker-body">
            <div class="sale-picker-search-wrap">
              <span class="sale-picker-floating-label">Item Name</span>
              <input id="sale-picker-name" autocomplete="off" placeholder="Search item name, SKU or barcode" />
              <div id="sale-picker-results" class="sale-picker-results hidden"></div>
            </div>

            <div id="sale-picker-selected" class="sale-picker-selected hidden">
              <div><strong id="sale-picker-selected-name"></strong><small id="sale-picker-selected-meta"></small></div>
              <button id="sale-picker-clear-selection" type="button" class="sale-picker-new-item">Change</button>
            </div>

            <div class="sale-picker-grid-three">
              <label class="sale-picker-field"><span>Quantity</span><input id="sale-picker-qty" type="number" min="0.001" step="0.001" inputmode="decimal" value="1" /></label>
              <label class="sale-picker-field"><span>Free Qty</span><input id="sale-picker-free" type="number" min="0" step="0.001" inputmode="decimal" value="0" /></label>
              <label class="sale-picker-field"><span>Unit</span><select id="sale-picker-unit"><option value="pcs">pcs</option><option value="kg">kg</option><option value="gm">gm</option><option value="ltr">ltr</option><option value="ml">ml</option><option value="packet">packet</option><option value="box">box</option><option value="dozen">dozen</option></select></label>
            </div>

            <div class="sale-picker-grid-two">
              <label class="sale-picker-field"><span>Rate (Price/Unit)</span><input id="sale-picker-rate" type="number" min="0" step="0.01" inputmode="decimal" value="0" /></label>
              <label class="sale-picker-field"><span>Tax Calculation</span><select id="sale-picker-tax-mode"><option value="without">Without Tax</option><option value="with">With Tax</option></select></label>
            </div>

            <h3 class="sale-picker-batch-title">Selected Batch Details</h3>
            <label class="sale-picker-field"><span>Size / Pack</span><input id="sale-picker-size" placeholder="e.g. 500 gm, 1 kg" /></label>

            <div style="display:flex;justify-content:flex-end;margin-top:14px">
              <button id="sale-picker-new-item" type="button" class="sale-picker-new-item">+ Create New Item</button>
            </div>
          </div>
          <div class="sale-picker-actions">
            <button id="sale-picker-save-new" class="sale-picker-save-new" type="button">Save & New</button>
            <button id="sale-picker-save" class="sale-picker-save" type="button">Save</button>
          </div>
        </div>
      </dialog>
    `;
  }

  document.body.insertAdjacentHTML('beforeend', pickerMarkup());

  const dialog = $('#sale-item-picker-dialog');
  const nameInput = $('#sale-picker-name');
  const resultBox = $('#sale-picker-results');
  let selectedItemId = null;

  function installSaleOpenRow() {
    const row = $('#page-sale .sale-add-row');
    if (!row || row.dataset.pickerReady === '1') return;
    row.dataset.pickerReady = '1';
    row.className = 'sale-picker-open-row';
    row.innerHTML = `
      <button id="open-sale-item-picker" class="sale-picker-open" type="button">
        <span class="plus-circle">+</span> Add Items <small>(Optional)</small>
      </button>
      <button id="open-sale-barcode-picker" class="sale-picker-barcode" type="button" aria-label="Barcode">${icon('search')}</button>
    `;
  }

  function matches(query) {
    const q = String(query || '').trim().toLowerCase();
    if (!q) return [];
    return state.items.filter(item =>
      `${item.name} ${item.sku || ''} ${item.barcode || ''} ${item.size || ''} ${item.unit || ''}`
        .toLowerCase().includes(q)
    ).slice(0, 30);
  }

  function renderPickerResults(query) {
    const rows = matches(query);
    if (!String(query || '').trim()) {
      resultBox.classList.add('hidden');
      resultBox.innerHTML = '';
      return;
    }
    resultBox.innerHTML = rows.map(item => `
      <button type="button" class="sale-picker-result" data-picker-item="${item.id}">
        <span><b>${esc(item.name)}</b><small>${esc(item.size || 'Default size')} · ${esc(item.unit || 'pcs')} · Stock ${item.stock}</small></span>
        <strong>${money(item.sale_price)}</strong>
      </button>
    `).join('') || '<div style="padding:18px;text-align:center;color:#8c929b">No item found</div>';
    resultBox.classList.remove('hidden');
  }

  function selectItem(item) {
    selectedItemId = item ? Number(item.id) : null;
    if (!item) {
      $('#sale-picker-selected').classList.add('hidden');
      return;
    }
    nameInput.value = item.name || '';
    $('#sale-picker-selected-name').textContent = item.name || '';
    $('#sale-picker-selected-meta').textContent = `${item.size || 'Default size'} · Stock ${item.stock} ${item.unit || 'pcs'}`;
    $('#sale-picker-selected').classList.remove('hidden');
    $('#sale-picker-unit').value = item.unit || 'pcs';
    $('#sale-picker-rate').value = num(item.sale_price);
    $('#sale-picker-size').value = item.size || '';
    resultBox.classList.add('hidden');
  }

  function resetPicker(keepOpen = true) {
    selectedItemId = null;
    nameInput.value = '';
    $('#sale-picker-qty').value = 1;
    $('#sale-picker-free').value = 0;
    $('#sale-picker-unit').value = 'pcs';
    $('#sale-picker-rate').value = 0;
    $('#sale-picker-tax-mode').value = 'without';
    $('#sale-picker-size').value = '';
    $('#sale-picker-selected').classList.add('hidden');
    resultBox.classList.add('hidden');
    resultBox.innerHTML = '';
    if (keepOpen) setTimeout(() => nameInput.focus(), 30);
  }

  function updatePickerCount() {
    const existing = $('#sale-picker-cart-count');
    if (existing) existing.remove();
    if (!state.saleCart.length) return;
    const badge = document.createElement('span');
    badge.id = 'sale-picker-cart-count';
    badge.className = 'sale-picker-cart-count';
    badge.textContent = state.saleCart.length;
    $('.sale-picker-head').appendChild(badge);
  }

  function mergeSaleLine(line) {
    const found = state.saleCart.find(existing =>
      Number(existing.item_id || 0) === Number(line.item_id || 0) &&
      String(existing.item_name || '') === String(line.item_name || '') &&
      String(existing.size || '') === String(line.size || '') &&
      Number(existing.rate || 0) === Number(line.rate || 0) &&
      Number(existing.gst_rate || 0) === Number(line.gst_rate || 0)
    );
    if (found) found.qty = num(found.qty) + num(line.qty);
    else state.saleCart.push(line);
  }

  function addPickerLine() {
    const item = selectedItemId ? state.items.find(row => Number(row.id) === selectedItemId) : null;
    const itemName = String(item?.name || nameInput.value || '').trim();
    const qty = num($('#sale-picker-qty').value);
    const freeQty = num($('#sale-picker-free').value);
    const unit = $('#sale-picker-unit').value || item?.unit || 'pcs';
    const size = String($('#sale-picker-size').value || item?.size || '').trim();
    const enteredRate = num($('#sale-picker-rate').value);
    const gstRate = num(item?.gst_rate || 0);
    if (!itemName) {
      toast('Item choose ya item name enter karein', true);
      nameInput.focus();
      return false;
    }
    if (qty <= 0) {
      toast('Quantity 0 se zyada honi chahiye', true);
      $('#sale-picker-qty').focus();
      return false;
    }
    const rate = $('#sale-picker-tax-mode').value === 'with' && gstRate > 0
      ? enteredRate / (1 + gstRate / 100)
      : enteredRate;

    mergeSaleLine({
      item_id: item ? Number(item.id) : null,
      item_name: itemName,
      size,
      qty,
      rate: Math.max(0, Number(rate.toFixed(6))),
      gst_rate: gstRate,
      unit,
    });

    // Free quantity is stored as a zero-rate stock line. It deducts stock but
    // does not increase the bill amount.
    if (freeQty > 0) {
      mergeSaleLine({
        item_id: item ? Number(item.id) : null,
        item_name: itemName,
        size: size ? `${size} · FREE` : 'FREE',
        qty: freeQty,
        rate: 0,
        gst_rate: 0,
        unit,
      });
    }

    renderCart('sale');
    updatePickerCount();
    return true;
  }

  function openPicker(focusBarcode = false) {
    installSaleOpenRow();
    updatePickerCount();
    resetPicker(false);
    dialog.showModal();
    setTimeout(() => {
      nameInput.placeholder = focusBarcode ? 'Scan or type barcode' : 'Search item name, SKU or barcode';
      nameInput.focus();
    }, 50);
  }

  document.addEventListener('click', event => {
    if (event.target.closest('#open-sale-item-picker')) return openPicker(false);
    if (event.target.closest('#open-sale-barcode-picker')) return openPicker(true);
    if (event.target.closest('#sale-picker-back')) return dialog.close();
    if (event.target.closest('#sale-picker-settings')) {
      dialog.close();
      navigate('settings');
      return;
    }
    const itemButton = event.target.closest('[data-picker-item]');
    if (itemButton) {
      const item = state.items.find(row => Number(row.id) === Number(itemButton.dataset.pickerItem));
      if (item) selectItem(item);
      return;
    }
    if (event.target.closest('#sale-picker-clear-selection')) {
      resetPicker(true);
      return;
    }
    if (event.target.closest('#sale-picker-new-item')) {
      dialog.close();
      openItem();
      return;
    }
    if (event.target.closest('#sale-picker-save-new')) {
      if (addPickerLine()) resetPicker(true);
      return;
    }
    if (event.target.closest('#sale-picker-save')) {
      if (addPickerLine()) {
        dialog.close();
        window.scrollTo({top: document.querySelector('#sale-cart')?.offsetTop || 0, behavior: 'smooth'});
      }
      return;
    }
  });

  nameInput.addEventListener('input', event => {
    selectedItemId = null;
    $('#sale-picker-selected').classList.add('hidden');
    renderPickerResults(event.target.value);
  });
  nameInput.addEventListener('keydown', event => {
    if (event.key !== 'Enter') return;
    const first = resultBox.querySelector('[data-picker-item]');
    if (first) {
      event.preventDefault();
      first.click();
    }
  });

  installSaleOpenRow();

  // Add a safe cleanup action for old imports where the same SaleReport was
  // imported once bill-wise and once item-wise.
  if (typeof loadImportHistory === 'function') {
    const previousLoadImportHistory = loadImportHistory;
    loadImportHistory = async function () {
      await previousLoadImportHistory();
      try {
        const audit = await api('/api/import/cleanup-itemwise-sales', {method: 'POST'});
        if (!audit.transaction_count) return;
        const banner = document.createElement('div');
        banner.className = 'import-duplicate-banner';
        banner.innerHTML = `
          <b>${audit.transaction_count} item-wise duplicate sale bills mile</b>
          <p>Same SaleReport ka proper bill-wise import bhi available hai. Sirf duplicate item-wise batch remove hoga; stock aur party balance reverse ho jayega.</p>
          <button id="cleanup-itemwise-sales" class="btn primary" type="button">Remove Item-wise Duplicate Bills</button>
        `;
        $('#import-history').prepend(banner);
      } catch (error) {
        console.warn('Sale duplicate audit failed', error);
      }
    };
  }

  document.addEventListener('click', async event => {
    const button = event.target.closest('#cleanup-itemwise-sales');
    if (!button) return;
    if (!confirm('Item-wise duplicate sale bills remove karein? Proper bill-wise invoices safe rahenge.')) return;
    button.disabled = true;
    try {
      const result = await api('/api/import/cleanup-itemwise-sales?execute=true', {method: 'POST'});
      toast(`${result.removed || result.transaction_count} duplicate bills removed`);
      await refreshAll();
      await loadImportHistory();
    } catch (error) {
      toast(error.message, true);
      button.disabled = false;
    }
  });
})();
