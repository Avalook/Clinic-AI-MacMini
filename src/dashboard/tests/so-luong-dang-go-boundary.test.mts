// Ô "Số lượng" của khung chỉnh đơn quầy (`ChinhDonQuay`) — sửa số mà tổng tiền không
// tính lại (prod 27/11/2026).
//
// Máy chủ tính đúng: 7 lượt sửa số 23–26/11, phiếu thu khớp số trên đơn 0 dòng lệch.
// Gốc là số gõ vào KHÔNG được gửi đi, theo ba đường:
//   1. chỉ gửi khi rời ô — gõ xong vuốt xuống xem Tổng (điện thoại) là chưa gửi;
//   2. lưu xong một dòng, nạp lại xoá trắng số đang gõ ở dòng khác (`setSoNhap({})`)
//      → rời ô thì thấy ô trống, không gửi;
//   3. số nằm trong `useState` — khung gắn lại (prod 16/11: 30 lần / 25′) là mất.
// Thêm: hai lần lưu chen nhau thì lần xong trước gỡ chữ "đang tính lại…" khi lần
// sau chưa xong → Tổng hiện số giữa chừng.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { demSau } from "../lib/dem-dang-chay.ts";
import { SO_RONG, soCanGui, taoKhoSoDangGo } from "../lib/so-dang-go.ts";

const GOC = new URL("../", import.meta.url);
const boChuThich = (ma: string) =>
  ma.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const doc = (p: string) => boChuThich(readFileSync(new URL(p, GOC), "utf8"));
const chinh = doc("app/(dashboard)/thu-ngan/ChinhDonQuay.tsx");

// ── Kho số đang gõ ──────────────────────────────────────────────────────────
test("kho: tách theo lượt; lượt chưa gõ trả CÙNG một tham chiếu rỗng", () => {
  const kho = taoKhoSoDangGo();
  assert.equal(kho.doc("v1"), SO_RONG);
  assert.equal(kho.doc("v1"), kho.doc("v1"));
  kho.ghi("v1", "a", "3");
  assert.deepEqual(kho.doc("v1"), { a: "3" });
  assert.equal(kho.doc("v2"), SO_RONG);
});

test("kho: lưu xong dòng A chỉ bỏ nháp của A, số đang gõ ở dòng B còn nguyên (đường 2)", () => {
  const kho = taoKhoSoDangGo();
  kho.ghi("v1", "a", "2");
  kho.ghi("v1", "b", "5");
  kho.boNeuBang("v1", "a", "2");
  assert.deepEqual(kho.doc("v1"), { b: "5" });
});

test("kho: đang lưu '2' mà quầy gõ tiếp thành '25' thì KHÔNG bỏ nháp '25'", () => {
  const kho = taoKhoSoDangGo();
  kho.ghi("v1", "a", "25");
  kho.boNeuBang("v1", "a", "2");
  assert.deepEqual(kho.doc("v1"), { a: "25" });
});

test("kho: ghi báo người nghe; bỏ hết thì về tham chiếu rỗng", () => {
  const kho = taoKhoSoDangGo();
  let lan = 0;
  const thoi = kho.nghe(() => lan++);
  kho.ghi("v1", "a", "1");
  kho.boNeuBang("v1", "a", "1");
  assert.equal(lan, 2);
  assert.equal(kho.doc("v1"), SO_RONG);
  thoi();
  kho.ghi("v1", "a", "1");
  assert.equal(lan, 2);
});

// ── Có gửi không, gửi số nào ────────────────────────────────────────────────
test("soCanGui: không gõ / số không đổi thì không gửi", () => {
  assert.equal(soCanGui(undefined, "2"), null);
  assert.equal(soCanGui("2", "2"), null);
  assert.equal(soCanGui("2,0", "2"), null);
});

// Tuyền chốt 27/11 (bấm staging): xoá trống ô số lượng rồi rời ô = khách không lấy
// dòng đó → bỏ tick (tick lại là hoàn tác). Dòng vốn chưa có số mà ô vẫn trống thì
// không làm gì (bấm vào rồi bấm ra không được bỏ tick nhầm).
test("soCanGui: xoá trống dòng đang có số → bỏ tick; dòng chưa có số → không làm gì", () => {
  assert.deepEqual(soCanGui("", "2"), { boTick: true });
  assert.deepEqual(soCanGui("   ", "1"), { boTick: true });
  assert.equal(soCanGui("", null), null);
});

test("ô trống KHÔNG tự lưu theo giờ (đang xoá để gõ số mới thì không nhảy về số cũ)", () => {
  assert.match(hook, /if \(chu\.trim\(\) === ""\) return;/);
});

test("xoá trống + rời ô gọi đúng lệnh bỏ tick của khung", () => {
  assert.match(hook, /if \("boTick" in kq\) \{[^}]*goi\.current\.boChon\(d\)/);
  assert.match(chinh, /boChon: \(d\) => chon\(d, false\)/);
});

test("soCanGui: đổi số thì gửi số (dấu phẩy thập phân được)", () => {
  assert.deepEqual(soCanGui("3", "2"), { so: 3 });
  assert.deepEqual(soCanGui("1,5", null), { so: 1.5 });
  assert.deepEqual(soCanGui(" 4 ", null), { so: 4 });
});

