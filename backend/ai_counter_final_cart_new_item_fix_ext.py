from __future__ import annotations

import backend.ai_counter_route_order_ext as desk

VERSION = "191"
_prev_page = desk._desk_page_with_quantity_fix

PATCH_JS = r'''
var _baseProcessSpeech191 = processSpeech;
var _baseRender191 = render;

function norm191(s){
  return String(s||'').toLowerCase()
    .replace(/काबुली|कबली/g,'काबली').replace(/देशी/g,'देसी').replace(/चने|चनों|चैनल|चेनल/g,'चना')
    .replace(/शॉप|सोप|शोफ|सौफ|सूफ|सूप/g,'सौंफ').replace(/souf|sauf|souff|shop/g,'saunf')
    .replace(/[^a-z0-9\u0900-\u097f.]+/g,' ').replace(/\s+/g,' ').trim();
}

function commandItemName191(raw){
  var t=norm191(raw);
  t=t.replace(/(?:\d+(?:\.\d+)?|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|आधा|डे[ढ़ढ़]|पाव)\s*(?:किलो|किलोग्राम|kg|kgs|kilo|ग्राम|gram|gm|लीटर|लिटर|ltr|liter|पीस|pcs|piece|पैकेट|packet|pack)\b/gi,' ');
  t=t.replace(/इसमें\s*से|isme\s*se|में\s*से|me\s*se|कम\s*कर\s*दो|कम\s*करो|कम\s*करना|\bकम\b|घटा\s*दो|घटाओ|decrease|reduce|minus|बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|increase|plus|हटा\s*दो|हटाओ|remove|delete|कर\s*दो|करो|set|quantity|qty|\bऔर\b|\baur\b|\bmore\b/gi,' ');
  return t.replace(/\s+/g,' ').trim();
}
function findCart191(raw){var q=commandItemName191(raw),qt=q.split(/\s+/).filter(Boolean),best=null,bs=0;if(!qt.length)return S.cart.length?S.cart[S.cart.length-1]:null;S.cart.forEach(function(x){var nt=norm191((x.item.name||'')+' '+(x.item.size||'')).split(/\s+/).filter(Boolean),h=0;qt.forEach(function(a){if(nt.some(function(b){return a===b||(a.length>=3&&b.length>=3&&(a.indexOf(b)===0||b.indexOf(a)===0));}))h++;});var s=h/Math.max(1,qt.length);if(s>bs){bs=s;best=x;}});return bs>=.5?best:null;}
function handleArithmetic191(raw){if(S.stage!=='items'||!S.cart.length)return false;var t=String(raw||''),dec=/कम\s*कर\s*दो|कम\s*करो|कम\s*करना|\bकम\b|घटा\s*दो|घटाओ|decrease|reduce|minus/i.test(t),inc=/बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|और\s*बढ़ा|aur\s*badha|increase|\bplus\b/i.test(t);if(!dec&&!inc)return false;var q=qty(t);if(!q||!(Number(q.qty)>0))return false;var x=findCart191(t);if(!x)return false;var old=Number(x.qty||0),next=dec?old-Number(q.qty):old+Number(q.qty);if(next<=0){S.cart=S.cart.filter(function(z){return z!==x;});render();$('choices').innerHTML='';say(x.item.name+' ki quantity zero ho gayi, item hata diya. Aur kuch?');return true;}x.qty=next;x.displayUnit=q.unit||x.displayUnit||x.item.unit||'';render();$('choices').innerHTML='';say(x.item.name+' ki quantity '+fmt(old)+' se '+displayQty(x)+' kar di. Aur kuch?');return true;}

// Product numbers such as Rajshree 10/20, Vimal 20 are part of the item name.
// Only strip a number when it is clearly followed by a quantity unit.
function newItemPrefill191(raw){
  var t=String(raw||'').trim();
  t=t.replace(/(?:\d+(?:\.\d+)?|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|आधा|डे[ढ़ढ़]|पाव)\s*(?:किलो|किलोग्राम|kg|kgs|kilo|ग्राम|gram|gm|लीटर|लिटर|ltr|liter|पीस|pcs|piece|पैकेट|packet|pack)\b/gi,' ');
  t=t.replace(/नया\s*(?:आइटम|item)|new\s*item|add\s*करो|add\s*कर\s*दो|ऐड\s*करो|ऐड\s*कर\s*दो|वाली|वाला|wali|wala/gi,' ');
  t=t.replace(/कम\s*कर\s*दो|कम\s*करो|घटा\s*दो|घटाओ|बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ/gi,' ');
  return t.replace(/\s+/g,' ').trim()||String(raw||'').trim();
}
function unitFromSpeech191(raw){var t=String(raw||'').toLowerCase();if(/किलो|किलोग्राम|kg|kgs|kilo/.test(t))return'kg';if(/ग्राम|gram|gm/.test(t))return'g';if(/लीटर|लिटर|ltr|liter/.test(t))return'ltr';if(/पैकेट|packet|pack/.test(t))return'packet';if(/पीस|pcs|piece/.test(t))return'pcs';return'pcs';}
function offerNewItem191(raw){if(S.stage!=='items')return;var p=String($('prompt').textContent||'').toLowerCase(),un=p.indexOf('item clear nahi hai')>=0||p.indexOf('item nahi mila')>=0||p.indexOf('ye item nahi mila')>=0;if(!un||$('choices').querySelector('[data-add-new-191]'))return;var name=newItemPrefill191(raw),b=document.createElement('button');b.type='button';b.className='choice-action';b.setAttribute('data-add-new-191','1');b.textContent='➕ '+name+' ko naya item add karein';b.onclick=function(){$('newName').value=name;$('newSize').value='';$('newRate').value='0';$('newBarcode').value='';$('newUnit').value=unitFromSpeech191(raw);$('choices').innerHTML='';openItemModal();};$('choices').appendChild(b);}
function ensureEditModal191(){if(document.getElementById('cartEditModal191'))return;var w=document.createElement('div');w.id='cartEditModal191';w.className='modal hidden';w.innerHTML='<div class="modal-card"><h2>✏️ Edit Bill Item</h2><div id="editItemName191" style="font-weight:900;margin-bottom:10px"></div><div class="field"><label>Quantity</label><input id="editQty191" inputmode="decimal"></div><div class="field"><label>Unit</label><select id="editUnit191"><option value="kg">kg</option><option value="g">g</option><option value="pcs">pcs</option><option value="packet">packet</option><option value="ltr">ltr</option></select></div><div class="field"><label>Rate ₹</label><input id="editRate191" inputmode="decimal"></div><div class="modal-actions"><button id="editCancel191">Cancel</button><button id="editSave191" class="primary">Save Changes</button></div></div>';document.body.appendChild(w);$('editCancel191').onclick=function(){w.classList.add('hidden');};$('editSave191').onclick=function(){var i=Number(w.getAttribute('data-index')),x=S.cart[i];if(!x)return;var qv=Number($('editQty191').value),rate=Number($('editRate191').value),unit=$('editUnit191').value;if(!(qv>0))return fail('Quantity 0 se zyada honi chahiye');if(rate<0||!isFinite(rate))return fail('Rate sahi daliye');x.qty=unit==='g'?qv/1000:qv;x.displayUnit=unit==='g'?'kg':unit;x.item=Object.assign({},x.item,{sale_price:rate});x.rateOverride=rate>0?rate:null;w.classList.add('hidden');render();say(x.item.name+' manually update kar diya.');};}
function openEdit191(i){ensureEditModal191();var x=S.cart[i];if(!x)return;var m=$('cartEditModal191');m.setAttribute('data-index',String(i));$('editItemName191').textContent=x.item.name+(x.item.size?' • '+x.item.size:'');var u=x.displayUnit||x.item.unit||'pcs',v=Number(x.qty||0);if(u==='g')v*=1000;$('editQty191').value=fmt(v);$('editUnit191').value=['kg','g','pcs','packet','ltr'].indexOf(u)>=0?u:'pcs';$('editRate191').value=Number(x.item.sale_price||0);m.classList.remove('hidden');}
render=function(){_baseRender191();ensureEditModal191();var ls=$('cart').querySelectorAll('.line');for(var i=0;i<ls.length;i++){if(ls[i].querySelector('[data-edit-191]'))continue;var b=document.createElement('button');b.type='button';b.className='remove';b.style.color='#0b82c2';b.setAttribute('data-edit-191',String(i));b.textContent='Edit';(function(j,z){z.onclick=function(e){e.preventDefault();e.stopPropagation();openEdit191(j);};})(i,b);var r=ls[i].querySelector('.right');if(r)r.appendChild(b);}}
processSpeech=async function(raw){raw=String(raw||'').trim();if(!raw)return;if(handleArithmetic191(raw))return;await _baseProcessSpeech191(raw);setTimeout(function(){offerNewItem191(raw);},0);};
'''

def _page() -> str:
    page=_prev_page();marker="$('scanBarcode').onclick=openScanner;"
    if "handleArithmetic191" not in page and marker in page: page=page.replace(marker,PATCH_JS+"\n"+marker,1)
    return page

desk._desk_page_with_quantity_fix=_page
