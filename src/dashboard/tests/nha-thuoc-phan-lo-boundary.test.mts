import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Màn Nhà thuốc sau contract tiền–thuốc CP4 (19/09/2026). Bốn điều dễ hỏng
// nhất khi ai đó "sửa nhanh" màn này.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const page = doc("app/(dashboard)/pharmacy/page.tsx");
const board = doc("app/(dashboard)/pharmacy/PharmacyBoard.tsx");
const dong = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");
const kieu = doc("app/(dashboard)/pharmacy/ban-thuoc.ts");
const proxy = doc("app/api/pharmacy/[action]/route.ts");

test("màn đọc qua máy chủ, không đọc thẳng Supabase", () => {
  // Giai đoạn tiền thuốc và các nút được phép là luật nghiệp vụ (FastAPI).
  // Bản trước đọc thẳng `prescription` + `drug_batch` rồi tự so tên thuốc.
  assert.match(page, /fetchFromBackend<ManNhaThuoc>\("\/api\/v1\/pharmacy\/ban-thuoc"\)/);
  assert.doesNotMatch(page, /getSupabaseServer|\.from\(/);
});

test("nút hiện theo lời máy chủ, không tự suy từ giai đoạn", () => {
  // Mã giai đoạn chỉ được dùng để tra NHÃN (ban-thuoc.ts). Component nào so
  // `giai_doan === "..."` để quyết nút là đang chép lại luật của máy chủ.
  for (const src of [board, dong]) {
    assert.doesNotMatch(src, /===\s*"(CHUA_SAN_SANG|SAN_SANG|CHO_XAC_MINH|DA_THU|CAN_DOI_SOAT|DA_THU_CU)"/);
  }
  for (const nut of ["chon_lo", "xac_dinh_thuoc", "khai_so_mua", "tu_choi", "chot", "giao_luong_cu"]) {
    assert.match(dong, new RegExp(`tt\\.${nut}`), `thiếu cổng tt.${nut}`);
  }
  for (const nut of ["bo", "doi", "giao"]) {
    assert.match(dong, new RegExp(`p\\.thao_tac\\.${nut}`), `thiếu cổng p.thao_tac.${nut}`);
  }
});

test("không gọi số hệ thống là 'tồn khả dụng' (HOLD J6)", () => {
  // Tên chính thức của con số chống bán trùng chưa chốt với kho.
  for (const src of [board, dong, kieu]) {
    assert.doesNotMatch(src, /tồn khả dụng/i);
  }
  assert.match(dong, /Tồn vật lý/);
  assert.match(dong, /Có thể phân lô lúc này/);
});

test("proxy mở đủ và chỉ đúng các thao tác phân lô của máy chủ", () => {
  for (const [a, p] of [
    ["xac-dinh-thuoc", "xac-dinh-thuoc"],
    ["so-luong-mua", "so-luong-mua"],
    ["phan-lo", "phan-lo"],
    ["bo-phan-lo", "bo-phan-lo"],
    ["doi-lo", "doi-lo"],
  ]) {
    assert.match(proxy, new RegExp(`"${a}":\\s*"/api/v1/pharmacy/${p}"`));
  }
  assert.doesNotMatch(dong, /window\.confirm/);
});
