from __future__ import annotations

import backend.ai_counter_route_order_ext as desk

VERSION = "189"
_prev_page = desk._desk_page_with_quantity_fix

PATCH_JS = r'''
var _baseProcessSpeech189 = processSpeech;

function norm189(s){
  return String(s||'').toLowerCase()
    .replace(/काबुली|कबली/g,'काबली')
    .replace(/देशी/g,'देसी')
    .replace(/चने|चनों|चैनल|चेनल/g,'चना')
    .replace(/[^a-z0-9\u0900-\u097f.]+/g,' ')
    .replace(/\s+/g,' ').trim();
}

function commandItemName189(raw){
  var t=norm189(raw);
  t=t.replace(/(?:\d+(?:\.\d+)?|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|आधा|डे[ढ़ढ़]|पाव)\s*(?:किलो|किलोग्राम|kg|kgs|kilo|ग्राम|gram|gm|लीटर|लिटर|ltr|liter|पीस|pcs|piece|पैकेट|packet|pack)\b/gi,' ');
  t=t.replace(/इसमें\s*से|isme\s*se|में\s*से|me\s*se|कम\s*कर\s*दो|कम\s*करो|कम\s*करना|कम|घटा\s*दो|घटाओ|decrease|reduce|minus|बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|increase|plus|हटा\s*दो|हटाओ|remove|delete|कर\s*दो|करो|set|quantity|qty/gi,' ');
  return t.replace(/\s+/g,' ').trim();
}

function findCart189(raw){
  var q=commandItemName189(raw), qt=q.split(/\s+/).filter(Boolean);
  if(!qt.length) return S.cart.length ? S.cart[S.cart.length-1] : null;
  var best=null, bestScore=0;
  S.cart.forEach(function(x){
    var n=norm189((x.item.name||'')+' '+(x.item.size||''));
    var nt=n.split(/\s+/).filter(Boolean), hit=0;
    qt.forEach(function(a){
      if(nt.some(function(b){return a===b || (a.length>=3 && b.length>=3 && (a.indexOf(b)===0 || b.indexOf(a)===0));})) hit++;
    });
    var score=hit/Math.max(1,qt.length);
    if(score>bestScore){bestScore=score;best=x;}
  });
  return bestScore>=0.60 ? best : null;
}

function handleArithmetic189(raw){
  if(S.stage!=='items' || !S.cart.length) return false;
  var t=String(raw||'');
  var dec=/कम\s*कर\s*दो|कम\s*करो|कम\s*करना|\bकम\b|घटा\s*दो|घटाओ|decrease|reduce|minus/i.test(t);
  var inc=/बढ़ा\s*दो|बढा\s*दो|बढ़ाओ|बढाओ|increase|\bplus\b/i.test(t);
  if(!dec && !inc) return false;
  var q=qty(t); if(!q || !(Number(q.qty)>0)) return false;
  var x=findCart189(t); if(!x) return false;
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
  say(x.item.name+' '+old+' se '+displayQty(x)+' '+(dec?'kam kar diya':'badha diya')+'. Aur kuch?');
  return true;
}

function newItemPrefill189(raw){
  var t=String(raw||'').trim();
  t=t.replace(/(?:\d+(?:\.\d+)?|एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|आधा|डे[ढ़ढ़]|पाव)\s*(?:किलो|किलोग्राम|kg|kgs|kilo|ग्राम|gram|gm|लीटर|लिटर|ltr|liter|पीस|pcs|piece|पैकेट|packet|pack)\b/gi,' ');
  t=t.replace(/नया\s*(?:आइटम|item)|new\s*item|add\s*करो|add\s*कर\s*दो|ऐड\s*करो|ऐड\s*कर\s*दो|वाली|वाला|wali|wala/gi,' ');
  t=t.replace(/\s+/g,' ').trim();
  return t || String(raw||'').trim();
}

function unitFromSpeech189(raw){
  var t=String(raw||'').toLowerCase();
  if(/किलो|किलोग्राम|kg|kgs|kilo/.test(t)) return 'kg';
  if(/ग्राम|gram|gm/.test(t)) return 'g';
  if(/लीटर|लिटर|ltr|liter/.test(t)) return 'ltr';
  if(/पैकेट|packet|pack/.test(t)) return 'packet';
  if(/पीस|pcs|piece/.test(t)) return 'pcs';
  return 'pcs';
}

function offerNewItem189(raw){
  if(S.stage!=='items') return;
  var p=String($('prompt').textContent||'').toLowerCase();
  var unresolved = p.indexOf('item clear nahi hai')>=0 || p.indexOf('item nahi mila')>=0 || p.indexOf('ye item nahi mila')>=0;
  if(!unresolved) return;
  if($('choices').querySelector('[data-add-new-189]')) return;
  var name=newItemPrefill189(raw);
  var b=document.createElement('button');
  b.type='button'; b.className='choice-action'; b.setAttribute('data-add-new-189','1');
  b.textContent='➕ '+name+' ko naya item add karein';
  b.onclick=function(){
    $('newName').value=name;
    $('newSize').value='';
    $('newRate').value='0';
    $('newBarcode').value='';
    $('newUnit').value=unitFromSpeech189(raw);
    $('choices').innerHTML='';
    openItemModal();
  };
  $('choices').appendChild(b);
}

processSpeech = async function(raw){
  raw=String(raw||'').trim();
  if(!raw) return;
  if(handleArithmetic189(raw)) return;
  await _baseProcessSpeech189(raw);
  setTimeout(function(){offerNewItem189(raw);},0);
};
'''


def _page() -> str:
    page = _prev_page()
    marker = "$('scanBarcode').onclick=openScanner;"
    if "handleArithmetic189" not in page and marker in page:
        page = page.replace(marker, PATCH_JS + "\n" + marker, 1)
    return page


desk._desk_page_with_quantity_fix = _page