test("soCanGui: gõ chữ thì báo câu, KHÔNG gửi rỗng lên máy chủ", () => {
  const kq = soCanGui("2 hộp", "1");
  assert.ok(kq && "loi" in kq && kq.loi.length > 0);
  assert.ok(soCanGui("abc", null) && "loi" in (soCanGui("abc", null) ?? {}));
});

// ── Khung dùng kho + tự lưu (máy giữ không ai đưa về state) ─────────────────
const hook = doc("app/(dashboard)/thu-ngan/useSoLuongTuLuu.ts");

test("số đang gõ đọc từ kho theo lượt, không từ useState (đường 3)", () => {
  assert.match(
    hook,
    /useSyncExternalStore\(\s*khoSoDangGo\.nghe,\s*\(\) => khoSoDangGo\.doc\(visitId\)/,
  );
  assert.match(chinh, /const \{ soNhap, go, doiSo \} = useSoLuongTuLuu\(/);
  assert.doesNotMatch(chinh, /useState<Record<string, string>>/);
  assert.doesNotMatch(chinh, /setSoNhap/);
});

test("nạp lại đơn không xoá số đang gõ; chỉ bỏ nháp đúng dòng vừa lưu (đường 2)", () => {
  assert.doesNotMatch(chinh, /\(\{\}\)/, "không còn lệnh xoá trắng nháp");
  assert.match(hook, /finally \{[^}]*khoSoDangGo\.boNeuBang\(visitId, id, v\)/);
});

test("ô Số lượng: tự lưu khi ngừng gõ, lưu khi Enter, lưu khi rời ô (đường 1)", () => {
  // Hẹn gửi phải nằm NGAY trong hàm gõ `go` (đoạn hẹn lại lúc gắn lại không tính).
  assert.match(
    hook,
    /const go = \(id: string, chu: string\) => \{[^}]*khoSoDangGo\.ghi\(visitId, id, chu\);[^}]*setTimeout\(\(\) => void doiSo\(id\), CHO_GO_MS\)/,
  );
  assert.match(chinh, /onChange=\{\(e\) => go\(d\.id, e\.target\.value\)\}/);
  assert.match(chinh, /e\.key === "Enter"/);
  assert.match(chinh, /onBlur=\{\(\) => void doiSo\(d\.id\)\}/);
});

test("lệnh số lượng đi qua batDau/xong như mọi lệnh khác (màn cha che Tổng)", () => {
  assert.match(chinh, /luu: \(d, so\) =>\s*lenh\(\{ thao_tac: "so-luong"/);
  assert.match(
    chinh,
    /const lenh = async \([^)]*\) => \{\s*batDau\(\);\s*const loi = await gui\(than\);\s*hetChay\(\);\s*await xong\(loi, cau\);/,
  );
});

test("ô Số lượng không bị khoá trong lúc lưu (tự lưu không giật con trỏ)", () => {
  const o = chinh.match(/aria-label=\{`Số lượng \$\{d\.ten\}`\}/);
  assert.ok(o, "còn ô Số lượng");
  const khoi = chinh.slice(chinh.lastIndexOf("<input", o.index), o.index);
  assert.match(khoi, /disabled=\{!d\.mua \|\| d\.da_chot\}/);
});

test("nạp lại đứt mạng vẫn báo cha (không kẹt 'đang tính lại…')", () => {
  assert.match(chinh, /try \{\s*await tai\(\);\s*\} finally \{\s*await onDoi\(/);
});

test("hẹn giờ nổ khi dòng đã bỏ tick / đã chốt thì không gửi", () => {
  assert.match(hook, /if \(kq === null \|\| !d\.mua \|\| d\.da_chot\)/);
});

test("khung gắn lại mà còn nháp chưa gửi thì tự hẹn gửi lại; nháp trống thì bỏ, không bỏ tick", () => {
  assert.match(hook, /Object\.entries\(khoSoDangGo\.doc\(visitId\)\)/);
  assert.match(hook, /if \(chu\.trim\(\) === ""\) khoSoDangGo\.boNeuBang\(visitId, id, chu\);/);
});

// ── Màn cha che Tổng tới khi lần lưu CUỐI xong ──────────────────────────────
test("demSau: hai lần chỉnh chen nhau — lần đầu xong vẫn còn che; lần cuối xong mới mở", () => {
  let n = 0;
  n = demSau(n, "bat-dau");
  n = demSau(n, "bat-dau");
  n = demSau(n, "xong");
  assert.ok(n > 0, "lần sau chưa xong → vẫn 'đang tính lại…'");
  n = demSau(n, "xong");
  assert.equal(n, 0);
  assert.equal(demSau(0, "xong"), 0, "báo xong mà chưa báo bắt đầu (gỡ dòng lệch) không âm");
});

for (const [tep, che] of [
  ["app/(dashboard)/thu-ngan/QuayThuNgan.tsx", /dangTinhLai=\{chinh\.dang && tinhLai === l\.visit_id\}/],
  ["app/(dashboard)/pharmacy/BanLeThu.tsx", /dangTinhLai=\{chinh\.dang\}/],
] as const) {
  test(`${tep}: che Tổng theo bộ đếm useDemDangChay`, () => {
    const ma = doc(tep);
    assert.match(ma, /const chinh = useDemDangChay\(\)/);
    assert.match(ma, /onBatDau=\{[^}]*chinh\.batDau/);
    assert.match(ma, /finally \{\s*chinh\.xong\(\);/);
    assert.match(ma, che);
  });
}
