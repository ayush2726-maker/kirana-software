from __future__ import annotations

from fastapi.responses import Response

from backend.app import STATIC_DIR, app


ITEM_GROUPING_JS = r"""

/* Kirana Items Variant UI v0.4.3 */
(() => {
  'use strict';

  const invisibleChars = /[\u200B-\u200D\u2060\uFEFF]/g;
  const unitPattern = 'kg|kgs|kilogram|kilograms|g|gm|gms|gram|grams|ml|millilitre|millilitres|milliliter|milliliters|l|lt|ltr|litre|litres|liter|liters|pc|pcs|piece|pieces|pkt|pkts|packet|packets';
  const trailingPack = new RegExp(`^(.*?)(?:\\s+)(\\d+(?:\\.\\d+)?)\\s*(${unitPattern})?$`, 'i');

  function tidyText(value) {
    return String(value ?? '')
      .normalize('NFKC')
      .replace(invisibleChars, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function groupKey(value) {
    return tidyText(value)
      .toLocaleLowerCase('en-IN')
      .replace(/\s*\(\s*/g, '(')
      .replace(/\s*\)\s*/g, ')')
      .replace(/[._,\-/]+$/g, '')
      .trim();
  }

  function normalizeUnit(value) {
    const unit = tidyText(value).toLowerCase().replaceAll('.', '');
    const aliases = {
      g: 'gm', gm: 'gm', gms: 'gm', gram: 'gm', grams: 'gm',
      kg: 'kg', kgs: 'kg', kilogram: 'kg', kilograms: 'kg',
      ml: 'ml', millilitre: 'ml', millilitres: 'ml', milliliter: 'ml', milliliters: 'ml',
      l: 'ltr', lt: 'ltr', ltr: 'ltr', litre: 'ltr', litres: 'ltr', liter: 'ltr', liters: 'ltr',
      pc: 'pcs', pcs: 'pcs', piece: 'pcs', pieces: 'pcs',
      pkt: 'packet', pkts: 'packet', packet: 'packet', packets: 'packet',
    };
    return aliases[unit] || unit;
  }

  function cleanNumber(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return tidyText(value);
    return Number.isInteger(numeric) ? String(numeric) : String(numeric).replace(/0+$/, '').replace(/\.$/, '');
  }

  function splitVariant(item) {
    const originalName = tidyText(item?.name);
    let translation = '';
    let coreName = originalName;
    const translationMatch = originalName.match(/\s*(\([^()]*\))\s*$/);
    if (translationMatch) {
      translation = tidyText(translationMatch[1]);
      coreName = tidyText(originalName.slice(0, translationMatch.index));
    }

    let detectedSize = tidyText(item?.size);
    const packMatch = coreName.match(trailingPack);
    if (packMatch) {
      const numberText = packMatch[2];
      const embeddedUnit = packMatch[3] || '';
      const numeric = Number(numberText);
      const looksLikePack = Boolean(embeddedUnit) || Boolean(detectedSize) || (Number.isFinite(numeric) && numeric >= 10);
      if (looksLikePack) {
        coreName = tidyText(packMatch[1]).replace(/[\s\-_/,.]+$/g, '').trim();
        if (!detectedSize) {
          const normalizedEmbeddedUnit = normalizeUnit(embeddedUnit);
          detectedSize = `${cleanNumber(numberText)}${normalizedEmbeddedUnit ? ` ${normalizedEmbeddedUnit}` : ''}`.trim();
        }
      }
    }

    const baseName = tidyText(`${coreName}${translation ? ` ${translation}` : ''}`) || originalName || 'Unnamed Item';
    return {
      baseName,
      size: detectedSize,
    };
  }

  function variantSortValue(size) {
    const text = tidyText(size).toLowerCase();
    const value = Number.parseFloat(text);
    if (!Number.isFinite(value)) return { value: Number.MAX_SAFE_INTEGER, text };
    let multiplier = 1;
    if (/\bkg\b/.test(text)) multiplier = 1000;
    else if (/\bltr\b|\blitre\b|\bliter\b/.test(text)) multiplier = 1000;
    return { value: value * multiplier, text };
  }

  function pickPreferredVariant(current, candidate) {
    if (!current) return candidate;
    const currentStock = num(current.stock);
    const candidateStock = num(candidate.stock);
    if (candidateStock !== currentStock) return candidateStock > currentStock ? candidate : current;
    return num(candidate.id) > num(current.id) ? candidate : current;
  }

  renderItems = function renderGroupedItems() {
    const root = $('#items-cards');
    if (!root) return;

    const q = tidyText($('#item-filter')?.value).toLocaleLowerCase('en-IN');
    const lowOnly = Boolean($('#low-stock-btn')?.classList.contains('active-filter'));
    const groups = new Map();

    state.items.forEach(rawItem => {
      const parsed = splitVariant(rawItem);
      const item = { ...rawItem, display_name: parsed.baseName, display_size: parsed.size };
      const searchable = tidyText(`${rawItem.name} ${parsed.baseName} ${rawItem.sku} ${rawItem.barcode} ${rawItem.category} ${parsed.size} ${rawItem.unit}`).toLocaleLowerCase('en-IN');
      if (q && !searchable.includes(q)) return;
      if (lowOnly && num(rawItem.stock) > num(rawItem.min_stock)) return;

      const key = groupKey(parsed.baseName);
      if (!groups.has(key)) {
        groups.set(key, { name: parsed.baseName, variants: new Map() });
      }

      const sizeLabel = parsed.size || tidyText(rawItem.unit) || 'Default';
      const variantKey = groupKey(`${sizeLabel}|${normalizeUnit(rawItem.unit)}`);
      const group = groups.get(key);
      group.variants.set(variantKey, pickPreferredVariant(group.variants.get(variantKey), item));
    });

    const grouped = [...groups.values()].sort((a, b) =>
      a.name.localeCompare(b.name, 'en', { sensitivity: 'base', numeric: true })
    );

    root.innerHTML = grouped.map(group => {
      const variants = [...group.variants.values()].sort((a, b) => {
        const av = variantSortValue(a.display_size);
        const bv = variantSortValue(b.display_size);
        return av.value - bv.value || av.text.localeCompare(bv.text, 'en', { numeric: true });
      });
      const allLow = variants.every(item => num(item.stock) <= num(item.min_stock));

      return `
        <article class="item-card item-variant-card ${allLow ? 'low' : ''}">
          <div class="item-variant-head">
            <div>
              <h3>${esc(group.name)}</h3>
              <small>${variants.length} ${variants.length === 1 ? 'size' : 'sizes'}</small>
            </div>
            <span class="item-size-count">${variants.length === 1 ? esc(variants[0].display_size || variants[0].unit || 'Default') : 'All Sizes'}</span>
          </div>
          <div class="item-variant-list">
            ${variants.map(item => {
              const size = item.display_size || item.unit || 'Default';
              const low = num(item.stock) <= num(item.min_stock);
              return `
                <button type="button" class="item-variant-row ${low ? 'is-low' : ''}" data-edit-item="${item.id}">
                  <div class="item-variant-size">
                    <strong>${esc(size)}</strong>
                    <small>${esc(item.sku || item.barcode || '')}</small>
                  </div>
                  <div class="item-variant-value"><small>Sale</small><b>${money(item.sale_price)}</b></div>
                  <div class="item-variant-value"><small>Purchase</small><b>${money(item.purchase_price)}</b></div>
                  <div class="item-variant-value stock-value"><small>Stock</small><b class="${low ? 'negative' : 'positive'}">${item.stock} ${esc(item.unit || '')}</b></div>
                  <span class="item-variant-arrow">›</span>
                </button>`;
            }).join('')}
          </div>
        </article>`;
    }).join('') || emptyText('No items found');
  };
})();
"""


