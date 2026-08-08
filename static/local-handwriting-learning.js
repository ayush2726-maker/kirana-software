(function () {
  'use strict';
  if (window.__kiranaLocalLearning140) return;
  window.__kiranaLocalLearning140 = true;

  var originalFetch = window.fetch.bind(window);
  var pendingRows = [];

  function pathOf(input) {
    try {
      if (typeof input === 'string') return new URL(input, window.location.href).pathname;
      if (input && input.url) return new URL(input.url, window.location.href).pathname;
    } catch (ignore) {}
    return '';
  }

  function rememberOcr(response, path) {
    if (path !== '/api/photo-bill/ocr' || !response || !response.ok) return;
    try {
      response.clone().json().then(function (data) {
        if (!data || data.reader !== 'kirana_handwriting_local_v1' || !Array.isArray(data.items)) return;
        pendingRows = data.items.map(function (row, index) {
          return {
            index: index,
            source_text: String(row.source_text || ''),
            item_id: row.item_id ? Number(row.item_id) : null,
            item_name: String(row.item_name || ''),
            size: String(row.size || '')
          };
        });
      }).catch(function () {});
    } catch (ignore) {}
  }

  function parseSaveBody(options) {
    try {
      if (!options || typeof options.body !== 'string') return null;
      var parsed = JSON.parse(options.body);
      return parsed && Array.isArray(parsed.items) ? parsed.items : null;
    } catch (ignore) {
      return null;
    }
  }

  function learningRows(savedItems) {
    if (!Array.isArray(savedItems) || !savedItems.length || !pendingRows.length) return [];
    var result = [];
    savedItems.forEach(function (saved, index) {
      var pending = pendingRows[index] || null;
      if (!pending || !pending.source_text) return;
      var itemId = saved && saved.item_id ? Number(saved.item_id) : null;
      if (!itemId) return;
      result.push({
        source_text: pending.source_text,
        item_id: itemId,
        item_name: String(saved.item_name || ''),
        size: String(saved.size || '')
      });
    });
    return result;
  }

  function sendLearning(rows) {
    if (!rows.length) return;
    originalFetch('/api/photo-bill/learn', {
      method: 'POST',
      credentials: 'include',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ rows: rows })
    }).catch(function () {});
  }

  window.fetch = function (input, options) {
    var path = pathOf(input);
    var savedItems = (path === '/api/purchases' || path === '/api/sales') ? parseSaveBody(options) : null;
    return originalFetch(input, options).then(function (response) {
      rememberOcr(response, path);
      if (savedItems && response && response.ok) {
        sendLearning(learningRows(savedItems));
        pendingRows = [];
      }
      return response;
    });
  };
})();
