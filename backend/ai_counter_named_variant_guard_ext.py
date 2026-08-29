from __future__ import annotations

import backend.ai_counter_route_order_ext as desk
import backend.ai_counter_spoken_number_normalize_ext  # noqa: F401

VERSION = "193"
_prev_page = desk._desk_page_with_quantity_fix

PATCH_JS = r'''
var _baseProcessSpeech193 = processSpeech;

function normVariant193(s){
  return String(s||'').toLowerCase()
    .replace(/वाली|वाला|wali|wala|में|मे|main|mein/gi,' ')
    .replace(/[^a-z0-9\u0900-\u097f.]+/g,' ')
    .replace(/\s+/g,' ').trim();
}

function variantPhrase193(raw){
  var t=(typeof spokenDigits192==='function'?spokenDigits192(raw):String(raw||'')).trim();
  var clean=normVariant193(t);
  var m=clean.match(/^(.*?\S)\s+(\d+(?:\.\d+)?)$/);
  if(!m) return null;
  // A trailing number without a quantity unit is treated as part of the product name.
  if(/(?:kg|kgs|kilo|किलो|ग्राम|gram|gm|pcs|piece|पीस|packet|पैकेट|ltr|liter|लीटर)\s+\d+(?:\.\d+)?$/i.test(clean)) return null;
  return {name:(m[1]+' '+m[2]).trim(),number:m[2],spoken:t};
}

function itemLabel193(x){return normVariant193((x.name||'')+' '+(x.size||''));}

async function handleNamedVariant193(raw){
  if(S.stage!=='items') return false;
  var vp=variantPhrase193(raw); if(!vp) return false;
  clearFail();$('heard').textContent='You: '+vp.spoken;
  try{
    var d=await api('/api/ai-counter/bootstrap');
    var q=normVariant193(vp.name), qt=q.split(' ').filter(Boolean);
    var rows=(d.items||[]).filter(function(it){
      var toks=itemLabel193(it).split(' ').filter(Boolean);
      return qt.every(function(a){return toks.indexOf(a)>=0;});
    });
    rows.sort(function(a,b){
      var ae=itemLabel193(a)===q?1:0,be=itemLabel193(b)===q?1:0;if(ae!==be)return be-ae;
      return (Number(b.sale_price||0)>0?1:0)-(Number(a.sale_price||0)>0?1:0);
    });
    $('choices').innerHTML='';
    if(rows.length===1 || (rows.length>1&&itemLabel193(rows[0])===q&&itemLabel193(rows[1])!==q)){
      addItem(rows[0],{qty:1,unit:rows[0].unit||'pcs'},false);say(rows[0].name+' add kar diya. Aur kuch?');return true;
    }
    if(rows.length>1){choices(rows.slice(0,4),function(r){addItem(r,{qty:1,unit:r.unit||'pcs'},false);say(r.name+' add kar diya. Aur kuch?');});say('Is number ke multiple items mile hain. Sahi item select kijiye.');return true;}
    say('Ye item nahi mila. Naya item add kar sakte hain.');
    var b=document.createElement('button');b.type='button';b.className='choice-action';b.textContent='➕ '+vp.name+' ko naya item add karein';
    b.onclick=function(){$('newName').value=vp.name;$('newSize').value='';$('newRate').value='0';$('newBarcode').value='';$('newUnit').value='pcs';$('choices').innerHTML='';openItemModal();};
    $('choices').appendChild(b);return true;
  }catch(e){fail(e.message);return true;}
}

processSpeech=async function(raw){
  raw=String(raw||'').trim();if(!raw)return;
  var normalized=(typeof spokenDigits192==='function'?spokenDigits192(raw):raw);
  $('heard').textContent='You: '+normalized;
  if(await handleNamedVariant193(normalized))return;
  return _baseProcessSpeech193(normalized);
};
'''

def _page() -> str:
    page=_prev_page();marker="$('scanBarcode').onclick=openScanner;"
    if "handleNamedVariant193" not in page and marker in page:
        page=page.replace(marker,PATCH_JS+"\n"+marker,1)
    return page

desk._desk_page_with_quantity_fix=_page
