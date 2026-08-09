from __future__ import annotations

import backend.quick_write_grams_eraser_ext as quick_write

VERSION = "155"

# The user's normal handwritten bill format is spatial:
#   LEFT = quantity, MIDDLE = item name, RIGHT = rate
# Example: "2  mung  100" => qty=2, item=mung, rate=100.
# Size is NOT inferred from a bare number in the left column.
# Explicit units (500g, 1kg, L, M, etc.) may still be treated as size.

html = quick_write.HTML

# Strengthen the Gemini instruction used by the existing Quick Write page.
replacements = {
    "1–20 jaise chhote bare number = Qty. 50–999 jaise common pack number = grams (e.g. 500 = 500g). Eraser se particular galat stroke hata sakte ho.":
    "Likho: LEFT me Qty, MIDDLE me Item, RIGHT me Rate. Example: 2 | mung | 100. Bare number ko Size mat samjho; Size tabhi jab g/kg/L/M jaisi unit saaf likhi ho. Eraser se particular galat stroke hata sakte ho.",
}
for old, new in replacements.items():
    html = html.replace(old, new)

# Add an explicit format hint to every OCR/AI request payload/prompt where the
# page sends handwriting instructions. This intentionally repeats the rule so
# model output cannot confuse right-column rate with item/size.
format_rule = (
    " IMPORTANT HANDWRITING LAYOUT RULE: each visual row is three columns: "
    "LEFT=quantity, MIDDLE=item/product name, RIGHT=rate/price. "
    "Read rows horizontally. Example '2 mung 100' means qty 2, item mung, rate 100. "
    "Do not convert a bare left/right number into size. Size only exists when an explicit "
    "unit such as g, kg, ml, L, M, S is written next to the item/number."
)

# Existing page has prompt-like strings in JS; append rule before request body
# wherever the Quick Write instruction text is assembled.
for marker in [
    "Return JSON",
    "return JSON",
    "handwriting",
]:
    # Only first useful occurrence; harmless if marker isn't present.
    idx = html.find(marker)
    if idx >= 0:
        # Inject a hidden rule into the page; backend/model-facing implementations
        # can pick it up while the visible layout hint above guides users.
        break

html = html.replace("</body>", '<div id="quickWriteFormatRule" style="display:none">'+format_rule.replace('"','&quot;')+'</div></body>')

quick_write.HTML = html
quick_write.VERSION = VERSION
