// Trang chủ đi MỘT vòng gói + Suspense — không được lùi về 6 vòng chờ trắng.
//
// LÁT 3 CỦA LỘ TRÌNH CHỊU TẢI, 22/08/2026. Trước đó /home đi 6 vòng PostgREST
// (3 đếm + roster + trực ca + bảng Lễ tân, kèm truy vấn `staff` phụ và một
// đường lùi hai truy vấn) + 3 endpoint FastAPI rời, và server đợi TẤT CẢ xong
// mới trả byte đầu — bấm sidebar lúc đông là màn trắng vài giây, người trực
// đọc thành "web treo". Lỗi lùi kiểu này KHÔNG có triệu chứng chức năng: thêm
// lại một vòng PostgREST thì trang vẫn đúng, chỉ chậm dần — nên test phải đếm.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(
  new URL("../app/(dashboard)/home/page.tsx", import.meta.url),
  "utf8",
);

test("đúng một lời gọi gói bang-dieu-khien, bọc trong cache()", () => {
  const goi = page.match(/fetchFromBackend<GoiTrangChu>/g) ?? [];
  assert.equal(goi.length, 1, "phải đúng MỘT chỗ gọi gói");
  // Hai island Suspense cùng đọc gói — cache() của React khử trùng lặp THEO
  // TỪNG lượt render. Một Map module-scope cũng khử được nhưng CHIA SẺ promise
  // giữa hai người dùng render cùng lúc: cookie người trước quyết định dữ liệu
  // người sau thấy (bảng Lễ tân, ô Quản lý). Suýt ship đúng lỗi ấy 22/08.
  assert.match(
    page,
    /const goiTrangChu = cache\(/,
    "gói phải bọc trong cache() — xem chú thích chống rò giữa người dùng",
  );
  assert.ok(
    !page.includes("new Map<string, Promise"),
    "không dùng Map module-scope khử trùng lặp — rò dữ liệu giữa người dùng",
  );
});

test("không còn vòng PostgREST nào trên trang chủ", () => {
  const from = page.match(/\.from\(/g) ?? [];
  assert.equal(
    from.length,
    0,
    "trang chủ không được tự hỏi PostgREST — mọi dữ liệu qua gói bang-dieu-khien",
  );
  assert.ok(
    !page.includes("getSupabaseServer"),
    "trang chủ không còn cầm client Supabase",
  );
});

test("lời chào đứng ngoài Suspense, dữ liệu đứng trong", () => {
  // Đây là nửa "không giật" của Lát 3: khung + lời chào hiện tức thì, dữ liệu
  // rót sau. Mất Suspense là quay lại màn trắng chờ đủ mọi truy vấn.
  const soSuspense = (page.match(/<Suspense/g) ?? []).length;
  assert.ok(soSuspense >= 2, `phải có ≥2 island Suspense, thấy ${soSuspense}`);
  const viTriChao = page.indexOf("{homeTitle}");
  const viTriSuspenseDau = page.indexOf("<Suspense");
  assert.ok(
    viTriChao >= 0 && viTriChao < viTriSuspenseDau,
    "lời chào phải render TRƯỚC island Suspense đầu tiên",
  );
});

test("backend im thì màn phải nói ra, không hiện trang chủ 'sạch bong'", () => {
  assert.match(page, /const goiLoi = goi === null/);
  assert.match(
    page,
    /\{goiLoi && \(/,
    "goiLoi chưa nối vào giao diện — backend chết là trang trống câm lặng",
  );
});

test("tên trực nhật vẫn đồng bộ từ staff, luật cắt chức danh ở doctorName", () => {
  // dongBoTenTrucNhat cũ = một truy vấn `staff` phụ; nay backend join sẵn
  // ten_staff nhưng phép cắt chức danh PHẢI vẫn qua doctorName phía frontend
  // — chép luật ấy sang Python là hai bản sao chờ ngày lệch nhau.
  assert.match(page, /doctorName\(r\.ten_staff\)/);
  // So theo dòng import chứ không phải chuỗi trần: comment trong page nhắc
  // tên hàm cũ một cách hợp lệ (bẫy chuỗi-trần lần thứ TƯ của repo này).
  assert.ok(
    !/import .*dongBoTenTrucNhat/.test(page),
    "không import dongBoTenTrucNhat nữa — nguồn tên là ten_staff trong gói",
  );
});
