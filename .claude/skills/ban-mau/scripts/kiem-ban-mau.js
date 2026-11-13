// Kiểm một artboard .dc.html ngoài trình duyệt:
//   1. mọi {{hole}} trong khuôn phải có trong renderVals() (thiếu là im lặng ra rỗng),
//   2. chạy kịch bản logic (tuỳ chọn) với class Component của chính artboard.
// Dùng: node kiem-ban-mau.js Main.dc.html [kich-ban.js]
// kich-ban.js: module.exports = function (Component, ok) { const c = new Component({}); ... ok(dieuKien, 'mô tả'); }
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(process.argv[2], 'utf8');
const js = html.match(/<script type="text\/x-dc"[^>]*>([\s\S]*?)<\/script>/)[1];
class DCLogic {
  constructor(p) { this.props = p || {}; this.state = {}; }
  setState(o) { Object.assign(this.state, o); }
}
const Component = new Function('DCLogic', js + '; return Component;')(DCLogic);

const tpl = html.match(/<x-dc>([\s\S]*)<\/x-dc>/)[1];
const bienLap = new Set([...tpl.matchAll(/as="(\w+)"/g)].map((m) => m[1]));
const holes = new Set([...tpl.matchAll(/\{\{\s*([\w.$]+)\s*\}\}/g)].map((m) => m[1].split('.')[0]));
const v0 = new Component({}).renderVals();
let thieu = 0;
for (const h of holes) {
  if (!(h in v0) && !bienLap.has(h) && h !== 'true' && h !== 'false') { console.log('THIẾU HOLE:', h); thieu++; }
}

let dung = 0, sai = 0;
const ok = (t, moTa) => { if (t) dung++; else sai++; console.log(t ? 'ok ' : 'SAI', moTa); };
if (process.argv[3]) require(path.resolve(process.argv[3]))(Component, ok);

console.log(`\nHole thiếu: ${thieu} · đúng: ${dung} · sai: ${sai}`);
process.exit(thieu || sai ? 1 : 0);
