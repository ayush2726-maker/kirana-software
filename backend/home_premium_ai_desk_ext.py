from __future__ import annotations

import backend.native_owner_app_ext as native_owner

VERSION = "201"
_prev_native_html = native_owner.native_owner_html

STYLE = r'''
<style id="kirana-premium-home-201">
#page-home{max-width:980px;margin:0 auto}
#page-home .home-hero{border-radius:30px;padding:28px;background:linear-gradient(135deg,#5546e8 0%,#3478ee 54%,#28b8e8 100%);box-shadow:0 24px 55px rgba(49,72,200,.22)}
#page-home .home-hero:after{content:'';position:absolute;width:260px;height:260px;border:1px solid rgba(255,255,255,.14);border-radius:50%;right:-85px;bottom:-135px;box-shadow:0 0 0 44px rgba(255,255,255,.035),0 0 0 88px rgba(255,255,255,.025)}
#page-home .home-hero-copy{position:relative;z-index:2;max-width:620px}
#page-home .hero-eyebrow{letter-spacing:.14em;font-weight:850;opacity:.82}
#page-home .home-hero h1{font-size:clamp(30px,5vw,48px);line-height:1.04;letter-spacing:-1.7px;margin:10px 0 12px}
#page-home .home-hero p{max-width:570px;font-size:16px;opacity:.86}
#page-home .hero-actions{display:none!important}
#page-home .hero-metrics{position:relative;z-index:2;gap:12px;margin-top:24px}
#page-home .hero-metrics>div{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.18);backdrop-filter:blur(10px);border-radius:20px;padding:16px 18px}
#page-home .hero-metrics small{opacity:.76}
#page-home .hero-metrics strong{font-size:25px;letter-spacing:-.7px}
.premium-ai-home{position:relative;overflow:hidden;display:grid;grid-template-columns:96px 1fr auto;align-items:center;gap:20px;margin:18px 0;background:linear-gradient(135deg,#3477f5 0%,#3c8df0 42%,#2ac6d8 100%);color:#fff;border-radius:28px;padding:22px;box-shadow:0 18px 42px rgba(45,118,226,.22)}
.premium-ai-home:after{content:'';position:absolute;right:-44px;top:-74px;width:240px;height:240px;border-radius:50%;background:rgba(255,255,255,.08)}
.premium-ai-robot{position:relative;z-index:2;width:88px;height:88px;border-radius:28px;background:rgba(255,255,255,.94);display:grid;place-items:center;font-size:51px;box-shadow:0 12px 28px rgba(26,68,142,.16)}
.premium-ai-copy{position:relative;z-index:2;min-width:0}.premium-ai-title{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.premium-ai-title strong{font-size:28px;line-height:1}.premium-ai-new{font-size:11px;font-weight:900;letter-spacing:.08em;padding:5px 8px;border-radius:99px;background:#7d4dff}.premium-ai-copy p{margin:8px 0 7px;font-size:15px;opacity:.94}.premium-ai-ready{font-size:13px}.premium-ai-ready i{display:inline-block;width:9px;height:9px;border-radius:50%;background:#22e47a;margin-right:6px}.premium-ai-open{position:relative;z-index:2;display:grid;place-items:center;gap:7px;width:112px;height:112px;border:1px solid rgba(255,255,255,.48);border-radius:50%;background:rgba(255,255,255,.15);color:#fff;font-weight:900;box-shadow:inset 0 0 0 7px rgba(255,255,255,.08)}.premium-ai-open .mic{font-size:37px;line-height:1}.premium-ai-open small{font-size:11px;font-weight:800}.premium-ai-chips{position:relative;z-index:2;grid-column:1/-1;display:flex;gap:8px;overflow:auto;padding-top:2px;scrollbar-width:none}.premium-ai-chips::-webkit-scrollbar{display:none}.premium-ai-chip{white-space:nowrap;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.1);color:#fff;border-radius:99px;padding:9px 13px;font-size:12px;font-weight:700}
#page-home .quick-card{border:0;border-radius:28px;box-shadow:0 12px 36px rgba(23,32,51,.07);padding:22px;margin-top:18px}
#page-home .quick-card .card-title{margin-bottom:14px}
#page-home .quick-grid{grid-template-columns:repeat(6,1fr);gap:13px}
#page-home .quick-grid button{min-width:0;padding:10px 4px;border-radius:18px;background:transparent;border:0}
#page-home .quick-grid small{display:none}
#page-home .quick-grid b{font-size:12px;margin-top:7px}
#page-home .quick-icon{width:58px;height:58px;border-radius:18px;box-shadow:none}
#page-home .quick-grid button:nth-child(1) .quick-icon{background:#e8fbf3;color:#14a56f}
#page-home .quick-grid button:nth-child(2) .quick-icon{background:#f1ebff;color:#7a4af4}
#page-home .quick-grid button:nth-child(3) .quick-icon{background:#fff1e6;color:#f07b2c}
#page-home .quick-grid button:nth-child(4) .quick-icon{background:#eaf3ff;color:#2e71db}
#page-home .quick-grid button:nth-child(5) .quick-icon{background:#ffedf0;color:#e85464}
#page-home .quick-grid button:nth-child(6) .quick-icon{background:#e8fbfa;color:#13a9a3}
#page-home .section-heading{margin-top:28px}
#page-home .search-card{border:0;box-shadow:0 10px 28px rgba(23,32,51,.07);border-radius:20px}
#page-home .list-stack>.transaction-row,#page-home .list-stack>.list-row{border-radius:19px;box-shadow:0 7px 22px rgba(23,32,51,.05)}
#page-home .primary-fab{box-shadow:0 12px 30px rgba(37,99,235,.3)}
@media(max-width:720px){#page-home .home-hero{padding:24px 20px;border-radius:26px}#page-home .home-hero h1{font-size:34px}.premium-ai-home{grid-template-columns:72px 1fr auto;gap:13px;padding:18px;border-radius:25px}.premium-ai-robot{width:68px;height:68px;border-radius:22px;font-size:39px}.premium-ai-title strong{font-size:24px}.premium-ai-copy p{font-size:13px}.premium-ai-open{width:82px;height:82px}.premium-ai-open .mic{font-size:29px}.premium-ai-open small{display:none}#page-home .quick-grid{grid-template-columns:repeat(3,1fr);gap:9px}#page-home .quick-icon{width:54px;height:54px}}
</style>
'''

