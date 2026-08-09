from __future__ import annotations

import re

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "154"

# --- 1) Quick Write number meaning ---
# Small bare numbers remain quantity (2 => qty 2).
# Common kirana pack numbers 50/100/200/250/500 etc. mean grams when no unit
# was written. Also repair impossible AI readings such as 500kg -> 500g.
_original_rows_from_ai = quick_canvas._rows_from_ai


def _rows_from_ai_154(ai_rows, items, bill_type, conn, bid):
    repaired = []
    for raw in ai_rows:
        row = dict(raw or {})
        size = str(row.get("size") or "").strip().lower().replace(" ", "")
        try:
            qty = float(row.get("qty") or 1)
        except Exception:
            qty = 1.0

        # Bare large pack number: 100 / 200 / 500 => grams, not quantity.
        if not size and 50 <= qty <= 999:
            whole = int(qty) if qty.is_integer() else qty
            row["size"] = f"{whole}g"
            row["qty"] = 1

        # Defensive correction: handwriting "500" must never become 500kg.
        m = re.fullmatch(r"(\d+(?:\.\d+)?)kg", size)
        if m:
            value = float(m.group(1))
            if 50 <= value <= 999:
                whole = int(value) if value.is_integer() else value
                row["size"] = f"{whole}g"
                row["qty"] = 1

        repaired.append(row)
    return _original_rows_from_ai(repaired, items, bill_type, conn, bid)


quick_canvas._rows_from_ai = _rows_from_ai_154
quick_canvas.VERSION = VERSION

# --- 2) Particular-stroke eraser on pencil canvas ---
html = quick_canvas.HTML
html = html.replace(
    '<button class="btn secondary" id="clear">Clear Page</button>',
    '<button class="btn secondary" id="clear">Clear Page</button><button class="btn secondary" id="eraser">🧽 Eraser</button>',
)
html = html.replace(
    '.secondary{background:#fff;color:#0873a7;border:2px solid #b8d6e6}',
    '.secondary{background:#fff;color:#0873a7;border:2px solid #b8d6e6}.secondary.eraser-on{background:#fff3cd;color:#7a5200;border-color:#e3aa00}',
)
html = html.replace(
    "var lines=[],items=[],parties=[],strokes=[],drawing=false,current=[];",
    "var lines=[],items=[],parties=[],strokes=[],drawing=false,current=[],erasing=false;",
)
html = html.replace(
    "function start(e){e.preventDefault();drawing=true;current=[pos(e)];strokes.push(current);c.setPointerCapture&&c.setPointerCapture(e.pointerId)}function move(e){if(!drawing)return;e.preventDefault();current.push(pos(e));redraw()}function end(){drawing=false;current=[]}",
    "function eraseAt(p){var radius=28,rr=radius*radius,changed=false;for(var i=strokes.length-1;i>=0;i--){var s=strokes[i],hit=false;for(var j=0;j<s.length;j+=Math.max(1,Math.floor(s.length/35))){var dx=s[j].x-p.x,dy=s[j].y-p.y;if(dx*dx+dy*dy<=rr){hit=true;break}}if(hit){strokes.splice(i,1);changed=true}}if(changed)redraw()}function start(e){e.preventDefault();drawing=true;c.setPointerCapture&&c.setPointerCapture(e.pointerId);if(erasing){eraseAt(pos(e));current=[];return}current=[pos(e)];strokes.push(current)}function move(e){if(!drawing)return;e.preventDefault();if(erasing){eraseAt(pos(e));return}current.push(pos(e));redraw()}function end(){drawing=false;current=[]}",
)
html = html.replace(
    "q('clear').onclick=clearPad;",
    "q('clear').onclick=clearPad;q('eraser').onclick=function(){erasing=!erasing;this.classList.toggle('eraser-on',erasing);this.textContent=erasing?'✏️ Pencil':'🧽 Eraser';show(erasing?'Eraser ON: jis galat stroke par finger chalaoge, wahi hatega.':'Pencil ON');};",
)
html = html.replace(
    'Bare number = Qty (e.g. काबली 2). Unit ke saath number = Size (e.g. काबली 2kg).',
    '1–20 jaise chhote bare number = Qty. 50–999 jaise common pack number = grams (e.g. 500 = 500g). Eraser se particular galat stroke hata sakte ho.',
)
quick_canvas.HTML = html
