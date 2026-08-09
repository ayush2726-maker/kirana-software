from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "166"
html = quick_canvas.HTML

# The Android recognizer dialog should tell the user what the current AI step
# expects instead of always saying "Item bolo". Keep a no-argument fallback so
# older APKs continue working until the next validated native build is installed.
if "function voicePrompt2()" not in html:
    html = html.replace(
        "  function nativeListen2(){",
        """  function voicePrompt2(){
    if(!aiOn2) return 'Item aur quantity boliye';
    if(aiStep2==='customer') return 'Customer ka naam boliye';
    if(aiStep2==='customer_missing') return 'Customer nahi mila. Add customer ya skip boliye';
    if(aiStep2==='item_missing') return 'Naya item add karna hai to add item boliye, warna cancel';
    if(aiStep2==='complete') return 'Save bill boliye, ya agla item boliye';
    return 'Item aur quantity boliye, jaise 1 kilo moong';
  }

  function nativeListen2(){""",
        1,
    )
    html = html.replace(
        "        window.KiranaVoice.start();",
        """        try { window.KiranaVoice.start(voicePrompt2()); }
        catch (_) { window.KiranaVoice.start(); }""",
        1,
    )

quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
