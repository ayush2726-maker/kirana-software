from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "160"

# Chrome Custom Tabs require the site microphone permission before
# SpeechRecognition.start(). Build 159 started recognition immediately, which
# returns `not-allowed` when the permission was not yet granted (or was denied).
# This patch explicitly asks for mic access first, then starts continuous
# recognition. If permission was previously blocked, it gives a useful message
# instead of repeatedly throwing `not-allowed`.
html = quick_canvas.HTML

patch_js = r'''
<script>
(function(){
  function byId(id){return document.getElementById(id)}
  var btn=byId('voice');
  if(!btn) return;
  var Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  var localRec=null, localOn=false;

  async function ensureMic(){
    if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){
      throw new Error('Microphone access is phone/browser me available nahi hai. Chrome me page kholkar try karein.');
    }
    try{
      var stream=await navigator.mediaDevices.getUserMedia({audio:true});
      stream.getTracks().forEach(function(t){try{t.stop()}catch(_){}});
      return true;
    }catch(e){
      var name=(e&&e.name)||'';
      if(name==='NotAllowedError'||name==='PermissionDeniedError'){
        throw new Error('Mic permission blocked hai. Chrome me is site ki Microphone permission Allow karke Voice Bill dobara dabayein.');
      }
      throw new Error('Mic start nahi hua: '+(e&&e.message?e.message:name||'unknown error'));
    }
  }

  async function sendHeard(text){
    try{
      if(typeof show==='function') show('Suna: '+text);
      var r=await fetch('/api/quick-bill/voice-parse',{
        method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text:text,bill_type:byId('type')?byId('type').value:'sale'})
      });
      var d=await r.json();
      if(!r.ok) throw new Error(d.detail||'Voice parse failed');
      if(d.items&&d.items.length){
        if(typeof lines!=='undefined'){lines=lines.concat(d.items); if(typeof render==='function') render();}
        if(typeof show==='function') show(d.items.length+' item voice se add hua. Bolte raho…');
      }
    }catch(e){if(typeof show==='function') show(e.message||String(e),true)}
  }

  btn.onclick=async function(ev){
    if(ev){ev.preventDefault();ev.stopPropagation()}
    if(!Recognition){
      if(typeof show==='function') show('Is Chrome/browser me voice recognition available nahi hai.',true);
      return;
    }
    if(localOn){
      localOn=false; btn.textContent='🎤 Voice Bill'; btn.classList.remove('eraser-on');
      try{if(localRec)localRec.stop()}catch(_){}
      return;
    }
    try{
      btn.textContent='🎤 Mic Allow…';
      if(typeof show==='function') show('Microphone permission check ho rahi hai…');
      await ensureMic();
      if(!localRec){
        localRec=new Recognition();
        localRec.lang='hi-IN'; localRec.continuous=true; localRec.interimResults=false;
        localRec.onresult=function(e){
          for(var i=e.resultIndex;i<e.results.length;i++){
            if(e.results[i].isFinal){var t=e.results[i][0].transcript.trim(); if(t) sendHeard(t)}
          }
        };
        localRec.onerror=function(e){
          if(e.error==='not-allowed'||e.error==='service-not-allowed'){
            localOn=false; btn.textContent='🎤 Voice Bill'; btn.classList.remove('eraser-on');
            if(typeof show==='function') show('Mic permission blocked hai. Chrome → site permissions → Microphone → Allow karein.',true);
            return;
          }
          if(e.error!=='no-speech'&&typeof show==='function') show('Voice error: '+e.error,true);
        };
        localRec.onend=function(){if(localOn){setTimeout(function(){try{localRec.start()}catch(_){}},250)}};
      }
      localOn=true; btn.textContent='⏹ Stop Voice'; btn.classList.add('eraser-on');
      if(typeof show==='function') show('Voice ON: bolo — “2 moong 100”. Har item bolte jao.');
      try{localRec.start()}catch(e){if(typeof show==='function') show('Voice start error: '+e.message,true)}
    }catch(e){
      localOn=false; btn.textContent='🎤 Voice Bill'; btn.classList.remove('eraser-on');
      if(typeof show==='function') show(e.message||String(e),true);
    }
  };
})();
</script>
'''

html = html.replace('</body>', patch_js + '</body>')
quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
