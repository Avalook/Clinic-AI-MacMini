import assert from "node:assert/strict";
import test from "node:test";

import { cauHoanTatPhieu, ghepConTrong, gopGiaTri, laMauDieuTri, tachGiaTri } from "./phieu-ket-qua.ts";

const khung = [
  { block: [{ ma: "a", ten: "Tử cung" }, { ma: "b", ten: "Buồng trứng" }] },
  { block: [{ ma: "c", ten: "Kết luận" }, { ma: "d", ten: "Kết luận" }, { ma: "e" }] },
];

test("ghepConTrong: gắn mã theo thứ tự khung, kể cả hai ô trùng tên", () => {
  assert.deepEqual(ghepConTrong(khung, ["Buồng trứng", "Kết luận"]), [
    { ma: "b", ten: "Buồng trứng" },
    { ma: "c", ten: "Kết luận" },
  ]);
  assert.deepEqual(ghepConTrong(khung, ["Kết luận", "Kết luận", "e"]), [
    { ma: "c", ten: "Kết luận" },
    { ma: "d", ten: "Kết luận" },
    { ma: "e", ten: "e" },
  ]);
  assert.deepEqual(ghepConTrong(khung, []), []);
});

test("ghepConTrong: rác không ném", () => {
  assert.deepEqual(ghepConTrong(khung, null), []);
  assert.deepEqual(ghepConTrong(khung, "Tử cung"), []);
  assert.deepEqual(ghepConTrong(khung, [1, null, "Tử cung"]), [{ ma: "a", ten: "Tử cung" }]);
  assert.deepEqual(ghepConTrong(khung, ["không có"]), []);
  assert.deepEqual(ghepConTrong([{ block: null }, {} as never], ["x"]), []);
});

test("gopGiaTri: ô bảng `ma::cột` gộp về một ô, bỏ ô rỗng", () => {
  assert.deepEqual(gopGiaTri({ a: "12", "t::A": "5", "t::B": "", "t::C": "7", b: "" }), {
    a: { gia_tri: "12", nguon: "USER" },
    t: { gia_tri: { A: "5", C: "7" }, nguon: "USER" },
  });
});

test("tachGiaTri ↔ gopGiaTri đi vòng không đổi", () => {
  const may = {
    a: { gia_tri: "12", nguon: "USER" },
    t: { gia_tri: { A: "5", C: "7" }, nguon: "USER" },
  };
  assert.deepEqual(tachGiaTri(may), { a: "12", "t::A": "5", "t::C": "7" });
  assert.deepEqual(gopGiaTri(tachGiaTri(may)), may);
  assert.deepEqual(tachGiaTri({ n: { gia_tri: null, nguon: "USER" } }), { n: "" });
});

test("phiếu điều trị: câu báo [Xong] là 'Đã xong <tên dịch vụ>', mẫu khác giữ câu cũ", () => {
  const goc = { tenDichVu: "Laser trẻ hoá tiền đình", daDongDichVu: true, viSao: null, laLanSua: false, conTrong: [] };
  assert.equal(cauHoanTatPhieu({ ...goc, mau: "KQ_PHIEU_DIEU_TRI" }), "Đã xong Laser trẻ hoá tiền đình.");
  assert.equal(cauHoanTatPhieu({ ...goc, mau: "PHIEU_DIEU_TRI" }), "Đã xong Laser trẻ hoá tiền đình.");
  assert.equal(cauHoanTatPhieu({ ...goc, mau: "MAU_PHIEU_DIEU_TRI", tenDichVu: "  " }), "Đã xong dịch vụ.");
  assert.equal(
    cauHoanTatPhieu({ ...goc, mau: "SIEU_AM_PHU_KHOA" }),
    "Đã hoàn tất phiếu, đóng dịch vụ và báo có kết quả.",
  );
  assert.equal(cauHoanTatPhieu({ ...goc, mau: null }), "Đã hoàn tất phiếu, đóng dịch vụ và báo có kết quả.");
  // Chưa đóng được dịch vụ thì KHÔNG nói "Đã xong" — kể cả phiếu điều trị.
  assert.equal(
    cauHoanTatPhieu({ ...goc, mau: "KQ_PHIEU_DIEU_TRI", daDongDichVu: false, viSao: "chưa thu tiền" }),
    "Đã hoàn tất phiếu. Dịch vụ CHƯA đóng: chưa thu tiền.",
  );
  assert.equal(
    cauHoanTatPhieu({ ...goc, mau: "KQ_PHIEU_DIEU_TRI", laLanSua: true, conTrong: ["Ghi chú"] }),
    "Đã ghi bản sửa của kết quả. Còn 1 mục trống: Ghi chú (chỉ nhắc).",
  );
  assert.equal(laMauDieuTri("KQ_PHIEU_DIEU_TRI_X"), false);
  assert.equal(laMauDieuTri(undefined), false);
});
