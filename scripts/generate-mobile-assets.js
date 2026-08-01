const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

const assetsDir = path.join(__dirname, "..", "assets");
fs.mkdirSync(assetsDir, { recursive: true });

const crcTable = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(buffer) {
  let c = 0xffffffff;
  for (const byte of buffer) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const typeBuffer = Buffer.from(type, "ascii");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 0);
  return Buffer.concat([length, typeBuffer, data, crc]);
}

function makePng(width, height, pixel) {
  const raw = Buffer.alloc((width * 4 + 1) * height);
  let offset = 0;
  for (let y = 0; y < height; y += 1) {
    raw[offset++] = 0;
    for (let x = 0; x < width; x += 1) {
      const [r, g, b, a] = pixel(x, y);
      raw[offset++] = r;
      raw[offset++] = g;
      raw[offset++] = b;
      raw[offset++] = a;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  return Buffer.concat([
    signature,
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0))
  ]);
}

function insideRoundedRect(x, y, left, top, right, bottom, radius) {
  if (x >= left + radius && x <= right - radius && y >= top && y <= bottom) return true;
  if (x >= left && x <= right && y >= top + radius && y <= bottom - radius) return true;
  const centers = [
    [left + radius, top + radius],
    [right - radius, top + radius],
    [left + radius, bottom - radius],
    [right - radius, bottom - radius]
  ];
  return centers.some(([cx, cy]) => ((x - cx) ** 2 + (y - cy) ** 2) <= radius ** 2);
}

function distanceToSegment(x, y, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lengthSq = dx * dx + dy * dy;
  const t = Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / lengthSq));
  const px = x1 + t * dx;
  const py = y1 + t * dy;
  return Math.hypot(x - px, y - py);
}

function isK(x, y, scale = 1, offsetX = 0, offsetY = 0) {
  const sx = (x - offsetX) / scale;
  const sy = (y - offsetY) / scale;
  const vertical = sx >= 145 && sx <= 200 && sy >= 115 && sy <= 397;
  const upper = distanceToSegment(sx, sy, 185, 260, 350, 120) <= 30;
  const lower = distanceToSegment(sx, sy, 185, 255, 350, 395) <= 30;
  return vertical || upper || lower;
}

const icon = makePng(512, 512, (x, y) => {
  const tile = insideRoundedRect(x, y, 44, 44, 468, 468, 108);
  const base = tile ? [15, 145, 207, 255] : [11, 130, 194, 255];
  return isK(x, y) ? [255, 255, 255, 255] : base;
});

const adaptive = makePng(512, 512, (x, y) => {
  const tile = insideRoundedRect(x, y, 105, 105, 407, 407, 86);
  if (!tile) return [0, 0, 0, 0];
  return isK(x, y, 0.66, 87, 87) ? [255, 255, 255, 255] : [11, 130, 194, 255];
});

fs.writeFileSync(path.join(assetsDir, "icon.png"), icon);
fs.writeFileSync(path.join(assetsDir, "adaptive-icon.png"), adaptive);
fs.writeFileSync(path.join(assetsDir, "splash.png"), icon);
console.log("Kirana mobile PNG assets generated successfully");
