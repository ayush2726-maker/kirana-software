from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "170"

html = quick_canvas.HTML

modal = r'''
<div id="aiCustomerModal" style="display:none;position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.42);align-items:center;justify-content:center;padding:18px">
  <div style="width:min(94vw,430px);background:#fff;border-radius:18px;padding:18px;box-shadow:0 16px 50px rgba(0,0,0,.28)">
    <div id="aiCustomerTitle" style="font-weight:900;font-size:20px;color:#263746;margin-bottom:8px">Customer</div>
    <div id="aiCustomerHint" style="font-size:14px;color:#667784;margin-bottom:12px"></div>
    <select id="aiCustomerSelect" style="display:none;width:100%;min-height:52px;border:2px solid #c9d9e2;border-radius:12px;padding:8px;font:inherit;margin-bottom:10px"></select>
    <input id="aiCustomerPhone" inputmode="numeric" maxlength="10" placeholder="10 digit mobile number" style="display:none;width:100%;min-height:52px;border:2px solid #c9d9e2;border-radius:12px;padding:10px;font:inherit;box-sizing:border-box;margin-bottom:10px" />
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button type="button" id="aiCustomerOk" class="btn">Create Customer</button>
      <button type="button" id="aiCustomerCash" class="btn secondary">Cash / No Name</button>
      <button type="button" id="aiCustomerCancel" class="btn secondary">Cancel</button>
    </div>
  </div>
</div>
'''
if 'id="aiCustomerModal"' not in html:
    html = html.replace('</body>', modal + '</body>', 1)

helper_anchor = "  window.KiranaVoiceResult=async function(text){"
helper_js = r'''
  function customerModal2(name,matches){
    return new Promise(function(resolve){
      var m=q('aiCustomerModal'), title=q('aiCustomerTitle'), hint=q('aiCustomerHint');
      var sel=q('aiCustomerSelect'), phone=q('aiCustomerPhone'), ok=q('aiCustomerOk');
      var cash=q('aiCustomerCash'), cancel=q('aiCustomerCancel');
      if(!m){resolve({action:'cancel'});return}
      title.textContent=matches&&matches.length>1?'Same naam ke customer mile':'Naya Customer';
      hint.textContent=matches&&matches.length>1?'Mobile number dekhkar sahi customer select karo.':name+' list me nahi mila. Mobile number dalo aur customer create karo.';
      sel.innerHTML='';phone.value='';
      if(matches&&matches.length>1){
        sel.style.display='block';phone.style.display='none';ok.textContent='Select Customer';
        matches.forEach(function(p){var o=document.createElement('option');o.value=String(p.id);o.textContent=String(p.name||'')+' — '+(p.phone?String(p.phone):'No mobile');sel.appendChild(o)});
      }else{
        sel.style.display='none';phone.style.display='block';ok.textContent='Create Customer';
        setTimeout(function(){try{phone.focus()}catch(_){}},120);
      }
      m.style.display='flex';
      function done(v){m.style.display='none';ok.onclick=null;cash.onclick=null;cancel.onclick=null;resolve(v)}
      ok.onclick=function(){
        if(matches&&matches.length>1){done({action:'select',id:Number(sel.value||0)});return}
        var ph=String(phone.value||'').replace(/\D/g,'');
        if(ph.length!==10){hint.textContent='10 digit mobile number dalo.';phone.focus();return}
        done({action:'create',phone:ph});
      };
      cash.onclick=function(){done({action:'cash'})};
      cancel.onclick=function(){done({action:'cancel'})};
    })
  }

  async function finishCustomer2(p){
    if(!p)return false;
    q('party').value=String(p.id||'');
    aiStep2='item';
    prompt2((p.name||'Customer')+' select ho gaya. Ab item bolo.');
    setTimeout(nativeListen2,300);
    return true;
  }

'''
if helper_anchor in html and 'function customerModal2(' not in html:
    html = html.replace(helper_anchor, helper_js + helper_anchor, 1)