SCRIPT = r'''
<script id="kirana-premium-home-script-201">
(function(){
 'use strict';
 if(window.__kiranaPremiumHome201)return;window.__kiranaPremiumHome201=true;
 function svg(id){return '<svg class="ui-icon"><use href="#'+id+'"></use></svg>';}
 function go(page){var all=document.querySelectorAll('[data-page="'+page+'"]');for(var i=0;i<all.length;i++){if(!all[i].closest('.premium-home-quick')){all[i].click();return;}}}
 async function openAi(btn){
  if(btn.disabled)return;btn.disabled=true;
  var old=btn.innerHTML;btn.innerHTML='<span class="mic">…</span><small>Opening</small>';
  try{
   var r=await fetch('/api/ai-counter/kiosk-token',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:'{}'});
   var d=await r.json();if(!r.ok)throw new Error(d.detail||'AI Desk open nahi hua');
   if(!d.url)throw new Error('AI Desk URL missing');window.location.assign(d.url);
  }catch(e){btn.disabled=false;btn.innerHTML=old;alert(e.message||'AI Desk open nahi hua');}
 }
 function install(){
  var home=document.getElementById('page-home');if(!home)return;
  var hero=home.querySelector('.home-hero');if(!hero)return;
  if(!document.getElementById('premiumAiHome201')){
   var card=document.createElement('section');card.id='premiumAiHome201';card.className='premium-ai-home';
   card.innerHTML='<div class="premium-ai-robot">🤖</div><div class="premium-ai-copy"><div class="premium-ai-title"><strong>AI Desk</strong><span class="premium-ai-new">NEW</span></div><p>Bolkar bill banao, item dhoondo aur customer select karo.</p><div class="premium-ai-ready"><i></i>Online & Ready</div></div><button id="premiumAiOpen201" class="premium-ai-open" type="button"><span class="mic">🎙️</span><small>Tap to Speak</small></button><div class="premium-ai-chips"><span class="premium-ai-chip">👤 Customer select</span><span class="premium-ai-chip">🛍️ Voice billing</span><span class="premium-ai-chip">▥ Barcode scan</span><span class="premium-ai-chip">＋ Naya bill</span></div>';
   hero.insertAdjacentElement('afterend',card);document.getElementById('premiumAiOpen201').onclick=function(){openAi(this)};
  }
  var grid=home.querySelector('.quick-grid');if(grid&&!grid.classList.contains('premium-home-quick')){
   grid.classList.add('premium-home-quick');
   grid.innerHTML=''
    +'<button type="button" data-ph-page="sale"><span class="quick-icon">'+svg('icon-sale')+'</span><b>New Sale</b></button>'
    +'<button type="button" data-ph-ai="1"><span class="quick-icon">'+svg('icon-ai')+'</span><b>AI Desk</b></button>'
    +'<button type="button" data-ph-page="items"><span class="quick-icon">'+svg('icon-items')+'</span><b>Items</b></button>'
    +'<button type="button" data-ph-page="transactions"><span class="quick-icon">'+svg('icon-transaction')+'</span><b>All Txn</b></button>'
    +'<button type="button" data-ph-page="parties"><span class="quick-icon">'+svg('icon-party')+'</span><b>Parties</b></button>'
    +'<button type="button" data-ph-page="reports"><span class="quick-icon">'+svg('icon-report')+'</span><b>Reports</b></button>';
   grid.querySelectorAll('[data-ph-page]').forEach(function(b){b.onclick=function(){go(this.getAttribute('data-ph-page'));};});
   var ai=grid.querySelector('[data-ph-ai]');if(ai)ai.onclick=function(){openAi(document.getElementById('premiumAiOpen201'));};
  }
  var subtitle=document.getElementById('business-subtitle');if(subtitle)subtitle.textContent='Billing • Stock • AI Desk';
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
 setTimeout(install,400);setTimeout(install,1400);
})();
</script>
'''


def _inject(page: str) -> str:
    if 'kirana-premium-home-script-201' in page:
        return page
    return page.replace('</head>', STYLE + '</head>', 1).replace('</body>', SCRIPT + '</body>', 1)


def native_owner_html_premium_home() -> str:
    return _inject(_prev_native_html())

native_owner.native_owner_html = native_owner_html_premium_home
