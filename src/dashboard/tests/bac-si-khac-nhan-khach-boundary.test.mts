import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Bác sĩ khác NHẬN khách (29/10/2026): lịch BS A quá tải, BS B nhận khám — màn
// chỉ vẽ + gửi lệnh; "ai nhận trước giữ", giữ lịch hẹn ở `DoiBacSiService`.

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const BAN_KHAM = "../app/(dashboard)/ban-kham/BanKham.tsx";

test("proxy: nhận / trả lại theo LƯỢT, nằm trong danh sách trắng", () => {
  const r = read("../app/api/luot-kham/route.ts");
  assert.match(r, /"nhan-khach": \(id\) => `\/api\/v1\/luot-kham\/visits\/\$\{id\}\/nhan-khach`/);
  assert.match(
    r,
    /"tra-khach-ve-lich": \(id\) => `\/api\/v1\/luot-kham\/visits\/\$\{id\}\/tra-khach-ve-lich`/,
  );
  assert.match(read("../app/(dashboard)/_lam-viec/hoan-tac.ts"), /\| "tra-khach-ve-lich"/);
});

test("bàn khám: nhóm 'Khách của bác sĩ khác' gập sẵn, [Nhận] + [Hoàn tác], nhãn Lịch", () => {
  const ui = read(BAN_KHAM);
  assert.match(ui, /khach_bac_si_khac\?: KhachBacSiKhac\[\]/);
  assert.match(ui, /Khách của bác sĩ khác \(\{ds\.length\}\)/);
  assert.match(ui, /guiThaoTac\("nhan-khach", d\.visit_id\)/);
  assert.match(ui, /lenhHoanTac\("tra-khach-ve-lich", d\.visit_id\)/);
  assert.match(ui, /<NhomBacSiKhac ds=\{bacSiKhac\} choBam=\{choBam\} onDaDoi=\{napLai\} \/>/);
  // Khách mình đã nhận vẫn thấy lịch hẹn là bác sĩ nào.
  assert.match(ui, /Lịch: \{d\.lich_bac_si\}/);
  // Gập sẵn: mặc định đóng.
  assert.match(ui, /function NhomBacSiKhac[\s\S]*?useState\(false\)/);
});
