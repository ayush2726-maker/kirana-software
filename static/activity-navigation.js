(() => {
  'use strict';

  const style = document.createElement('style');
  style.textContent = `
    .transaction-date-heading{
      display:flex;
      align-items:center;
      gap:10px;
      margin:18px 4px 8px;
      color:var(--muted);
      font-size:13px;
      font-weight:800;
      letter-spacing:.02em;
      text-transform:uppercase;
    }
    .transaction-date-heading::after{
      content:'';
      height:1px;
      flex:1;
      background:rgba(130,145,160,.22);
    }
    .transaction-card + .transaction-date-heading{margin-top:22px}
  `;
  document.head.appendChild(style);

  function category(kind) {
    if (kind === 'sale') return 'sale';
    if (kind === 'purchase') return 'purchase';
    return 'other';
  }

  function dateWiseMix(rows) {
    const groups = new Map();
    rows.forEach(row => {
      const key = row.entry_date || '';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    });

    const result = [];
    [...groups.keys()].sort().reverse().forEach(date => {
      const queues = { sale: [], purchase: [], other: [] };
      groups.get(date)
        .slice()
        .sort((a, b) => {
          const created = String(b.created_at || '').localeCompare(String(a.created_at || ''));
          return created || Number(b.id || 0) - Number(a.id || 0);
        })
        .forEach(row => queues[category(row.kind)].push(row));

      while (queues.sale.length || queues.purchase.length || queues.other.length) {
        if (queues.sale.length) result.push(queues.sale.shift());
        if (queues.purchase.length) result.push(queues.purchase.shift());
        if (queues.other.length) result.push(queues.other.shift());
      }
    });
    return result;
  }

  function longDate(value) {
    if (!value) return 'Date not available';
    const date = new Date(`${value}T00:00:00`);
    const now = new Date();
    const todayKey = now.toISOString().slice(0, 10);
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayKey = yesterday.toISOString().slice(0, 10);
    if (value === todayKey) return 'Today';
    if (value === yesterdayKey) return 'Yesterday';
    return date.toLocaleDateString('en-IN', {
      weekday: 'short', day: '2-digit', month: 'short', year: 'numeric'
    });
  }

  function cardHtml(row, includeUnpaid = true) {
    const unpaid = includeUnpaid && num(row.due) > 0;
    return `<article class="transaction-card" data-activity-kind="${row.kind}" data-activity-id="${row.id}">
      <div class="transaction-top">
        <div>
          <h3>${esc(row.title || row.ref || activityLabel(row.kind))}</h3>
          <span class="status-pill ${statusClass(row.kind)}">${activityLabel(row.kind)}${unpaid ? ' : UNPAID' : ''}</span>
        </div>
        <time>${niceDate(row.entry_date)}<br><small>${esc(row.ref || '')}</small></time>
      </div>
      <div class="transaction-values">
        <div><small>Total</small><strong>${money(row.amount)}</strong></div>
        <div><small>${unpaid ? 'Balance' : 'Status'}</small><strong class="${unpaid ? 'negative' : ''}">${unpaid ? money(row.due) : esc(row.status || 'Completed')}</strong></div>
        <div class="transaction-actions"><span>${icon('receipt')}</span><span>${icon('arrow')}</span></div>
      </div>
    </article>`;
  }

  function groupedHtml(rows, includeUnpaid = true) {
    if (!rows.length) return emptyText('Abhi koi transaction nahi hai.');
    let previousDate = null;
    return rows.map(row => {
      const heading = row.entry_date !== previousDate
        ? `<div class="transaction-date-heading">${esc(longDate(row.entry_date))}</div>`
        : '';
      previousDate = row.entry_date;
      return heading + cardHtml(row, includeUnpaid);
    }).join('');
  }

  renderActivity = function () {
    const q = ($('#activity-search')?.value || '').toLowerCase();
    const rows = dateWiseMix(state.activity.filter(row =>
      `${row.title} ${row.ref} ${row.kind}`.toLowerCase().includes(q)
    ));
    $('#activity-list').innerHTML = groupedHtml(rows, true);
  };

  renderTransactions = function () {
    const q = ($('#tx-filter')?.value || '').toLowerCase();
    const rows = dateWiseMix(state.activity.filter(row =>
      (state.txTab === 'all' || (state.txTab === 'other'
        ? !['sale', 'purchase'].includes(row.kind)
        : row.kind === state.txTab)) &&
      `${row.title} ${row.ref} ${row.kind}`.toLowerCase().includes(q)
    ));

    const title = state.txTab === 'sale'
      ? 'Sale Transactions'
      : state.txTab === 'purchase'
        ? 'Purchase Transactions'
        : state.txTab === 'other'
          ? 'Other Transactions'
          : 'Transactions';
    const subtitle = state.txTab === 'sale'
      ? 'All sale invoices date-wise'
      : state.txTab === 'purchase'
        ? 'All purchase invoices date-wise'
        : 'Sale, purchase, payments and documents';
    const heading = $('#page-transactions .page-heading h1');
    const subheading = $('#page-transactions .page-heading p');
    if (heading) heading.textContent = title;
    if (subheading) subheading.textContent = subtitle;
    $('#transactions-list').innerHTML = groupedHtml(rows, true);
  };

  function openFilteredTransactions(tab) {
    state.txTab = tab;
    $$('[data-tx-tab]').forEach(button => {
      button.classList.toggle('active', button.dataset.txTab === tab);
    });
    closeIfOpen($('#txn-launcher'));
    navigate('transactions');
  }

  document.addEventListener('click', event => {
    const launch = event.target.closest('[data-menu-launch]');
    if (!launch) return;
    const target = launch.dataset.menuLaunch;
    if (target !== 'sales' && target !== 'purchases') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openFilteredTransactions(target === 'sales' ? 'sale' : 'purchase');
  }, true);
})();
