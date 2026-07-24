(() => {
  'use strict';

  let currentAudit = null;
  let loading = false;

  const style = document.createElement('style');
  style.textContent = `
    #duplicate-sale-cleanup-card{border:1px solid #ef476f;background:#fff7f9}
    #duplicate-sale-cleanup-card .duplicate-cleanup-status{display:grid;gap:6px}
    #duplicate-sale-cleanup-card h2{margin:0;color:#2b3039}
    #duplicate-sale-cleanup-card p{margin:0;color:#68717e;line-height:1.45}
    #duplicate-sale-cleanup-card button{margin-top:10px;width:100%}
    .sale-history-cleanup-v2{margin:12px 0;padding:14px;border:1px solid #ef476f;border-radius:14px;background:#fff7f9}
    .sale-history-cleanup-v2 b{display:block;margin-bottom:5px}.sale-history-cleanup-v2 p{margin:0 0 10px;color:#68717e}.sale-history-cleanup-v2 button{width:100%}
  `;
  document.head.appendChild(style);

  function auditCount(audit = {}) {
    return Number(audit.transaction_count || 0);
  }

  function card() {
    return document.querySelector('#duplicate-sale-cleanup-card');
  }

  function markup(audit = {}) {
    const count = auditCount(audit);
    const batches = Number(audit.batch_count || 0);
    return `
      <div class="duplicate-cleanup-status">
        <h2>${count ? `${count} item-wise duplicate Sale bills mile` : 'Duplicate Sale Bills Cleanup'}</h2>
        <p>${count
          ? `${batches} old SaleReport batch mein har item ka alag bill bana hua hai. Inhe remove karke original SaleReport dobara import karein.`
          : 'Automatic strict check optional hai. Direct removal ke liye neeche Sales Import Batches section use karein.'}</p>
      </div>
      <button data-manual-cleanup-sales-v2 class="btn secondary" type="button" ${loading ? 'disabled' : ''}>
        ${loading ? 'Checking…' : count ? `Remove ${count} Duplicate Sale Bills` : 'Automatic Duplicate Check'}
      </button>
    `;
  }

  function renderCard(audit = currentAudit || {}) {
    const host = card();
    if (!host) return;
    host.innerHTML = markup(audit);
  }

  function renderSaleBanner(audit = currentAudit || {}) {
    const page = document.querySelector('#page-transactions');
    if (!page) return;
    let banner = document.querySelector('#sale-history-cleanup-v2');
    const show = typeof state !== 'undefined' && state.txTab === 'sale';
    if (!show) {
      banner?.remove();
      return;
    }
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'sale-history-cleanup-v2';
      banner.className = 'sale-history-cleanup-v2';
      const tabs = page.querySelector('.tabs');
      page.insertBefore(banner, tabs || page.firstChild);
    }
    const count = auditCount(audit);
    banner.innerHTML = `<b>${count ? `${count} duplicate Sale bills mile` : 'Duplicate Sale Bills Check'}</b><p>${count ? 'Old item-wise imported bills remove karke report dobara import karein.' : 'Direct batch removal Vyapar Import page mein available hai.'}</p><button data-manual-cleanup-sales-v2 class="btn secondary" type="button">${count ? `Remove ${count} Duplicate Sale Bills` : 'Automatic Duplicate Check'}</button>`;
  }

  function renderAll(audit = currentAudit || {}) {
    renderCard(audit);
    renderSaleBanner(audit);
  }

  async function fetchAudit() {
    if (loading) return currentAudit || {};
    loading = true;
    renderAll();
    try {
      currentAudit = await api('/api/import/manual-itemwise-sales', {method: 'POST'});
    } catch (error) {
      currentAudit = {};
      toast(error.message || 'Duplicate check failed', true);
    } finally {
      loading = false;
      renderAll(currentAudit);
    }
    return currentAudit;
  }

  async function removeDuplicates() {
    const audit = await fetchAudit();
    const count = auditCount(audit);
    if (!count) {
      toast('Automatic match nahi mila. Vyapar Import mein Sales Import Batches se galat import direct remove karein.');
      return;
    }
    const names = (audit.batches || []).map(row => row.filename).filter(Boolean).join(', ');
    const ok = confirm(
      `${count} item-wise duplicate Sale bills remove honge.\n\n` +
      `${names || 'SaleReport'}\n\n` +
      'Stock, party balance aur cash effect reverse hoga. Uske baad original SaleReport dobara import karna hai. Continue karein?'
    );
    if (!ok) return;
    loading = true;
    renderAll(audit);
    try {
      const result = await api('/api/import/manual-itemwise-sales?execute=true', {method: 'POST'});
      toast(`${result.removed || result.transaction_count || count} duplicate Sale bills removed`);
      currentAudit = null;
      await refreshAll();
      if (typeof loadTransactions === 'function' && typeof state !== 'undefined' && state.txTab === 'sale') {
        await loadTransactions();
      }
      if (typeof loadImportHistory === 'function' && document.querySelector('#page-import')?.classList.contains('active')) {
        await loadImportHistory();
      }
    } catch (error) {
      toast(error.message, true);
    } finally {
      loading = false;
      renderAll(currentAudit || {});
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-manual-cleanup-sales-v2]');
    if (!button) return;
    removeDuplicates();
  });

  if (typeof renderTransactions === 'function') {
    const previous = renderTransactions;
    renderTransactions = function (...args) {
      const result = previous(...args);
      renderSaleBanner(currentAudit || {});
      return result;
    };
  }

  renderCard({});
})();
