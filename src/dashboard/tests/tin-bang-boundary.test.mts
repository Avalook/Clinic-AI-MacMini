// AI NGHE `SU_KIEN_BANG` PHẢI ĐỌC `TinBang` — máy kiểm phạm vi (16/11/2026).
//
// Từ 16/11 `detail` của `SU_KIEN_BANG` là `{t, v}` (hoặc `null`), không còn là chuỗi
// tên bảng. Người nghe còn so `detail === "slot_hold"` thì KHÔNG BAO GIỜ khớp — màn
// mất cập nhật tức thời mà không có gì đỏ: tsc không bắt được vì `CustomEvent` ép
// kiểu tuỳ ý, và nhịp dự phòng che đi phần lớn. Soát PR bắt được hai chỗ như vậy
// (màn Đặt lịch giữ chỗ, kịch bản e2e phiếu khám); máy này giữ cho không có chỗ thứ ba.
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

function moiFile(thuMuc: string, ra: string[] = []): string[] {
  for (const ten of readdirSync(thuMuc)) {
    if (ten === "node_modules" || ten === ".next" || ten.startsWith(".")) continue;
    const con = join(thuMuc, ten);
    if (statSync(con).isDirectory()) moiFile(con, ra);
    else if (/\.(tsx?|mjs|mts)$/.test(ten) && !/\.test\.mts$/.test(ten)) ra.push(con);
  }
  return ra;
}

const GOC = fileURLToPath(new URL("../", import.meta.url));
const NGUON = ["app", "lib", "components", "e2e"]
  .map((d) => join(GOC, d))
  .filter((d) => existsSync(d))
  .flatMap((d) => moiFile(d));

test("mọi tay nghe SU_KIEN_BANG đọc detail bằng TinBang", () => {
  const nghe = NGUON.filter((f) => /addEventListener\(SU_KIEN_BANG/.test(readFileSync(f, "utf8")));
  assert.ok(nghe.length >= 3, `phải thấy các tay nghe (useNgheBang, giữ chỗ, phiếu): ${nghe.length}`);
  for (const f of nghe) {
    const ma = readFileSync(f, "utf8");
    assert.match(ma, /TinBang/, `${f}: detail là {t, v} — đọc bằng TinBang / canHoiLai, đừng so chuỗi`);
    assert.doesNotMatch(ma, /CustomEvent<string/, `${f}: detail không còn là chuỗi`);
  }
});

test("không ai phát SU_KIEN_BANG với detail là chuỗi tên bảng", () => {
  for (const f of NGUON) {
    const ma = readFileSync(f, "utf8");
    assert.doesNotMatch(ma, /bang-doi['"],\s*\{\s*detail:\s*['"]/, `${f}: detail phải là {t, v}`);
  }
});
