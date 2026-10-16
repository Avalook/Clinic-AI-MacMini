// CHỈ ĐỊNH TICK CHƯA GỬI (14/10/2026, bấm thật staging): bác sĩ tick dịch vụ ở
// khối 2 rồi bấm [Hoàn tất] mà chưa bấm "Chỉ định N mục" → tick mất âm thầm,
// khách sang quầy thu không có chỉ định. Khoá: còn tick chưa gửi thì Hoàn tất
// KHÔNG gọi thẳng `kham-xong`; hỏi tại chỗ bằng XacNhanTaiCho (không window.confirm).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  cauChiDinhChuaGui,
  conChiDinhChuaGui,
  gopChiDinhChuaGui,
  guiRoiTiep,
  type ChiDinhChuaGui,
} from "../lib/chi-dinh-chua-gui.ts";

const read = (path: string): string => readFileSync(new URL(path, import.meta.url), "utf8");

function khoi(soMuc: number, gui: boolean, nhatKy: string[], ten = "k"): ChiDinhChuaGui {
  return {
    soMuc,
    guiNgay: async () => {
      nhatKy.push(`gui-${ten}`);
      return gui;
    },
    boChon: () => {
      nhatKy.push(`bo-${ten}`);
    },
  };
}

test("conChiDinhChuaGui: chỉ true khi còn ≥ 1 mục tick", () => {
  assert.equal(conChiDinhChuaGui(null), false);
  assert.equal(conChiDinhChuaGui(undefined), false);
  assert.equal(conChiDinhChuaGui(khoi(0, true, [])), false);
  assert.equal(conChiDinhChuaGui(khoi(2, true, [])), true);
});

test("cauChiDinhChuaGui: nói rõ số mục và hai lối ra", () => {
  const cau = cauChiDinhChuaGui(3);
  assert.match(cau, /Còn 3 mục đã chọn chưa gửi chỉ định/);
  assert.match(cau, /Chỉ định 3 mục/);
  assert.match(cau, /bỏ tick/);
});

test("gopChiDinhChuaGui: không khối nào còn tick → null; cộng số mục; gửi/bỏ cả hai", async () => {
  assert.equal(gopChiDinhChuaGui([null, undefined, khoi(0, true, [])]), null);
  const nk: string[] = [];
  const gop = gopChiDinhChuaGui([khoi(2, true, nk, "cls"), null, khoi(1, true, nk, "tt")]);
  assert.equal(gop?.soMuc, 3);
  assert.equal(await gop?.guiNgay(), true);
  assert.deepEqual(nk, ["gui-cls", "gui-tt"]);
  gop?.boChon();
  assert.deepEqual(nk.slice(2), ["bo-cls", "bo-tt"]);
});

test("gopChiDinhChuaGui: khối đầu gửi hỏng thì dừng, không gửi nửa chừng", async () => {
  const nk: string[] = [];
  const gop = gopChiDinhChuaGui([khoi(1, false, nk, "cls"), khoi(1, true, nk, "tt")]);
  assert.equal(await gop?.guiNgay(), false);
  assert.deepEqual(nk, ["gui-cls"]);
});

test("guiRoiTiep: gửi xong mới chạy bước kế; gửi hỏng thì KHÔNG chạy bước kế", async () => {
  const nk: string[] = [];
  const tiep = () => {
    nk.push("tiep");
  };
  assert.equal(await guiRoiTiep(khoi(2, true, nk), tiep), true);
  assert.deepEqual(nk, ["gui-k", "tiep"]);
  nk.length = 0;
  assert.equal(await guiRoiTiep(khoi(2, false, nk), tiep), false);
  assert.deepEqual(nk, ["gui-k"], "gửi hỏng → không hoàn tất / không chuyển khách");
});

const banKham = read("../app/(dashboard)/ban-kham/BanKham.tsx");
const phieuLuot = read("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
const danhMuc = read("../app/(dashboard)/_lam-viec/phieu-kham/DanhMucChiDinh.tsx");

test("Bàn khám: còn tick chưa gửi thì Hoàn tất dừng TRƯỚC khi gọi gui / guiThaoTac", () => {
  const dau = banKham.indexOf("const bam = async");
  assert.ok(dau > 0);
  const than = banKham.slice(dau, banKham.indexOf("const t = tone(dong)", dau));
  const chan = than.indexOf("conChiDinhChuaGui(chuaGui)");
  const hoi = than.indexOf("setHoiChiDinh(");
  const gate = than.indexOf("if (!completionGate)");
  const gui = than.indexOf("await gui(thaoTac)");
  assert.ok(chan > 0 && hoi > chan, "phải kiểm tick chưa gửi rồi mở dải hỏi");
  assert.ok(gate > hoi, "cổng lưu phiếu chạy SAU khi đã xử lý chỉ định");
  assert.ok(gui > hoi, "lệnh gửi chỉ sau dải hỏi");
  assert.match(than.slice(chan, gate), /return;/, "chặn thật: return, không đi tiếp");
  assert.doesNotMatch(than.slice(0, hoi), /guiThaoTac\(|await gui\(/);
});

test("Bàn khám: dải hỏi dùng XacNhanTaiCho, đủ hai nút, [Chỉ định ngay] gửi rồi mới Hoàn tất", () => {
  assert.doesNotMatch(banKham, /window\.confirm\(/);
  assert.match(banKham, /nhanDongY="Chỉ định ngay rồi hoàn tất"/);
  assert.match(banKham, /nhanThoi="Bỏ chọn"/);
  assert.match(banKham, /guiRoiTiep\(chuaGui,[\s\S]{0,200}bam\(thaoTac, true\)/);
  assert.match(banKham, /cau=\{cauChiDinhChuaGui\(chuaGui\.soMuc\)\}/);
});

test("Bàn khám: đổi khách / phòng / ngày khi còn tick chưa gửi cũng phải qua dải hỏi", () => {
  assert.match(
    banKham,
    /const chonKhach = useCallback\(\(id: string\) => chuyenDi\(\(\) => moKhach\(id\)\)/,
  );
  assert.match(banKham, /nhanThoi="Bỏ chọn và chuyển"/);
  assert.match(banKham, /chuyenDi\(\(\) => \{\s*setChonId\(null\)/);
  assert.match(banKham, /chuyenDi\(\(\) => \{\s*setHang\(null\)/);
});

test("Dải hỏi là chữ trung tính — không hộp vàng/đỏ cho việc bình thường", () => {
  const dai = banKham.slice(banKham.indexOf('nhanDongY="Chỉ định ngay rồi hoàn tất"'));
  assert.doesNotMatch(dai.slice(0, 600), /bg-warning|bg-danger|text-warning/);
  assert.doesNotMatch(read("../lib/chi-dinh-chua-gui.ts"), /warning|danger/);
});

test("Khối chỉ định báo tick chưa gửi lên màn cha, cả hai danh mục (cận lâm sàng + thủ thuật)", () => {
  assert.match(danhMuc, /onChuaGui\?: \(c: ChiDinhChuaGui \| null\) => void/);
  assert.match(danhMuc, /guiNgay: \(\) => datMoiNhat\.current\(\)/);
  assert.match(phieuLuot, /gopChiDinhChuaGui\(Object\.values\(chuaGuiTheo\)\)/);
  assert.equal((phieuLuot.match(/onChuaGui=\{baoChuaGuiCls\}/g) ?? []).length, 2);
  assert.equal((phieuLuot.match(/onChuaGui=\{baoChuaGuiTt\}/g) ?? []).length, 2);
  assert.match(banKham, /onChuaGui=\{baoChuaGui\}/);
});
