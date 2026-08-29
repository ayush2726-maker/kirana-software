from __future__ import annotations

import backend.ai_counter_route_order_ext as desk

VERSION = "184"
_prev_page = desk._desk_page_with_quantity_fix

NEW_CART_JS = r'''function normCmd(s){return String(s||'').toLowerCase().replace(/काबुली/g,'काबली').replace(/कबली/g,'काबली').replace(/देशी/g,'देसी').replace(/चैनल/g,'चना').replace(/शॉप|सोप|शोफ|सौफ/g,'सौंफ').replace(/[^a-z0-9\u0900-\u097f.]+/g,' ').trim()}
function cartScore(q,x){q=normCmd(q);var n=normCmd((x.item.name||'')+' '+(x.item.size||''));var qw=q.split(/\s+/).filter(Boolean),nw=n.split(/\s+/).filter(Boolean),hit=0;qw.forEach(function(a){if(nw.some(function(b){return a===b||(a.length>=3&&b.length>=3&&(a.indexOf(b)===0||b.indexOf(a)===0))}))hit++});return hit/Math.max(1,qw.length)}
function findCartItem(name){var best=null,bs=0;S.cart.forEach(function(x){var s=cartScore(name,x);if(s>bs){bs=s;best=x}});return bs>=.55?best:null}
function cleanCartCommandName(t){return String(t||'').replace(new RegExp(QNUM,'ig'),' ').replace(new RegExp(QUNIT,'ig'),' ').replace(/इसमें\s*से|isme\s*se|हटा\s*दो|हटाओ|निकाल\s*दो|निकालो|remove|delete|बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|और\s*बढ़ा\s*दो|कम\s*कर\s*दो|घटा\s*दो|घटाओ|कम\s*करो|कर\s*दो|करो|set|quantity|qty/gi,' ').replace(/\s+/g,' ').trim()}
function applyCartQty(x,q,mode){var old=Number(x.qty||0),next;if(mode==='add')next=old+Number(q.qty||0);else if(mode==='subtract')next=Math.max(0,old-Number(q.qty||0));else next=Number(q.qty||0);if(next<=0){S.cart=S.cart.filter(function(z){return Number(z.item.id)!==Number(x.item.id)});render();clearChoices(false);say(x.item.name+' ki quantity zero ho gayi, item hata diya. Aur kuch?');return true}x.qty=next;if(mode==='set'){x.displayUnit=q.unit||x.item.unit||'';x.spokenValue=q.spokenValue;x.spokenUnit=q.unit||''}else if(q.unit==='g'&&x.spokenUnit==='g'&&x.spokenValue!=null){x.spokenValue=Math.max(0,Number(x.spokenValue)+(mode==='add'?1:-1)*Number(q.spokenValue||0));x.spokenUnit='g';x.displayUnit='g'}else{x.spokenValue=next;x.spokenUnit=(q.unit==='g'?'kg':(q.unit||x.spokenUnit||x.displayUnit||x.item.unit||''));x.displayUnit=x.spokenUnit}render();clearChoices(false);var verb=mode==='add'?'badha di':mode==='subtract'?'kam kar di':'set kar di';say(x.item.name+' ki quantity '+displayQty(x)+' '+verb+'. Aur kuch?');return true}
function handleCartCommand(raw){if(S.stage!=='items'||!S.cart.length)return false;var t=String(raw||'').trim();var remove=/हटा\s*दो|हटाओ|निकाल\s*दो|निकालो|remove|delete/i.test(t);var add=/बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|और\s*बढ़ा/i.test(t);var subtract=/कम\s*कर\s*दो|कम\s*करो|घटा\s*दो|घटाओ|decrease|reduce/i.test(t);var set=/कर\s*दो|करो|set|quantity|qty/i.test(t)&&!add&&!subtract;if(remove){var rn=cleanCartCommandName(t),rx=findCartItem(rn);if(rx){S.cart=S.cart.filter(function(z){return Number(z.item.id)!==Number(rx.item.id)});render();clearChoices(false);say(rx.item.name+' hata diya. Aur kuch?');return true}return false}if(add||subtract||set){var q=parseQtySpeech(t);if(!q)return false;var name=cleanCartCommandName(t),x=findCartItem(name);if(!x)return false;return applyCartQty(x,q,add?'add':subtract?'subtract':'set')}return false}'''


def _page() -> str:
    page = _prev_page()
    start = page.find("function normCmd(s){")
    end = page.find("\nasync function handle(raw){", start)
    if start >= 0 and end > start:
        page = page[:start] + NEW_CART_JS + page[end:]
    return page


desk._desk_page_with_quantity_fix = _page
