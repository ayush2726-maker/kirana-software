from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.app import app, db
from backend.owner_session_ext import COOKIE_NAME, _session_row
import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "162"


@app.post("/api/quick-bill/customer")
async def quick_bill_add_customer(request: Request):
    session = _session_row(request.cookies.get(COOKIE_NAME))
    if not session:
        return JSONResponse({"detail": "Session expired"}, status_code=401)
    try:
        data = await request.json()
    except Exception:
        data = {}
    name = str(data.get("name") or "").strip()
    if len(name) < 2:
        return JSONResponse({"detail": "Customer name chahiye"}, status_code=400)
    bid = int(session["business_id"])
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM parties WHERE business_id=? AND lower(name)=lower(?) AND type IN ('customer','both') LIMIT 1",
            (bid, name),
        ).fetchone()
        if existing:
            return JSONResponse({"ok": True, "party": dict(existing), "created": False})
        cur = conn.execute(
            "INSERT INTO parties(business_id,name,type,phone,gstin,address,opening_balance,balance,created_at,updated_at) "
            "VALUES(?,?,'customer','','','',0,0,datetime('now'),datetime('now'))",
            (bid, name),
        )
        row = conn.execute("SELECT * FROM parties WHERE id=?", (int(cur.lastrowid),)).fetchone()
    return JSONResponse({"ok": True, "party": dict(row), "created": True})


