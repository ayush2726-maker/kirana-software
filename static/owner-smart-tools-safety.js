(function () {
  'use strict';
  if (window.__kiranaPhotoDraftSafety143) return;
  window.__kiranaPhotoDraftSafety143 = true;

  function q(id) { return document.getElementById(id); }
  function num(value) {
    var n = Number(value || 0);
    return Number.isFinite(n) ? n : 0;
  }

  function validCatalogValues() {
    var list = q('item-options');
    if (!list) return new Set();
    return new Set(Array.prototype.map.call(list.querySelectorAll('option'), function (option) {
      return String(option.value || '').trim().toLowerCase();
    }).filter(Boolean));
  }

  function rowState() {
    var body = q('draft-lines');
    if (!body) return { ok: false, invalid: 0, active: 0 };
    var catalog = validCatalogValues();
    var active = 0;
    var invalid = 0;
    Array.prototype.forEach.call(body.querySelectorAll('tr'), function (row) {
      var item = row.querySelector('[data-field="item_name"]');
      var qty = row.querySelector('[data-field="qty"]');
      var rate = row.querySelector('[data-field="rate"]');
      var text = String(item && item.value || '').trim();
      if (!text) return;
      active += 1;
      var exact = catalog.has(text.toLowerCase());
      if (!exact || num(qty && qty.value) <= 0 || num(rate && rate.value) <= 0) invalid += 1;
    });
    return { ok: active > 0 && invalid === 0, invalid: invalid, active: active };
  }

  function helper() {
    var node = q('photo-save-guard');
    if (node) return node;
    var save = q('save-bill');
    if (!save || !save.parentNode) return null;
    node = document.createElement('div');
    node.id = 'photo-save-guard';
    node.style.width = '100%';
    node.style.marginTop = '8px';
    node.style.padding = '10px 12px';
    node.style.borderRadius = '10px';
    node.style.fontWeight = '800';
    node.style.fontSize = '13px';
    save.parentNode.parentNode.insertBefore(node, save.parentNode);
    return node;
  }

  function updateGuard() {
    var save = q('save-bill');
    var draft = q('bill-draft');
    if (!save || !draft || !draft.classList.contains('show')) return;
    var state = rowState();
    var note = helper();
    save.disabled = !state.ok;
    if (!note) return;
    if (state.ok) {
      note.textContent = '✓ Sabhi item rows catalog se verify hain. Bill save kar sakte ho.';
      note.style.background = '#e8f7ef';
      note.style.color = '#087b48';
    } else {
      note.textContent = state.active
        ? '⚠ ' + state.invalid + ' row verify nahi hai. Har row me Item Catalog ka correct item select karo; tab Save Bill enable hoga.'
        : '⚠ Valid item row chahiye.';
      note.style.background = '#fff0ef';
      note.style.color = '#a6293d';
    }
  }

  document.addEventListener('click', function (event) {
    var save = event.target && event.target.closest ? event.target.closest('#save-bill') : null;
    if (!save) return;
    var state = rowState();
    if (!state.ok) {
      event.preventDefault();
      event.stopImmediatePropagation();
      updateGuard();
      var status = q('ocr-status');
      if (status) {
        status.textContent = 'Galat bill save hone se roka gaya. Pehle har row ka correct catalog item select karo.';
        status.className = 'status show error';
      }
    }
  }, true);

  document.addEventListener('input', function (event) {
    if (event.target && event.target.closest && event.target.closest('#bill-draft')) {
      window.setTimeout(updateGuard, 0);
    }
  });
  document.addEventListener('change', function (event) {
    if (event.target && event.target.closest && event.target.closest('#bill-draft')) {
      window.setTimeout(updateGuard, 30);
    }
  });

  var observer = new MutationObserver(function () { window.setTimeout(updateGuard, 0); });
  var draft = q('bill-draft');
  if (draft) observer.observe(draft, { subtree: true, childList: true, attributes: true, attributeFilter: ['class'] });
  window.setInterval(updateGuard, 1000);
})();
