// Ô tìm khách phải hỏi CẢ MÁY CHỦ, không chỉ lọc thứ đã tải sẵn.
//
// TÌM ĐƯỢC KHI NGHIỆM THU 11/08/2026.
//
// `page.tsx` tải danh sách khách bằng `.limit(300)`. `CustomersView` lọc trên
// đúng mảng đó. Ô tìm kiếm chỉ gọi `setTerm` — nên nó chỉ nhìn thấy 300 hồ sơ
// đầu tiên.
//
// Đường tìm phía máy chủ ĐÃ TỒN TẠI và viết đúng: `?q=` → `.or(full_name.ilike,
// patient_code.ilike, phone_primary.ilike, full_name_unaccent.ilike)`. Nó chỉ
// không được ô tìm kiếm gọi bao giờ — chỉ chạy tình cờ khi người dùng đổi bộ lọc.
//
// Staging có 21 khách nên không lộ. Phòng khám thật vượt 300 hồ sơ thì lễ tân gõ
// tên khách cũ và nhận "Không tìm thấy khách khớp từ khoá." — sai mà nghe chắc
// chắn — rồi tạo hồ sơ trùng cho người đã có. Với hồ sơ y tế, một bệnh nhân hai
// hồ sơ nghĩa là tiền sử bị chẻ đôi.
//
// Cùng họ với hai lỗi khác tìm được cùng ngày (`doDetail` gắn sai ô, `dobError`
// chỉ nối vào form): LUẬT ĐÚNG, KHÔNG NỐI VÀO ĐƯỜNG THẬT.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const view = readFileSync(
  new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
  "utf8",
);
const page = readFileSync(
  new URL("../app/(dashboard)/customers/page.tsx", import.meta.url),
  "utf8",
);

/** Bỏ chú thích trước khi dò — một bài kiểm đọc mã phải phân biệt mã với lời kể về mã. */
const boChuThich = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("ô tìm kiếm KHÔNG được chỉ gọi setTerm", () => {
  const ma = boChuThich(view);
  assert.doesNotMatch(
    ma,
    /onChange=\{\s*\(event\)\s*=>\s*setTerm\(event\.target\.value\)\s*\}/,
    "onChange chỉ đặt state cục bộ ⇒ tìm kiếm dừng ở 300 hồ sơ đã tải",
  );
});

test("gõ vào ô tìm kiếm phải dẫn tới truy vấn máy chủ", () => {
  const ma = boChuThich(view);
  assert.match(ma, /function goTim\(/, "phải có hàm nối ô tìm kiếm với máy chủ");
  // goTim phải vừa lọc tại chỗ (setTerm) vừa gọi go(...) — thiếu vế nào cũng hỏng:
  // thiếu setTerm thì gõ bị khựng, thiếu go thì lại chỉ thấy 300 hồ sơ.
  const than = /function goTim\([\s\S]*?\n  \}/.exec(ma)?.[0] ?? "";
  assert.match(than, /setTerm\(/, "goTim phải lọc ngay trên thứ đã tải");
  assert.match(than, /\bgo\(/, "goTim phải hỏi máy chủ");
  assert.match(than, /setTimeout\(/, "phải hoãn, không bắn một yêu cầu mỗi phím");
});

test("Enter tìm ngay, không đợi hết hoãn", () => {
  const ma = boChuThich(view);
  assert.match(ma, /onKeyDown/, "phải bắt phím Enter ở ô tìm kiếm");
  assert.match(ma, /huyHoanTim\(\)/, "Enter phải huỷ lần hoãn đang chờ");
});

test("máy chủ vẫn tìm bằng đủ BỐN cách, gồm tên không dấu", () => {
  // Đây là phần vốn đã đúng — canh để đừng ai rút bớt khi sửa chỗ khác.
  const ma = boChuThich(page);
  for (const cot of [
    "full_name.ilike",
    "patient_code.ilike",
    "phone_primary.ilike",
    "full_name_unaccent.ilike",
  ]) {
    assert.ok(ma.includes(cot), `mất cách tìm: ${cot}`);
  }
});

test("giới hạn 300 vẫn còn — nên đường máy chủ là BẮT BUỘC, không phải tuỳ chọn", () => {
  // Nếu ai đó nâng limit lên rất cao và bỏ đường máy chủ đi, bài kiểm này vẫn
  // xanh nhưng vấn đề quay lại ở quy mô lớn hơn. Ghi rõ ràng buộc ở đây để lần
  // sau còn nhớ VÌ SAO cần cả hai.
  const ma = boChuThich(page);
  assert.match(
    ma,
    /\.from\("patient"\)[\s\S]{0,400}?\.limit\((\d+)\)/,
    "không tìm thấy giới hạn của truy vấn danh sách khách",
  );
});
