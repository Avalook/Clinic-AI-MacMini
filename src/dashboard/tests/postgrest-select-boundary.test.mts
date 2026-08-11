// Chuỗi `select` của PostgREST KHÔNG phải SQL — không được có chú thích trong đó.
//
// LỖI TÔI TỰ GÂY RA 11/08/2026, và nó làm TRẮNG cả màn Quản lý khách hàng.
//
// Thêm cột `updated_at` vào truy vấn danh sách khách, kèm hai dòng giải thích:
//
//   const SELECT = `
//     …, van_de_di_kham, linh_vuc,
//     -- Thẻ khoá lạc quan cho form sửa hồ sơ: mốc màn hình đã đọc.
//     updated_at
//   `;
//
// Chuỗi ấy trông như SQL nên `--` trông như chú thích. Nó không phải: đây là
// tham số `select` của PostgREST, một danh sách cột phân cách bằng dấu phẩy, và
// `--` chỉ là ký tự trong tên cột. PostgREST trả:
//
//   failed to parse select parameter (…,--Thẻkhoálạcquancho…)
//
// Câu giải thích viết cho người đọc đã giết chính thứ nó giải thích.
//
// VÌ SAO NÓ LỌT: tôi nghiệm thu tính năng bằng đường API (PATCH /api/patients),
// thấy 200 và 409 đúng như thiết kế, rồi dừng. Không mở lại trang tiêu thụ dữ
// liệu. Một truy vấn hỏng ở tầng đọc thì đường ghi vẫn xanh nguyên.
//
// Bài kiểm này canh CẢ LỚP LỖI, không riêng chỗ vừa hỏng: mọi chuỗi select trong
// dashboard, ở mọi file.

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const GOC = new URL("../app", import.meta.url).pathname;

function moiFileTsx(thuMuc: string): string[] {
  const ra: string[] = [];
  for (const ten of readdirSync(thuMuc)) {
    if (ten === "node_modules" || ten === ".next") continue;
    const duong = join(thuMuc, ten);
    if (statSync(duong).isDirectory()) ra.push(...moiFileTsx(duong));
    else if (/\.(ts|tsx)$/.test(ten)) ra.push(duong);
  }
  return ra;
}

/**
 * Mọi chuỗi truyền vào `.select(...)`, kèm tên file để báo lỗi cho ra chỗ.
 *
 * PHẢI GHÉP CÁC MẢNH NỐI BẰNG `+`. Nhiều nơi viết:
 *
 *   .select(
 *     "clinic_patient_id, patient_code, full_name, date_of_birth, " +
 *       "phone_primary, phone_secondary, …",
 *   )
 *
 * Bản đầu của bài kiểm này bắt từng mảnh riêng, nên mảnh đầu kết thúc bằng dấu
 * phẩy — hoàn toàn đúng, vì mảnh sau nối tiếp — và bị báo là "dấu phẩy thừa".
 * Hai báo động giả trên hai trang đang chạy tốt. Một bài kiểm hay kêu oan thì
 * người ta sẽ tắt nó, và mất luôn phép kiểm thật nằm cạnh.
 */
function moiChuoiSelect(): { file: string; chuoi: string }[] {
  const ra: { file: string; chuoi: string }[] = [];
  /** Gom mọi chuỗi nghĩa đen trong một đoạn mã thành MỘT chuỗi. */
  const ghep = (doan: string): string =>
    [...doan.matchAll(/([`"'])([\s\S]*?)\1/g)].map((m) => m[2]).join("");

  for (const file of moiFileTsx(GOC)) {
    const ma = readFileSync(file, "utf8");
    // Từ `.select(` tới dấu `)` cân bằng đầu tiên — đủ cho mọi cách viết hiện có.
    for (const m of ma.matchAll(/\.select\(([\s\S]*?)\)\s*(?:\.|,|;|$)/g)) {
      const chuoi = ghep(m[1]);
      if (chuoi) ra.push({ file, chuoi });
    }
    for (const m of ma.matchAll(
      /const\s+[A-Z_]*SELECT[A-Z_]*\s*=\s*([\s\S]*?);/g,
    )) {
      const chuoi = ghep(m[1]);
      if (chuoi) ra.push({ file, chuoi });
    }
  }
  return ra;
}

test("không chuỗi select nào chứa chú thích kiểu SQL", () => {
  const hong: string[] = [];
  for (const { file, chuoi } of moiChuoiSelect()) {
    if (chuoi.includes("--") || chuoi.includes("/*")) {
      hong.push(`${file.replace(GOC, "app")}: ${chuoi.trim().slice(0, 120)}`);
    }
  }
  assert.deepEqual(
    hong,
    [],
    "chuỗi select có chú thích ⇒ PostgREST trả 'failed to parse select parameter' " +
      "và màn dùng nó sẽ trắng:\n  " + hong.join("\n  "),
  );
});

test("không chuỗi select nào có dấu phẩy thừa hoặc rỗng giữa các cột", () => {
  // Cùng họ: `a, , b` hay `a,` cuối chuỗi cũng làm PostgREST từ chối cả câu, và
  // cũng dễ sinh ra khi thêm/bớt cột lúc sửa vội.
  const hong: string[] = [];
  for (const { file, chuoi } of moiChuoiSelect()) {
    // Bỏ phần lồng trong embed `staff:nhan_vien_staff_id ( full_name )` — dấu
    // phẩy bên trong ngoặc có luật riêng.
    const phang = chuoi.replace(/\([^)]*\)/g, "");
    if (/,\s*,/.test(phang) || /,\s*$/.test(phang.trim())) {
      hong.push(`${file.replace(GOC, "app")}: ${chuoi.trim().slice(0, 120)}`);
    }
  }
  assert.deepEqual(hong, [], "chuỗi select có dấu phẩy thừa:\n  " + hong.join("\n  "));
});

test("bài kiểm này thật sự tìm thấy chuỗi select để canh", () => {
  // Nếu biểu thức dò hỏng, hai phép kiểm trên sẽ xanh vĩnh viễn mà không canh gì
  // — kiểu bài kiểm tệ nhất, vì nó tạo cảm giác an toàn giả.
  const n = moiChuoiSelect().length;
  assert.ok(n >= 20, `chỉ tìm thấy ${n} chuỗi select — biểu thức dò có vẻ đã hỏng`);
});
