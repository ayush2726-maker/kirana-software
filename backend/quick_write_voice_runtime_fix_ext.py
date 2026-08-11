from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "176"

html = quick_canvas.HTML

runtime_js = r'''
(function(){
  var voiceBtn=q('voice'), voiceText=q('voiceText'), aiBtn=q('aiBill');
  var aiPanel=q('aiPanel'), aiPrompt=q('aiPrompt'), aiHeard=q('aiHeard');
  var aiListen=q('aiListen'), aiSkip=q('aiSkip'), aiStop=q('aiStop'), aiAdd=q('aiAddItem');
  var aiOn2=false, aiStep2='idle', pendingCustomer2='', pendingItem2=null, partyCache2=[];
  var browserRec2=null, browserVoiceStarting2=false;
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
  function showAdd2(on){if(aiAdd)aiAdd.style.display=on?'inline-block':'none'}

  function manualVoice2(message){
    if(!aiPanel||!voiceText){
      show(message||'Mic available nahi hai. Keyboard mic ya typing use karein.',true);
      return false;
    }
    var box=document.getElementById('aiManualVoice2');
    if(!box){
      box=document.createElement('div');box.id='aiManualVoice2';box.className='ks-ai-manual-voice';
      box.innerHTML='<label>Type or use keyboard mic</label><div><input id="aiManualVoiceInput2" autocomplete="off" placeholder="Customer ya item bolkar/type karke Enter karein"><button type="button" id="aiManualVoiceSend2">Add</button></div>';
      var controls=aiListen&&aiListen.parentNode;
      aiPanel.insertBefore(box,controls||null);
      var input=document.getElementById('aiManualVoiceInput2'),send=document.getElementById('aiManualVoiceSend2');
      var submit=function(){var text=String(input&&input.value||'').trim();if(!text)return;if(input)input.value='';window.KiranaVoiceResult(text)};
      if(send)send.onclick=submit;
      if(input)input.onkeydown=function(e){if(e.key==='Enter'){e.preventDefault();submit()}};
    }
    box.style.display='block';
    var field=document.getElementById('aiManualVoiceInput2');if(field)field.focus();
    show(message||'Phone mic service available nahi hai. Neeche type ya keyboard mic use karein.',true);
    return false;
  }

  function beginBrowserVoice2(Recognition){
    try{
      if(!browserRec2){
        browserRec2=new Recognition();
        browserRec2.lang='hi-IN';browserRec2.continuous=false;browserRec2.interimResults=false;browserRec2.maxAlternatives=3;
        browserRec2.onresult=function(event){
          var text='';
          for(var i=event.resultIndex||0;i<event.results.length;i++){
            if(event.results[i].isFinal!==false&&event.results[i][0])text=String(event.results[i][0].transcript||'').trim();
          }
          if(text)window.KiranaVoiceResult(text);
        };
        browserRec2.onerror=function(event){
          browserVoiceStarting2=false;
          var code=String(event&&event.error||'unknown');
          if(code==='aborted'||code==='no-speech'){show('Awaaz nahi mili. Bolo button dobara dabayein.',true);return}
          if(code==='not-allowed'||code==='service-not-allowed'){
            manualVoice2('Mic permission blocked hai. Chrome site settings me Microphone Allow karein, ya neeche keyboard mic use karein.');return;
          }
          manualVoice2('Chrome voice start nahi hua ('+code+'). Neeche keyboard mic ya typing use karein.');
        };
        browserRec2.onend=function(){browserVoiceStarting2=false};
      }
      browserRec2.start();
      show('Mic ready: boliye…');
      return true;
    }catch(error){
      browserVoiceStarting2=false;
      if(error&&error.name==='InvalidStateError')return true;
      return manualVoice2('Chrome mic start nahi hua. Neeche keyboard mic ya typing use karein.');
    }
  }

  function browserListen2(){
    var Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!Recognition)return false;
    if(browserVoiceStarting2)return true;
    browserVoiceStarting2=true;
    var begin=function(){return beginBrowserVoice2(Recognition)};
    try{
      if(navigator.mediaDevices&&typeof navigator.mediaDevices.getUserMedia==='function'){
        show('Microphone permission check ho rahi hai…');
        navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){
          try{stream.getTracks().forEach(function(track){track.stop()})}catch(_){}
          begin();
        }).catch(function(error){
          var denied=error&&(error.name==='NotAllowedError'||error.name==='PermissionDeniedError');
          if(denied){
            browserVoiceStarting2=false;
            manualVoice2('Mic permission blocked hai. Chrome site settings me Microphone Allow karein, ya neeche keyboard mic use karein.');
            return;
          }
          // Some Android WebViews reject getUserMedia even though their
          // system SpeechRecognizer is available. The permission probe is
          // only advisory there, so still try the recognizer itself.
          show('Direct phone voice try ho rahi hai…');
          begin();
        });
        return true;
      }
    }catch(_){}
    return begin();
  }

  function nativeListen2(){
    try{
      if(window.KiranaVoice && typeof window.KiranaVoice.start==='function'){
        show('Mic ready: bolo…');
        window.KiranaVoice.start();
        return true;
      }
    }catch(e){show('Native voice start issue: '+(e&&e.message?e.message:e),true)}
    if(browserListen2())return true;
    return manualVoice2('Is app/browser me direct mic available nahi hai. Neeche keyboard mic ya typing use karein.');
  }

  async function createMissing2(){
    if(!pendingItem2)return false;
    try{
      var rr=await fetch('/api/quick-bill/item',{
        method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:pendingItem2.item_name,size:pendingItem2.size||'',rate:pendingItem2.rate||0,bill_type:q('type').value})
      });
      var dd=await rr.json();if(!rr.ok)throw new Error(dd.detail||'Item add nahi hua');
      var it=dd.item;
      pendingItem2.item_id=Number(it.id);pendingItem2.item_name=it.name;pendingItem2.size=it.size||pendingItem2.size||'';
      pendingItem2.match_confidence=1;pendingItem2.needs_create=false;
      if(!(pendingItem2.rate>0))pendingItem2.rate=Number((q('type').value==='purchase'?it.purchase_price:it.sale_price)||0);
      lines.push(pendingItem2);render();
      var label=pendingItem2.item_name+(pendingItem2.size?' '+pendingItem2.size:'');
      pendingItem2=null;showAdd2(false);aiStep2='item';
      prompt2(label+' naya item add ho gaya aur bill me aa gaya. Ab agla item bolo.');
      setTimeout(nativeListen2,350);return true;
    }catch(e){show(e.message||String(e),true);return false}
  }

  async function parseItem2(text){
    text=String(text||'').trim();
    if(!text)return false;
    heard2(text);
    try{
      var r=await fetch('/api/quick-bill/voice-parse',{
        method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text:text,bill_type:q('type').value})
      });
      var d=await r.json();
      if(!r.ok)throw new Error(d.detail||'Voice parse failed');
      var got=d.items||[];
      if(!got.length){show('Item samajh nahi aaya. Dobara bolo.',true);return false}
      var matched=got.filter(function(x){return x.item_id}), missing=got.filter(function(x){return !x.item_id});
      if(matched.length){lines=lines.concat(matched);render();show(matched.length+' item add hua. Total '+lines.length+' item.');}
      if(missing.length){
        pendingItem2=missing[0];aiStep2='item_missing';showAdd2(true);
        var label=pendingItem2.item_name+(pendingItem2.size?' '+pendingItem2.size:'');
        prompt2(label+' item list me nahi hai. Add Item dabao ya bolo add item.');
        if(voiceText)voiceText.value='';return false;
      }
      if(voiceText)voiceText.value='';
      return matched.length>0;
    }catch(e){show(e.message||String(e),true);return false}
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

    if(aiStep2==='item_missing'){
      if(/add|yes|haan|हाँ|जोड़|जोड|item/.test(low)){await createMissing2();return}
      if(/cancel|नहीं|nahi|skip|छोड़|छोड/.test(low)){pendingItem2=null;showAdd2(false);aiStep2='item';prompt2('Theek hai, item add nahi kiya. Agla item bolo.');setTimeout(nativeListen2,300);return}
      prompt2('Add item bolo, ya cancel.');return;
    }

    if(aiStep2==='item'){
      if(/bill complete|complete|finish|done|बस|bas/.test(low)){aiStep2='complete';prompt2('Bill ready hai. Save bill bolo ya seedha aur item bolo.');return}
      var added=await parseItem2(text);
      if(added && aiStep2==='item'){prompt2('Item add ho gaya. Agla item bolo, ya bill complete.');setTimeout(nativeListen2,350)}
      return;
    }

    if(aiStep2==='complete'){
      if(/save|सेव/.test(low)){aiOn2=false;aiStep2='idle';q('save').click();return}
      // Any normal speech after bill-ready is treated as the next item.
      aiStep2='item';
      var added2=await parseItem2(text);
      if(added2 && aiStep2==='item'){prompt2('Item add ho gaya. Agla item bolo, ya bill complete.');setTimeout(nativeListen2,350)}
      return;
    }
  };

  voiceBtn.onclick=function(e){if(e){e.preventDefault();e.stopPropagation()}nativeListen2()};

  if(aiBtn)aiBtn.onclick=function(e){
    if(e){e.preventDefault();e.stopPropagation()}
    aiOn2=true;aiStep2='customer';pendingCustomer2='';pendingItem2=null;showAdd2(false);
    if(aiPanel)aiPanel.style.display='block';
    prompt2('Aapka naam bataiye. Customer nahi chahiye to skip boliye.');
    setTimeout(nativeListen2,250);
  };
  if(aiListen)aiListen.onclick=function(e){if(e)e.preventDefault();nativeListen2()};
  if(aiAdd)aiAdd.onclick=function(e){if(e)e.preventDefault();createMissing2()};
  if(aiSkip)aiSkip.onclick=function(e){if(e)e.preventDefault();aiOn2=true;q('party').value='';aiStep2='item';prompt2('Customer skip. Ab item bolo.');setTimeout(nativeListen2,250)};
  if(aiStop)aiStop.onclick=function(e){if(e)e.preventDefault();aiOn2=false;aiStep2='idle';pendingItem2=null;showAdd2(false);if(aiPanel)aiPanel.style.display='none';show('AI Bill stopped.')};

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