old_customer = r'''    if(aiStep2==='customer'){
      var ps=await parties2();
      var cs=ps.filter(function(p){return p.type==='customer'||p.type==='both'});
      var found=cs.find(function(p){return norm2(p.name)===low})||cs.find(function(p){var n=norm2(p.name);return n&&low&&(n.indexOf(low)>=0||low.indexOf(n)>=0)});
      if(found){q('party').value=String(found.id);aiStep2='item';prompt2(found.name+' mil gaya. Ab item bolo.');setTimeout(nativeListen2,300);return}
      pendingCustomer2=text;aiStep2='customer_missing';prompt2(text+' customer nahi mila. Add customer bolo, ya skip.');return;
    }

    if(aiStep2==='customer_missing'){
      if(/skip|cash|कैश|छोड़|छोड/.test(low)){q('party').value='';aiStep2='item';prompt2('Customer skip. Ab item bolo.');setTimeout(nativeListen2,300);return}
      if(/add|yes|haan|हाँ|जोड़|जोड/.test(low)){
        try{
          var rr=await fetch('/api/quick-bill/customer',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:pendingCustomer2})});
          var dd=await rr.json();if(!rr.ok)throw new Error(dd.detail||'Customer add nahi hua');
          partyCache2=[];await parties2();fillParties();q('party').value=String(dd.party.id);
          aiStep2='item';prompt2(dd.party.name+' add ho gaya. Ab item bolo.');setTimeout(nativeListen2,300);
        }catch(e){show(e.message||String(e),true)}
        return;
      }
      prompt2('Add customer bolo, ya skip.');return;
    }
'''
new_customer = r'''    if(aiStep2==='customer'){
      if(/^(cash|cash customer|कैश|कैश कस्टमर|skip|स्किप)$/.test(low)){
        q('party').value='';aiStep2='item';prompt2('Cash bill. Ab item bolo.');setTimeout(nativeListen2,300);return;
      }
      var ps=await parties2();
      var cs=ps.filter(function(p){return p.type==='customer'||p.type==='both'});
      var exacts=cs.filter(function(p){return norm2(p.name)===low});
      if(exacts.length===1){await finishCustomer2(exacts[0]);return}
      if(exacts.length>1){
        var choice=await customerModal2(text,exacts);
        if(choice.action==='select'){
          var chosen=exacts.find(function(p){return Number(p.id)===Number(choice.id)});if(chosen){await finishCustomer2(chosen);return}
        }
        if(choice.action==='cash'){q('party').value='';aiStep2='item';prompt2('Cash bill. Ab item bolo.');setTimeout(nativeListen2,300);return}
        prompt2('Customer ka naam dobara bolo.');setTimeout(nativeListen2,300);return;
      }
      var close=cs.filter(function(p){var n=norm2(p.name);return n&&low&&(n.indexOf(low)>=0||low.indexOf(n)>=0)});
      if(close.length===1){await finishCustomer2(close[0]);return}
      if(close.length>1){
        var choice2=await customerModal2(text,close);
        if(choice2.action==='select'){
          var chosen2=close.find(function(p){return Number(p.id)===Number(choice2.id)});if(chosen2){await finishCustomer2(chosen2);return}
        }
        if(choice2.action==='cash'){q('party').value='';aiStep2='item';prompt2('Cash bill. Ab item bolo.');setTimeout(nativeListen2,300);return}
        prompt2('Customer ka naam dobara bolo.');setTimeout(nativeListen2,300);return;
      }
      pendingCustomer2=text;
      var createChoice=await customerModal2(text,[]);
      if(createChoice.action==='cash'){
        q('party').value='';aiStep2='item';prompt2('Cash bill. Ab item bolo.');setTimeout(nativeListen2,300);return;
      }
      if(createChoice.action==='create'){
        try{
          var rr=await fetch('/api/quick-bill/customer-smart',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:pendingCustomer2,phone:createChoice.phone})});
          var dd=await rr.json();if(!rr.ok)throw new Error(dd.detail||'Customer add nahi hua');
          partyCache2=[];await parties2();fillParties();await finishCustomer2(dd.party);return;
        }catch(e){show(e.message||String(e),true);aiStep2='customer';setTimeout(nativeListen2,300);return}
      }
      aiStep2='customer';prompt2('Customer ka naam dobara bolo.');setTimeout(nativeListen2,300);return;
    }
'''
if old_customer in html:
    html = html.replace(old_customer, new_customer, 1)

html = html.replace("prompt2('Aapka naam bataiye. Customer nahi chahiye to skip boliye.');", "prompt2('Customer ka naam boliye. Cash bill ke liye cash boliye.');", 1)

quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
