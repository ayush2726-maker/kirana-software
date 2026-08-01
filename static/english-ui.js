(() => {
  'use strict';

  const exact = new Map([
    ['Billing, Stock aur Khata — Sab Ek Jagah', 'Billing, Inventory & Accounts — All in One'],
    ['Apni dukaan shuru karein', 'Set Up Your Business'],
    ['Dukaan ka naam', 'Business Name'],
    ['Apni Dukaan Ka Account Banayein', 'Create Your Business Account'],
    ['30 din free trial · Alag customer order link · Koi card nahi', '30-day free trial · Separate customer ordering link · No card required'],
    ['Parties & Khata', 'Parties & Accounts'],
    ['PARTY KHATA', 'PARTY ACCOUNT'],
    ['Customer receivable aur supplier payable', 'Customer receivables and supplier payables'],
    ['CSV ya Excel upload karke preview aur import karein', 'Upload a CSV or Excel file to preview and import'],
    ['Vyapar export file choose karein', 'Choose a Vyapar export file'],
    ['Product master pehle upload karein.', 'Upload the product master first.'],
    ['Customers aur suppliers import karein.', 'Import customers and suppliers.'],
    ['Invoice line reports upload karein.', 'Upload invoice line reports.'],
    ['Stock aur outstanding compare karein.', 'Compare stock and outstanding balances.'],
    ['Sale minus purchase total. Exact item-wise cost history se calculation aur accurate hogi.', 'Sales minus purchases. Accuracy improves with item-level cost history.'],
    ['Data ko phone/laptop par safe rakhein', 'Keep your data safely on your phone or laptop'],
    ['Automatic duplicate check optional hai. Direct import remove karne ke liye neeche Sales Import Batches use karein.', 'Automatic duplicate checking is optional. Use Sales Import Batches below to remove an imported batch directly.'],
    ['Galat item-wise SaleReport ko direct remove karein. Sirf selected import batch delete hoga.', 'Remove an incorrect item-wise SaleReport import directly. Only the selected import batch will be deleted.'],
    ['Sales import batches load ho rahe hain…', 'Loading sales import batches...'],
    ['App loading retry hua. Login karein.', 'The app retried loading. Please sign in.'],
    ['App script load nahi hua. Page reload karein.', 'The app script did not load. Reload the page.'],
    ['App startup mein dikkat aayi. Login screen restore ki gayi.', 'The app had a startup error. The login screen was restored.'],
    ['App load nahi hui, login screen restore kar di gayi.', 'The app did not load. The login screen was restored.'],
    ['Pehle item add karein', 'Add an item first'],
    ['Hold karne ke liye item add karein', 'Add an item before holding the bill'],
    ['Returned item add karein', 'Add a returned item first'],
    ['Current bill clear karein?', 'Clear the current bill?'],
    ['Current purchase clear karein?', 'Clear the current purchase?'],
    ['File choose karein', 'Choose a file'],
    ['Abhi koi import nahi hua.', 'No imports yet.'],
    ['Dukaan ka customer link galat hai', 'The customer link is invalid'],
    ['Database wala mobile number', 'Registered mobile number'],
    ['WhatsApp OTP Request Karein', 'Request WhatsApp OTP'],
    ['Request dukaan ko jayegi. Dukaan WhatsApp par OTP bhejegi.', 'The request will go to the business. The business will send the OTP on WhatsApp.'],
    ['Product search karein', 'Search products'],
    ['Cart me Add', 'Add to Cart'],
    ['Order Request', 'Request Order'],
    ['Current Rate', 'Your Rate'],
    ['Dono PIN same nahi hain', 'Both PIN entries must match.'],
    ['Admin account ke liye naya PIN set karein. Ye link sirf ek baar chalega.', 'Set a new PIN for the admin account. This link works only once.'],
    ['Naya PIN / Password', 'New PIN / Password'],
    ['PIN dobara dalein', 'Confirm PIN'],
    ['Naya PIN Save Karein', 'Save New PIN'],
    ['PIN reset ho gaya. Ab owner login page khul raha hai…', 'PIN reset successfully. Opening the owner login page...'],
    ['Reset link invalid ya use ho chuka hai', 'The reset link is invalid or has already been used'],
    ['Naya recovery link banana padega.', 'A new recovery link is required.'],
    ['Owner username nahi mila', 'Owner username was not found'],
    ['Recovery link invalid, expired ya use ho chuka hai', 'The recovery link is invalid, expired, or already used'],
    ['Login expired', 'Your login session has expired'],
    ['Offline entries synced', 'Offline entries have been synced'],
    ['Saved offline; will sync later', 'Saved offline and will sync later'],
    ['Order held', 'Bill placed on hold'],
    ['Purchase held', 'Purchase placed on hold'],
    ['Import completed', 'Import completed'],
    ['Preview ready', 'Preview ready'],
    ['Business settings saved', 'Business settings saved'],
    ['Account added', 'Account added']
  ]);

  const partial = [
    [' aur ', ' and '],
    [' ya ', ' or '],
    [' pehle ', ' first '],
    [' choose karein', ' choose'],
    [' import karein', ' import'],
    [' upload karein', ' upload'],
    [' compare karein', ' compare'],
    [' load ho rahe hain', ' are loading'],
    [' save karein', ' save'],
    [' login karein', ' sign in'],
    [' remove karein', ' remove'],
    [' delete hoga', ' will be deleted']
  ];

  function preserveWhitespace(original, translated) {
    const lead = original.match(/^\s*/)?.[0] || '';
    const trail = original.match(/\s*$/)?.[0] || '';
    return `${lead}${translated}${trail}`;
  }

  function translateValue(value) {
    if (!value || typeof value !== 'string') return value;
    const trimmed = value.trim();
    if (!trimmed) return value;

    if (exact.has(trimmed)) {
      return preserveWhitespace(value, exact.get(trimmed));
    }

    let translated = value;
    for (const [from, to] of partial) {
      if (translated.includes(from)) translated = translated.split(from).join(to);
    }
    return translated;
  }

  function shouldSkipTextNode(node) {
    const parent = node.parentElement;
    if (!parent) return true;
    const tag = parent.tagName;
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'CODE', 'PRE'].includes(tag)) return true;
    if (parent.closest('[data-language-lock="true"]')) return true;
    return false;
  }

  function translateElement(root) {
    if (!root) return;

    if (root.nodeType === Node.TEXT_NODE) {
      if (!shouldSkipTextNode(root)) {
        const next = translateValue(root.nodeValue);
        if (next !== root.nodeValue) root.nodeValue = next;
      }
      return;
    }

    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE && root.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;

    if (root.nodeType === Node.ELEMENT_NODE) {
      for (const attribute of ['placeholder', 'title', 'aria-label']) {
        if (root.hasAttribute?.(attribute)) {
          const oldValue = root.getAttribute(attribute);
          const newValue = translateValue(oldValue);
          if (newValue !== oldValue) root.setAttribute(attribute, newValue);
        }
      }
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        return shouldSkipTextNode(node) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      const next = translateValue(node.nodeValue);
      if (next !== node.nodeValue) node.nodeValue = next;
    });

    const elements = root.querySelectorAll?.('[placeholder],[title],[aria-label]') || [];
    elements.forEach(element => {
      for (const attribute of ['placeholder', 'title', 'aria-label']) {
        if (!element.hasAttribute(attribute)) continue;
        const oldValue = element.getAttribute(attribute);
        const newValue = translateValue(oldValue);
        if (newValue !== oldValue) element.setAttribute(attribute, newValue);
      }
    });
  }

  function start() {
    translateElement(document.body);

    const observer = new MutationObserver(mutations => {
      for (const mutation of mutations) {
        if (mutation.type === 'characterData') {
          translateElement(mutation.target);
          continue;
        }
        mutation.addedNodes.forEach(translateElement);
      }
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });

    window.KiranaEnglishUI = {
      translate: translateValue,
      refresh: () => translateElement(document.body)
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
