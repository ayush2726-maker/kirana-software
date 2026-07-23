(() => {
  'use strict';

  const style = document.createElement('style');
  style.textContent = `
    .transaction-date-heading{
      display:flex;align-items:center;gap:10px;margin:18px 4px 8px;
      color:var(--muted);font-size:13px;font-weight:800;letter-spacing:.02em;text-transform:uppercase;
    }
    .transaction-date-heading::after{content:'';height:1px;flex:1;background:rgba(130,145,160,.22)}
    .transaction-card + .transaction-date-heading{margin-top:22px}
    .transaction-history-more{display:flex;justify-content:center;padding:18px 0 34px}
    .transaction-history-more button{
      min-width:210px;min-height:48px;border:1px solid #bed8e8;border-radius:12px;
      background:#fff;color:#087bc1;font-size:15px;font-weight:800;cursor:pointer;
    }
    .transaction-history-more button:disabled{opacity:.65;cursor:default}
  `;
  document.head.appendChild(style);

  const PAGE_SIZE = 200;
  const txHistory = {
    tab: null,
    rows: [],
    offset: 0,
    hasMore: true,
    loading: false,
    requestId: 0,
  };

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

  function historyRows() {
    if (txHistory.tab === state.txTab) return txHistory.rows;
    return state.activity;
  }

  function moreHtml() {
    if (!txHistory.hasMore && txHistory.rows.length) {
      return '<div class="transaction-history-more"><small>Complete history loaded</small></div>';
    }
    if (!txHistory.hasMore) return '';
    return `<div class="transaction-history-more">
      <button id="load-more-transactions" type="button" ${txHistory.loading ? 'disabled' : ''}>
        ${txHistory.loading ? 'Loading older records…' : 'Load Older Transactions'}
      </button>
    </div>`;
  }

  async function loadTransactionPage(reset = false) {
    const tab = state.txTab || 'all';
    if (txHistory.loading && !reset) return;

    const requestId = ++txHistory.requestId;
    if (reset || txHistory.tab !== tab) {
      txHistory.tab = tab;
      txHistory.rows = [];
      txHistory.offset = 0;
      txHistory.hasMore = true;
      const list = $('#transactions-list');
      if (list) list.innerHTML = emptyText('Transactions load ho rahe hain…');
    }
    if (!txHistory.hasMore) return;

    txHistory.loading = true;
    renderTransactions();
    try {
      const kindParam = ['sale', 'purchase'].includes(tab) ? `&kind=${encodeURIComponent(tab)}` : '';
      const rows = await api(`/api/activity?limit=${PAGE_SIZE}&offset=${txHistory.offset}${kindParam}`);
      if (requestId !== txHistory.requestId || tab !== state.txTab) return;

      const seen = new Set(txHistory.rows.map(row => `${row.kind}:${row.id}`));
      rows.forEach(row => {
        const key = `${row.kind}:${row.id}`;
        if (!seen.has(key)) {
          txHistory.rows.push(row);
          seen.add(key);
        }
      });
      txHistory.offset += rows.length;
      txHistory.hasMore = rows.length === PAGE_SIZE;
    } catch (error) {
      toast(error.message, true);
    } finally {
      if (requestId === txHistory.requestId) {
        txHistory.loading = false;
        renderTransactions();
      }
    }
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
    const source = historyRows();
    const rows = dateWiseMix(source.filter(row =>
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

    const list = $('#transactions-list');
    if (!list) return;
    list.innerHTML = groupedHtml(rows, true) + (txHistory.tab === state.txTab ? moreHtml() : '');
  };

  loadTransactions = async function () {
    await loadTransactionPage(true);
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
    const more = event.target.closest('#load-more-transactions');
    if (more) {
      loadTransactionPage(false);
      return;
    }

    const tab = event.target.closest('[data-tx-tab]');
    if (tab) {
      setTimeout(() => loadTransactionPage(true), 0);
      return;
    }

    const launch = event.target.closest('[data-menu-launch]');
    if (!launch) return;
    const target = launch.dataset.menuLaunch;
    if (target !== 'sales' && target !== 'purchases') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openFilteredTransactions(target === 'sales' ? 'sale' : 'purchase');
  }, true);

  let scrollTimer = null;
  window.addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      if (!$('#page-transactions')?.classList.contains('active')) return;
      if (!txHistory.hasMore || txHistory.loading) return;
      const remaining = document.documentElement.scrollHeight - window.scrollY - window.innerHeight;
      if (remaining < 700) loadTransactionPage(false);
    }, 80);
  }, {passive: true});
})();
