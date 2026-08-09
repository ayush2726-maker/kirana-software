from __future__ import annotations

import backend.quick_write_canvas_fix_ext as quick_canvas

VERSION = "153"

html = quick_canvas.HTML

html = html.replace(
    "<th>Amount</th></tr>",
    "<th>Amount</th><th>Delete</th></tr>",
)

html = html.replace(
    ".low{color:#a16a00}.total",
    ".low{color:#a16a00}.del-row{border:0;background:#fff0ef;color:#b42318;border-radius:10px;min-width:44px;min-height:40px;font-size:20px;font-weight:900}.total",
)

old_render_tail = "<td><b class=\"amt\">'+money(n(x.qty)*n(x.rate))+'</b></td></tr>'"
new_render_tail = "<td><b class=\"amt\">'+money(n(x.qty)*n(x.rate))+'</b></td><td><button type=\"button\" class=\"del-row\" data-del=\"'+i+'\" aria-label=\"Delete item\">🗑️</button></td></tr>'"
html = html.replace(old_render_tail, new_render_tail)

needle = "q('rows').addEventListener('input',function(e){"
handler = "q('rows').addEventListener('click',function(e){var b=e.target.closest('.del-row');if(!b)return;e.preventDefault();var i=Number(b.dataset.del);if(!Number.isInteger(i)||i<0||i>=lines.length)return;lines.splice(i,1);if(lines.length){render()}else{q('rows').innerHTML='';q('draft').style.display='none';q('total').textContent=money(0)}show('Item delete ho gaya. Total '+lines.length+' item draft me.');});"
html = html.replace(needle, handler + needle)

quick_canvas.HTML = html
quick_canvas.VERSION = VERSION
