from __future__ import annotations

# Import grams/eraser extension for its side effects, but mutate the actual
# Quick Write canvas module because that module owns HTML and the active route.
import backend.quick_write_grams_eraser_ext  # noqa: F401
import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "156"

html = quick_canvas.HTML

old_hint = (
    "1–20 jaise chhote bare number = Qty. 50–999 jaise common pack number = grams "
    "(e.g. 500 = 500g). Eraser se particular galat stroke hata sakte ho."
)
new_hint = (
    "Likho: LEFT me Qty, MIDDLE me Item, RIGHT me Rate. Example: 2 | mung | 100. "
    "Bare number ko Size mat samjho; Size tabhi jab g/kg/L/M jaisi unit saaf likhi ho. "
    "Eraser se particular galat stroke hata sakte ho."
)
html = html.replace(old_hint, new_hint)

# Keep the rule in the rendered page for clarity/debugging. The active HTML is
# owned by quick_canvas, not quick_write_grams_eraser_ext.
format_rule = (
    "LEFT=quantity, MIDDLE=item/product name, RIGHT=rate/price. "
    "Read each handwritten row horizontally. Example 2 mung 100 means qty 2, "
    "item mung, rate 100. Bare left/right numbers are not size."
)
html = html.replace(
    "</body>",
    '<div id="quickWriteFormatRule" style="display:none">' + format_rule + "</div></body>",
)

quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
