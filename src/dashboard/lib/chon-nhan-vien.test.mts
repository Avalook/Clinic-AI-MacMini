import assert from "node:assert/strict";
import test from "node:test";

import { dangTim, khopNhanVien, nhomNhanVien, MA_NHOM_KHAC } from "./chon-nhan-vien.ts";

const DS = [
  { id: "1", name: "Bác sĩ nội tiết Lê Thiệu Quyết", vai: "DOCTOR", hoTen: "Bác sĩ · BSNT. Lê Thiệu Quyết" },
  { id: "2", name: "Điều dưỡng Nguyễn Thị Diễm Thuý", vai: "NURSE_ULTRASOUND", tenNgan: "Thuý" },
  { id: "3", name: "Hà Vũ", vai: "TRUONG_CA" },
  { id: "4", name: "Quỳnh Anh", vai: "CSKH" },
  { id: "5", name: "Bác sĩ Phan Chí Thành", vai: "DOCTOR" },
  { id: "6", name: "Thư", vai: "TKYK" },
  { id: "7", name: "Người lạ", vai: null },
  { id: "8", name: "Mã sai", vai: "KHONG_CO" },
];

test("thứ tự nhóm: Bác sĩ, Điều dưỡng, Trưởng ca, CSKH, rồi vai khác, cuối là Khác", () => {
  const nhom = nhomNhanVien(DS);
  assert.deepEqual(
    nhom.map((n) => n.nhan),
    ["Bác sĩ", "Điều dưỡng", "Trưởng ca", "CSKH", "Thư ký Y khoa", "Khác"],
  );
  assert.equal(nhom.at(-1)?.ma, MA_NHOM_KHAC);
  assert.deepEqual(
    nhom.at(-1)?.nguoi.map((n) => n.id),
    ["8", "7"],
    "không có vai hoặc mã lạ → Khác, xếp theo tên",
  );
});

test("trong nhóm xếp theo tên tiếng Việt", () => {
  const bs = nhomNhanVien(DS)[0];
  // "Bác sĩ nội…" trước "Bác sĩ Phan…" (n < p, không phân biệt hoa thường).
  assert.deepEqual(bs.nguoi.map((n) => n.id), ["1", "5"]);
});

test("tìm không dấu / có dấu, khớp cả họ, đệm, tên", () => {
  assert.ok(khopNhanVien("le quyet", DS[0]));
  assert.ok(khopNhanVien("Thiệu", DS[0]), "tên đệm");
  assert.ok(khopNhanVien("LÊ", DS[0]), "họ, hoa thường");
  assert.ok(khopNhanVien("bsnt", DS[0]), "chữ đang lưu trong full_name");
  assert.ok(khopNhanVien("thuy", DS[1]), "Thuý ↔ thuy");
  assert.ok(khopNhanVien("diem thuy", DS[1]));
  assert.ok(!khopNhanVien("quyet", DS[1]));
  assert.ok(khopNhanVien("duong", DS[1]), "Điều dưỡng → đ thành d");
});

test("đang tìm thì chỉ còn nhóm có kết quả", () => {
  const nhom = nhomNhanVien(DS, "thanh");
  assert.deepEqual(nhom.map((n) => n.ma), ["DOCTOR"]);
  assert.deepEqual(nhom[0].nguoi.map((n) => n.id), ["5"]);
  assert.deepEqual(nhomNhanVien(DS, "khong ai ten nay"), []);
});

test("ca biên: rỗng, null, chuỗi rác, tên ký tự lạ — không ném", () => {
  assert.deepEqual(nhomNhanVien([]), []);
  assert.deepEqual(nhomNhanVien(null), []);
  assert.deepEqual(nhomNhanVien(undefined, undefined), []);
  for (const rac of ["%%", "(", "\\", "[a-", ".*", "   ", "💥", 42, null, {}]) {
    assert.doesNotThrow(() => nhomNhanVien(DS, rac));
  }
  assert.equal(nhomNhanVien(DS, "%%(").reduce((s, n) => s + n.nguoi.length, 0), DS.length,
    "toàn ký tự rác = như chưa gõ");
  assert.ok(!dangTim("  ((  "));
  assert.ok(dangTim("ha"));
  const la = [{ id: "x", name: "A\u0000B (Ca 2) – “Lan”", vai: "CSKH" }];
  assert.ok(khopNhanVien("lan", la[0]));
  assert.ok(khopNhanVien("ca 2", la[0]));
  // Dòng hỏng (thiếu id) bị bỏ qua thay vì làm vỡ cả danh sách.
  const hong = [null, { name: "x" }, ...DS] as unknown as typeof DS;
  assert.equal(nhomNhanVien(hong).reduce((s, n) => s + n.nguoi.length, 0), DS.length);
});
