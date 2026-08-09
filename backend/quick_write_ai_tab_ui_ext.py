from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "171"
html = quick_canvas.HTML

patch = r'''
<style id="kirana-ai-tab-ui-171">
.ks-tabs{display:flex;gap:8px;max-width:980px;margin:12px auto 0;padding:0 12px;position:sticky;top:69px;z-index:8;background:#eef8fe;padding-top:8px;padding-bottom:8px}
.ks-tab{flex:1;min-height:48px;border:1px solid #cddfe9;background:#fff;color:#3b5668;border-radius:14px;font:inherit;font-weight:900;padding:9px 12px;box-shadow:0 2px 8px rgba(20,79,112,.06)}
.ks-tab.active{background:#087fba;color:#fff;border-color:#087fba;box-shadow:0 6px 18px rgba(8,127,186,.2)}
.ks-ai-hero{display:none;background:linear-gradient(135deg,#e8f8ff,#f8fcff);border:1px solid #b9dfee;border-radius:18px;padding:14px;margin-bottom:12px}
.ks-ai-hero.show{display:block}.ks-ai-hero h2{margin:0 0 5px;font-size:20px;color:#173d55}.ks-ai-hero p{margin:0;color:#617582;font-size:13px;line-height:1.45}
body.ks-ai-mode .canvas-wrap,body.ks-ai-mode #voiceFallback,body.ks-ai-mode #make,body.ks-ai-mode #more,body.ks-ai-mode #undo,body.ks-ai-mode #clear,body.ks-ai-mode #eraser,body.ks-ai-mode #voice{display:none!important}
body.ks-ai-mode #aiBill{display:none!important}
body.ks-ai-mode #aiPanel{display:block!important;margin-top:0!important;border:1px solid #b8dce9!important;border-radius:18px!important;background:#fff!important;padding:16px!important;box-shadow:0 8px 24px rgba(28,89,120,.09)}
body.ks-ai-mode #aiPrompt{font-size:18px!important;line-height:1.35!important;color:#173d55!important;background:#eff9fd;border-radius:12px;padding:12px!important}
body.ks-ai-mode #aiHeard{font-size:14px!important;background:#f7fafc;border:1px dashed #d4e2e8;border-radius:10px;padding:9px!important;min-height:38px}
body.ks-ai-mode #aiListen{flex:1;min-width:145px;min-height:54px;font-size:16px}
body.ks-ai-mode #aiStop,body.ks-ai-mode #aiSkip,body.ks-ai-mode #aiAddItem{min-height:50px}
body.ks-ai-mode .card:first-of-type{border-color:#c0dfea;box-shadow:0 6px 20px rgba(27,89,119,.07)}
#aiCustomerModal>div{border-radius:22px!important;padding:20px!important;box-shadow:0 24px 70px rgba(10,35,50,.30)!important}
#aiCustomerTitle{font-size:22px!important;color:#163c54!important}#aiCustomerHint{line-height:1.45!important}
#aiCustomerSelect,#aiCustomerPhone{min-height:56px!important;border-radius:14px!important;border-color:#afd4e4!important;font-size:16px!important}
#aiCustomerOk,#aiCustomerCash,#aiCustomerCancel{min-height:50px!important;flex:1}
@media(max-width:700px){.ks-tabs{top:68px}.ks-tab{font-size:14px}.ks-ai-hero{margin-top:2px}body.ks-ai-mode #aiPanel{padding:13px!important}}
</style>
<script id="kirana-ai-tab-ui-script-171">
(function(){
 'use strict';
 if(window.__kiranaAiTab171)return;window.__kiranaAiTab171=true;
 function el(id){return document.getElementById(id)}
 function setup(){
   var main=document.querySelector('main.wrap');if(!main||el('ksSmartTabs'))return;
   var tabs=document.createElement('div');tabs.id='ksSmartTabs';tabs.className='ks-tabs';
   tabs.innerHTML='<button type="button" class="ks-tab active" id="ksWriteTab">✍️ Handwriting</button><button type="button" class="ks-tab" id="ksAiTab">🤖 AI Bill</button>';
   var header=document.querySelector('header.head');if(header&&header.parentNode)header.parentNode.insertBefore(tabs,main);else main.parentNode.insertBefore(tabs,main);
   var hero=document.createElement('div');hero.id='ksAiHero';hero.className='ks-ai-hero';
   hero.innerHTML='<h2>🤖 AI Bill Assistant</h2><p>Customer ka naam bolo → customer select/create hoga → items bolte jao → saved rate ke saath bill draft banta jayega. Cash bill ke liye “cash” bolo.</p>';
   main.insertBefore(hero,main.firstChild);
   var wt=el('ksWriteTab'),at=el('ksAiTab');
   function mode(ai){
     document.body.classList.toggle('ks-ai-mode',!!ai);wt.classList.toggle('active',!ai);at.classList.toggle('active',!!ai);hero.classList.toggle('show',!!ai);
     if(ai){
       var panel=el('aiPanel');if(panel)panel.style.display='block';
       var btn=el('aiBill');if(btn)setTimeout(function(){try{btn.click()}catch(_){}},80);
       setTimeout(function(){var p=el('aiPrompt');if(p)p.scrollIntoView({behavior:'smooth',block:'center'})},180);
     }
   }
   wt.onclick=function(){mode(false)};at.onclick=function(){mode(true)};
   try{var u=new URL(location.href);if(u.searchParams.get('tab')==='ai'||location.hash==='#ai')mode(true)}catch(_){}
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
 setTimeout(setup,300);
})();
</script>
'''

if 'kirana-ai-tab-ui-171' not in html:
    html = html.replace('</body>', patch + '</body>', 1)

quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
