(function () {
  'use strict';

  var parties = [];
  var accounts = [];
  var state = null;

  function q(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function num(value) {
    var parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function roundMoney(value) {
    return Math.round((num(value) + Number.EPSILON) * 100) / 100;
  }

  function money(value) {
    return '₹' + num(value).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
      return ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      })[character];
    });
  }

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  async function api(path, options) {
    var config = options || {};
    var headers = Object.assign({ Accept: 'application/json' }, config.headers || {});
    var body = config.body;
    if (body && typeof body !== 'string') {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    var response = await fetch(path, Object.assign({}, config, {
      body: body,
      headers: headers,
      credentials: 'include',
      cache: 'no-store'
    }));
    var data = await response.json().catch(function () { return null; });
    if (response.status === 401) {
      window.location.replace('/owner-login');
      throw new Error('Session expired');
    }
    if (!response.ok) {
      throw new Error(data && data.detail ? data.detail : 'Request failed (' + response.status + ')');
    }
    return data;
  }

  function toast(message, isError) {
    var node = q('#txn-toast') || q('#toast');
    if (!node) {
      window.alert(message);
      return;
    }
    node.textContent = String(message || 'Done');
    node.className = (node.id === 'txn-toast' ? 'txn-toast' : 'toast') + ' show' + (isError ? ' error' : '');
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(function () {
      node.className = node.id === 'txn-toast' ? 'txn-toast' : 'toast';
    }, 3500);
  }

  async function loadMaster() {
    var results = await Promise.all([
      api('/api/parties'),
      api('/api/accounts').catch(function () { return []; })
    ]);
    parties = results[0] || [];
    accounts = results[1] || [];
  }

  function partyAllowed(party, expectedType) {
    return party.type === expectedType || party.type === 'both';
  }

  function billById(id) {
    if (!state) return null;
    return state.bills.find(function (bill) {
      return Number(bill.id) === Number(id);
    }) || null;
  }

  function getAmount() {
    return roundMoney(q('#link-pay-amount') ? q('#link-pay-amount').value : 0);
  }

  function setAmount(value) {
    var input = q('#link-pay-amount');
    if (input) input.value = roundMoney(value).toFixed(2);
  }

  function totalAllocated(excludeId) {
    if (!state) return 0;
    return roundMoney(Object.keys(state.allocations).reduce(function (sum, key) {
      if (excludeId != null && Number(key) === Number(excludeId)) return sum;
      return sum + num(state.allocations[key]);
    }, 0));
  }

  function removeFromOrder(id) {
    if (!state) return;
    state.selectionOrder = state.selectionOrder.filter(function (value) {
      return Number(value) !== Number(id);
    });
  }

  function addToOrder(id) {
    if (!state) return;
    removeFromOrder(id);
    state.selectionOrder.push(Number(id));
  }

  function syncSelectionAmount() {
    if (!state || state.amountMode !== 'selection') return;
    setAmount(totalAllocated());
  }

  function updateSummary() {
    if (!state) return;
    var amount = getAmount();
    var allocated = totalAllocated();
    var allocatedNode = q('#link-allocated');
    var unallocatedNode = q('#link-unallocated');
    if (allocatedNode) allocatedNode.textContent = money(allocated);
    if (unallocatedNode) unallocatedNode.textContent = money(Math.max(0, roundMoney(amount - allocated)));
  }

  function syncBillRows() {
    if (!state) return;
    qa('[data-bill]').forEach(function (row) {
      var id = Number(row.getAttribute('data-bill'));
      var allocation = roundMoney(state.allocations[id] || 0);
      row.classList.toggle('selected', allocation > 0);
      var checkbox = q('[data-bill-check]', row);
      var input = q('[data-bill-amount]', row);
      if (checkbox) checkbox.checked = allocation > 0;
      if (input && document.activeElement !== input) {
        input.value = allocation > 0 ? allocation.toFixed(2) : '0';
      }
    });
    updateSummary();
  }

  function rebalanceSelectedToEnteredAmount() {
    if (!state) return;
    var remaining = getAmount();
    var next = {};
    var nextOrder = [];

    state.selectionOrder.forEach(function (id) {
      if (remaining <= 0) return;
      var bill = billById(id);
      if (!bill) return;
      var allocation = roundMoney(Math.min(num(bill.due), remaining));
      if (allocation <= 0) return;
      next[Number(id)] = allocation;
      nextOrder.push(Number(id));
      remaining = roundMoney(remaining - allocation);
    });

    state.allocations = next;
    state.selectionOrder = nextOrder;
    syncBillRows();
  }

  function billMarkup(bill) {
    var allocation = roundMoney(state.allocations[bill.id] || 0);
    return '<article class="linked-bill-row ' + (allocation > 0 ? 'selected' : '') + '" data-bill="' + Number(bill.id) + '">' +
      '<input type="checkbox" data-bill-check="' + Number(bill.id) + '" ' + (allocation > 0 ? 'checked' : '') + ' aria-label="Select ' + esc(bill.invoice_no || 'invoice') + '">' +
      '<div><b>' + esc(bill.invoice_no || 'Invoice') + '</b><small>' + esc(bill.invoice_date || '') + ' · Total ' + money(bill.total) + ' · Paid ' + money(bill.paid) + '</small></div>' +
      '<div class="linked-bill-amount"><small>Pending ' + money(bill.due) + '</small><input data-bill-amount="' + Number(bill.id) + '" type="number" inputmode="decimal" min="0" max="' + num(bill.due) + '" step="0.01" value="' + (allocation > 0 ? allocation.toFixed(2) : '0') + '"></div>' +
      '</article>';
  }

  function renderBills() {
    var host = q('#link-bills');
    if (!host || !state) return;
    if (!state.party) {
      host.innerHTML = '<div class="linked-payment-empty">Select a party to view pending invoices.</div>';
      return;
    }
    if (state.loading) {
      host.innerHTML = '<div class="linked-payment-empty">Loading pending invoices...</div>';
      return;
    }
    if (!state.bills.length) {
      host.innerHTML = '<div class="linked-payment-empty">No pending invoice found. Payment can still be saved On Account.</div>';
      return;
    }
    host.innerHTML = state.bills.map(billMarkup).join('');
    updateSummary();
  }

  async function loadBills() {
    if (!state || !state.party) return;
    state.loading = true;
    state.bills = [];
    state.allocations = {};
    state.selectionOrder = [];
    state.amountMode = 'selection';
    setAmount(0);
    renderBills();
    try {
      var data = await api('/api/parties/' + state.party + '/open-bills?payment_type=' + state.type);
      state.bills = data.bills || [];
      var totalNode = q('#link-total-due');
      if (totalNode) totalNode.textContent = money(data.total_due || 0);
    } catch (error) {
      toast(error.message, true);
    } finally {
      state.loading = false;
      renderBills();
    }
  }

  function autoLinkOldest() {
    if (!state) return;
    var amount = getAmount();
    var remaining;
    state.allocations = {};
    state.selectionOrder = [];

    if (amount <= 0) {
      state.amountMode = 'selection';
      state.bills.forEach(function (bill) {
        var due = roundMoney(bill.due);
        if (due <= 0) return;
        state.allocations[bill.id] = due;
        state.selectionOrder.push(Number(bill.id));
      });
      syncSelectionAmount();
    } else {
      state.amountMode = 'manual';
      remaining = amount;
      state.bills.forEach(function (bill) {
        if (remaining <= 0) return;
        var allocation = roundMoney(Math.min(num(bill.due), remaining));
        if (allocation <= 0) return;
        state.allocations[bill.id] = allocation;
        state.selectionOrder.push(Number(bill.id));
        remaining = roundMoney(remaining - allocation);
      });
    }
    syncBillRows();
  }

  function clearLinks() {
    if (!state) return;
    state.allocations = {};
    state.selectionOrder = [];
    if (state.amountMode === 'selection') setAmount(0);
    syncBillRows();
  }

  function selectBill(id, checked) {
    if (!state) return;
    var bill = billById(id);
    if (!bill) return;

    if (!checked) {
      delete state.allocations[id];
      removeFromOrder(id);
      syncSelectionAmount();
      syncBillRows();
      return;
    }

    addToOrder(id);
    var amount = getAmount();
    if (state.amountMode === 'selection' || amount <= 0) {
      state.amountMode = 'selection';
      state.allocations[id] = roundMoney(bill.due);
      syncSelectionAmount();
      syncBillRows();
      return;
    }

    var remaining = roundMoney(amount - totalAllocated(id));
    var allocation = roundMoney(Math.min(num(bill.due), Math.max(0, remaining)));
    if (allocation <= 0) {
      delete state.allocations[id];
      removeFromOrder(id);
      syncBillRows();
      toast('Entered payment amount is already fully linked.', true);
      return;
    }
    state.allocations[id] = allocation;
    syncBillRows();
  }

  function editBillAllocation(input) {
    if (!state) return;
    var id = Number(input.getAttribute('data-bill-amount'));
    var bill = billById(id);
    if (!bill) return;

    var requested = roundMoney(Math.min(num(input.value), num(bill.due)));
    if (state.amountMode === 'manual') {
      var available = roundMoney(Math.max(0, getAmount() - totalAllocated(id)));
      requested = roundMoney(Math.min(requested, available));
    }

    if (requested > 0) {
      state.allocations[id] = requested;
      addToOrder(id);
    } else {
      delete state.allocations[id];
      removeFromOrder(id);
    }

    input.value = requested > 0 ? requested.toFixed(2) : '0';
    var row = input.closest('[data-bill]');
    if (row) {
      row.classList.toggle('selected', requested > 0);
      var checkbox = q('[data-bill-check]', row);
      if (checkbox) checkbox.checked = requested > 0;
    }
    syncSelectionAmount();
    updateSummary();
  }

  function buildPaymentForm(type) {
    var form = q('#txn-payment-form');
    if (!form) return;
    var incoming = type === 'received';
    var expected = incoming ? 'customer' : 'supplier';

    state = {
      type: type,
      party: null,
      bills: [],
      allocations: {},
      selectionOrder: [],
      loading: false,
      amountMode: 'selection'
    };

    form.dataset.linked = '1';
    form.className = 'txn-form-card linked-payment-form';
    form.innerHTML =
      '<div class="txn-kind-badge">' + (incoming ? 'PAYMENT-IN' : 'PAYMENT-OUT') + '</div>' +
      '<label>Party<div class="linked-party-picker"><input id="link-party-search" type="search" autocomplete="off" placeholder="Search ' + (incoming ? 'customer' : 'supplier') + ' by name or mobile"><select id="link-party-select" class="party-native-select-hidden" name="party_id"><option value="">Select Party</option>' +
      parties.filter(function (party) { return partyAllowed(party, expected); }).map(function (party) {
        return '<option value="' + Number(party.id) + '">' + esc(party.name) + (party.phone ? ' · ' + esc(party.phone) : '') + '</option>';
      }).join('') + '</select><div id="link-party-results" class="party-search-results hidden"></div></div></label>' +
      '<div class="txn-two"><label>Amount<input id="link-pay-amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" value="0" required></label><label>Date<input name="payment_date" type="date" value="' + today() + '" required></label></div>' +
      '<div class="credit-only-note">Enter an amount first to distribute only that amount across selected bills. Or select bills directly and Amount will become their total.</div>' +
      '<div class="txn-two"><label>Mode<select name="mode"><option value="cash">Cash</option><option value="upi">UPI</option><option value="bank">Bank</option><option value="card">Card</option><option value="cheque">Cheque</option></select></label><label>Cash / Bank Account<select name="account_id"><option value="">Default Account</option>' + accounts.map(function (account) {
        return '<option value="' + Number(account.id) + '">' + esc(account.name) + ' · ' + money(account.balance) + '</option>';
      }).join('') + '</select></label></div>' +
      '<section class="linked-payment-section"><div class="linked-payment-headline"><div><b>Link Payment to Pending Bills</b><small>Amount first = capped allocation. Bills first = automatic total.</small></div><strong id="link-total-due">₹0.00</strong></div><div class="linked-payment-tools"><button type="button" data-link-action="auto">Auto Link Oldest</button><button type="button" data-link-action="clear">Clear Links</button></div><div id="link-bills"><div class="linked-payment-empty">Select a party to view pending invoices.</div></div><div class="linked-payment-summary"><div><small>Linked to Bills</small><strong id="link-allocated">₹0.00</strong></div><div><small>On Account</small><strong id="link-unallocated">₹0.00</strong></div></div></section>' +
      '<label>Note<textarea name="note" rows="3" placeholder="Optional note or reference"></textarea></label>' +
      '<button class="txn-primary" type="submit">Save ' + (incoming ? 'Payment-In' : 'Payment-Out') + '</button>';

    var search = q('#link-party-search');
    var resultBox = q('#link-party-results');
    var select = q('#link-party-select');

    function renderPartyResults() {
      var text = String(search.value || '').trim().toLowerCase();
      var rows = parties.filter(function (party) {
        return partyAllowed(party, expected) && (!text || [party.name, party.phone, party.gstin].join(' ').toLowerCase().indexOf(text) >= 0);
      }).slice(0, 50);
      resultBox.innerHTML = rows.length ? rows.map(function (party) {
        return '<button type="button" data-link-party="' + Number(party.id) + '"><b>' + esc(party.name) + '</b><small>' + esc(party.phone || '') + ' · Outstanding ' + money(party.balance) + '</small></button>';
      }).join('') : '<div class="party-search-empty">No matching party</div>';
      resultBox.classList.remove('hidden');
    }

    search.addEventListener('focus', renderPartyResults);
    search.addEventListener('input', renderPartyResults);
    resultBox.addEventListener('click', function (event) {
      var button = event.target.closest('[data-link-party]');
      if (!button) return;
      var id = Number(button.getAttribute('data-link-party'));
      var party = parties.find(function (row) { return Number(row.id) === id; });
      if (!party) return;
      state.party = id;
      select.value = String(id);
      search.value = party.name + (party.phone ? ' · ' + party.phone : '');
      resultBox.classList.add('hidden');
      loadBills();
    });
    select.addEventListener('change', function () {
      var id = Number(select.value);
      var party = parties.find(function (row) { return Number(row.id) === id; });
      if (!party) return;
      state.party = id;
      search.value = party.name + (party.phone ? ' · ' + party.phone : '');
      loadBills();
    });
  }

  async function upgradePaymentForm() {
    var form = q('#txn-payment-form');
    if (!form || form.dataset.upgraded) return;
    form.dataset.upgraded = '1';
    try {
      if (!parties.length) await loadMaster();
      var title = String(q('#txn-form-title') ? q('#txn-form-title').textContent : '').toLowerCase();
      buildPaymentForm(title.indexOf('out') >= 0 ? 'paid' : 'received');
    } catch (error) {
      toast(error.message, true);
    }
  }

  async function savePayment(form) {
    if (!state || !state.party) {
      toast('Select a party', true);
      return;
    }
    var data = Object.fromEntries(new FormData(form).entries());
    var amount = getAmount();
    if (amount <= 0) {
      toast('Enter a payment amount greater than zero', true);
      return;
    }

    var allocations = state.bills.map(function (bill) {
      return {
        reference_type: state.type === 'received' ? 'sale' : 'purchase',
        reference_id: Number(bill.id),
        amount: roundMoney(state.allocations[bill.id] || 0)
      };
    }).filter(function (allocation) {
      return allocation.amount > 0;
    });

    var allocated = roundMoney(allocations.reduce(function (sum, allocation) {
      return sum + allocation.amount;
    }, 0));
    if (allocated > amount + 0.01) {
      toast('Linked bill amount is greater than payment amount', true);
      return;
    }

    var button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = 'Saving...';
    try {
      var saved = await api('/api/payments/linked', {
        method: 'POST',
        body: {
          payment_type: state.type,
          party_id: state.party,
          payment_date: data.payment_date || today(),
          amount: amount,
          mode: data.mode || 'cash',
          account_id: data.account_id ? Number(data.account_id) : null,
          note: data.note || '',
          allocations: allocations
        }
      });
      toast((state.type === 'received' ? 'Payment-In' : 'Payment-Out') + ' saved and linked to ' + (saved.allocations || []).length + ' bill(s)');
      window.setTimeout(function () {
        window.location.replace('/?page=home&stable=106');
      }, 650);
    } catch (error) {
      button.disabled = false;
      button.textContent = 'Save ' + (state.type === 'received' ? 'Payment-In' : 'Payment-Out');
      toast(error.message, true);
    }
  }

  document.addEventListener('click', function (event) {
    var action = event.target.closest('[data-link-action]');
    if (action) {
      event.preventDefault();
      if (action.getAttribute('data-link-action') === 'auto') autoLinkOldest();
      else clearLinks();
      return;
    }

    var checkbox = event.target.closest('[data-bill-check]');
    if (checkbox && state) {
      selectBill(Number(checkbox.getAttribute('data-bill-check')), checkbox.checked);
    }
  }, true);

  document.addEventListener('input', function (event) {
    if (!state) return;
    if (event.target.id === 'link-pay-amount') {
      state.amountMode = 'manual';
      rebalanceSelectedToEnteredAmount();
      return;
    }
    if (event.target.hasAttribute('data-bill-amount')) {
      editBillAllocation(event.target);
    }
  }, true);

  document.addEventListener('submit', function (event) {
    if (event.target.id === 'txn-payment-form' && event.target.dataset.linked === '1') {
      event.preventDefault();
      event.stopPropagation();
      savePayment(event.target);
    }
  }, true);

  async function boot() {
    try {
      await loadMaster();
    } catch (error) {
      console.error(error);
    }
    upgradePaymentForm();
    new MutationObserver(upgradePaymentForm).observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  boot();
})();
