from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "161"

html = quick_canvas.HTML

# Always-visible dictation field. This uses the phone keyboard/Gboard microphone
# as a reliable fallback when Chrome Custom Tab blocks Web Speech Recognition.
voice_box = '''<div id="voiceFallback" style="margin-top:10px;padding:10px;border:1px solid #d5e2e9;border-radius:12px;background:#f8fbfd">
  <div style="font-weight:900;margin-bottom:7px">🎙️ Voice / Type Item</div>
  <input id="voiceText" autocomplete="off" placeholder="Bolo ya type karo: 2 moong 100" style="width:100%;min-height:48px;border:2px solid #b8d6e6;border-radius:12px;padding:10px;font:inherit" />
  <div style="font-size:12px;color:#6f7d88;margin-top:6px">Agar Voice Bill direct mic na chale, field par tap karke keyboard ka 🎤 mic use karo. Baat rukne ke 1.2 sec baad item auto-add ho jayega.</div>
</div>'''
html = html.replace('</div><canvas id="pad">', '</div>'+voice_box+'<canvas id="pad">', 1)

# Override the previous voice button with a robust flow:
# 1) Try browser SpeechRecognition.
# 2) If blocked/not-allowed/unavailable, focus fallback field and open keyboard.
# 3) Text/dictation auto-parses after a short pause, no extra Add button needed.
voice_js = r'''
(function(){
  var vb=q('voice'), vt=q('voiceText'), timer=null;
  if(!vb||!vt)return;
  async function sendVoiceText(t){
    t=(t||'').trim(); if(!t)return;
    try{
      show('Suna: '+t);
      var r=await fetch('/api/quick-bill/voice-parse',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,bill_type:q('type').value})});
      var d=await r.json(); if(!r.ok)throw new Error(d.detail||'Voice parse failed');
      if(d.items&&d.items.length){lines=lines.concat(d.items);render();show(d.items.length+' item add hua. Agla bolo…');vt.value='';}
      else show('Item samajh nahi aaya. Dobara bolo/type karo.',true);
    }catch(e){show(e.message||String(e),true)}
  }
  function fallback(msg){
    try{if(rec){voiceOn=false;rec.stop()}}catch(_){}
    vb.textContent='🎙️ Voice / Type'; vb.classList.remove('eraser-on');
    show(msg||'Phone voice fallback ON: neeche field me keyboard mic se bolo.');
    setTimeout(function(){try{vt.focus();vt.click()}catch(_){}},80);
  }
  vt.addEventListener('input',function(){
    clearTimeout(timer); var t=this.value;
    timer=setTimeout(function(){if((t||'').trim())sendVoiceText(t)},1200);
  });
  vt.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();clearTimeout(timer);sendVoiceText(vt.value)}});
  vb.onclick=async function(){
    var SR2=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR2){fallback('Is browser me direct voice available nahi hai. Keyboard mic se bolo.');return}
    try{
      if(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia){
        var s=await navigator.mediaDevices.getUserMedia({audio:true}); s.getTracks().forEach(function(t){t.stop()});
      }
    }catch(e){fallback('Mic browser me blocked/busy hai. Keyboard mic se bolo. Screen recorder mic use kar raha ho to usse bhi conflict ho sakta hai.');return}
    try{
      if(!rec){
        rec=new SR2(); rec.lang='hi-IN'; rec.continuous=true; rec.interimResults=false;
        rec.onresult=function(e){for(var i=e.resultIndex;i<e.results.length;i++){if(e.results[i].isFinal)sendVoiceText(e.results[i][0].transcript)}};
        rec.onerror=function(e){if(e.error==='not-allowed'||e.error==='service-not-allowed'||e.error==='audio-capture'){fallback('Direct mic allow nahi hua. Keyboard mic fallback kholo.')}else{show('Voice error: '+e.error,true)}};
        rec.onend=function(){if(voiceOn){try{rec.start()}catch(_){fallback('Direct voice restart nahi hua. Keyboard mic use karo.')}}};
      }
      voiceOn=!voiceOn;
      this.textContent=voiceOn?'⏹ Stop Voice':'🎤 Voice Bill'; this.classList.toggle('eraser-on',voiceOn);
      if(voiceOn){show('Voice ON: bolo “2 moong 100”.');rec.start()}else{rec.stop()}
    }catch(e){fallback('Direct voice start nahi hua. Keyboard mic se bolo.')}
  };
})();
'''
html = html.replace('</script>', voice_js + '</script>')
quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
