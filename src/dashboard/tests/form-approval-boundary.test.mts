// Không phiếu khám nào được bày ra cho bác sĩ khi bản thân nó còn ghi "chờ bác
// sĩ duyệt".
//
// LỊCH SỬ CỦA BÀI KIỂM NÀY, vì nó vừa đổi hình.
//
// Bản đầu khẳng định đúng một sự việc: `NK` KHÔNG được nằm trong registry. Lúc
// ấy `nk.ts` là bản lắp tạm từ các trường nam khoa nằm rải trong section Hiếm
// muộn của tài liệu bàn giao — không có mục Nam khoa riêng, nên không ai dám
// cho bác sĩ ký vào, và cách an toàn nhất là giữ nó ngoài cửa.
//
// 04/08/2026 cả hai điều kiện đó hết đúng: `nk.ts` dựng lại theo
// docs/spec-form-nam-khoa.md §5, và có một dòng trong `clinical_form_approval`
// ghi ai cho phép dùng, lúc nào, kèm ghi chú "bản dùng thử, chưa có chữ ký BS
// Nam khoa".
//
// Nên bài kiểm đổi từ MỘT SỰ VIỆC ("NK bị cấm cửa") sang CÁI LUẬT đứng sau nó
// ("form còn dấu chờ duyệt thì không được bày ra") — và luật ấy giờ soi cả năm
// form chứ không riêng NK. Xoá hẳn bài kiểm thì lần sau có người dán một form
// nháp vào registry mà không ai biết.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const registrySource = readFileSync(
  new URL("../lib/form-schemas/index.ts", import.meta.url),
  "utf8",
);

/** Mã form đang được bày ra cho engine dựng — đọc thẳng từ registry. */
function exposedCodes(): string[] {
  const block = registrySource.match(/const REGISTRY[^=]*=\s*\{([\s\S]*?)\n\};/);
  assert.ok(block, "không đọc được REGISTRY trong lib/form-schemas/index.ts");
  return [...block[1].matchAll(/^\s*([A-Z_]+)\s*:/gm)].map((m) => m[1]);
}

function schemaSource(code: string): string {
  return readFileSync(
    new URL(`../lib/form-schemas/${code.toLowerCase()}.ts`, import.meta.url),
    "utf8",
  );
}

test("registry đang bày ra đúng năm phiếu khám", () => {
  assert.deepEqual(
    [...exposedCodes()].sort(),
    ["HMVS", "NK", "NT", "PK", "SK"],
    "đổi danh sách form phải là quyết định có chủ ý, không phải hệ quả phụ",
  );
});

// DẤU CHỜ DUYỆT ĐƯỢC PHÉP Ở CHÚ THÍCH, KHÔNG ĐƯỢC Ở CHỮ HIỆN RA.
//
// Bốn form đang chạy (PK, SK, NT, HMVS) còn năm dấu //TODO-BS-REVIEW, và cả
// năm đều nằm trong chú thích — chúng là câu hỏi thật gửi bác sĩ, ví dụ *"docx
// ghi BMT, nhiều khả năng là BMI"*. Bắt bài kiểm chặn chúng sẽ đẩy người ta đi
// XOÁ GHI CHÚ cho test xanh, thay vì đi hỏi bác sĩ — mất luôn câu hỏi, và câu
// hỏi mới là thứ có giá trị.
//
// Chỗ thật sự nguy hiểm là chữ HIỆN RA MÀN HÌNH: nhãn và tiêu đề được in lên
// phiếu kết quả đưa cho bệnh nhân. Đã từng lọt một lần — bản đầu của bài kiểm
// này sinh ra chính vì `title: "Khám thai (khung tối thiểu) — //TODO-BS-REVIEW"`
// nằm trong sk.ts.

test("dấu chờ duyệt không được lọt vào bất kỳ chữ nào hiện ra màn hình", () => {
  for (const code of exposedCodes()) {
    // Mọi chuỗi trong file: nhãn, tiêu đề, placeholder, nhãn của từng lựa chọn.
    // Rộng hơn `label:`/`title:` vì một mã form mới có thể thêm kiểu field khác.
    const chuoi = [...schemaSource(code).matchAll(/"((?:[^"\\]|\\.)*)"/g)];
    for (const [, s] of chuoi) {
      assert.equal(
        /TODO|FIXME|XXX|\?\?\?/.test(s),
        false,
        `${code}: chuỗi "${s}" chứa ghi chú nội bộ — nó sẽ hiện lên màn hình`,
      );
    }
  }
});

test("mọi dấu chờ duyệt còn lại đều nằm trong chú thích", () => {
  // Không chặn, chỉ khẳng định chúng ở đúng chỗ. Danh sách câu hỏi còn treo cho
  // bác sĩ nằm ở đây, đọc được bằng: grep -rn TODO-BS-REVIEW lib/form-schemas/
  for (const code of exposedCodes()) {
    for (const dong of schemaSource(code).split("\n")) {
      if (!dong.includes("TODO-BS-REVIEW")) continue;
      assert.ok(
        dong.trimStart().startsWith("//") || dong.includes("// "),
        `${code}: dấu chờ duyệt nằm ngoài chú thích ở dòng: ${dong.trim()}`,
      );
    }
  }
});
