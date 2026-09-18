// S0-3 (18/09/2026). Sinh hiệu chỉ đo ở MỘT nơi (màn Đo sinh hiệu), BMI chỉ là
// số máy chủ TÍNH RA. Trước đó: màn đo và bệnh án có ô BMI gõ tay (số gõ tay
// thắng số tính), còn ba phiếu chuyên khoa mỗi phiếu tự có ô mạch/huyết áp/cân
// nặng — số đo điều dưỡng bị trộn vào form_data rồi tự lưu ngược vào phiếu.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { pkSchema } from "../lib/form-schemas/pk.ts";
import { hmvsSchema } from "../lib/form-schemas/hmvs.ts";
import { nkSchema } from "../lib/form-schemas/nk.ts";
import { sinhHieuHienThi, sinhHieuPhieuCu } from "../lib/sinh-hieu-dong-bo.ts";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

const KHOA_SINH_HIEU = [
  "nhip_tim", "nhiet_do", "huyet_ap", "nhip_tho", "can_nang", "chieu_cao", "bmt", "bmi",
  "mach", "spo2",
  "kls_chieu_cao", "kls_can_nang", "kls_huyet_ap", "kls_mach", "kls_bmi",
];

test("ba phiếu chuyên khoa không còn ô nhập sinh hiệu nào", () => {
  for (const schema of [pkSchema, hmvsSchema, nkSchema]) {
    const khoa = schema.sections.flatMap((s) => s.fields.map((f) => f.key));
    for (const k of KHOA_SINH_HIEU) {
      assert.ok(!khoa.includes(k), `${schema.service_code} còn ô sinh hiệu "${k}"`);
    }
  }
  // Phần khám tổng quát KHÔNG phải sinh hiệu thì giữ nguyên.
  const pk = pkSchema.sections.flatMap((s) => s.fields.map((f) => f.key));
  for (const k of ["da_niem_mac", "tuyen_giap", "vu"]) assert.ok(pk.includes(k), k);
  const nk = nkSchema.sections.flatMap((s) => s.fields.map((f) => f.key));
  assert.ok(nk.includes("kls_nam_hoa"));
});

test("màn Đo sinh hiệu và bệnh án không có ô nhập BMI", () => {
  const bang = read("../app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx");
  assert.doesNotMatch(bang, /gui: "bmi"/, "màn đo còn gửi BMI gõ tay");
  const ba = read("../app/(dashboard)/tasks/ClinicalRecordForm.tsx");
  assert.doesNotMatch(ba, /\["bmi", "BMI"/, "bệnh án còn ô nhập BMI");
  assert.doesNotMatch(ba, /bmiGoiY/, "bệnh án còn nút gợi ý BMI");
  assert.doesNotMatch(ba, /bmi: f\.bmi/, "bệnh án còn gửi BMI lên máy chủ");
});

test("API phiếu chuyên khoa không trộn số đo vào form_data", () => {
  const route = read("../app/api/clinical-form/route.ts");
  assert.doesNotMatch(route, /sinhHieuTheoKhoaPhieu/);
  assert.doesNotMatch(route, /kls_\$\{/);
  assert.match(route, /sinh_hieu,/);
  const engine = read("../app/(dashboard)/tasks/ServiceFormEngine.tsx");
  assert.match(engine, /<KhoiSinhHieuChiXem khoi=\{sinhHieu\} \/>/);
  assert.match(engine, /<AndrologyReview values=\{values\} visitId=\{visitId\} \/>/);
});

test("khối chỉ xem: số đo mới nhất; lượt chưa đo thì đọc lại ô phiếu cũ", () => {
  const o = sinhHieuHienThi({
    systolic: 118, diastolic: 76, pulse: 80, temperature: null, weight_kg: "54",
    height_cm: "160", respiratory_rate: null, spo2: null, bmi: "21.1", pain_score: null,
  });
  assert.deepEqual(o.map((x) => x.nhan), ["Huyết áp", "Mạch", "Cân nặng", "Chiều cao", "BMI"]);
  assert.equal(o[0].gia_tri, "118/76 mmHg");
  assert.equal(o[4].gia_tri, "21.1");
  assert.deepEqual(sinhHieuHienThi(null), []);

  // Phiếu lưu trước S0-3 vẫn đọc được — form_data cũ không bị migration.
  const cu = sinhHieuPhieuCu({ nhip_tim: 82, bmt: "22", kls_can_nang: "70", vu: "BT", huyet_ap: " " });
  assert.deepEqual(cu, [
    { nhan: "Nhịp tim", gia_tri: "82" },
    { nhan: "Cân nặng", gia_tri: "70" },
    { nhan: "BMT (ghi tay)", gia_tri: "22" },
  ]);
});
