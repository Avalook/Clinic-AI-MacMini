import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const TAB = "../app/(dashboard)/ke-toan/ThueSuat.tsx";

test("thuế suất: route Next chỉ chuyển tiếp tới /api/v1/ke-toan/thue-suat, kiểm nhóm", () => {
  assert.match(read("../app/api/ke-toan/thue-suat/route.ts"), /proxyJsonToBackend\("GET", `\/api\/v1\/ke-toan\/thue-suat\?/);
  const nhom = read("../app/api/ke-toan/thue-suat/nhom/[nhom]/route.ts");
  assert.match(nhom, /proxyJsonToBackend\("PUT", `\/api\/v1\/ke-toan\/thue-suat\/nhom\//);
  assert.match(nhom, /DICH_VU.*THUOC.*VAT_TU/);
  assert.match(read("../app/api/ke-toan/thue-suat/mat-hang/route.ts"), /proxyJsonToBackend\("PUT", "\/api\/v1\/ke-toan\/thue-suat\/mat-hang"/);
});

test("Kế toán có tab Thuế suất; cột thuế đọc mã từ máy chủ, đếm dòng chưa đặt do máy chủ tính", () => {
  const ui = read("../app/(dashboard)/ke-toan/KeToan.tsx");
  assert.match(ui, /<ThanhTab /);
  assert.match(ui, /<ThueSuat \/>/);
  assert.match(ui, /data\.dong_chua_thue/);
  assert.match(ui, /tenThueSuat\(h\.thue_suat\)/);
  assert.doesNotMatch(ui, /\.reduce\(/);
});

test("tab Thuế suất: màn chỉ chọn và gửi; không tự chuẩn hoá / tách thuế / kiểm quyền", () => {
  const ui = read(TAB);
  // Chuẩn hoá, ưu tiên dòng > mặt hàng > nhóm, tách thuế: máy chủ (thue_gtgt.py).
  assert.doesNotMatch(ui, /parseFloat|Number\(|\.reduce\(|Math\.round/);
  assert.doesNotMatch(ui, /window\.confirm/);
  assert.doesNotMatch(ui, /<button(?![^>]*type=)/);
  // Quyền do máy chủ trả (duoc_dat) — không tự suy theo vai.
  assert.match(ui, /data\?\.duoc_dat/);
  assert.doesNotMatch(ui, /role ===|QUAN_LY|MANAGEMENT/);
  // Hoàn tác: sau mỗi lần đặt có nút Hoàn tác gửi lại giá trị cũ.
  assert.match(ui, /Hoàn tác/);
  // Mức hay dùng có đủ KCT / KKKNT và ô nhập % khác.
  const muc = read("../app/(dashboard)/ke-toan/thue-suat.ts");
  assert.match(muc, /\["KCT"/);
  assert.match(muc, /\["KKKNT"/);
  assert.match(ui, /MUC_THUE/);
  assert.match(ui, /Khác \(nhập %\)/);
});
