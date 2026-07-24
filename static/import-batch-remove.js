(() => {
  'use strict';

  let loading = false;

  const style = document.createElement('style');
  style.textContent = `
    #sales-import-batches-card{border:1px solid #f0b43c;background:#fffaf0}
    #sales-import-batches-card h2{margin:0 0 5px}
    #sales-import-batches-card>p{margin:0 0 12px;color:#6c7480;line-height:1.45}
    .removable-batch-list{display:grid;gap:10px}
    .removable-batch-row{background:#fff;border:1px solid #e1e5ea;border-radius:13px;padding:12px;display:grid;gap:9px}
    .removable-batch-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
    .removable-batch-top b{display:block;word-break:break-word}
    .removable-batch-top small{display:block;color:#767f8b;margin-top:4px;line-height:1.35}
    .removable-batch-count{white-space:nowrap;color:#202630;font-weight:800}
    .removable-batch-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}
    .removable-batch-stats div{background:#f5f7f9;border-radius:9px;padding:8px}
    .removable-batch-stats small{display:block;color:#79818d;font-size:10px;margin-bottom:2px}
    .removable-batch-stats strong{font-size:13px}
    .remove-import-button{width:100%;border:0;border-radius:10px;min-height:45px;background:#ef3156;color:#fff;font-weight:800;font-size:15px}
    .remove-import-button:disabled{background:#aeb5bf;color:#f5f6f7}
    .removable-batch-message{padding:17px;text-align:center;color:#757e8a;background:#fff;border-radius:11px}
  `;
  document.head.appendChild(style);

  const host = () => document.querySelector('#removable-sales-batches');

  function batchRow(batch) {
    const blocked = Number(batch.linked_payments || 0) > 0;
    return `
      <article class="removable-batch-row">
        <div class="removable-batch-top">
          <div>
            <b>${esc(batch.filename || 'SaleReport')}</b>
            <small>${niceDate(batch.date_from)} to ${niceDate(batch.date_to)} · Imported ${niceDate((batch.created_at || '').slice(0,10))}</small>
          </div>
          <span class="removable-batch-count">${Number(batch.transactions || 0).toLocaleString('en-IN')} bills</span>
        </div>
        <div class="removable-batch-stats">
          <div><small>ITEM LINES</small><strong>${Number(batch.lines || 0).toLocaleString('en-IN')}</strong></div>
          <div><small>TOTAL</small><strong>${money(batch.total)}</strong></div>
          <div><small>LINKED PAYMENTS</small><strong>${Number(batch.linked_payments || 0)}</strong></div>
        </div>
        <button
          class="remove-import-button"
          data-remove-sales-batch="${batch.id}"
          data-remove-filename="${encodeURIComponent(batch.filename || '')}"
          data-remove-transactions="${batch.transactions || 0}"
          data-remove-lines="${batch.lines || 0}"
          type="button"
          ${blocked ? 'disabled' : ''}
        >${blocked ? 'Linked Payment Hai — Remove Blocked' : 'Remove This Sales Import'}</button>
      </article>
    `;
  }

  async function loadRemovableBatches() {
    const element = host();
    if (!element || loading) return;
    loading = true;
    element.innerHTML = '<div class="removable-batch-message">Sales import batches load ho rahe hain…</div>';
    try {
      const batches = await api('/api/import/removable-sales-batches');
      element.innerHTML = batches.length
        ? batches.map(batchRow).join('')
        : '<div class="removable-batch-message">Koi active Sales import batch nahi hai.</div>';
    } catch (error) {
      element.innerHTML = `<div class="removable-batch-message">${esc(error.message || 'Batch list load nahi hui')}</div>`;
    } finally {
      loading = false;
    }
  }

  async function removeBatch(button) {
    const batchId = Number(button.dataset.removeSalesBatch || 0);
    const filename = decodeURIComponent(button.dataset.removeFilename || '');
    const transactions = Number(button.dataset.removeTransactions || 0);
    const lines = Number(button.dataset.removeLines || 0);
    if (!batchId || !filename) return;

    const ok = confirm(
      `Is poore Sales import ko remove karein?\n\n${filename}\n${transactions.toLocaleString('en-IN')} bills · ${lines.toLocaleString('en-IN')} item lines\n\nStock, party outstanding aur imported cash/bank effect reverse hoga. Manual sales aur doosre import batches delete nahi honge.`
    );
    if (!ok) return;

    button.disabled = true;
    button.textContent = 'Removing Import…';
    try {
      const result = await api(`/api/import/remove-sales-batch/${batchId}`, {
        method: 'POST',
        body: {confirm_filename: filename},
      });
      toast(`${Number(result.removed_transactions || 0).toLocaleString('en-IN')} imported Sale bills removed`);
      await refreshAll();
      if (typeof loadTransactions === 'function' && typeof state !== 'undefined' && state.txTab === 'sale') {
        await loadTransactions();
      }
      if (typeof loadImportHistory === 'function') {
        await loadImportHistory();
      }
      await loadRemovableBatches();
    } catch (error) {
      toast(error.message, true);
      button.disabled = false;
      button.textContent = 'Remove This Sales Import';
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-sales-batch]');
    if (button) removeBatch(button);
  });

  if (typeof loadImportHistory === 'function') {
    const previousLoadImportHistory = loadImportHistory;
    loadImportHistory = async function (...args) {
      const result = await previousLoadImportHistory(...args);
      await loadRemovableBatches();
      return result;
    };
  }

  setTimeout(loadRemovableBatches, 350);
})();
