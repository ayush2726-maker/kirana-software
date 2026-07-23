(() => {
  'use strict';

  let latestAudit = null;
  let auditPromise = null;

  const style = document.createElement('style');
  style.textContent = `
    .duplicate-sale-cleanup-banner{
      margin:12px 0;
      padding:14px;
      border:1px solid #ef476f;
      border-radius:14px;
      background:#fff6f8;
      box-shadow:0 5px 14px rgba(239,71,111,.08);
    }
    .duplicate-sale-cleanup-banner b{display:block;margin-bottom:5px;color:#252936}
    .duplicate-sale-cleanup-banner p{margin:0 0 10px;color:#666d7b;font-size:13px;line-height:1.45}
    .duplicate-sale-cleanup-banner button{width:100%}
  `;
  document.head.appendChild(style);

  function countOf(audit = {}) {
    return Number(audit.transaction_count || 0);
  }

  function batchesOf(audit = {}) {
    return Number(audit.batch_count || 0);
  }

  function bannerHtml(audit = {}) {
    const count = countOf(audit);
    const batches = batchesOf(audit);
    return `
      <b>${count ? `${count} possible duplicate item-wise Sale bills mile` : 'Duplicate / item-wise Sale bills check karein'}</b>
      <p>${count
        ? `${batches} SaleReport import batch mein har item ka alag bill bana hua lag raha hai. Remove karne ke baad original SaleReport dobara upload karein.`
        : 'Agar imported SaleReport mein har item ka alag bill bana hai to yahan se safely check karke remove karein.'}</p>
      <button data-manual-cleanup-sales class="btn primary" type="button">
        ${count ? `Remove ${count} Duplicate Sale Bills` : 'Check Duplicate Sale Bills'}
      </button>
    `;
  }

  function renderImportBanner(audit = latestAudit || {}) {
    const host = document.querySelector('#import-history');
    if (!host) return;
    let banner = document.querySelector('#manual-itemwise-cleanup-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'manual-itemwise-cleanup-banner';
      banner.className = 'duplicate-sale-cleanup-banner';
      host.prepend(banner);
    }
    banner.innerHTML = bannerHtml(audit);
  }

  function renderSaleBanner(audit = latestAudit || {}) {
    const page = document.querySelector('#page-transactions');
    if (!page) return;
    let banner = document.querySelector('#sale-history-cleanup-banner');
    const shouldShow = typeof state !== 'undefined' && state.txTab === 'sale';
    if (!shouldShow) {
      banner?.remove();
      return;
    }
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'sale-history-cleanup-banner';
      banner.className = 'duplicate-sale-cleanup-banner';
      const tabs = page.querySelector('.tabs');
      page.insertBefore(banner, tabs || page.firstChild);
    }
    banner.innerHTML = bannerHtml(audit);
  }

  function renderEverywhere(audit = latestAudit || {}) {
    renderImportBanner(audit);
    renderSaleBanner(audit);
  }

  async function fetchAudit(force = false) {
    if (auditPromise && !force) return auditPromise;
    auditPromise = api('/api/import/manual-itemwise-sales', {method: 'POST'})
      .then(audit => {
        latestAudit = audit || {};
        renderEverywhere(latestAudit);
        return latestAudit;
      })
      .catch(error => {
        console.warn('Manual sale cleanup audit failed', error);
        latestAudit = {};
        renderEverywhere(latestAudit);
        return latestAudit;
      })
      .finally(() => {
        auditPromise = null;
      });
    return auditPromise;
  }

  if (typeof loadImportHistory === 'function') {
    const previousLoadImportHistory = loadImportHistory;
    loadImportHistory = async function () {
      await previousLoadImportHistory();
      renderImportBanner(latestAudit || {});
      await fetchAudit(true);
    };
  }

  if (typeof renderTransactions === 'function') {
    const previousRenderTransactions = renderTransactions;
    renderTransactions = function (...args) {
      const result = previousRenderTransactions(...args);
      renderSaleBanner(latestAudit || {});
      if (typeof state !== 'undefined' && state.txTab === 'sale' && !latestAudit && !auditPromise) {
        fetchAudit();
      }
      return result;
    };
  }

  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-manual-cleanup-sales]');
    if (!button) return;

    const buttons = [...document.querySelectorAll('[data-manual-cleanup-sales]')];
    buttons.forEach(item => { item.disabled = true; });

    try {
      const audit = await fetchAudit(true);
      if (!countOf(audit)) {
        toast('Koi high-confidence duplicate SaleReport batch nahi mila');
        renderEverywhere(audit);
        return;
      }

      const names = (audit.batches || []).map(row => row.filename).filter(Boolean).join(', ');
      const ok = confirm(
        `${audit.transaction_count} duplicate item-wise sale bills remove honge.\n\n` +
        `${names || 'SaleReport'}\n\n` +
        'Stock, party balance aur cash effect reverse hoga. Iske baad sahi SaleReport dobara upload karna hai. Continue karein?'
      );
      if (!ok) return;

      const result = await api('/api/import/manual-itemwise-sales?execute=true', {method: 'POST'});
      toast(`${result.removed || result.transaction_count || 0} duplicate sale bills removed`);
      latestAudit = null;
      await refreshAll();
      if (typeof loadTransactions === 'function' && typeof state !== 'undefined' && state.txTab === 'sale') {
        await loadTransactions();
      }
      if (document.querySelector('#page-import')?.classList.contains('active') && typeof loadImportHistory === 'function') {
        await loadImportHistory();
      } else {
        await fetchAudit(true);
      }
    } catch (error) {
      toast(error.message, true);
    } finally {
      document.querySelectorAll('[data-manual-cleanup-sales]').forEach(item => { item.disabled = false; });
    }
  });
})();
