// CORE-A (Tuyền chốt 23/09/2026): không còn "Ký bệnh án"; trên Bàn khám chỉ có
// [Bắt đầu khám] ở trên và MỘT nút [Hoàn tất] ở cuối hồ sơ; Hoàn tất không khoá.

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const chiMa = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "");

const BAN_KHAM = chiMa(doc("../app/(dashboard)/ban-kham/BanKham.tsx"));
const BENH_AN = chiMa(doc("../app/(dashboard)/tasks/ClinicalRecordForm.tsx"));
const PANEL = chiMa(doc("../app/(dashboard)/tasks/HoSoHoanTatPanel.tsx"));
const PROXY = chiMa(doc("../app/api/clinical/[visit_id]/[action]/route.ts"));

test("không còn khung / nút / chữ Ký bệnh án trên luồng chuẩn", () => {
  assert.equal(
    existsSync(new URL("../app/(dashboard)/tasks/ClinicalSignPanel.tsx", import.meta.url)),
    false,
  );
  for (const [ten, ma] of [
    ["BanKham", BAN_KHAM],
    ["ClinicalRecordForm", BENH_AN],
    ["HoSoHoanTatPanel", PANEL],
  ] as const) {
    assert.doesNotMatch(ma, /Ký bệnh án|ClinicalSignPanel/, `${ten} còn nhắc ký`);
  }
  assert.doesNotMatch(PANEL, /"sign"/, "panel không được gọi thao tác sign");
  assert.doesNotMatch(PROXY, /"sign"/, "proxy không còn cho thao tác sign");
});

test("trên chỉ còn Bắt đầu khám; Hoàn tất là nút duy nhất khép phiên", () => {
  assert.match(BAN_KHAM, /"Bắt đầu khám"/);
  assert.doesNotMatch(BAN_KHAM, /"Khám xong"|"Hoàn tất khám"/, "không còn nút khám xong ở trên");
  // Một nút khép phiên, hai nghĩa theo màn (24/09/2026): Bàn khám → "Hoàn tất"
  // (kham-xong), Bàn khám tư vấn → "Xong tư vấn" (xong-tu-van).
  const hoanTat =
    BAN_KHAM.match(/bam\((?:tuVan \? "xong-tu-van" : )?"kham-xong"\)/g) ?? [];
  assert.equal(hoanTat.length, 1, "đúng MỘT nút gọi kham-xong");
  assert.match(BAN_KHAM, /"Hoàn tất"/);
  // Tuyền 24/09/2026: "xoá - chuyển bác sĩ chính đi" → nút chỉ còn "Xong tư vấn".
  assert.match(BAN_KHAM, /"Xong tư vấn"/);
  assert.doesNotMatch(BAN_KHAM, /"Xong tư vấn — chuyển bác sĩ chính"/);
});

test("Hoàn tất không khoá: khách đã khám xong vẫn sửa bệnh án/phiếu được", () => {
  assert.doesNotMatch(BAN_KHAM, /dong\.trang_thai === "done"\s*\|\|/, "không khoá theo 'done'");
  assert.doesNotMatch(BAN_KHAM, /sẽ khoá hồ sơ/);
});
