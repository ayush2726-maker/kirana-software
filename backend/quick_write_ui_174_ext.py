from __future__ import annotations

"""Final visual shell for the Handwriting and AI Bill experiences.

The Quick Write feature is assembled by a set of compatibility extensions.
Keeping this as the last, visual-only layer lets the billing/voice behaviour stay
unchanged while both tabs share one predictable mobile-first design.
"""

import backend.quick_write_canvas_fix_ext as quick_canvas


VERSION = "174"
html = quick_canvas.HTML

# An older compatibility layer appends another IIFE immediately after the
# initial async load call. Without the statement terminator, browsers attempt
# to call the resolved catch expression as a function and stop that layer.
_broken_runtime_join = "load().catch(function(e){show(e.message,true)})\n(function(){"
if _broken_runtime_join in html:
    html = html.replace(
        _broken_runtime_join,
        "load().catch(function(e){show(e.message,true)});\n(function(){",
        1,
    )


PATCH = r'''
<style id="kirana-quick-write-ui-174">
:root{
  --ks-blue:#2463eb;
  --ks-blue-dark:#1849b8;
  --ks-blue-soft:#eef4ff;
  --ks-cyan-soft:#edfaff;
  --ks-ink:#172033;
  --ks-muted:#667085;
  --ks-line:#dfe5ef;
  --ks-card:#fff;
  --ks-danger:#d92d20;
  --ks-shadow:0 10px 30px rgba(16,24,40,.08);
}
html{background:#f3f6fb}
body.ks-quick-174{min-height:100vh;background:linear-gradient(180deg,#f7f9fd 0,#eef4fb 100%);color:var(--ks-ink)}
body.ks-quick-174 .head{
  min-height:72px;padding:calc(10px + env(safe-area-inset-top)) 16px 10px;
  gap:12px;border-bottom:1px solid #e5eaf2;background:rgba(255,255,255,.96);
  box-shadow:0 2px 12px rgba(16,24,40,.045);backdrop-filter:blur(14px)
}
body.ks-quick-174 .back{width:42px;height:42px;flex:0 0 42px;border:1px solid #dce6f6;background:#f2f7ff;color:var(--ks-blue);font-size:27px;box-shadow:none}
body.ks-quick-174 .head>div{min-width:0}
body.ks-quick-174 .head small{display:block;font-size:10px;letter-spacing:1.45px;color:var(--ks-blue)}
body.ks-quick-174 .head h1{overflow:hidden;margin:1px 0 0;font-size:20px;line-height:1.2;text-overflow:ellipsis;white-space:nowrap}
#smartModeCaption{display:block;margin-top:2px;color:var(--ks-muted);font-size:10px;line-height:1.2}
body.ks-quick-174 .ks-tabs{
  top:calc(72px + env(safe-area-inset-top));max-width:900px;margin:0 auto;padding:10px 12px;
  gap:6px;background:rgba(243,246,251,.96);backdrop-filter:blur(12px)
}
body.ks-quick-174 .ks-tab{min-height:46px;border:1px solid #d9e0ec;border-radius:12px;background:#fff;color:#475467;font-size:13px;box-shadow:0 2px 8px rgba(16,24,40,.035)}
body.ks-quick-174 .ks-tab.active{border-color:var(--ks-blue);background:var(--ks-blue);color:#fff;box-shadow:0 7px 18px rgba(36,99,235,.22)}
body.ks-quick-174 .wrap{max-width:900px;padding:4px 12px calc(92px + env(safe-area-inset-bottom))}
body.ks-quick-174 .card{margin-bottom:12px;padding:14px;border:1px solid #e0e6ef;border-radius:18px;background:var(--ks-card);box-shadow:var(--ks-shadow)}
.ks-section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 12px}
.ks-section-heading>div{min-width:0}.ks-section-heading b{display:block;font-size:15px}.ks-section-heading small{display:block;margin-top:2px;color:var(--ks-muted);font-size:10px;font-weight:650}
.ks-section-icon{display:grid;width:36px;height:36px;flex:0 0 36px;place-items:center;border-radius:11px;background:var(--ks-blue-soft);color:var(--ks-blue);font-size:17px}
body.ks-quick-174 .grid{gap:10px}
body.ks-quick-174 label{gap:5px;color:#475467;font-size:11px;font-weight:800}
body.ks-quick-174 select,body.ks-quick-174 input{min-height:48px;border:1px solid #d7deea;border-radius:12px;padding:10px 12px;color:var(--ks-ink);font-size:14px;outline:none}
body.ks-quick-174 select:focus,body.ks-quick-174 input:focus{border-color:#84adff;box-shadow:0 0 0 3px rgba(36,99,235,.11)}
body.ks-quick-174 .canvas-wrap{position:relative;margin-top:12px;border:1px solid #dbe3ed;border-radius:15px;background:#fff;box-shadow:inset 0 0 0 1px rgba(255,255,255,.8)}
body.ks-quick-174 .canvas-tools{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;padding:9px;border-bottom:1px solid #e6ebf2;background:#f8fafc}
body.ks-quick-174 .canvas-tools .btn{min-width:0;min-height:42px;padding:8px 5px;border:1px solid #d9e2ef;border-radius:10px;font-size:11px;white-space:nowrap}
body.ks-quick-174 .btn{min-height:48px;border-radius:12px;background:var(--ks-blue);font-size:13px;box-shadow:none}
body.ks-quick-174 .btn:active{transform:translateY(1px)}
body.ks-quick-174 .secondary{border:1px solid #d6e0ee;background:#fff;color:var(--ks-blue)}
body.ks-quick-174 .secondary.eraser-on{border-color:#fdb022;background:#fffaeb;color:#b54708}
#voiceFallback{margin:0!important;padding:10px 11px!important;border:0!important;border-bottom:1px solid #e6ebf2!important;border-radius:0!important;background:#fafdff!important}
#voiceFallback>div:first-child{margin:0 0 6px!important;color:#344054;font-size:11px!important}
#voiceFallback input{min-height:42px!important;border:1px solid #ced9e7!important;border-radius:10px!important;font-size:12px!important}
#voiceFallback>div:last-child{margin-top:5px!important;color:#7c8798!important;font-size:9px!important;line-height:1.35!important}
.ks-canvas-guide{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;border-bottom:1px solid #edf0f5;background:#fff;color:#667085;font-size:9px;font-weight:800;letter-spacing:.4px}
.ks-canvas-guide span{display:flex;align-items:center;gap:5px}.ks-canvas-guide i{width:6px;height:6px;border-radius:50%;background:#2e90fa}
body.ks-quick-174 canvas{height:clamp(360px,52vh,520px);background-color:#fff;background-image:linear-gradient(#edf1f6 1px,transparent 1px);background-size:100% 46px}
body.ks-quick-174 .actions{gap:8px;margin-top:10px}
body.ks-quick-174 .actions .btn{flex:1;min-width:140px}
body.ks-quick-174 .hint{margin:9px 2px 0;padding:9px 10px;border-radius:10px;background:#f8fafc;color:#667085;font-size:9px;line-height:1.45}
body.ks-quick-174 .status{margin-top:10px;padding:10px 11px;border:1px solid #cde7d8;border-radius:10px;background:#ecfdf3;color:#027a48;font-size:11px}
body.ks-quick-174 .status.err{border-color:#fecdca;background:#fef3f2;color:#b42318}
body.ks-quick-174 #draft{border-top:3px solid var(--ks-blue)}
body.ks-quick-174 #draft .table{border-color:#e1e7ef;border-radius:12px}
body.ks-quick-174 #draft th{background:#f8fafc;color:#475467}
body.ks-quick-174 #draft .total{color:var(--ks-ink);font-size:18px}
body.ks-quick-174 .ks-ai-hero{margin:0 0 12px;padding:12px 14px;border:1px solid #c7d7fe;border-radius:16px;background:linear-gradient(135deg,#edf4ff,#f7fbff);box-shadow:none}
body.ks-quick-174 .ks-ai-hero h2{margin:0 0 3px;color:#1849b8;font-size:15px}
body.ks-quick-174 .ks-ai-hero p{color:#536273;font-size:10px;line-height:1.45}
body.ks-quick-174.ks-ai-mode .ks-bill-card{border-color:#d8e3fb}
body.ks-quick-174.ks-ai-mode .canvas-wrap,body.ks-quick-174.ks-ai-mode #voiceFallback,body.ks-quick-174.ks-ai-mode .ks-draft-actions,body.ks-quick-174.ks-ai-mode .hint{display:none!important}
body.ks-quick-174.ks-ai-mode #aiPanel{margin:12px 0 0!important;padding:0!important;border:1px solid #d8e3f4!important;border-radius:17px!important;background:#fff!important;box-shadow:0 10px 28px rgba(36,99,235,.09)!important;overflow:hidden}
.ks-ai-panel-head{display:flex;align-items:center;gap:10px;padding:13px 14px;border-bottom:1px solid #e8edf5;background:linear-gradient(135deg,#f3f7ff,#f7fbff)}
.ks-ai-orb{display:grid;width:38px;height:38px;flex:0 0 38px;place-items:center;border-radius:12px;background:var(--ks-blue);color:#fff;font-size:18px;box-shadow:0 6px 14px rgba(36,99,235,.2)}
.ks-ai-panel-head b{display:block;font-size:14px}.ks-ai-panel-head small{display:block;margin-top:2px;color:var(--ks-muted);font-size:9px}
#ksAiProgress{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;padding:11px 13px 2px;background:#fff}
#ksAiProgress span{position:relative;padding-top:13px;color:#98a2b3;font-size:8px;font-weight:800;text-align:center}
#ksAiProgress span:before{position:absolute;top:0;left:50%;width:8px;height:8px;border:2px solid #d0d5dd;border-radius:50%;background:#fff;content:"";transform:translateX(-50%)}
#ksAiProgress span:not(:last-child):after{position:absolute;top:4px;left:calc(50% + 7px);width:calc(100% - 14px);height:2px;background:#e4e7ec;content:""}
#ksAiProgress span.active,#ksAiProgress span.done{color:var(--ks-blue)}
#ksAiProgress span.active:before,#ksAiProgress span.done:before{border-color:var(--ks-blue);background:var(--ks-blue)}
#ksAiProgress span.done:after{background:var(--ks-blue)}
body.ks-quick-174.ks-ai-mode #aiPrompt{margin:10px 13px 0!important;padding:13px!important;border:1px solid #d9e6ff;border-radius:12px!important;background:#eff5ff!important;color:#163b72!important;font-size:15px!important;line-height:1.4!important}
body.ks-quick-174.ks-ai-mode #aiHeard{margin:8px 13px 0!important;min-height:40px;padding:10px!important;border:1px dashed #d0d8e6!important;border-radius:10px!important;background:#fafbfc!important;color:#667085!important;font-size:10px!important}
body.ks-quick-174.ks-ai-mode #aiPanel>div:last-child{display:grid!important;grid-template-columns:1fr 1fr;gap:8px!important;margin:0!important;padding:12px 13px 14px!important}
body.ks-quick-174.ks-ai-mode #aiListen{grid-column:1/-1;min-height:54px!important;background:var(--ks-blue);font-size:15px!important}
body.ks-quick-174.ks-ai-mode #aiAddItem{grid-column:1/-1}
body.ks-quick-174.ks-ai-mode #aiStop{border-color:#fecdca!important;color:var(--ks-danger)!important}
#aiCustomerModal{backdrop-filter:blur(5px)}
#aiCustomerModal>div{border:1px solid #e1e7ef!important;border-radius:20px!important;padding:18px!important;box-shadow:0 24px 70px rgba(16,24,40,.28)!important}
#aiCustomerTitle{color:var(--ks-ink)!important;font-size:19px!important}#aiCustomerHint{color:var(--ks-muted)!important;font-size:12px!important}
#aiCustomerSelect,#aiCustomerPhone{min-height:50px!important;border:1px solid #d4dcea!important;border-radius:12px!important;font-size:14px!important}
@media(min-width:720px){
  body.ks-quick-174 .wrap{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr);align-items:start;gap:14px}
  body.ks-quick-174 .wrap>.ks-ai-hero{grid-column:1/-1}
  body.ks-quick-174 .wrap>#draft{grid-column:1/-1}
  body.ks-quick-174 canvas{height:500px}
}
@media(max-width:520px){
  body.ks-quick-174 .head{min-height:68px;padding-left:12px;padding-right:12px}
  body.ks-quick-174 .ks-tabs{top:calc(68px + env(safe-area-inset-top));padding:8px 10px}
  body.ks-quick-174 .wrap{padding-left:10px;padding-right:10px}
  body.ks-quick-174 .card{padding:12px;border-radius:16px}
  body.ks-quick-174 .canvas-tools{grid-template-columns:repeat(2,minmax(0,1fr))}
  body.ks-quick-174 .grid{grid-template-columns:1fr 1fr}
  body.ks-quick-174 select{padding-left:9px;padding-right:7px;font-size:12px}
  body.ks-quick-174 .actions .btn{min-width:0;font-size:11px}
}
</style>
<script id="kirana-quick-write-ui-script-174">
(function(){
  'use strict';
  if(window.__kiranaQuickWriteUi174)return;window.__kiranaQuickWriteUi174=true;
  function byId(id){return document.getElementById(id)}
  function setup(){
    document.body.classList.add('ks-quick-174');
    var header=document.querySelector('.head');
    var title=header&&header.querySelector('h1');
    if(title){
      title.textContent='Smart Bill';
      if(!byId('smartModeCaption')){
        var caption=document.createElement('span');caption.id='smartModeCaption';caption.textContent='Write or speak to create a credit bill';title.parentNode.appendChild(caption);
      }
    }
    var card=document.querySelector('main.wrap > .card');
    if(card&&!card.classList.contains('ks-bill-card')){
      card.classList.add('ks-bill-card');
      var grid=card.querySelector('.grid');
      if(grid){
        var heading=document.createElement('div');heading.className='ks-section-heading';
        heading.innerHTML='<div><b>Bill details</b><small>Select transaction type and party</small></div><span class="ks-section-icon">₹</span>';
        card.insertBefore(heading,grid);
      }
      var canvas=card.querySelector('.canvas-wrap');
      if(canvas){
        var tools=canvas.querySelector('.canvas-tools');
        var guide=document.createElement('div');guide.className='ks-canvas-guide';
        guide.innerHTML='<span><i></i>QTY</span><span><i></i>ITEM / SIZE</span><span><i></i>RATE</span>';
        var pad=byId('pad');if(pad)canvas.insertBefore(guide,pad);
        if(tools){
          if(byId('undo'))byId('undo').textContent='↶ Undo';
          if(byId('clear'))byId('clear').textContent='⌫ Clear';
          if(byId('eraser'))byId('eraser').textContent='◇ Eraser';
          if(byId('voice'))byId('voice').textContent='🎙 Voice item';
        }
      }
      var make=byId('make');if(make){var actions=make.closest('.actions');if(actions)actions.classList.add('ks-draft-actions');make.textContent='Read handwriting';}
      var more=byId('more');if(more)more.textContent='+ Add another page';
    }
    var hero=byId('ksAiHero');
    if(hero){hero.innerHTML='<h2>AI voice billing</h2><p>Say customer, items and quantity step by step. Saved rates are applied automatically.</p>';}
    var panel=byId('aiPanel');
    if(panel&&!byId('ksAiProgress')){
      var oldTitle=panel.firstElementChild;if(oldTitle)oldTitle.style.display='none';
      var head=document.createElement('div');head.className='ks-ai-panel-head';
      head.innerHTML='<span class="ks-ai-orb">✦</span><div><b>AI Bill Assistant</b><small>Hands-free billing in Hindi or English</small></div>';
      panel.insertBefore(head,panel.firstChild);
      var progress=document.createElement('div');progress.id='ksAiProgress';
      progress.innerHTML='<span data-ai-progress="1" class="active">CUSTOMER</span><span data-ai-progress="2">ITEMS</span><span data-ai-progress="3">REVIEW</span>';
      var prompt=byId('aiPrompt');panel.insertBefore(progress,prompt||head.nextSibling);
      if(prompt){
        var sync=function(){
          var text=String(prompt.textContent||'').toLowerCase(),step=1;
          if(/item|product|rate|qty|quantity/.test(text))step=2;
          if(/ready|complete|save/.test(text))step=3;
          panel.querySelectorAll('[data-ai-progress]').forEach(function(node){var n=Number(node.getAttribute('data-ai-progress'));node.classList.toggle('done',n<step);node.classList.toggle('active',n===step)});
        };
        new MutationObserver(sync).observe(prompt,{childList:true,subtree:true,characterData:true});sync();
      }
    }
    var write=byId('ksWriteTab'),ai=byId('ksAiTab'),caption=byId('smartModeCaption');
    if(write&&!write.__ksUi174){write.__ksUi174=true;write.addEventListener('click',function(){if(caption)caption.textContent='Write rows as Qty · Item / Size · Rate';});}
    if(ai&&!ai.__ksUi174){ai.__ksUi174=true;ai.addEventListener('click',function(){if(caption)caption.textContent='Speak customer and items to create a draft';});}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
  setTimeout(setup,180);setTimeout(setup,650);
})();
</script>
'''


if "kirana-quick-write-ui-174" not in html:
    html = html.replace("</body>", PATCH + "</body>", 1)

quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
