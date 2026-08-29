from __future__ import annotations

import backend.ai_counter_route_order_ext as desk
import backend.ai_counter_spoken_number_normalize_ext  # noqa: F401

VERSION = "198"
_prev_page = desk._desk_page_with_quantity_fix

PATCH_JS = r'''
var _baseProcessSpeech193 = processSpeech;

function normVariant193(s){
  return String(s||'').toLowerCase()
    .replace(/वाली|वाला|wali|wala|में|मे|main|mein/gi,' ')
    .replace(/[^a-z0-9\u0900-\u097f.]+/g,' ')
    .replace(/\s+/g,' ').trim();
}

function itemLabel193(x){return normVariant193((x.name||'')+' '+(x.size||''));}

function variantPhrase193(raw){
  var t=(typeof spokenDigits192==='function'?spokenDigits192(raw):String(raw||'')).trim();
  var clean=normVariant193(t);
  var m=clean.match(/^(.*?\S)\s+(\d+(?:\.\d+)?)$/);
  if(!m) return null;
  if(/(?:kg|kgs|kilo|किलो|ग्राम|gram|gm|pcs|piece|पीस|packet|पैकेट|ltr|liter|लीटर)\s+\d+(?:\.\d+)?$/i.test(clean)) return null;
  return {name:(m[1]+' '+m[2]).trim(),number:m[2],spoken:t};
}

async function handleNamedVariant193(raw){
  if(S.stage!=='items') return false;
  var t=(typeof spokenDigits192==='function'?spokenDigits192(raw):String(raw||'')).trim();
  var clean=normVariant193(t);
  var parts=clean.match(/^(.*?\S)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$/);
  var requestedQty=null, query='';
  if(parts){
    // Example: "Vimal 10 4" => item Vimal, size/variant 10, quantity 4.
    // A bare final number is quantity; rate is only parsed by explicit rate words in spoken-rate flow.
    query=(parts[1]+' '+parts[2]).trim();
    requestedQty=Number(parts[3]);
  }else{
    var vp=variantPhrase193(t); if(!vp) return false;
    query=vp.name;
  }
  clearFail();$('heard').textContent='You: '+t;
  try{
    var d=await api('/api/ai-counter/bootstrap');
    var q=normVariant193(query), qt=q.split(' ').filter(Boolean);
    var rows=(d.items||[]).filter(function(it){
      var toks=itemLabel193(it).split(' ').filter(Boolean);
      return qt.every(function(a){return toks.indexOf(a)>=0;});
    });
    rows.sort(function(a,b){
      var ae=itemLabel193(a)===q?1:0,be=itemLabel193(b)===q?1:0;if(ae!==be)return be-ae;
      return (Number(b.sale_price||0)>0?1:0)-(Number(a.sale_price||0)>0?1:0);
    });
    $('choices').innerHTML='';
    var qty=(requestedQty!=null&&isFinite(requestedQty)&&requestedQty>0)?requestedQty:1;
    function addVariant(r){addItem(r,{qty:qty,unit:r.unit||'pcs'},false);say(r.name+' '+qty+' quantity add kar diya. Aur kuch?');}
    if(rows.length===1 || (rows.length>1&&itemLabel193(rows[0])===q&&itemLabel193(rows[1])!==q)){
      addVariant(rows[0]);return true;
    }
    if(rows.length>1){choices(rows.slice(0,4),function(r){addVariant(r);});say('Is number ke multiple items mile hain. Sahi item select kijiye.');return true;}
    say('Ye item nahi mila. Naya item add kar sakte hain.');
    var b=document.createElement('button');b.type='button';b.className='choice-action';b.textContent='➕ '+query+' ko naya item add karein';
    b.onclick=function(){$('newName').value=query;$('newSize').value='';$('newRate').value='0';$('newBarcode').value='';$('newUnit').value='pcs';$('choices').innerHTML='';openItemModal();};
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
