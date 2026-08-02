(function () {
  'use strict';

  var originalFetch = window.fetch.bind(window);

  function readableDetail(detail) {
    if (!detail) return 'The bulk item request could not be completed.';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map(function (entry) {
        if (typeof entry === 'string') return entry;
        if (!entry || typeof entry !== 'object') return String(entry || 'Invalid value');
        var location = Array.isArray(entry.loc)
          ? entry.loc.filter(function (part) { return part !== 'body'; }).join(' → ')
          : '';
        var message = entry.msg || entry.message || entry.type || 'Invalid value';
        return location ? location + ': ' + message : message;
      }).join('\n');
    }
    if (typeof detail === 'object') {
      return detail.message || detail.msg || JSON.stringify(detail);
    }
    return String(detail);
  }

  window.fetch = async function (input, init) {
    var response = await originalFetch(input, init);
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    if (response.ok || url.indexOf('/api/items/bulk-') === -1) return response;

    var data = await response.clone().json().catch(function () { return null; });
    if (!data || typeof data.detail === 'string') return response;

    var headers = new Headers(response.headers);
    headers.set('Content-Type', 'application/json');
    return new Response(
      JSON.stringify(Object.assign({}, data, { detail: readableDetail(data.detail) })),
      {
        status: response.status,
        statusText: response.statusText,
        headers: headers
      }
    );
  };
})();