ITEM_GROUPING_CSS = r"""

/* Kirana Items Variant UI v0.4.3 */
.item-card.item-variant-card {
  padding: 0;
  overflow: hidden;
  border-left: 4px solid var(--primary, #0b7bc1);
}
.item-card.item-variant-card.low {
  border-left-color: var(--coral, #ef476f);
}
.item-variant-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 15px 16px 12px;
  border-bottom: 1px solid #edf0f4;
}
.item-variant-head h3 {
  margin: 0;
  font-size: 17px;
  line-height: 1.25;
}
.item-variant-head small {
  display: block;
  margin-top: 3px;
  color: #8a90a0;
  font-size: 12px;
}
.item-size-count {
  flex: 0 0 auto;
  padding: 6px 10px;
  border-radius: 999px;
  background: #eef5fb;
  color: #617083;
  font-size: 11px;
  font-weight: 700;
}
.item-variant-list {
  display: grid;
}
.item-variant-row {
  width: 100%;
  min-height: 68px;
  display: grid;
  grid-template-columns: minmax(72px, 1.15fr) repeat(3, minmax(62px, 1fr)) 14px;
  align-items: center;
  gap: 8px;
  padding: 11px 13px;
  border: 0;
  border-bottom: 1px solid #edf0f4;
  background: #fff;
  color: inherit;
  text-align: left;
}
.item-variant-row:last-child { border-bottom: 0; }
.item-variant-row:active { background: #f4f9fd; }
.item-variant-row.is-low { background: linear-gradient(90deg, rgba(239,71,111,.045), #fff 32%); }
.item-variant-size,
.item-variant-value {
  min-width: 0;
}
.item-variant-size strong {
  display: block;
  font-size: 15px;
  color: #313746;
}
.item-variant-size small,
.item-variant-value small {
  display: block;
  overflow: hidden;
  color: #9a9fad;
  font-size: 10px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-variant-value b {
  display: block;
  margin-top: 3px;
  overflow: hidden;
  color: #303644;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-variant-value.stock-value b.negative { color: #e43d68; }
.item-variant-value.stock-value b.positive { color: #19a974; }
.item-variant-arrow {
  color: #9aa1af;
  font-size: 25px;
  line-height: 1;
}
@media (max-width: 430px) {
  .item-variant-row {
    grid-template-columns: minmax(64px, 1.2fr) repeat(3, minmax(54px, 1fr)) 10px;
    gap: 5px;
    padding-inline: 10px;
  }
  .item-variant-value b { font-size: 12px; }
  .item-variant-size strong { font-size: 14px; }
}
"""


