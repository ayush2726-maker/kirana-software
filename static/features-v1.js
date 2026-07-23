(() => {
  'use strict';

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];
  const html = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
  const authToken = () => localStorage.getItem('ks_token') || '';

  let advanced = {};
  let labelItemId = null;
  let scanStream = null;
  let scanFrame = null;
  let lastInvoice = null;

  async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (authToken()) headers.Authorization = `Bearer ${authToken()}`;
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }
    const response = await fetch(path, { ...options, headers });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`);
    return data;
  }

  function notify(message, isError = false) {
    if (typeof toast === 'function') toast(message, isError);
    else alert(message);
  }

  function eanCheckDigit(base12) {
    const digits = String(base12).replace(/\D/g, '').slice(0, 12).padStart(12, '0');
    const total = [...digits].reduce((sum, digit, index) => sum + Number(digit) * (index % 2 ? 3 : 1), 0);
    return String((10 - total % 10) % 10);
  }

  function makeLocalBarcode() {
    const time = String(Date.now()).slice(-9);
    const random = String(Math.floor(Math.random() * 10));
    const base = `29${time}${random}`.slice(0, 12);
    return base + eanCheckDigit(base);
  }

  function validEan13(value) {
    const digits = String(value || '').replace(/\D/g, '');
    return digits.length === 13 && digits.slice(-1) === eanCheckDigit(digits.slice(0, 12));
  }

  const EAN_L = ['0001101','0011001','0010011','0111101','0100011','0110001','0101111','0111011','0110111','0001011'];
  const EAN_G = ['0100111','0110011','0011011','0100001','0011101','0111001','0000101','0010001','0001001','0010111'];
  const EAN_R = ['1110010','1100110','1101100','1000010','1011100','1001110','1010000','1000100','1001000','1110100'];
  const EAN_PARITY = ['LLLLLL','LLGLGG','LLGGLG','LLGGGL','LGLLGG','LGGLLG','LGGGLL','LGLGLG','LGLGGL','LGGLGL'];

  function eanSvg(value) {
    let digits = String(value || '').replace(/\D/g, '');
    if (digits.length === 12) digits += eanCheckDigit(digits);
    if (!validEan13(digits)) return code39Svg(value);
    const first = Number(digits[0]);
    let bits = '101';
    for (let index = 1; index <= 6; index += 1) {
      const digit = Number(digits[index]);
      bits += EAN_PARITY[first][index - 1] === 'L' ? EAN_L[digit] : EAN_G[digit];
    }
    bits += '01010';
    for (let index = 7; index <= 12; index += 1) bits += EAN_R[Number(digits[index])];
    bits += '101';
    const bars = [...bits].map((bit, index) => bit === '1' ? `<rect x="${index + 4}" y="2" width="1" height="${index < 3 || (index >= 45 && index < 50) || index >= 92 ? 34 : 30}"/>` : '').join('');
    return `<svg class="barcode-svg" viewBox="0 0 103 43" role="img" aria-label="Barcode ${digits}" xmlns="http://www.w3.org/2000/svg"><g fill="#000">${bars}</g><text x="51.5" y="41" text-anchor="middle" font-size="7" font-family="Arial, sans-serif">${digits}</text></svg>`;
  }

  const CODE39 = {
    '0':'nnnwwnwnn','1':'wnnwnnnnw','2':'nnwwnnnnw','3':'wnwwnnnnn','4':'nnnwwnnnw','5':'wnnwwnnnn','6':'nnwwwnnnn','7':'nnnwnnwnw','8':'wnnwnnwnn','9':'nnwwnnwnn',
    'A':'wnnnnwnnw','B':'nnwnnwnnw','C':'wnwnnwnnn','D':'nnnnwwnnw','E':'wnnnwwnnn','F':'nnwnwwnnn','G':'nnnnnwwnw','H':'wnnnnwwnn','I':'nnwnnwwnn','J':'nnnnwwwnn',
    'K':'wnnnnnnww','L':'nnwnnnnww','M':'wnwnnnnwn','N':'nnnnwnnww','O':'wnnnwnnwn','P':'nnwnwnnwn','Q':'nnnnnnwww','R':'wnnnnnwwn','S':'nnwnnnwwn','T':'nnnnwnwwn',
    'U':'wwnnnnnnw','V':'nwwnnnnnw','W':'wwwnnnnnn','X':'nwnnwnnnw','Y':'wwnnwnnnn','Z':'nwwnwnnnn','-':'nwnnnnwnw','.':'wwnnnnwnn',' ':'nwwnnnwnn','$':'nwnwnwnnn','/':'nwnwnnnwn','+':'nwnnnwnwn','%':'nnnwnwnwn','*':'nwnnwnwnn'
  };

  function code39Svg(value) {
    const clean = String(value || '').toUpperCase().replace(/[^0-9A-Z.\- $/+%]/g, '').slice(0, 30) || 'ITEM';
    const encoded = `*${clean}*`;
    const narrow = 1.2;
    const wide = 3;
    let x = 4;
    let bars = '';
    for (const character of encoded) {
      const pattern = CODE39[character] || CODE39['-'];
      [...pattern].forEach((widthCode, index) => {
        const width = widthCode === 'w' ? wide : narrow;
        if (index % 2 === 0) bars += `<rect x="${x.toFixed(1)}" y="2" width="${width}" height="30"/>`;
        x += width;
      });
      x += narrow;
    }
    const viewWidth = x + 4;
    return `<svg class="barcode-svg" viewBox="0 0 ${viewWidth} 43" role="img" aria-label="Barcode ${html(clean)}" xmlns="http://www.w3.org/2000/svg"><g fill="#000">${bars}</g><text x="${viewWidth / 2}" y="41" text-anchor="middle" font-size="7" font-family="Arial, sans-serif">${html(clean)}</text></svg>`;
  }

  function barcodeSvg(value) {
    return validEan13(value) || String(value || '').replace(/\D/g, '').length === 12 ? eanSvg(value) : code39Svg(value);
  }

  async function loadAdvanced(force = false) {
    if (Object.keys(advanced).length && !force) return advanced;
    try {
      const response = await request('/api/settings/advanced');
      advanced = response.settings || {};
      localStorage.setItem('ks_advanced_settings', JSON.stringify(advanced));
    } catch {
      try { advanced = JSON.parse(localStorage.getItem('ks_advanced_settings') || '{}'); } catch { advanced = {}; }
    }
    applyFeatureSettings();
    return advanced;
  }

  async function saveAdvanced() {
    const response = await request('/api/settings/advanced', { method: 'PUT', body: { settings: advanced } });
    advanced = response.settings || advanced;
    localStorage.setItem('ks_advanced_settings', JSON.stringify(advanced));
    applyFeatureSettings();
  }

  function ensureOption(select, value, label) {
    if (!select || [...select.options].some(option => option.value === value)) return;
    select.add(new Option(label, value));
  }

  function setVisible(selector, visible) {
    qsa(selector).forEach(element => element.classList.toggle('feature-hidden', visible === false));
  }

  function applyFeatureSettings() {
    const general = advanced.general || {};
    const transaction = advanced.transaction || {};
    const print = advanced.print || {};
    const item = advanced.item || {};

    document.documentElement.dataset.kiranaTheme = String(general.theme || 'Modern').toLowerCase().replaceAll(' ', '-');
    document.documentElement.dataset.kiranaAccent = String(print.accent || 'Blue').toLowerCase();

    const printSelect = qs('#invoice-print-size');
    ensureOption(printSelect, 'print-a5', 'A5');
    if (printSelect) {
      printSelect.value = print.mode === 'thermal'
        ? (print.thermal_size === '58mm' ? 'print-58mm' : 'print-80mm')
        : (print.regular_size === 'A5' ? 'print-a5' : 'print-a4');
    }

    setVisible('#sale-invoice-no, #purchase-invoice-no', transaction.invoice_header !== false);
    qsa('#sale-invoice-no, #purchase-invoice-no').forEach(el => el.parentElement?.classList.toggle('feature-hidden', transaction.invoice_header === false));
    qsa('#sale-time, #purchase-time').forEach(el => el.parentElement?.classList.toggle('feature-hidden', transaction.transaction_time === false));
    setVisible('.sale-party-panel, .billing-party-panel', transaction.party_details !== false);
    setVisible('.sale-terms-grid', transaction.payment_terms !== false);
    const stateField = qs('#sale-state')?.closest('label');
    if (stateField) stateField.classList.toggle('feature-hidden', transaction.state_of_supply === false);
    setVisible('[data-action="new-item"]', item.enabled !== false);
    setVisible('.feature-scan-button', transaction.barcode_scanning !== false && item.barcode_scanning !== false);

    const stockField = qs('#item-form [name="stock"]')?.closest('label');
    const minStockField = qs('#item-form [name="min_stock"]')?.closest('label');
    if (stockField) stockField.classList.toggle('feature-hidden', item.stock_maintenance === false);
    if (minStockField) minStockField.classList.toggle('feature-hidden', item.stock_maintenance === false);

    const profit = qs('#sale-profit-preview');
    if (profit) profit.classList.toggle('feature-hidden', transaction.profit_while_sale === false);
    updateProfitPreview();
  }

  function ensureCoreUi() {
    const printSelect = qs('#invoice-print-size');
    ensureOption(printSelect, 'print-a5', 'A5');

    const barcodeInput = qs('#item-form [name="barcode"]');
    if (barcodeInput && !qs('#item-barcode-actions')) {
      const actions = document.createElement('div');
      actions.id = 'item-barcode-actions';
      actions.className = 'item-barcode-actions';
      actions.innerHTML = '<button type="button" class="btn secondary" data-generate-form-barcode>Generate</button><button type="button" class="btn secondary" data-print-form-label>Print Label</button>';
      barcodeInput.closest('label')?.appendChild(actions);
    }

    const itemToolbar = qs('#page-items .search-toolbar');
    if (itemToolbar && !qs('#barcode-center-btn')) {
      const button = document.createElement('button');
      button.id = 'barcode-center-btn';
      button.type = 'button';
      button.className = 'btn barcode-center-button';
      button.innerHTML = '<span>▥</span> Barcode Labels';
      itemToolbar.insertAdjacentElement('afterend', button);
    }

    [['sale', '.sale-search-wrap'], ['purchase', '.billing-search-wrap'], ['return', '.billing-search-wrap']].forEach(([kind, selector]) => {
      const input = qs(`#${kind}-item-search`);
      const wrap = input?.closest(selector) || input?.parentElement;
      if (!wrap || qs(`[data-scan-kind="${kind}"]`, wrap)) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'feature-scan-button';
      button.dataset.scanKind = kind;
      button.title = 'Scan barcode';
      button.innerHTML = '⌗';
      wrap.appendChild(button);
    });

    const invoiceActions = qs('#invoice-dialog .invoice-actions');
    if (invoiceActions && !qs('#share-invoice')) {
      const button = document.createElement('button');
      button.id = 'share-invoice';
      button.type = 'button';
      button.className = 'btn secondary';
      button.textContent = 'Share';
      invoiceActions.insertBefore(button, qs('#print-invoice'));
    }

    const saleSummary = qs('.sale-summary-panel');
    if (saleSummary && !qs('#sale-profit-preview')) {
      const profit = document.createElement('div');
      profit.id = 'sale-profit-preview';
      profit.className = 'sale-profit-preview';
      profit.innerHTML = '<span>Estimated Profit</span><strong>₹0.00</strong>';
      saleSummary.insertBefore(profit, saleSummary.querySelector('.sale-due-strip'));
    }

    ensureDialogs();
    ensureSettingsStudioButton();
  }

  function ensureDialogs() {
    if (!qs('#barcode-label-dialog')) {
      const dialog = document.createElement('dialog');
      dialog.id = 'barcode-label-dialog';
      dialog.className = 'feature-dialog barcode-label-dialog';
      dialog.innerHTML = `
        <header><div><h2>Barcode Generator & Labels</h2><small>Internal EAN-13 ya existing barcode print karein</small></div><button type="button" data-feature-close>×</button></header>
        <div class="feature-dialog-body">
          <label>Item<select id="label-item-select"></select></label>
          <div id="label-item-preview" class="label-item-preview"></div>
          <label>Barcode<input id="label-barcode" autocomplete="off"></label>
          <div class="feature-button-row"><button type="button" class="btn secondary" id="generate-selected-barcode">Generate Barcode</button><button type="button" class="btn secondary" id="generate-all-barcodes">Generate All Missing</button></div>
          <div class="feature-grid">
            <label>Labels quantity<input id="label-quantity" type="number" min="1" max="260" value="1"></label>
            <label>Label paper<select id="label-layout"><option value="sheet-381">38.1 × 21.2 mm (5×13 A4)</option><option value="sheet-50">50 × 25 mm (4×11 A4)</option><option value="thermal-80">80 mm Thermal</option><option value="thermal-58">58 mm Thermal</option></select></label>
          </div>
          <div class="feature-checks"><label><input id="label-show-price" type="checkbox" checked> Show sale price</label><label><input id="label-show-shop" type="checkbox" checked> Show shop name</label></div>
        </div>
        <footer><button type="button" class="btn secondary" data-feature-close>Cancel</button><button type="button" class="btn primary" id="print-barcode-labels">Print Labels</button></footer>`;
      document.body.appendChild(dialog);
    }

    if (!qs('#barcode-scan-dialog')) {
      const dialog = document.createElement('dialog');
      dialog.id = 'barcode-scan-dialog';
      dialog.className = 'feature-dialog barcode-scan-dialog';
      dialog.innerHTML = '<header><div><h2>Scan Barcode</h2><small>Barcode ko camera ke frame mein rakhein</small></div><button type="button" data-scan-close>×</button></header><div class="scanner-stage"><video id="barcode-video" autoplay playsinline muted></video><div class="scanner-frame"></div><p id="scanner-status">Camera starting…</p></div>';
      document.body.appendChild(dialog);
      dialog.addEventListener('close', stopScanner);
    }

    if (!qs('#feature-studio-dialog')) {
      const dialog = document.createElement('dialog');
      dialog.id = 'feature-studio-dialog';
      dialog.className = 'feature-dialog feature-studio-dialog';
      dialog.innerHTML = `
        <header><div><h2>Themes, Print & Barcode</h2><small>App aur invoice ka professional look</small></div><button type="button" data-feature-close>×</button></header>
        <form id="feature-studio-form" class="feature-dialog-body">
          <label>App Theme<select name="app_theme"><option>Modern</option><option>Compact</option><option>Classic</option><option>Midnight</option></select></label>
          <label>Accent Color<select name="accent"><option>Blue</option><option>Green</option><option>Purple</option><option>Coral</option></select></label>
          <label>Invoice Theme<select name="invoice_theme"><option>Modern</option><option>Classic</option><option>Minimal</option></select></label>
          <label>Regular Paper<select name="regular_size"><option>A4</option><option>A5</option></select></label>
          <label>Default Barcode Label<select name="label_size"><option value="sheet-381">38.1 × 21.2 mm</option><option value="sheet-50">50 × 25 mm</option><option value="thermal-80">80 mm Thermal</option><option value="thermal-58">58 mm Thermal</option></select></label>
          <div class="feature-checks stacked"><label><input name="show_barcode" type="checkbox"> Print barcode in invoice</label><label><input name="auto_barcode" type="checkbox"> New item par barcode auto-generate</label></div>
        </form>
        <footer><button type="button" class="btn secondary" data-feature-close>Cancel</button><button type="button" class="btn primary" id="save-feature-studio">Save</button></footer>`;
      document.body.appendChild(dialog);
    }
  }

  function ensureSettingsStudioButton() {
    const menu = qs('#advanced-settings-home .vy-settings-menu');
    if (!menu || qs('[data-feature-studio]', menu)) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.featureStudio = '1';
    button.innerHTML = '<span class="vy-setting-icon">🎨</span><span><b>Themes, Barcode & Labels</b><small>A5 print, invoice themes and barcode generator</small></span><i>›</i>';
    menu.appendChild(button);
  }

  function itemById(id) {
    try { return state.items.find(item => Number(item.id) === Number(id)); } catch { return null; }
  }

  function fillLabelItems(selectedId = null) {
    const select = qs('#label-item-select');
    if (!select) return;
    const rows = [...(state.items || [])].sort((a, b) => `${a.name} ${a.size}`.localeCompare(`${b.name} ${b.size}`, 'en', { numeric: true }));
    select.innerHTML = rows.map(item => `<option value="${item.id}">${html(item.name)}${item.size ? ` · ${html(item.size)}` : ''}</option>`).join('');
    if (selectedId && rows.some(item => Number(item.id) === Number(selectedId))) select.value = String(selectedId);
    labelItemId = Number(select.value) || null;
    syncLabelPreview();
  }

  function syncLabelPreview() {
    const item = itemById(qs('#label-item-select')?.value || labelItemId);
    labelItemId = item?.id || null;
    const preview = qs('#label-item-preview');
    const barcode = qs('#label-barcode');
    if (!item) {
      if (preview) preview.innerHTML = '<p>No item selected</p>';
      if (barcode) barcode.value = '';
      return;
    }
    if (barcode) barcode.value = item.barcode || '';
    if (preview) preview.innerHTML = `<div><b>${html(item.name)}</b><small>${html(item.size || item.unit || '')}</small><strong>${money(item.sale_price)}</strong></div><div class="mini-barcode">${item.barcode ? barcodeSvg(item.barcode) : '<span>Barcode not generated</span>'}</div>`;
  }

  function openLabelDialog(itemId = null) {
    fillLabelItems(itemId);
    const settings = advanced.item || {};
    qs('#label-layout').value = settings.label_size || 'sheet-381';
    qs('#barcode-label-dialog').showModal();
  }

  async function generateSavedItemBarcode(itemId, force = false) {
    const response = await request(`/api/items/${itemId}/barcode/generate${force ? '?force=true' : ''}`, { method: 'POST' });
    const item = itemById(itemId);
    if (item) item.barcode = response.barcode;
    const form = qs('#item-form');
    if (form?.elements.id.value && Number(form.elements.id.value) === Number(itemId)) form.elements.barcode.value = response.barcode;
    syncLabelPreview();
    if (typeof renderItems === 'function') renderItems();
    return response.barcode;
  }

  async function generateFormBarcode() {
    const form = qs('#item-form');
    if (!form) return;
    const itemId = Number(form.elements.id.value) || null;
    const barcode = itemId ? await generateSavedItemBarcode(itemId, true) : makeLocalBarcode();
    form.elements.barcode.value = barcode;
    notify('Barcode generated');
  }

  async function generateAllMissing() {
    const response = await request('/api/items/barcodes/generate-missing', { method: 'POST' });
    if (typeof refreshMasterData === 'function') await refreshMasterData();
    if (typeof renderItems === 'function') renderItems();
    fillLabelItems(labelItemId);
    notify(`${response.count} barcode generated`);
  }

  function printFormLabel() {
    const form = qs('#item-form');
    const itemId = Number(form?.elements.id.value) || null;
    if (itemId) {
      qs('#item-dialog')?.close();
      openLabelDialog(itemId);
      return;
    }
    const draft = {
      id: 'draft',
      name: form?.elements.name.value || 'New Item',
      size: form?.elements.size.value || '',
      unit: form?.elements.unit.value || '',
      sale_price: Number(form?.elements.sale_price.value || 0),
      barcode: form?.elements.barcode.value || makeLocalBarcode(),
    };
    printLabels(draft, 1, advanced.item?.label_size || 'sheet-381', true, true);
  }

  function labelMarkup(item, showPrice, showShop) {
    const shop = state.me?.business?.name || 'Kirana Software';
    return `<div class="barcode-label">${showShop ? `<div class="label-shop">${html(shop)}</div>` : ''}<div class="label-item">${html(item.name)}</div>${item.size ? `<div class="label-size">${html(item.size)}</div>` : ''}<div class="label-code">${barcodeSvg(item.barcode)}</div>${showPrice ? `<div class="label-price">MRP / Sale ${money(item.sale_price)}</div>` : ''}</div>`;
  }

  function printLabels(item, quantity, layout, showPrice, showShop) {
    if (!item?.barcode) return notify('Pehle barcode generate karein', true);
    const count = Math.max(1, Math.min(260, Number(quantity || 1)));
    const labels = Array.from({ length: count }, () => labelMarkup(item, showPrice, showShop)).join('');
    const layoutCss = {
      'sheet-381': '@page{size:A4;margin:10.35mm 9.75mm}.label-sheet{display:grid;grid-template-columns:repeat(5,38.1mm);grid-auto-rows:21.2mm}',
      'sheet-50': '@page{size:A4;margin:11mm 5mm}.label-sheet{display:grid;grid-template-columns:repeat(4,50mm);grid-auto-rows:25mm}',
      'thermal-80': '@page{size:80mm auto;margin:2mm}.label-sheet{width:76mm;display:grid;grid-template-columns:1fr;gap:2mm}.barcode-label{height:28mm}',
      'thermal-58': '@page{size:58mm auto;margin:2mm}.label-sheet{width:54mm;display:grid;grid-template-columns:1fr;gap:2mm}.barcode-label{height:26mm}',
    }[layout] || '';
    const win = window.open('', '_blank', 'noopener,noreferrer');
    if (!win) return notify('Browser popup allow karein', true);
    win.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Barcode Labels</title><style>*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;color:#000}${layoutCss}.barcode-label{overflow:hidden;display:grid;grid-template-rows:auto auto auto 1fr auto;align-items:center;justify-items:center;padding:1.2mm;border:.15mm solid #ddd;text-align:center}.label-shop{font-size:7pt;font-weight:700;line-height:1}.label-item{max-width:100%;font-size:8pt;font-weight:700;line-height:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.label-size{font-size:6.5pt;line-height:1}.label-code{width:94%;height:10mm}.barcode-svg{width:100%;height:100%;display:block}.label-price{font-size:7pt;font-weight:700;line-height:1}@media print{.barcode-label{break-inside:avoid}}</style></head><body><main class="label-sheet">${labels}</main><script>onload=()=>{setTimeout(()=>{print();close()},250)}<\/script></body></html>`);
    win.document.close();
  }

  async function printSelectedLabels() {
    const item = itemById(qs('#label-item-select').value);
    if (!item) return notify('Item select karein', true);
    let barcode = qs('#label-barcode').value.trim();
    if (!barcode) barcode = await generateSavedItemBarcode(item.id);
    item.barcode = barcode;
    const layout = qs('#label-layout').value;
    advanced.item ||= {};
    advanced.item.label_size = layout;
    localStorage.setItem('ks_advanced_settings', JSON.stringify(advanced));
    printLabels(item, qs('#label-quantity').value, layout, qs('#label-show-price').checked, qs('#label-show-shop').checked);
  }

  async function startScanner(kind) {
    const input = qs(`#${kind}-item-search`);
    if (!input) return;
    if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) {
      const code = prompt('Camera scanner available nahi hai. Barcode number enter karein:');
      if (code) applyScannedCode(kind, code);
      return;
    }
    const dialog = qs('#barcode-scan-dialog');
    dialog.dataset.kind = kind;
    dialog.showModal();
    const video = qs('#barcode-video');
    const status = qs('#scanner-status');
    try {
      scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      video.srcObject = scanStream;
      await video.play();
      status.textContent = 'Scanning…';
      const detector = new BarcodeDetector({ formats: ['ean_13','ean_8','code_128','code_39','upc_a','upc_e'] });
      const tick = async () => {
        if (!scanStream) return;
        try {
          const results = await detector.detect(video);
          if (results.length) {
            applyScannedCode(kind, results[0].rawValue);
            dialog.close();
            return;
          }
        } catch { /* next frame */ }
        scanFrame = requestAnimationFrame(tick);
      };
      tick();
    } catch (error) {
      status.textContent = error.message || 'Camera permission failed';
    }
  }

  function stopScanner() {
    if (scanFrame) cancelAnimationFrame(scanFrame);
    scanFrame = null;
    if (scanStream) scanStream.getTracks().forEach(track => track.stop());
    scanStream = null;
    const video = qs('#barcode-video');
    if (video) video.srcObject = null;
  }

  function applyScannedCode(kind, code) {
    const item = (state.items || []).find(row => String(row.barcode || '').trim() === String(code || '').trim());
    if (item && typeof addToCart === 'function') {
      addToCart(kind, item.id);
      notify(`${item.name} added`);
      return;
    }
    const input = qs(`#${kind}-item-search`);
    input.value = code;
    if (typeof showItemResults === 'function') showItemResults(kind, code);
    notify('Barcode item master mein nahi mila', true);
  }

  function updateProfitPreview() {
    const element = qs('#sale-profit-preview strong');
    if (!element || typeof state === 'undefined') return;
    const profit = (state.saleCart || []).reduce((sum, line) => {
      const item = itemById(line.item_id);
      return sum + (Number(line.rate || 0) - Number(item?.purchase_price || 0)) * Number(line.qty || 0);
    }, 0) - Number(qs('#sale-discount')?.value || 0);
    element.textContent = money(profit);
    element.classList.toggle('negative', profit < 0);
    element.classList.toggle('positive', profit >= 0);
  }

  function numberToWords(value) {
    const number = Math.round(Number(value || 0));
    if (!number) return 'Zero Rupees Only';
    const ones = ['', 'One','Two','Three','Four','Five','Six','Seven','Eight','Nine','Ten','Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen','Seventeen','Eighteen','Nineteen'];
    const tens = ['', '', 'Twenty','Thirty','Forty','Fifty','Sixty','Seventy','Eighty','Ninety'];
    const two = n => n < 20 ? ones[n] : `${tens[Math.floor(n / 10)]}${n % 10 ? ` ${ones[n % 10]}` : ''}`;
    const three = n => `${n >= 100 ? `${ones[Math.floor(n / 100)]} Hundred ` : ''}${two(n % 100)}`.trim();
    let n = number;
    const parts = [];
    const units = [[10000000, 'Crore'], [100000, 'Lakh'], [1000, 'Thousand']];
    units.forEach(([unit, label]) => {
      if (n >= unit) {
        parts.push(`${three(Math.floor(n / unit))} ${label}`);
        n %= unit;
      }
    });
    if (n) parts.push(three(n));
    return `${parts.join(' ')} Rupees Only`;
  }

  function invoiceBarcodeFor(line) {
    const item = itemById(line.item_id);
    return item?.barcode || '';
  }

  function decorateInvoice(data, kind) {
    const sheet = qs('#invoice-sheet');
    if (!sheet) return;
    const print = advanced.print || {};
    const transaction = advanced.transaction || {};
    const business = data.business || state.me?.business || {};
    const currentSize = qs('#invoice-print-size')?.value || 'print-a4';
    const theme = String(print.theme || 'Modern').toLowerCase();
    const accent = String(print.accent || 'Blue').toLowerCase();
    sheet.className = `invoice-sheet ${currentSize} invoice-theme-${theme} invoice-accent-${accent}`;

    const company = sheet.querySelector('.invoice-top > div:first-child');
    if (company) {
      company.innerHTML = `${print.company_name !== false ? `<h2>${html(business.name || 'Kirana Software')}</h2>` : ''}${print.address !== false && business.address ? `<p>${html(business.address)}</p>` : ''}${print.phone !== false && business.phone ? `<p>${html(business.phone)}</p>` : ''}${print.gstin !== false && business.gstin ? `<p>GSTIN ${html(business.gstin)}</p>` : ''}`;
    }
    const meta = sheet.querySelector('.invoice-meta');
    if (meta) meta.classList.toggle('feature-hidden', transaction.invoice_header === false);
    const party = sheet.querySelector('.invoice-party');
    if (party) party.classList.toggle('feature-hidden', transaction.party_details === false);

    const table = sheet.querySelector('.invoice-table');
    if (table) {
      const showBarcode = print.show_barcode === true;
      table.innerHTML = `<thead><tr><th>Item</th><th>Size</th>${showBarcode ? '<th>Barcode</th>' : ''}<th>Qty</th><th>Rate</th><th>Total</th></tr></thead><tbody>${(data.items || []).map(line => {
        const code = invoiceBarcodeFor(line);
        return `<tr><td>${html(line.item_name)}</td><td>${html(line.size || '-')}</td>${showBarcode ? `<td class="invoice-barcode-cell">${code ? barcodeSvg(code) : '-'}</td>` : ''}<td>${line.qty}</td><td>${money(line.rate)}</td><td>${money(line.line_total)}</td></tr>`;
      }).join('')}</tbody>`;
    }

    const totals = sheet.querySelector('.invoice-totals');
    if (totals) {
      const totalQuantity = (data.items || []).reduce((sum, line) => sum + Number(line.qty || 0), 0);
      totals.innerHTML = `<div><span>Subtotal</span><b>${money(data.subtotal)}</b></div>${Number(data.discount || 0) ? `<div><span>Discount</span><b>${money(data.discount)}</b></div>` : ''}${print.tax_details !== false ? `<div><span>Tax</span><b>${money(data.tax)}</b></div>` : ''}<div class="invoice-grand-total"><span>Grand Total</span><b>${money(data.total)}</b></div>${print.received_amount !== false ? `<div><span>${kind.includes('return') ? 'Settled' : 'Paid'}</span><b>${money(data.paid)}</b></div>` : ''}${print.balance_amount !== false ? `<div><span>${kind.includes('return') ? 'Credit Adj.' : 'Balance'}</span><b>${money(data.due)}</b></div>` : ''}${print.total_quantity !== false ? `<div><span>Total Quantity</span><b>${totalQuantity}</b></div>` : ''}${print.payment_mode !== false ? `<div><span>Payment Mode</span><b>${html(data.payment_mode || '-')}</b></div>` : ''}`;
    }

    qsa('.invoice-extra-block', sheet).forEach(block => block.remove());
    const extras = document.createElement('div');
    extras.className = 'invoice-extra-block';
    extras.innerHTML = `${print.amount_words !== false ? `<p><b>Amount in words:</b> ${html(numberToWords(data.total))}</p>` : ''}${print.terms_conditions !== false && transaction.terms_conditions !== false ? '<p><b>Terms:</b> Goods once sold will be accepted for return only as per shop policy.</p>' : ''}${transaction.print_time ? `<p><b>Printed:</b> ${new Date().toLocaleString('en-IN')}</p>` : ''}`;
    sheet.appendChild(extras);
  }

  function printInvoiceWindow() {
    const sheet = qs('#invoice-sheet');
    if (!sheet) return;
    const size = qs('#invoice-print-size')?.value || 'print-a4';
    const orientation = advanced.print?.orientation || 'portrait';
    const page = size === 'print-a5' ? `A5 ${orientation}` : size === 'print-a4' ? `A4 ${orientation}` : size === 'print-58mm' ? '58mm auto' : '80mm auto';
    const width = size === 'print-a5' ? '148mm' : size === 'print-a4' ? '210mm' : size === 'print-58mm' ? '58mm' : '80mm';
    const margin = size.includes('mm') ? '2mm' : '8mm';
    const win = window.open('', '_blank', 'noopener,noreferrer');
    if (!win) return notify('Browser popup allow karein', true);
    win.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Invoice</title><style>@page{size:${page};margin:${margin}}*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;color:#111}.invoice-sheet{width:${width};max-width:100%;margin:0 auto;padding:${size.includes('mm') ? '1mm' : '0'};font-size:${advanced.print?.text_size === 'large' ? '12pt' : advanced.print?.text_size === 'medium' ? '10pt' : '8.5pt'}}.invoice-top{display:flex;justify-content:space-between;gap:8mm;border-bottom:2px solid #222;padding-bottom:4mm}.invoice-top h2{margin:0 0 1mm;font-size:16pt}.invoice-top p,.invoice-meta p{margin:.5mm 0}.invoice-meta{text-align:right}.invoice-party{padding:3mm 0;border-bottom:1px solid #aaa}.invoice-table{width:100%;border-collapse:collapse;margin-top:3mm}.invoice-table th,.invoice-table td{border:1px solid #aaa;padding:1.5mm;text-align:left}.invoice-table th{background:#edf5fa}.invoice-totals{margin:3mm 0 0 auto;width:min(85mm,100%)}.invoice-totals>div{display:flex;justify-content:space-between;padding:1mm 0;border-bottom:1px dotted #aaa}.invoice-grand-total{font-size:1.15em;font-weight:700}.invoice-extra-block{border-top:1px solid #bbb;margin-top:4mm;padding-top:2mm}.invoice-extra-block p{margin:1mm 0}.invoice-thanks{text-align:center;margin-top:5mm}.invoice-barcode-cell{width:28mm}.invoice-barcode-cell svg{width:26mm;height:10mm}.feature-hidden{display:none!important}.invoice-theme-modern{border-top:4px solid var(--invoice-accent,#0b7bc1)}.invoice-theme-classic .invoice-top{border:2px double #222;padding:3mm}.invoice-theme-minimal .invoice-table th,.invoice-theme-minimal .invoice-table td{border-left:0;border-right:0}.invoice-accent-blue{--invoice-accent:#0b7bc1}.invoice-accent-green{--invoice-accent:#168a50}.invoice-accent-purple{--invoice-accent:#7557c7}.invoice-accent-coral{--invoice-accent:#ef3152}@media print{body{print-color-adjust:exact;-webkit-print-color-adjust:exact}}</style></head><body>${sheet.outerHTML}<script>onload=()=>setTimeout(()=>{print();close()},250)<\/script></body></html>`);
    win.document.close();
  }

  async function shareInvoice() {
    if (!lastInvoice) return;
    const data = lastInvoice.data;
    const number = data.invoice_no || data.return_no || '';
    const messageSettings = advanced.messaging || {};
    let text = messageSettings.template || 'Namaste {party}, invoice {invoice} amount {amount}. Balance {balance}.';
    text = text.replaceAll('{party}', data.party_name || 'Customer').replaceAll('{invoice}', number).replaceAll('{amount}', money(data.total)).replaceAll('{balance}', money(data.due));
    if (messageSettings.show_web_invoice !== false) text += `\n${location.origin}`;
    try {
      if (navigator.share) await navigator.share({ title: `Invoice ${number}`, text });
      else window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank');
    } catch (error) {
      if (error?.name !== 'AbortError') notify(error.message, true);
    }
  }

  function openFeatureStudio() {
    const form = qs('#feature-studio-form');
    const general = advanced.general || {};
    const print = advanced.print || {};
    const item = advanced.item || {};
    form.elements.app_theme.value = ['Modern','Compact','Classic','Midnight'].includes(general.theme) ? general.theme : 'Modern';
    form.elements.accent.value = print.accent || 'Blue';
    form.elements.invoice_theme.value = print.theme || 'Modern';
    form.elements.regular_size.value = print.regular_size || 'A4';
    form.elements.label_size.value = item.label_size || 'sheet-381';
    form.elements.show_barcode.checked = print.show_barcode === true;
    form.elements.auto_barcode.checked = item.auto_barcode === true;
    qs('#feature-studio-dialog').showModal();
  }

  async function saveFeatureStudio() {
    const form = qs('#feature-studio-form');
    advanced.general ||= {};
    advanced.print ||= {};
    advanced.item ||= {};
    advanced.general.theme = form.elements.app_theme.value;
    advanced.print.accent = form.elements.accent.value;
    advanced.print.theme = form.elements.invoice_theme.value;
    advanced.print.regular_size = form.elements.regular_size.value;
    advanced.item.label_size = form.elements.label_size.value;
    advanced.print.show_barcode = form.elements.show_barcode.checked;
    advanced.item.auto_barcode = form.elements.auto_barcode.checked;
    await saveAdvanced();
    qs('#feature-studio-dialog').close();
    notify('Theme, print aur barcode settings saved');
  }

  function wrapCoreFunctions() {
    if (typeof showInvoice === 'function' && !showInvoice.__featureWrapped) {
      const original = showInvoice;
      const wrapped = function(data, kind = 'sale') {
        lastInvoice = { data, kind };
        original(data, kind);
        decorateInvoice(data, kind);
      };
      wrapped.__featureWrapped = true;
      showInvoice = wrapped;
    }

    if (typeof renderCart === 'function' && !renderCart.__featureWrapped) {
      const original = renderCart;
      const wrapped = function(kind) {
        const result = original(kind);
        if (kind === 'sale') updateProfitPreview();
        return result;
      };
      wrapped.__featureWrapped = true;
      renderCart = wrapped;
    }

    if (typeof saveItem === 'function' && !saveItem.__featureWrapped) {
      const original = saveItem;
      const wrapped = async function(form) {
        if (advanced.item?.auto_barcode && !form.elements.barcode.value.trim()) form.elements.barcode.value = makeLocalBarcode();
        return original(form);
      };
      wrapped.__featureWrapped = true;
      saveItem = wrapped;
    }

    if (typeof showItemResults === 'function' && !showItemResults.__featureWrapped) {
      const original = showItemResults;
      const wrapped = function(kind, query) {
        const result = original(kind, query);
        if (advanced.transaction?.display_purchase_price) {
          const root = qs(`#${kind}-search-results`);
          qsa('[data-add-line]', root).forEach(row => {
            const id = Number(row.dataset.addLine.split(':')[1]);
            const item = itemById(id);
            const small = row.querySelector('small');
            if (small && item && !small.dataset.purchaseShown) {
              small.dataset.purchaseShown = '1';
              small.textContent += ` · Purchase ${money(item.purchase_price)}`;
            }
          });
        }
        return result;
      };
      wrapped.__featureWrapped = true;
      showItemResults = wrapped;
    }
  }

  document.addEventListener('click', async event => {
    const close = event.target.closest('[data-feature-close]');
    if (close) {
      close.closest('dialog')?.close();
      return;
    }
    if (event.target.closest('[data-scan-close]')) {
      qs('#barcode-scan-dialog')?.close();
      return;
    }
    if (event.target.closest('#barcode-center-btn')) return openLabelDialog();
    if (event.target.closest('[data-generate-form-barcode]')) return generateFormBarcode().catch(error => notify(error.message, true));
    if (event.target.closest('[data-print-form-label]')) return printFormLabel();
    const scan = event.target.closest('[data-scan-kind]');
    if (scan) return startScanner(scan.dataset.scanKind);
    if (event.target.closest('#generate-selected-barcode')) {
      if (!labelItemId) return notify('Item select karein', true);
      return generateSavedItemBarcode(labelItemId, true).then(() => notify('Barcode generated')).catch(error => notify(error.message, true));
    }
    if (event.target.closest('#generate-all-barcodes')) return generateAllMissing().catch(error => notify(error.message, true));
    if (event.target.closest('#print-barcode-labels')) return printSelectedLabels().catch(error => notify(error.message, true));
    if (event.target.closest('#share-invoice')) return shareInvoice();
    if (event.target.closest('[data-feature-studio]')) return openFeatureStudio();
    if (event.target.closest('#save-feature-studio')) return saveFeatureStudio().catch(error => notify(error.message, true));
    if (event.target.closest('#print-invoice')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return printInvoiceWindow();
    }
  }, true);

  document.addEventListener('change', event => {
    if (event.target.id === 'label-item-select') syncLabelPreview();
    if (event.target.id === 'label-barcode') {
      const item = itemById(labelItemId);
      if (item) item.barcode = event.target.value.trim();
      syncLabelPreview();
    }
    if (event.target.id === 'invoice-print-size') qs('#invoice-sheet')?.classList.add(event.target.value);
  });

  const init = async () => {
    ensureCoreUi();
    wrapCoreFunctions();
    await loadAdvanced();
    const observer = new MutationObserver(() => {
      ensureCoreUi();
      ensureSettingsStudioButton();
      applyFeatureSettings();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(init, 80));
  else setTimeout(init, 80);
})();
