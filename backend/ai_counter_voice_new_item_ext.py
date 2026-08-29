from __future__ import annotations

import backend.ai_counter_route_order_ext as desk

VERSION = "186"
_prev_page = desk._desk_page_with_quantity_fix

VOICE_CART_AND_NEW_ITEM_JS = r'''
function voiceNorm(s){return String(s||'').toLowerCase().replace(/काबुली|कबली/g,'काबली').replace(/देशी/g,'देसी').replace(/चने|चनों/g,'चना').replace(/चैनल|चेनल/g,'चना').replace(/शॉप|सोप|शोफ|सौफ/g,'सौंफ').replace(/\s+/g,' ').trim()}
function voiceCartName(s){return voiceNorm(s).replace(/ढाई\s*सौ|dhai\s*sau|डे[ढ़ढ़]|dedh|आधा|aadha|half|पाव|paav|pav|quarter|\d+(?:\.\d+)?|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|किलो|किलोग्राम|kg|kilo|ग्राम|gram|gm|लीटर|लिटर|ltr|liter|पीस|pcs|piece|पैकेट|packet|pack/gi,' ').replace(/इसमें\s*से|isme\s*se|में\s*से|me\s*se|हटा\s*दो|हटाओ|निकाल\s*दो|निकालो|remove|delete|बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|increase|plus|कम\s*कर\s*दो|कम\s*करो|कम\s*करना|घटा\s*दो|घटाओ|decrease|reduce|minus|कर\s*दो|करो|set|quantity|qty/gi,' ').replace(/\s+/g,' ').trim()}
function voiceCartMatch(name){var qn=voiceCartName(name),qt=qn.split(' ').filter(Boolean);if(!qt.length)return S.cart.length?S.cart[S.cart.length-1]:null;var best=null,bs=0;S.cart.forEach(function(x){var n=voiceNorm((x.item.name||'')+' '+(x.item.size||'')),nt=n.split(' ').filter(Boolean),hit=0;qt.forEach(function(a){if(nt.some(function(b){return a===b||(a.length>=3&&b.length>=3&&(a.indexOf(b)===0||b.indexOf(a)===0))}))hit++});var sc=hit/Math.max(1,qt.length);if(sc>bs){bs=sc;best=x}});return bs>=.5?best:null}
function cartCommand(raw){if(S.stage!=='items'||!S.cart.length)return false;var t=String(raw||'');var remove=/हटा\s*दो|हटाओ|निकाल\s*दो|निकालो|remove|delete/i.test(t);var dec=/कम\s*कर\s*दो|कम\s*करो|कम\s*करना|घटा\s*दो|घटाओ|decrease|reduce|minus/i.test(t);var inc=/बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|increase|plus/i.test(t);var set=/कर\s*दो|करो|set|quantity|qty/i.test(t)&&!inc&&!dec;if(!(remove||inc||dec||set))return false;var x=voiceCartMatch(t);if(!x)return false;if(remove){S.cart=S.cart.filter(function(z){return z!==x});render();say(x.item.name+' hata diya. Aur kuch?');return true}var q=qty(t);if(!q)return false;var old=Number(x.qty||0),amount=Number(q.qty||0),next=old;if(dec)next=old-amount;else if(inc)next=old+amount;else next=amount;if(next<=0){S.cart=S.cart.filter(function(z){return z!==x});render();say(x.item.name+' ki quantity zero ho gayi, item hata diya. Aur kuch?');return true}x.qty=next;x.displayUnit=q.unit||x.displayUnit||x.item.unit||'';render();var verb=dec?'kam kar di':inc?'badha di':'set kar di';say(x.item.name+' ki quantity '+displayQty(x)+' '+verb+'. Aur kuch?');return true}
function voiceNewItemName(raw){var t=String(raw||'').trim();t=t.replace(/नया\s*(?:आइटम|item)|new\s*item|नयी\s*(?:आइटम|item)|नया\s*सामान|item\s*(?:बना|बनाओ|बना\s*दो)|आइटम\s*(?:बना|बनाओ|बना\s*दो)/gi,' ');t=t.replace(/add\s*(?:कर\s*दो|करो)?|ऐड\s*(?:कर\s*दो|करो)?|जोड़\s*(?:दो|दो)|जोड़\s*(?:दो|दो)/gi,' ');t=t.replace(/(?:rate|रेट|भाव|price|कीमत)\s*(?:₹|rs\.?|रुपये?|रुपया)?\s*\d+(?:\.\d+)?/gi,' ');t=t.replace(/वाली|वाला|wali|wala/gi,' ');return t.replace(/\s+/g,' ').trim()}
function voiceRate(raw){var t=String(raw||'').toLowerCase();var m=t.match(/(?:rate|रेट|भाव|price|कीमत)\s*(?:₹|rs\.?|रुपये?|रुपया)?\s*(\d+(?:\.\d+)?)/i);if(!m)m=t.match(/(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)\s*(?:रुपये?|रुपया|rupees?|rs\.?)\b/i);if(!m&&S.pendingNewItem)m=t.match(/^\s*(\d+(?:\.\d+)?)\s*$/);return m?Number(m[1]):null}
function voiceUnit(raw){var t=String(raw||'').toLowerCase();if(/पैकेट|packet|pack/.test(t))return'packet';if(/पीस|pcs|piece/.test(t))return'pcs';if(/किलो|kg|kilo/.test(t))return'kg';if(/ग्राम|gram|gm/.test(t))return'g';if(/लीटर|लिटर|ltr|liter|litre/.test(t))return'ltr';return'pcs'}
async function createPendingVoiceItem(){var p=S.pendingNewItem;if(!p||!(Number(p.rate)>0))return false;try{var d=await api('/api/ai-counter/items',{method:'POST',body:JSON.stringify({name:p.name,size:p.size||'',unit:p.unit||'pcs',sale_price:Number(p.rate),barcode:''})});addItem(d.item,{qty:Number(p.qty||1),unit:d.item.unit||p.unit||'pcs'},false);S.pendingNewItem=null;say(d.item.name+(d.created?' naya item bana kar':'')+' bill me add kar diya. Rate '+money(d.item.sale_price)+'. Aur kuch?');return true}catch(e){fail(e.message);say('Naya item save nahi hua. Screen par error check kijiye.');return true}}
async function handlePendingVoiceItem(raw){if(!S.pendingNewItem)return false;if(/cancel|रद्द|छोड़\s*दो|chhod\s*do|नहीं|nahi/i.test(String(raw||''))){var old=S.pendingNewItem.name;S.pendingNewItem=null;say(old+' naya item cancel kar diya. Aur kuch?');return true}var r=voiceRate(raw);if(!(r>0)){say(S.pendingNewItem.name+' ka sale rate rupaye me boliye. Jaise: rate 10 rupaye.');return true}S.pendingNewItem.rate=r;return await createPendingVoiceItem()}
async function handleVoiceNewItem(raw){if(S.stage!=='items')return false;var t=String(raw||'');if(!/नया\s*(?:आइटम|item)|new\s*item|नयी\s*(?:आइटम|item)|नया\s*सामान|item\s*(?:बना|बनाओ)|आइटम\s*(?:बना|बनाओ)/i.test(t))return false;var name=voiceNewItemName(t);if(!name){say('Naye item ka naam boliye. Jaise: naya item Vimal 10 add karo.');return true}var explicitUnit=/किलो|kg|kilo|ग्राम|gram|gm|लीटर|लिटर|ltr|liter|पीस|pcs|piece|पैकेट|packet|pack/i.test(t);var q=explicitUnit?qty(t):null;var r=voiceRate(t);S.pendingNewItem={name:name,size:'',unit:voiceUnit(t),qty:q?Number(q.qty||1):1,rate:r};if(r>0)return await createPendingVoiceItem();say(name+' naya item banana hai. Iska sale rate boliye. Jaise: rate 10 rupaye.');return true}
'''