def no_cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }


@app.get("/app.js", include_in_schema=False)
def app_javascript_with_item_grouping() -> Response:
    base = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    return Response(
        content=f"{base}\n{ITEM_GROUPING_JS}",
        media_type="application/javascript",
        headers=no_cache_headers(),
    )


@app.get("/styles.css", include_in_schema=False)
def stylesheet_with_item_grouping() -> Response:
    base = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    return Response(
        content=f"{base}\n{ITEM_GROUPING_CSS}",
        media_type="text/css",
        headers=no_cache_headers(),
    )


@app.get("/sw.js", include_in_schema=False)
def refreshed_service_worker() -> Response:
    base = (STATIC_DIR / "sw.js").read_text(encoding="utf-8")
    base = base.replace("kirana-v0.4.1", "kirana-v0.4.3")
    return Response(
        content=base,
        media_type="application/javascript",
        headers=no_cache_headers(),
    )


# These exact asset routes must run before the generic /{path:path} SPA fallback.
extension_paths = {"/app.js", "/styles.css", "/sw.js"}
extension_routes = [route for route in app.router.routes if getattr(route, "path", None) in extension_paths]
other_routes = [route for route in app.router.routes if route not in extension_routes]
catch_all_index = next(
    (index for index, route in enumerate(other_routes) if getattr(route, "path", None) == "/{path:path}"),
    len(other_routes),
)
app.router.routes[:] = other_routes[:catch_all_index] + extension_routes + other_routes[catch_all_index:]
