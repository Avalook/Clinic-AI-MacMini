import assert from "node:assert/strict";
import test from "node:test";

import { phut, soatLoi, type GioMoCua, type Khung, type MaCa } from "./soat-gio-ca.ts";

const MO_CUA: GioMoCua = Object.fromEntries(
  Array.from({ length: 7 }, (_, t) => [String(t), { mo: "07:00", dong: "22:00" }]),
);

const DUNG: Record<MaCa, Khung> = {
  SANG: { bat_dau: "08:00", ket_thuc: "13:00" },
  CHIEU: { bat_dau: "14:00", ket_thuc: "17:30" },
  TOI: { bat_dau: "17:30", ket_thuc: "21:30" },
};

const doi = (goc: Record<MaCa, Khung>, ma: MaCa, k: Khung) => ({ ...goc, [ma]: k });

test("phut: đọc HH:MM, từ chối rác", () => {
  assert.equal(phut("08:00"), 480);
  assert.equal(phut("21:30"), 1290);
  assert.equal(phut("8:05"), 485, "một chữ số giờ vẫn đọc được");
  for (const x of ["", "abc", "25:00", "08:70", "08", "08:0"]) {
    assert.equal(phut(x), null, `phải từ chối: ${x}`);
  }
});

test("cấu hình đúng thì không báo gì", () => {
  assert.deepEqual(soatLoi(DUNG, MO_CUA), []);
});

test("ca sát nhau (17:30 → 17:30) KHÔNG phải chồng nhau", () => {
  // Chiều kết thúc đúng lúc tối bắt đầu — liền mạch, không có giờ nào thuộc
  // hai ca. Báo nhầm ở đây là chặn đúng cấu hình đang chạy thật.
  assert.deepEqual(soatLoi(DUNG, MO_CUA), []);
});

test("giờ gõ sai định dạng thì báo đúng ca đó", () => {
  const loi = soatLoi(doi(DUNG, "CHIEU", { bat_dau: "14h", ket_thuc: "17:30" }), MO_CUA);
  assert.ok(loi.some((x) => x.includes("Ca chiều") && x.includes("HH:MM")), loi.join(" | "));
});

test("kết thúc trước bắt đầu thì báo", () => {
  const loi = soatLoi(doi(DUNG, "SANG", { bat_dau: "13:00", ket_thuc: "08:00" }), MO_CUA);
  assert.ok(loi.some((x) => x.includes("Ca sáng") && x.includes("kết thúc")), loi.join(" | "));
});

test("hai ca chồng nhau thì báo, và nói vì sao nó hỏng KPI", () => {
  const loi = soatLoi(doi(DUNG, "CHIEU", { bat_dau: "12:00", ket_thuc: "17:30" }), MO_CUA);
  assert.ok(loi.some((x) => x.includes("chồng nhau")), loi.join(" | "));
  assert.ok(loi.some((x) => x.includes("đếm đôi")), "phải nói hậu quả thật");
});

test("ca tràn ngoài giờ mở cửa thì báo — kiểu sai không tự lộ ra", () => {
  const loi = soatLoi(doi(DUNG, "TOI", { bat_dau: "17:30", ket_thuc: "23:00" }), MO_CUA);
  assert.ok(loi.some((x) => x.includes("Ca tối")), loi.join(" | "));
  assert.ok(loi.some((x) => x.includes("bị cắt")), "phải nói rõ hậu quả là bị cắt");
});

test("chỉ một thứ đóng sớm thì gọi đúng tên thứ đó", () => {
  const gio: GioMoCua = { ...MO_CUA, "6": { mo: "07:00", dong: "18:00" } };
  const loi = soatLoi(DUNG, gio);
  assert.ok(loi.length > 0, "ca tối không lọt vào ngày đóng lúc 18:00");
  assert.ok(loi.every((x) => x.includes("Thứ Bảy")), loi.join(" | "));
});

test("thứ khai giờ hỏng thì bỏ qua thứ đó, không báo bừa", () => {
  const gio: GioMoCua = { ...MO_CUA, "3": { mo: "xx", dong: "22:00" } };
  assert.deepEqual(soatLoi(DUNG, gio), []);
});

test("hai ô sai thì báo cả hai cùng lúc", () => {
  // Sửa một ô rồi bấm Lưu để biết ô thứ hai là cách làm người ta nản.
  let ca = doi(DUNG, "SANG", { bat_dau: "13:00", ket_thuc: "08:00" });
  ca = doi(ca, "TOI", { bat_dau: "17:30", ket_thuc: "23:00" });
  const loi = soatLoi(ca, MO_CUA);
  assert.ok(loi.some((x) => x.includes("Ca sáng")), loi.join(" | "));
  assert.ok(loi.some((x) => x.includes("Ca tối")), loi.join(" | "));
});