# Keep explicit API ahead of the frontend catch-all.
for wanted_path in ("/api/quick-bill/customer",):
    matches = [route for route in list(app.router.routes) if getattr(route, "path", None) == wanted_path]
    for route in matches:
        app.router.routes.remove(route)
    fallback_index = next(
        (i for i, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
        len(app.router.routes),
    )
    app.router.routes[fallback_index:fallback_index] = matches


html = quick_canvas.HTML

voice_box = '''<div id="voiceFallback" style="margin-top:10px;padding:10px;border:1px solid #d5e2e9;border-radius:12px;background:#f8fbfd">
  <div style="font-weight:900;margin-bottom:7px">🎙️ Voice / Type Item</div>
  <input id="voiceText" autocomplete="off" placeholder="Bolo ya type karo: 2 moong 100" style="width:100%;min-height:48px;border:2px solid #b8d6e6;border-radius:12px;padding:10px;font:inherit" />
  <div style="font-size:12px;color:#6f7d88;margin-top:6px">Native app me mic permission milte hi voice chalegi. Text fallback bhi available hai.</div>
</div>'''
if 'id="voiceFallback"' not in html:
    html = html.replace('</div><canvas id="pad">', '</div>'+voice_box+'<canvas id="pad">', 1)

# Add an interactive AI Bill button beside Voice Bill.
if 'id="aiBill"' not in html:
    html = html.replace(
        '<button class="btn secondary" id="voice">🎤 Voice Bill</button>',
        '<button class="btn secondary" id="voice">🎤 Voice Bill</button><button class="btn secondary" id="aiBill">🤖 AI Bill</button>',
        1,
    )

ai_panel = '''<div id="aiPanel" style="display:none;margin-top:10px;padding:12px;border:2px solid #8ccbe9;border-radius:14px;background:#f4fbff">
  <div style="font-weight:900;font-size:17px">🤖 AI Bill Assistant</div>
  <div id="aiPrompt" style="margin-top:7px;font-weight:750;color:#34495a">AI ready</div>
  <div id="aiHeard" style="margin-top:5px;font-size:13px;color:#6f7d88"></div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:9px">
    <button class="btn" id="aiListen" type="button">🎤 Bolo</button>
    <button class="btn secondary" id="aiSkip" type="button">Skip Customer</button>
    <button class="btn secondary" id="aiStop" type="button">Stop AI</button>
  </div>
</div>'''
if 'id="aiPanel"' not in html:
    html = html.replace('<div id="status" class="status"></div>', '<div id="status" class="status"></div>'+ai_panel, 1)

voice_js = r'''
(function(){
  var vb=q('voice'), vt=q('voiceText'), aiBtn=q('aiBill'), aiPanel=q('aiPanel'), aiPrompt=q('aiPrompt'), aiHeard=q('aiHeard');
  var timer=null, aiOn=false, aiStep='idle', pendingCustomer='', partyCache=[];
  if(!vb||!vt)return;

  function say(t){
    try{ if(window.speechSynthesis){window.speechSynthesis.cancel();var u=new SpeechSynthesisUtterance(t);u.lang='hi-IN';u.rate=1;window.speechSynthesis.speak(u);} }catch(_){}
  }
  function setPrompt(t){if(aiPrompt)aiPrompt.textContent=t;show(t);say(t)}
  function norm(t){return String(t||'').toLowerCase().replace(/[^a-z0-9\u0900-\u097f]+/g,' ').trim()}
  function cleanItemSpeech(t){
    t=String(t||'').trim();
    // “5 kilo moong” means qty 5 of kg-unit Moong; do not let “kilo” pollute item matching.
    t=t.replace(/^(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilo|kilogram|किलो|किलोग्राम)\s+/i,'$1 ');
    return t;
  }
  async function getParties(){
    if(partyCache.length)return partyCache;
    try{var r=await fetch('/api/parties',{credentials:'include',cache:'no-store'});var d=await r.json();if(r.ok&&Array.isArray(d))partyCache=d;}catch(_){}
    return partyCache;
  }
  async function sendVoiceText(t){
    t=cleanItemSpeech(t); if(!t)return;
    try{
      if(aiHeard)aiHeard.textContent='Suna: '+t;
      var r=await fetch('/api/quick-bill/voice-parse',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,bill_type:q('type').value})});
      var d=await r.json(); if(!r.ok)throw new Error(d.detail||'Voice parse failed');
      if(d.items&&d.items.length){
        lines=lines.concat(d.items);render();
        if(aiOn){setPrompt(d.items.length+' item add ho gaya. Aur item batao, ya bolo bill complete.');}
        else show(d.items.length+' item add hua. Agla bolo…');
        vt.value='';
      }else setPrompt('Item samajh nahi aaya. Dobara bolo.');
    }catch(e){show(e.message||String(e),true)}
  }

  function nativeListen(){
    if(window.KiranaVoice&&typeof window.KiranaVoice.start==='function'){
      try{window.KiranaVoice.start();return true}catch(_){}
    }
    try{vt.focus();vt.click();show('Native mic available nahi hai. Neeche field me type/keyboard mic use karo.')}catch(_){}
    return false;
  }
  window.KiranaVoiceError=function(code){show('Voice permission/start issue: '+code,true)};
  window.KiranaVoiceResult=async function(text){
    text=String(text||'').trim(); if(!text)return;
    if(aiHeard)aiHeard.textContent='Suna: '+text;
    if(!aiOn){await sendVoiceText(text);return;}
    var low=norm(text);
    if(aiStep==='customer'){
      var ps=await getParties();
      var customers=ps.filter(function(p){return p.type==='customer'||p.type==='both'});
      var exact=customers.find(function(p){return norm(p.name)===low}) || customers.find(function(p){var n=norm(p.name);return n&&low&&(n.indexOf(low)>=0||low.indexOf(n)>=0)});
      if(exact){q('party').value=String(exact.id);aiStep='item';setPrompt(exact.name+' mil gaya. Ab item bolo, jaise 5 kilo moong.');setTimeout(nativeListen,350);return;}
      pendingCustomer=text;aiStep='customer_missing';setPrompt(text+' customer nahi mila. Bolo add customer, ya skip.');return;
    }
    if(aiStep==='customer_missing'){
      if(/skip|छोड़|छोड|cash|कैश/.test(low)){q('party').value='';aiStep='item';setPrompt('Customer skip kar diya. Ab item bolo.');setTimeout(nativeListen,350);return;}
      if(/add|जोड़|जोड|haan|हाँ|yes/.test(low)){
        try{
          var r=await fetch('/api/quick-bill/customer',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:pendingCustomer})});
          var d=await r.json();if(!r.ok)throw new Error(d.detail||'Customer add nahi hua');
          partyCache=[];await getParties();fillParties();q('party').value=String(d.party.id);aiStep='item';setPrompt(d.party.name+' add ho gaya. Ab item bolo.');setTimeout(nativeListen,350);
        }catch(e){show(e.message||String(e),true)}
        return;
      }
      setPrompt('Bolo add customer, ya skip.');return;
    }
    if(aiStep==='item'){
      if(/bill complete|complete|बस|bas|finish|done/.test(low)){aiStep='complete';setPrompt('Bill ready hai. Check kar lo. Save bill bolne par save kar dunga.');return;}
      if(/save bill|bill save|सेव बिल/.test(low)){try{q('save').click()}catch(_){};aiOn=false;aiStep='idle';return;}
      await sendVoiceText(text);setTimeout(nativeListen,450);return;
    }
    if(aiStep==='complete'){
      if(/save|सेव/.test(low)){try{q('save').click()}catch(_){};aiOn=false;aiStep='idle';setPrompt('Bill save process start ho gaya.');}
      else if(/item|और|aur|add/.test(low)){aiStep='item';setPrompt('Theek hai, agla item bolo.');setTimeout(nativeListen,350);}
    }
  };

  function startAi(){
    aiOn=true;aiStep='customer';pendingCustomer='';if(aiPanel)aiPanel.style.display='block';
    setPrompt('Aapka naam bataiye. Customer nahi chahiye to skip bol sakte hain.');setTimeout(nativeListen,300);
  }
  if(aiBtn)aiBtn.onclick=function(e){if(e){e.preventDefault();e.stopPropagation()}startAi()};
  if(q('aiListen'))q('aiListen').onclick=nativeListen;
  if(q('aiSkip'))q('aiSkip').onclick=function(){if(!aiOn)startAi();q('party').value='';aiStep='item';setPrompt('Customer skip kar diya. Ab item bolo.');setTimeout(nativeListen,300)};
  if(q('aiStop'))q('aiStop').onclick=function(){aiOn=false;aiStep='idle';if(aiPanel)aiPanel.style.display='none';show('AI Bill stopped.')};

  // Voice Bill also uses the native Android bridge first. No browser WebSpeech dependency in the APK.
  vb.onclick=function(ev){if(ev){ev.preventDefault();ev.stopPropagation()}nativeListen()};
  vt.addEventListener('input',function(){clearTimeout(timer);var t=this.value;timer=setTimeout(function(){if((t||'').trim()){if(aiOn)window.KiranaVoiceResult(t);else sendVoiceText(t)}},900)});
  vt.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();clearTimeout(timer);if(aiOn)window.KiranaVoiceResult(vt.value);else sendVoiceText(vt.value)}});
})();
'''
html = html.replace('})();\n</script>', voice_js + '\n})();\n</script>', 1)
html = html.replace(
    'Likho: LEFT me Qty, MIDDLE me Item, RIGHT me Rate.',
    'Likho: LEFT me Qty, MIDDLE me Item, RIGHT me Rate. Ya 🤖 AI Bill se poora bill baat karke banao.',
)
quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
