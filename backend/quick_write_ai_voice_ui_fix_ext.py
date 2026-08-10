from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "172"
html = quick_canvas.HTML

# 1) Do not start the recognizer while TTS is still speaking. This makes the
# assistant actually say each prompt first, then open the Google mic dialog.
needle = "function nativeListen2(){\n    try{"
replacement = "function nativeListen2(){\n    try{if(window.speechSynthesis&&window.speechSynthesis.speaking){setTimeout(nativeListen2,220);return true}}catch(_){}\n    try{"
if needle in html and "speechSynthesis.speaking" not in html:
    html = html.replace(needle, replacement, 1)

patch = r'''
<style id="kirana-ai-voice-ui-172">
/* The top AI tab is now the only AI entry point. */
#aiBill{display:none!important}
</style>
<script id="kirana-ai-voice-ui-script-172">
(function(){
  'use strict';
  if(window.__kiranaAiVoiceUi172)return;window.__kiranaAiVoiceUi172=true;
  function el(id){return document.getElementById(id)}
  function speak(t){
    t=String(t||'').trim();if(!t||!window.speechSynthesis)return;
    try{
      window.speechSynthesis.cancel();
      var u=new SpeechSynthesisUtterance(t);u.lang='hi-IN';u.rate=.95;u.pitch=1;
      window.speechSynthesis.speak(u);
    }catch(_){}
  }
  function setup(){
    var write=el('ksWriteTab'), ai=el('ksAiTab'), panel=el('aiPanel'), stop=el('aiStop');
    if(write && !write.__ks172){
      write.__ks172=true;
      write.addEventListener('click',function(){
        try{if(stop)stop.click()}catch(_){}
        if(panel)panel.style.display='none';
      });
    }
    // Customer chooser/phone modal does not use prompt2, so speak its next step here.
    var modal=el('aiCustomerModal');
    if(modal && !modal.__ks172){
      modal.__ks172=true;
      var last='';
      var announce=function(){
        if(modal.style.display==='none')return;
        var title=(el('aiCustomerTitle')&&el('aiCustomerTitle').textContent)||'';
        var hint=(el('aiCustomerHint')&&el('aiCustomerHint').textContent)||'';
        var msg=(title+' '+hint).trim();
        if(msg && msg!==last){last=msg;speak(msg)}
      };
      new MutationObserver(function(){setTimeout(announce,40)}).observe(modal,{attributes:true,attributeFilter:['style'],subtree:true,childList:true,characterData:true});
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
  setTimeout(setup,250);setTimeout(setup,900);
})();
</script>
'''

if 'kirana-ai-voice-ui-172' not in html:
    html = html.replace('</body>', patch + '</body>', 1)

quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