def _page() -> str:
    page = _prev_page()
    # Replace the cart-command block last, after every earlier AI desk patch.
    start = page.find("function cartCommand(raw){")
    end = page.find("\nfunction splitItemQty", start)
    helper_start = VOICE_CART_AND_NEW_ITEM_JS.find("function cartCommand(raw){")
    helper_end = VOICE_CART_AND_NEW_ITEM_JS.find("function voiceNewItemName", helper_start)
    if start >= 0 and end > start and helper_start >= 0 and helper_end > helper_start:
        replacement = VOICE_CART_AND_NEW_ITEM_JS[:helper_end].rstrip()
        page = page[:page.rfind("function speechFix", 0, start)] + replacement + "\n" + page[end + 1:]
    else:
        marker = "async function processSpeech(raw){"
        if marker in page and "function handleVoiceNewItem(raw)" not in page:
            page = page.replace(marker, VOICE_CART_AND_NEW_ITEM_JS + "\n" + marker, 1)

    hook = "async function processSpeech(raw){clearFail();raw=String(raw||'').trim();if(!raw)return;$('heard').textContent='You: '+raw;if(cartCommand(raw))return;"
    hooked = "async function processSpeech(raw){clearFail();raw=String(raw||'').trim();if(!raw)return;$('heard').textContent='You: '+raw;if(S.pendingNewItem){if(await handlePendingVoiceItem(raw))return;}if(await handleVoiceNewItem(raw))return;if(cartCommand(raw))return;"
    if hook in page:
        page = page.replace(hook, hooked, 1)
    return page


desk._desk_page_with_quantity_fix = _page
