from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "163"

# Final Quick Write runtime patch. Earlier voice code used browser WebSpeech and
# could leave the AI/voice handlers unbound depending on string-injection scope.
# Bind both controls inside the original Quick Write closure, where q/lines/render
# are guaranteed to exist, and prefer the Android KiranaVoice bridge.
html = quick_canvas.HTML

runtime_js = r'''
(function(){
  var voiceBtn=q('voice'), voiceText=q('voiceText'), aiBtn=q('aiBill');
  var aiPanel=q('aiPanel'), aiPrompt=q('aiPrompt'), aiHeard=q('aiHeard');
  var aiListen=q('aiListen'), aiSkip=q('aiSkip'), aiStop=q('aiStop');
  var aiOn2=false, aiStep2='idle', pendingCustomer2='', partyCache2=[];
  if(!voiceBtn) return;

  function norm2(t){return String(t||'').toLowerCase().replace(/[^a-z0-9\u0900-\u097f]+/g,' ').trim()}
  function prompt2(t){
    if(aiPrompt) aiPrompt.textContent=t;
    show(t);
    try{
      if(window.speechSynthesis){
        window.speechSynthesis.cancel();
        var u=new SpeechSynthesisUtterance(t);u.lang='hi-IN';u.rate=1;window.speechSynthesis.speak(u);
      }
    }catch(_){}
  }
  function heard2(t){if(aiHeard)aiHeard.textContent='Suna: '+t}

  function nativeListen2(){
    try{
      if(window.KiranaVoice && typeof window.KiranaVoice.start==='function'){
        show('Mic ready: bolo…');
        window.KiranaVoice.start();
        return true;
      }
    }catch(e){show('Native voice start issue: '+(e&&e.message?e.message:e),true)}
    if(voiceText){
      voiceText.focus();
      show('Native mic available nahi hai. Neeche type karo ya keyboard mic use karo.');
    }else show('Native mic available nahi hai.',true);
    return false;
  }

  async function parseItem2(text){
    text=String(text||'').trim();
    if(!text)return;
    heard2(text);
    try{
      var r=await fetch('/api/quick-bill/voice-parse',{
        method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text:text,bill_type:q('type').value})
      });
      var d=await r.json();
      if(!r.ok)throw new Error(d.detail||'Voice parse failed');
      var got=d.items||[];
      if(!got.length){show('Item samajh nahi aaya. Dobara bolo.',true);return}
      lines=lines.concat(got);render();
      show(got.length+' item add hua. Total '+lines.length+' item.');
      if(voiceText)voiceText.value='';
    }catch(e){show(e.message||String(e),true)}
  }

  async function parties2(){
    if(partyCache2.length)return partyCache2;
    try{
      var r=await fetch('/api/parties',{credentials:'include',cache:'no-store'});
      var d=await r.json();if(r.ok&&Array.isArray(d))partyCache2=d;
    }catch(_){}
    return partyCache2;
  }

  window.KiranaVoiceError=function(code){
    show('Voice start issue: '+String(code||'unknown')+'. Dobara Voice Bill dabao.',true);
  };

  window.KiranaVoiceResult=async function(text){
    text=String(text||'').trim();if(!text)return;
    heard2(text);
    if(!aiOn2){await parseItem2(text);return}
    var low=norm2(text);

    if(aiStep2==='customer'){
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

    if(aiStep2==='item'){
      if(/bill complete|complete|finish|done|बस|bas/.test(low)){aiStep2='complete';prompt2('Bill ready hai. Save bill bolo ya aur item bolo.');return}
      await parseItem2(text);prompt2('Item add ho gaya. Agla item bolo, ya bill complete.');setTimeout(nativeListen2,350);return;
    }

    if(aiStep2==='complete'){
      if(/save|सेव/.test(low)){aiOn2=false;aiStep2='idle';q('save').click();return}
      if(/item|add|aur|और/.test(low)){aiStep2='item';prompt2('Theek hai, agla item bolo.');setTimeout(nativeListen2,300)}
    }
  };

  voiceBtn.onclick=function(e){if(e){e.preventDefault();e.stopPropagation()}nativeListen2()};

  if(aiBtn)aiBtn.onclick=function(e){
    if(e){e.preventDefault();e.stopPropagation()}
    aiOn2=true;aiStep2='customer';pendingCustomer2='';
    if(aiPanel)aiPanel.style.display='block';
    prompt2('Aapka naam bataiye. Customer nahi chahiye to skip boliye.');
    setTimeout(nativeListen2,250);
  };
  if(aiListen)aiListen.onclick=function(e){if(e)e.preventDefault();nativeListen2()};
  if(aiSkip)aiSkip.onclick=function(e){if(e)e.preventDefault();aiOn2=true;q('party').value='';aiStep2='item';prompt2('Customer skip. Ab item bolo.');setTimeout(nativeListen2,250)};
  if(aiStop)aiStop.onclick=function(e){if(e)e.preventDefault();aiOn2=false;aiStep2='idle';if(aiPanel)aiPanel.style.display='none';show('AI Bill stopped.')};

  if(voiceText){
    voiceText.onkeydown=function(e){if(e.key==='Enter'){e.preventDefault();if(aiOn2)window.KiranaVoiceResult(voiceText.value);else parseItem2(voiceText.value)}};
  }
})();
'''

anchor = "q('type').onchange=fillParties;"
if anchor in html and 'aiOn2=false' not in html:
    html = html.replace(anchor, runtime_js + anchor, 1)

quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
