from __future__ import annotations

import backend.ai_counter_route_order_ext as desk

VERSION = "190"
_prev_page = desk._desk_page_with_quantity_fix

PATCH_JS = r'''
var _baseProcessSpeech190 = processSpeech;
var _baseRender190 = render;

function norm190(s){
  return String(s||'').toLowerCase()
    .replace(/काबुली|कबली/g,'काबली')
    .replace(/देशी/g,'देसी')
    .replace(/चने|चनों|चैनल|चेनल/g,'चना')
    .replace(/शॉप|सोप|शोफ|सौफ|सूफ|सूप/g,'सौंफ')
    .replace(/souf|sauf|souff|shop/g,'saunf')
    .replace(/[^a-z0-9\u0900-\u097f.]+/g,' ')
    .replace(/\s+/g,' ').trim();
}

function commandItemName190(raw){
  var t=norm190(raw);
  t=t.replace(/(?:\d+(?:\.\d+)?|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|आधा|डे[ढ़ढ़]|पाव)\s*(?:किलो|किलोग्राम|kg|kgs|kilo|ग्राम|gram|gm|लीटर|लिटर|ltr|liter|पीस|pcs|piece|पैकेट|packet|pack)\b/gi,' ');
  t=t.replace(/इसमें\s*से|isme\s*se|में\s*से|me\s*se|कम\s*कर\s*दो|कम\s*करो|कम\s*करना|\bकम\b|घटा\s*दो|घटाओ|decrease|reduce|minus|बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|increase|plus|हटा\s*दो|हटाओ|remove|delete|कर\s*दो|करो|set|quantity|qty|\bऔर\b|\baur\b|\bmore\b/gi,' ');
  return t.replace(/\s+/g,' ').trim();
}

function findCart190(raw){
  var q=commandItemName190(raw), qt=q.split(/\s+/).filter(Boolean);
  if(!qt.length) return S.cart.length ? S.cart[S.cart.length-1] : null;
  var best=null, bestScore=0;
  S.cart.forEach(function(x){
    var n=norm190((x.item.name||'')+' '+(x.item.size||''));
    var nt=n.split(/\s+/).filter(Boolean), hit=0;
    qt.forEach(function(a){
      if(nt.some(function(b){return a===b || (a.length>=3 && b.length>=3 && (a.indexOf(b)===0 || b.indexOf(a)===0));})) hit++;
    });
    var score=hit/Math.max(1,qt.length);
    if(score>bestScore){bestScore=score;best=x;}
  });
  return bestScore>=0.50 ? best : null;
}

function handleArithmetic190(raw){
  if(S.stage!=='items' || !S.cart.length) return false;
  var t=String(raw||'');
  var dec=/कम\s*कर\s*दो|कम\s*करो|कम\s*करना|\bकम\b|घटा\s*दो|घटाओ|decrease|reduce|minus/i.test(t);
  var inc=/बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|और\s*बढ़ा|aur\s*badha|increase|\bplus\b/i.test(t);
  if(!dec && !inc) return false;
  var q=qty(t); if(!q || !(Number(q.qty)>0)) return false;
  var x=findCart190(t); if(!x) return false;
  var old=Number(x.qty||0), amount=Number(q.qty||0);
  var next=dec ? old-amount : old+amount;
  if(next<=0){
    S.cart=S.cart.filter(function(z){return z!==x;});
    render();
    $('choices').innerHTML='';
    say(x.item.name+' ki quantity zero ho gayi, item hata diya. Aur kuch?');
    return true;
  }
  x.qty=next;
  x.displayUnit=q.unit||x.displayUnit||x.item.unit||'';
  render();
  $('choices').innerHTML='';
  say(x.item.name+' ki quantity '+fmt(old)+' se '+displayQty(x)+' kar di. Aur kuch?');
  return true;
}

function newItemPrefill190(raw){
  var t=String(raw||'').trim();
  t=t.replace(/(?:\d+(?:\.\d+)?|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|आधा|डे[ढ़ढ़]|पाव)\s*(?:किलो|किलोग्राम|kg|kgs|kilo|ग्राम|gram|gm|लीटर|लिटर|ltr|liter|पीस|pcs|piece|पैकेट|packet|pack)\b/gi,' ');
  t=t.replace(/नया\s*(?:आइटम|item)|new\s*item|add\s*करो|add\s*कर\s*दो|ऐड\s*करो|ऐड\s*कर\s*दो|वाली|वाला|wali|wala/gi,' ');
  t=t.replace(/कम\s*कर\s*दो|कम\s*करो|घटा\s*दो|घटाओ|बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ/gi,' ');
  t=t.replace(/\s+/g,' ').trim();
  return t || String(raw||'').trim();
}

function unitFromSpeech190(raw){
  var t=String(raw||'').toLowerCase();
  if(/किलो|किलोग्राम|kg|kgs|kilo/.test(t)) return 'kg';
  if(/ग्राम|gram|gm/.test(t)) return 'g';
  if(/लीटर|लिटर|ltr|liter/.test(t)) return 'ltr';
  if(/पैकेट|packet|pack/.test(t)) return 'packet';
  if(/पीस|pcs|piece/.test(t)) return 'pcs';
  return 'pcs';
}

function offerNewItem190(raw){
  if(S.stage!=='items') return;
  var p=String($('prompt').textContent||'').toLowerCase();
  var unresolved = p.indexOf('item clear nahi hai')>=0 || p.indexOf('item nahi mila')>=0 || p.indexOf('ye item nahi mila')>=0;
  if(!unresolved) return;
  if($('choices').querySelector('[data-add-new-190]')) return;
  var name=newItemPrefill190(raw);
  var b=document.createElement('button');
  b.type='button'; b.className='choice-action'; b.setAttribute('data-add-new-190','1');
  b.textContent='➕ '+name+' ko naya item add karein';
  b.onclick=function(){
    $('newName').value=name;
    $('newSize').value='';
    $('newRate').value='0';
    $('newBarcode').value='';
    $('newUnit').value=unitFromSpeech190(raw);
    $('choices').innerHTML='';
    openItemModal();
  };
  $('choices').appendChild(b);
}

function ensureEditModal190(){
  if(document.getElementById('cartEditModal190')) return;
  var wrap=document.createElement('div');
  wrap.id='cartEditModal190';wrap.className='modal hidden';
  wrap.innerHTML='<div class="modal-card"><h2>✏️ Edit Bill Item</h2><div id="editItemName190" style="font-weight:900;margin-bottom:10px"></div><div class="field"><label>Quantity</label><input id="editQty190" inputmode="decimal"></div><div class="field"><label>Unit</label><select id="editUnit190"><option value="kg">kg</option><option value="g">g</option><option value="pcs">pcs</option><option value="packet">packet</option><option value="ltr">ltr</option></select></div><div class="field"><label>Rate ₹</label><input id="editRate190" inputmode="decimal"></div><div class="modal-actions"><button id="editCancel190">Cancel</button><button id="editSave190" class="primary">Save Changes</button></div></div>';
  document.body.appendChild(wrap);
  document.getElementById('editCancel190').onclick=function(){wrap.classList.add('hidden');};
  document.getElementById('editSave190').onclick=function(){
    var i=Number(wrap.getAttribute('data-index'));var x=S.cart[i];if(!x)return;
    var qv=Number(document.getElementById('editQty190').value), rate=Number(document.getElementById('editRate190').value), unit=document.getElementById('editUnit190').value;
    if(!(qv>0))return fail('Quantity 0 se zyada honi chahiye');
    if(rate<0 || !isFinite(rate))return fail('Rate sahi daliye');
    x.qty=(unit==='g')?qv/1000:qv;
    x.displayUnit=(unit==='g')?'kg':unit;
    if(rate>=0){x.item=Object.assign({},x.item,{sale_price:rate});x.rateOverride=rate>0?rate:null;}
    wrap.classList.add('hidden');render();say(x.item.name+' manually update kar diya.');
  };
}

function openEdit190(i){
  ensureEditModal190();var x=S.cart[i];if(!x)return;var m=document.getElementById('cartEditModal190');
  m.setAttribute('data-index',String(i));document.getElementById('editItemName190').textContent=x.item.name+(x.item.size?' • '+x.item.size:'');
  var unit=x.displayUnit||x.item.unit||'pcs';var val=Number(x.qty||0);
  if(unit==='g'){val=val*1000;} else if(unit==='kg' && val<1 && /gram|g/i.test(String(x.item.unit||''))){unit='g';val=val*1000;}
  document.getElementById('editQty190').value=fmt(val);document.getElementById('editUnit190').value=['kg','g','pcs','packet','ltr'].indexOf(unit)>=0?unit:'pcs';
  document.getElementById('editRate190').value=Number(x.item.sale_price||0);m.classList.remove('hidden');
}

render=function(){
  _baseRender190();
  ensureEditModal190();
  var lines=$('cart').querySelectorAll('.line');
  for(var i=0;i<lines.length;i++){
    if(lines[i].querySelector('[data-edit-190]'))continue;
    var b=document.createElement('button');b.type='button';b.className='remove';b.style.color='#0b82c2';b.setAttribute('data-edit-190',String(i));b.textContent='Edit';
    (function(idx,btn){btn.onclick=function(e){e.preventDefault();e.stopPropagation();openEdit190(idx);};})(i,b);
    var right=lines[i].querySelector('.right');if(right)right.appendChild(b);
  }
};

processSpeech = async function(raw){
  raw=String(raw||'').trim();
  if(!raw) return;
  if(handleArithmetic190(raw)) return;
  await _baseProcessSpeech190(raw);
  setTimeout(function(){offerNewItem190(raw);},0);
};
'''


def _page() -> str:
    page = _prev_page()
    marker = "$('scanBarcode').onclick=openScanner;"
    if "handleArithmetic190" not in page and marker in page:
        page = page.replace(marker, PATCH_JS + "\n" + marker, 1)
    return page


desk._desk_page_with_quantity_fix = _page
