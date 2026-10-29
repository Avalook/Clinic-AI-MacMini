// Điều phối ca (Tuyền 29/10/2026): người điều phối chuyển được khách ĐANG LÀM —
// bác sĩ khám chính (hộp khách) và dịch vụ đang làm khi kéo thả (hỏi lý do).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const HOP = doc("../app/(dashboard)/truong-ca/QueuesClient.tsx");
const BS = doc("../app/(dashboard)/truong-ca/ChuyenBacSiKham.tsx");
const KEO = doc("../app/(dashboard)/truong-ca/keo-tha.ts");

test("hộp khách có mục Bác sĩ khám — chuyển bác sĩ bằng lệnh máy chủ, lý do bắt buộc, có Hoàn tác", () => {
  assert.match(HOP, /<ChuyenBacSiKham[\s\S]*?visitId=\{khach\.visit_id\}/);
  assert.match(BS, /fetch\("\/api\/dispatch\/doi-bac-si"/);
  assert.match(BS, /choDongY=\{lyDo\.trim\(\)\.length >= 3\}/);
  assert.match(BS, /guiDoi\(visitId, vua\.cu, "Hoàn tác chuyển bác sĩ"\)/);
  assert.match(BS, /\/api\/dispatch-read\?what=bac-si/, "danh sách người nhận do máy chủ lọc");
});

test("kéo thả dịch vụ đang làm: hỏi lý do rồi gọi chuyen-phong-dang-lam, không từ chối", () => {
  assert.match(KEO, /g\.data\.che_do === "CHUYEN_DANG_LAM"/);
  assert.match(KEO, /guiThaoTac\("chuyen-phong-dang-lam", x\.id,/);
  // Nhánh đang làm đứng TRƯỚC câu từ chối "lúc này không đổi phòng được".
  assert.ok(KEO.indexOf("CHUYEN_DANG_LAM") < KEO.indexOf("lúc này không đổi phòng được"));
  assert.match(HOP, /if \(k\.dich\.canLyDo\) \{/);
  assert.match(HOP, /<XacNhanTaiCho[\s\S]*?choDongY=\{lyDo\.trim\(\)\.length >= 3\}/);
});
