// KẾT QUẢ SIÊU ÂM PHỤ KHOA: Ô CÓ CẤU TRÚC, KHÔNG PHẢI MỘT ĐOẠN VĂN.
//
// Tuyền chốt 16/09/2026. `ultrasound_record.findings` là jsonb có cấu trúc từ
// đầu, nhưng màn nhập chỉ có một ô mô tả rồi gói thành `{mo_ta: "..."}` — nên
// nội mạc 8.5mm, AFC 8, buồng trứng 32×24×26 nằm lẫn trong văn xuôi: không so
// được giữa hai lần khám, không lọc, không đếm.

import assert from "node:assert/strict";
import test from "node:test";

import {
  doVaoO,
  dungFindings,
} from "../app/(dashboard)/sieu-am/ket-qua-phu-khoa-du-lieu.ts";

test("ô trống KHÁC số 0 — không đo thì không có khoá", () => {
  // 0 là một phép đo ("không thấy nang nào"); trống là "không đo". Đổi trống
  // thành 0 là bịa ra một quan sát chưa ai làm.
  assert.equal(dungFindings({}, ""), null);
  const chiAfc = dungFindings({ btp_afc: "0" }, "");
  assert.deepEqual(chiAfc, { buong_trung_phai: { afc: 0 } });
});

test("gom đúng nhóm, bỏ khoá rỗng", () => {
  const f = dungFindings(
    {
      tc_d: "45",
      tc_r: "38",
      tc_c: "42",
      tc_tu_the: "Ngả trước",
      nm_day: "8.5",
      btp_afc: "8",
      btt_afc: "7",
      dich: "Không có",
    },
    "Không thấy khối bất thường",
  );
  assert.deepEqual(f, {
    tu_cung: { d: 45, r: 38, c: 42, tu_the: "Ngả trước" },
    noi_mac: { day_mm: 8.5 },
    buong_trung_phai: { afc: 8 },
    buong_trung_trai: { afc: 7 },
    dich_o_bung: "Không có",
    mo_ta: "Không thấy khối bất thường",
  });
});

test("số gõ sai không lọt xuống database", () => {
  // Người đo gõ nhầm chữ vào ô số: bỏ qua ô ấy, KHÔNG lưu NaN.
  const f = dungFindings({ nm_day: "tám phẩy năm" }, "");
  assert.equal(f, null);
});

test("mở lại sửa được — findings đã lưu quay về đúng ô", () => {
  const o = doVaoO({
    tu_cung: { d: 45, hinh_dang: "Bình thường" },
    noi_mac: { day_mm: 8.5, hinh_anh: "Đồng nhất" },
    buong_trung_trai: { the_tich: 8.6, afc: 7 },
  });
  assert.equal(o.tc_d, "45");
  assert.equal(o.tc_hinh_dang, "Bình thường");
  assert.equal(o.nm_day, "8.5");
  assert.equal(o.btt_the_tich, "8.6");
  assert.equal(o.btt_afc, "7");
  // Khoá không có trong bản ghi cũ → ô trống, không phải "undefined".
  assert.equal(o.btp_afc, "");
});

test("bản ghi cũ kiểu một dòng vẫn mở được", () => {
  // Trước 16/09 mọi kết quả lưu dạng {mo_ta}. Mở một bản ghi như thế không
  // được vỡ, và không được biến đoạn văn ấy thành số.
  const o = doVaoO({ mo_ta: "Tử cung bình thường" });
  assert.equal(o.tc_d, "");
  assert.equal(o.phan_phu, "");
});
