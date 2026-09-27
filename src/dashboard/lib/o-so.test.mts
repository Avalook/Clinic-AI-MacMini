import assert from "node:assert/strict";
import test from "node:test";

import { buocLan, chuanHoaSo, locKhiGo, nhanVaDonVi } from "./o-so.ts";

test("đầu vào rác → rỗng / null, không ném", () => {
  for (const rac of [null, undefined, {}, [], Number.NaN, Infinity, true]) {
    assert.equal(locKhiGo(rac), "");
    assert.equal(chuanHoaSo(rac), "");
    assert.equal(buocLan(rac, 1), null);
    assert.deepEqual(nhanVaDonVi(rac), { nhan: "", donVi: null });
  }
  assert.equal(chuanHoaSo("abc"), null);
  assert.equal(chuanHoaSo("1.2.3"), null);
  assert.equal(chuanHoaSo("--1"), null);
  assert.equal(buocLan("36.6", Number.NaN), null);
  assert.equal(buocLan("36.6", 0), null);
});

test("dấu phẩy kiểu Việt và dấu chấm đều đọc được", () => {
  assert.equal(chuanHoaSo("36,6"), "36.6");
  assert.equal(chuanHoaSo("36.6"), "36.6");
  assert.equal(chuanHoaSo(" 36,60 "), "36.60");
  assert.equal(chuanHoaSo(",5"), "0.5");
  assert.equal(chuanHoaSo("37."), "37");
  assert.equal(chuanHoaSo("-0"), "0");
  assert.equal(chuanHoaSo("-2,5"), "-2.5");
  assert.equal(chuanHoaSo(""), "");
  assert.equal(chuanHoaSo("   "), "");
  assert.equal(chuanHoaSo(12), "12");
});

test("kích thước '12 x 8' chỉ khi ô cho phép", () => {
  assert.equal(chuanHoaSo("12 x 8"), null, "ô số thường không nhận hai chiều");
  assert.equal(chuanHoaSo("12 x 8", true), "12 x 8");
  assert.equal(chuanHoaSo("12x8", true), "12 x 8");
  assert.equal(chuanHoaSo("12,5 X 8", true), "12.5 x 8");
  assert.equal(chuanHoaSo("12 × 8 × 5", true), "12 x 8 x 5");
  assert.equal(chuanHoaSo("12*8", true), "12 x 8");
  assert.equal(chuanHoaSo("12 x", true), null);
  assert.equal(chuanHoaSo("1x2x3x4", true), null);
  assert.equal(chuanHoaSo("36,6", true), "36.6", "ô kích thước vẫn nhận một số");
});

test("lọc lúc gõ giữ nguyên chữ gõ dở", () => {
  assert.equal(locKhiGo("36,"), "36,");
  assert.equal(locKhiGo("36.6 độ"), "36.6 ", "chữ bỏ, rời ô mới cắt khoảng trắng");
  assert.equal(locKhiGo("12 x 8"), "12 x 8", "không lặng lẽ biến thành 128");
  assert.equal(locKhiGo("12 x 8 mm"), "12 x 8 ");
  assert.equal(locKhiGo("abc"), "");
});

test("lăn chuột theo hàng thập phân, không sai số thập phân", () => {
  assert.equal(buocLan("36.6", 1), "36.7");
  assert.equal(buocLan("36,6", -1), "36.5");
  assert.equal(buocLan("37", 1), "38");
  assert.equal(buocLan("0.1", 1), "0.2", "không ra 0.30000000000000004");
  assert.equal(buocLan("0.2", 1), "0.3");
  assert.equal(buocLan("1.25", 1), "1.26");
  assert.equal(buocLan("0", -1), "0", "không lăn xuống âm");
  assert.equal(buocLan("0.0", -1), "0.0");
  assert.equal(buocLan("-0.2", 1), "-0.1");
  assert.equal(buocLan("-0.1", 1), "0.0");
  assert.equal(buocLan("", 1), null, "ô trống: lăn không tự điền số");
  assert.equal(buocLan("12 x 8", 1), null);
});

test("đơn vị: khung có don_vi thì dùng, không thì tách từ nhãn", () => {
  assert.deepEqual(nhanVaDonVi("Chu kỳ kinh nguyệt (ngày)"), { nhan: "Chu kỳ kinh nguyệt", donVi: "ngày" });
  assert.deepEqual(nhanVaDonVi("IUI (số chu kỳ)"), { nhan: "IUI", donVi: "chu kỳ" });
  assert.deepEqual(nhanVaDonVi("Tuổi lần đầu thấy kinh"), { nhan: "Tuổi lần đầu thấy kinh", donVi: "tuổi" });
  assert.deepEqual(nhanVaDonVi("Số ngày hành kinh"), { nhan: "Số ngày hành kinh", donVi: "ngày" });
  assert.deepEqual(
    nhanVaDonVi("Thống kinh (Có/Không, độ)"),
    { nhan: "Thống kinh (Có/Không, độ)", donVi: null },
    "ngoặc là chú thích thì giữ nguyên nhãn",
  );
  assert.deepEqual(nhanVaDonVi("Cân nặng", "kg"), { nhan: "Cân nặng", donVi: "kg" });
  assert.deepEqual(nhanVaDonVi("PARA"), { nhan: "PARA", donVi: null });
});
