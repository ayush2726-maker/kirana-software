  /* Vyapar item-size variants v126 */
  function variantTidy(value) {
    return String(value == null ? '' : value).normalize('NFKC')
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, '')
      .replace(/\s+/g, ' ').trim();
  }

  function variantProductKey(value) {
    return variantTidy(String(value || '').replace(/\s*\([^()]*\)\s*$/, ''))
      .toLowerCase().replace(/[._,\\/\-]+/g, ' ').replace(/\s+/g, ' ').trim();
  }

  function variantNumber(value) {
    var numeric = Number(value);
    if (!Number.isFinite(numeric)) return variantTidy(value);
    return Number.isInteger(numeric) ? String(numeric) : String(numeric).replace(/0+$/, '').replace(/\.$/, '');
  }

  function variantParse(item) {
    var originalName = variantTidy(item && item.name);
    var explicitSize = variantTidy(item && item.size);
    var translation = '';
    var coreName = originalName;
    var translationMatch = originalName.match(/\s*(\([^()]*\))\s*$/);
    if (translationMatch) {
      translation = variantTidy(translationMatch[1]);
      coreName = variantTidy(originalName.slice(0, translationMatch.index));
    }
    var detectedSize = '';
    var pack = coreName.match(/^(.*?)\s+(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|gms|ml|l|lt|ltr|pc|pcs|pkt|packet)?$/i);
    if (pack && (explicitSize || pack[3] || translation || Number(pack[2]) >= 10)) {
      coreName = variantTidy(pack[1]).replace(/[\s\-_/,.]+$/g, '');
      detectedSize = variantNumber(pack[2]) + (pack[3] ? ' ' + variantTidy(pack[3]).toLowerCase() : '');
    }
    if (!explicitSize && !detectedSize && translation) {
      var grade = coreName.match(/^(.*?)\s+(XXL|XL|L|M|S)$/i);
      if (grade) {
        coreName = variantTidy(grade[1]).replace(/[\s\-_/,.]+$/g, '');
        detectedSize = grade[2].toUpperCase();
      }
    }
    var inside = translation ? variantTidy(translation.slice(1, -1)) : '';
    var baseName = variantTidy(coreName + (inside ? ' (' + inside + ')' : '')) || originalName || 'Unnamed Item';
    return {
      baseName: baseName,
      productKey: variantProductKey(baseName),
      size: explicitSize || detectedSize,
      label: explicitSize || detectedSize || variantTidy(item && item.unit) || 'Default'
    };
  }

  function variantSort(a, b) {
    var left = variantParse(a).label.toLowerCase();
    var right = variantParse(b).label.toLowerCase();
    var leftNumber = Number.parseFloat(left);
    var rightNumber = Number.parseFloat(right);
    if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber !== rightNumber) return leftNumber - rightNumber;
    return left.localeCompare(right, 'en', { numeric: true, sensitivity: 'base' });
  }

  function variantGroups(rows) {
    var groups = new Map();
    (rows || []).forEach(function (item) {
      var parsed = variantParse(item);
      if (!groups.has(parsed.productKey)) groups.set(parsed.productKey, { name: parsed.baseName, items: [] });
      groups.get(parsed.productKey).items.push(item);
    });
    return Array.from(groups.values()).map(function (group) {
      group.items.sort(variantSort);
      return group;
    }).sort(function (a, b) {
      return a.name.localeCompare(b.name, 'en', { numeric: true, sensitivity: 'base' });
    });
  }

  function ensureVariantStyles() {
    if (one('#owner-item-variant-style')) return;
    var style = document.createElement('style');
    style.id = 'owner-item-variant-style';
    style.textContent =
      '.item-product-card{padding:0;overflow:hidden}.item-product-head{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:15px 16px;border-bottom:1px solid #e7eef2}.item-product-head h3{margin:0}.item-product-head small{display:block;margin-top:4px;color:#798692}.item-product-count{background:#eaf6fd;color:#087fbf;border-radius:999px;padding:6px 10px;font-weight:800;font-size:12px}.item-variant-row{width:100%;border:0;border-bottom:1px solid #edf1f4;background:#fff;padding:12px 15px;display:grid;grid-template-columns:minmax(90px,1.2fr) repeat(3,minmax(62px,1fr)) 18px;gap:8px;align-items:center;text-align:left;color:inherit}.item-variant-row:last-child{border-bottom:0}.item-variant-row:active{background:#f1f8fc}.item-variant-cell{min-width:0}.item-variant-cell small,.item-variant-cell b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.item-variant-cell small{font-size:10px;color:#8a97a1}.item-variant-cell b{margin-top:3px;font-size:13px}.item-variant-size b{font-size:15px}.item-variant-stock.negative b{color:#d73d5d}.item-variant-stock.positive b{color:#149e6e}.item-variant-arrow{font-size:24px;color:#87939e}.search-result .variant-search-meta{display:block;margin-top:3px;color:#7e8b95;font-size:12px}.variant-picker-backdrop{position:fixed;inset:0;z-index:1300;background:rgba(25,38,50,.52);display:flex;align-items:flex-end;justify-content:center}.variant-picker-sheet{width:min(680px,100%);max-height:78vh;overflow:auto;background:#fff;border-radius:24px 24px 0 0;padding:18px 16px calc(18px + env(safe-area-inset-bottom));box-shadow:0 -12px 35px rgba(0,0,0,.22)}.variant-picker-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}.variant-picker-head h2{margin:0;font-size:23px}.variant-picker-close{width:42px;height:42px;border:0;border-radius:50%;font-size:28px;background:#eef4f7}.variant-picker-option{width:100%;display:grid;grid-template-columns:minmax(90px,1fr) 1fr 1fr 20px;gap:10px;align-items:center;border:1px solid #dbe6ec;border-radius:15px;background:#fff;padding:14px;margin:9px 0;text-align:left;color:inherit}.variant-picker-option strong,.variant-picker-option small{display:block}.variant-picker-option small{color:#7e8b95;margin-top:3px}.variant-picker-option .negative{color:#d73d5d}.variant-picker-option .positive{color:#149e6e}@media(max-width:430px){.item-variant-row{grid-template-columns:minmax(72px,1.2fr) repeat(3,minmax(52px,1fr)) 12px;padding-inline:10px;gap:5px}.item-variant-cell b{font-size:12px}.variant-picker-option{grid-template-columns:minmax(75px,1.1fr) 1fr 1fr 14px;padding:12px 10px}}';
    document.head.appendChild(style);
  }

  function closeVariantPicker() {
    var picker = one('#sale-variant-picker');
    if (picker) picker.remove();
    document.body.style.overflow = '';
  }

  function addSaleVariant(item) {
    if (!item) return;
    var parsed = variantParse(item);
    var existing = state.saleLines.find(function (line) { return Number(line.item_id) === Number(item.id); });
    if (existing) existing.qty += 1;
    else state.saleLines.push({
      item_id: item.id,
      item_name: parsed.baseName,
      size: parsed.size || item.size || '',
      qty: 1,
      rate: number(item.sale_price),
      gst_rate: number(item.gst_rate)
    });
    one('#sale-item-search').value = '';
    one('#sale-item-results').classList.add('hidden');
    closeVariantPicker();
    renderSaleLines();
  }

  function openVariantPicker(group) {
    ensureVariantStyles();
    closeVariantPicker();
    var backdrop = document.createElement('div');
    backdrop.id = 'sale-variant-picker';
    backdrop.className = 'variant-picker-backdrop';
    backdrop.innerHTML = '<section class="variant-picker-sheet"><div class="variant-picker-head"><div><small>SELECT SIZE / BATCH</small><h2>' + escapeHtml(group.name) + '</h2></div><button type="button" class="variant-picker-close">×</button></div>' + group.items.map(function (item) {
      var parsed = variantParse(item);
      var low = number(item.stock) <= number(item.min_stock);
      return '<button type="button" class="variant-picker-option" data-variant-item-id="' + Number(item.id) + '"><div><strong>' + escapeHtml(parsed.label) + '</strong><small>' + escapeHtml(item.sku || '') + '</small></div><div><small>Rate</small><strong>' + money(item.sale_price) + '</strong></div><div><small>Stock</small><strong class="' + (low ? 'negative' : 'positive') + '">' + escapeHtml(item.stock) + ' ' + escapeHtml(item.unit || '') + '</strong></div><span>›</span></button>';
    }).join('') + '</section>';
    document.body.appendChild(backdrop);
    document.body.style.overflow = 'hidden';
    one('.variant-picker-close', backdrop).addEventListener('click', closeVariantPicker);
    backdrop.addEventListener('click', function (event) {
      if (event.target === backdrop) return closeVariantPicker();
      var button = event.target.closest('[data-variant-item-id]');
      if (!button) return;
      var item = state.items.find(function (row) { return Number(row.id) === Number(button.getAttribute('data-variant-item-id')); });
      addSaleVariant(item);
    });
  }

  itemText = function itemText(item) {
    var parsed = variantParse(item);
    return [item.name, parsed.baseName, parsed.size, item.size, item.unit, item.sku, item.category].join(' ').toLowerCase();
  };

  renderItems = function renderItems() {
    ensureVariantStyles();
    var container = one('#items-list');
    if (!container) return;
    var query = String(one('#item-search').value || '').trim().toLowerCase();
    var rows = state.items.filter(function (item) {
      var matchesText = !query || itemText(item).indexOf(query) >= 0;
      var matchesFilter = state.itemFilter !== 'low' || number(item.stock) <= number(item.min_stock);
      return matchesText && matchesFilter;
    });
    var groups = variantGroups(rows);
    if (!groups.length) return showEmpty(container, 'No items found');
    container.innerHTML = groups.map(function (group) {
      return '<article class="item-card item-product-card"><div class="item-product-head"><div><h3>' + escapeHtml(group.name) + '</h3><small>' + group.items.length + (group.items.length === 1 ? ' size / batch' : ' sizes / batches') + '</small></div><span class="item-product-count">' + (group.items.length === 1 ? escapeHtml(variantParse(group.items[0]).label) : 'All Sizes') + '</span></div>' + group.items.map(function (item) {
        var parsed = variantParse(item);
        var low = number(item.stock) <= number(item.min_stock);
        return '<button type="button" class="item-variant-row" data-action="edit-item" data-id="' + Number(item.id) + '"><div class="item-variant-cell item-variant-size"><small>Size / Batch</small><b>' + escapeHtml(parsed.label) + '</b></div><div class="item-variant-cell"><small>Sale</small><b>' + money(item.sale_price) + '</b></div><div class="item-variant-cell"><small>Purchase</small><b>' + money(item.purchase_price) + '</b></div><div class="item-variant-cell item-variant-stock ' + (low ? 'negative' : 'positive') + '"><small>Stock</small><b>' + escapeHtml(item.stock) + ' ' + escapeHtml(item.unit || '') + '</b></div><span class="item-variant-arrow">›</span></button>';
      }).join('') + '</article>';
    }).join('');
  };

  renderSaleSearch = function renderSaleSearch() {
    ensureVariantStyles();
    var box = one('#sale-item-results');
    var query = String(one('#sale-item-search').value || '').trim().toLowerCase();
    if (!query) {
      box.classList.add('hidden');
      box.innerHTML = '';
      return;
    }
    var groups = variantGroups(state.items.filter(function (item) { return itemText(item).indexOf(query) >= 0; })).slice(0, 25);
    if (!groups.length) box.innerHTML = '<div class="empty-state">No item found</div>';
    else box.innerHTML = groups.map(function (group) {
      var first = group.items[0];
      var rates = group.items.map(function (item) { return number(item.sale_price); });
      var minRate = Math.min.apply(Math, rates);
      var maxRate = Math.max.apply(Math, rates);
      var rateText = minRate === maxRate ? money(minRate) : money(minRate) + ' - ' + money(maxRate);
      var labels = group.items.slice(0, 4).map(function (item) { return variantParse(item).label; }).join(', ');
      if (group.items.length > 4) labels += ' +' + (group.items.length - 4);
      return '<button type="button" class="search-result" data-action="add-sale-item" data-id="' + Number(first.id) + '"><div><b>' + escapeHtml(group.name) + '</b><small class="variant-search-meta">' + group.items.length + (group.items.length === 1 ? ' size: ' : ' sizes: ') + escapeHtml(labels) + '</small></div><strong>' + rateText + '</strong></button>';
    }).join('');
    box.classList.remove('hidden');
  };

  addSaleItem = function addSaleItem(itemId) {
    var selectedItem = state.items.find(function (row) { return Number(row.id) === Number(itemId); });
    if (!selectedItem) return;
    var selectedKey = variantParse(selectedItem).productKey;
    var group = variantGroups(state.items.filter(function (item) { return variantParse(item).productKey === selectedKey; }))[0];
    if (!group || !group.items.length) return;
    if (group.items.length === 1) return addSaleVariant(group.items[0]);
    openVariantPicker(group);
  };
