import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// "Hôm nào xong hôm đó" (29/10/2026): chỉ định cũ chưa làm hiện ở bàn khám để
// bác sĩ quyết — màn chỉ vẽ + gửi lệnh, luật ở `chi_dinh_cu_service`.

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const KHUNG = "../app/(dashboard)/_lam-viec/phieu-kham/ChiDinhCuChuaLam.tsx";

test("proxy: đọc theo lượt, hai lệnh theo chỉ định (danh sách trắng)", () => {
  const r = read("../app/api/luot-kham/route.ts");
  assert.match(r, /xem === "chi-dinh-cu"/);
  assert.match(r, /\/api\/v1\/luot-kham\/visits\/\$\{luot\}\/chi-dinh-cu/);
  assert.match(r, /"lam-hom-nay": \(id\) => `\/api\/v1\/luot-kham\/orders\/\$\{id\}\/lam-hom-nay`/);
  assert.match(r, /"tra-ve-luot-cu": \(id\) => `\/api\/v1\/luot-kham\/orders\/\$\{id\}\/tra-ve-luot-cu`/);
});

test("khung: [Làm hôm nay] gửi lệnh, [Hoàn tác] trả về lượt cũ, nhãn tiền do máy chủ nói", () => {
  const ui = read(KHUNG);
  assert.match(ui, /docBang<\{ chi_dinh_cu: ChiDinhCu\[\] \}>\("chi-dinh-cu"/);
  assert.match(ui, /guiThaoTac\("lam-hom-nay", c\.order_id, \{ visit_id: visitId \}\)/);
  assert.match(ui, /lenhHoanTac\("tra-ve-luot-cu", c\.order_id, \{ visit_id: visitId \}\)/);
  assert.match(ui, /\{c\.nhan_tien\}/);
  // Không tự tính tiền / trạng thái ở màn.
  assert.doesNotMatch(ui, /finance_state|PAID|\.reduce\(|window\.confirm/);
  assert.doesNotMatch(ui, /<button(?![^>]*type=)/);
});

test("khung nằm ở khối đầu phiếu khám bàn khám, chỉ bấm được khi phiếu đang ghi", () => {
  const p = read("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
  assert.match(p, /import ChiDinhCuChuaLam from "\.\/ChiDinhCuChuaLam"/);
  assert.match(p, /<ChiDinhCuChuaLam\s+visitId=\{visitId\}\s+choGhi=\{choGhi\}/);
  assert.match(read("../app/(dashboard)/_lam-viec/hoan-tac.ts"), /\| "tra-ve-luot-cu"/);
});
