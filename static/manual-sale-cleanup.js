(() => {
  'use strict';

  function renderManualCleanup(audit = {}) {
    const host = document.querySelector('#import-history');
    if (!host) return;
    document.querySelector('#manual-itemwise-cleanup-banner')?.remove();

    const count = Number(audit.transaction_count || 0);
    const batches = Number(audit.batch_count || 0);
    const banner = document.createElement('div');
    banner.id = 'manual-itemwise-cleanup-banner';
    banner.className = 'info-banner';
    banner.style.cssText = 'margin-bottom:12px;border-color:#ef476f;background:#fff6f8';
    banner.innerHTML = `
      <b>${count ? `${count} possible item-wise sale bills mile` : 'Old item-wise Sale bills check karein'}</b>
      <p>${count
        ? `${batches} SaleReport import batch mein lagbhag har item ka alag bill bana hua hai. Inhe remove karke wahi SaleReport dobara upload karein.`
        : 'Purane SaleReport import mein har item ka alag bill bana ho to yahan se check aur remove kar sakte hain.'}</p>
      <button id="manual-cleanup-itemwise-sales" class="btn primary" type="button">
        ${count ? 'Remove Item-wise Sale Bills' : 'Check Item-wise Sale Bills'}
      </button>
    `;
    host.prepend(banner);
  }

  if (typeof loadImportHistory === 'function') {
    const previousLoadImportHistory = loadImportHistory;
    loadImportHistory = async function () {
      await previousLoadImportHistory();
      try {
        const audit = await api('/api/import/manual-itemwise-sales', {method: 'POST'});
        renderManualCleanup(audit);
      } catch (error) {
        console.warn('Manual sale cleanup audit failed', error);
        renderManualCleanup({});
      }
    };
  }

  document.addEventListener('click', async event => {
    const button = event.target.closest('#manual-cleanup-itemwise-sales');
    if (!button) return;
    button.disabled = true;
    try {
      const audit = await api('/api/import/manual-itemwise-sales', {method: 'POST'});
      if (!audit.transaction_count) {
        toast('Koi high-confidence item-wise SaleReport batch nahi mila');
        renderManualCleanup(audit);
        return;
      }
      const names = (audit.batches || []).map(row => row.filename).filter(Boolean).join(', ');
      const ok = confirm(
        `${audit.transaction_count} item-wise sale bills remove honge.\n\n` +
        `${names || 'SaleReport'}\n\n` +
        'Stock, party balance aur cash effect reverse hoga. Iske baad SaleReport dobara upload karna hai. Continue karein?'
      );
      if (!ok) {
        button.disabled = false;
        return;
      }
      const result = await api('/api/import/manual-itemwise-sales?execute=true', {method: 'POST'});
      toast(`${result.removed || result.transaction_count} item-wise bills removed`);
      await refreshAll();
      await loadImportHistory();
    } catch (error) {
      toast(error.message, true);
      button.disabled = false;
    }
  });
})();
