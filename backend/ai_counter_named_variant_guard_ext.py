from __future__ import annotations

import backend.ai_counter_route_order_ext as desk

VERSION = "192"
_prev_page = desk._desk_page_with_quantity_fix

PATCH_JS = r'''
var _baseProcessSpeech192 = processSpeech;

function normVariant192(s){
  return String(s||'').toLowerCase()
    .replace(/वाली|वाला|wali|wala/gi,' ')
    .replace(/[^a-z0-9\u0900-\u097f.]+/g,' ')
    .replace(/\s+/g,' ').trim();
}

function variantPhrase192(raw){
  var t=String(raw||'').trim();
  if(!/(?:^|\s)\d+(?:\.\d+)?\s*(?:वाली|वाला|wali|wala)(?:\s|$)/i.test(t)) return null;
  var clean=normVariant192(t);
  var m=clean.match(/^(.*?\S)\s+(\d+(?:\.\d+)?)$/);
  if(!m) return null;
  return {name:(m[1]+' '+m[2]).trim(),number:m[2]};
}

function itemLabel192(x){return normVariant192((x.name||'')+' '+(x.size||''));}

async function handleNamedVariant192(raw){
  if(S.stage!=='items') return false;
  var vp=variantPhrase192(raw); if(!vp) return false;
  clearFail();$('heard').textContent='You: '+String(raw||'');
  try{
    var d=await api('/api/ai-counter/bootstrap');
    var q=normVariant192(vp.name), qt=q.split(' ').filter(Boolean);
    var rows=(d.items||[]).filter(function(it){
      var label=itemLabel192(it), toks=label.split(' ').filter(Boolean);
      return qt.every(function(a){return toks.indexOf(a)>=0;});
    });
    rows.sort(function(a,b){
      var ae=itemLabel192(a)===q?1:0, be=itemLabel192(b)===q?1:0;
      if(ae!==be) return be-ae;
      var ap=Number(a.sale_price||0)>0?1:0, bp=Number(b.sale_price||0)>0?1:0;
      return bp-ap;
    });
    $('choices').innerHTML='';
    if(rows.length===1 || (rows.length>1 && itemLabel192(rows[0])===q && itemLabel192(rows[1])!==q)){
      addItem(rows[0],{qty:1,unit:rows[0].unit||'pcs'},false);
      say(rows[0].name+' add kar diya. Aur kuch?');
      return true;
    }
    if(rows.length>1){
      choices(rows.slice(0,4),function(r){addItem(r,{qty:1,unit:r.unit||'pcs'},false);say(r.name+' add kar diya. Aur kuch?');});
      say('Is number ke multiple items mile hain. Sahi item select kijiye.');
      return true;
    }
    say('Ye item nahi mila. Naya item add kar sakte hain.');
    var b=document.createElement('button');b.type='button';b.className='choice-action';b.textContent='➕ '+vp.name+' ko naya item add karein';
    b.onclick=function(){$('newName').value=vp.name;$('newSize').value='';$('newRate').value='0';$('newBarcode').value='';$('newUnit').value='pcs';$('choices').innerHTML='';openItemModal();};
    $('choices').appendChild(b);
    return true;
  }catch(e){fail(e.message);return true;}
}

processSpeech=async function(raw){
  raw=String(raw||'').trim();if(!raw)return;
  if(await handleNamedVariant192(raw))return;
  return _baseProcessSpeech192(raw);
};
'''


def _page() -> str:
    page = _prev_page()
    marker = "$('scanBarcode').onclick=openScanner;"
    if "handleNamedVariant192" not in page and marker in page:
        page = page.replace(marker, PATCH_JS + "\n" + marker, 1)
    return page


desk._desk_page_with_quantity_fix = _page
