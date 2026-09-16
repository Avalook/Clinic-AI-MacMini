import assert from "node:assert/strict";
import test from "node:test";

import { chiaGiaiDoan, giaiDoanCua } from "../lib/form-schemas/giai-doan.ts";
// Nhập THẲNG từng tệp phiếu, không qua `index.ts`: tệp ấy nhập `./pk` không có
// đuôi, và Node (không có bundler) không tự đoán đuôi `.ts`.
import { hmvsSchema } from "../lib/form-schemas/hmvs.ts";
import { nkSchema } from "../lib/form-schemas/nk.ts";
import { ntSchema } from "../lib/form-schemas/nt.ts";
import { pkSchema } from "../lib/form-schemas/pk.ts";
import { skSchema } from "../lib/form-schemas/sk.ts";
import type { FormSchema } from "../lib/form-schemas/types.ts";

const SCHEMA: Record<string, FormSchema> = {
  PK: pkSchema,
  SK: skSchema,
  NT: ntSchema,
  HMVS: hmvsSchema,
  NK: nkSchema,
};
const getFormSchema = (ma: string): FormSchema | null => SCHEMA[ma] ?? null;

// Tên đuôi `-boundary` để nhóm kiểm CI vốn có (`test:boundary`) tự nhặt, khỏi
// sửa `ci.yml` — tệp ấy chứa sẵn giá trị giả kiểu `dummy-anon-key-for-build`
// nên chạm vào là chốt bí mật kêu.
//
// Chạy trên CẢ NĂM PHIẾU THẬT, không trên dữ liệu bịa. Thứ cần canh là "mục có
// thật trong phiếu có vào đúng giai đoạn không" — dữ liệu bịa thì chỉ kiểm được
// cái tôi tưởng tên mục trông như thế nào.

const PHIEU = ["PK", "SK", "NT", "HMVS", "NK"] as const;

test("MỌI mục của năm phiếu đều vào một giai đoạn có tên — không mục nào rơi vào 'Khác'", () => {
  const roi: string[] = [];
  for (const ma of PHIEU) {
    const schema = getFormSchema(ma);
    assert.ok(schema, `thiếu phiếu ${ma}`);
    for (const s of schema.sections) {
      if (giaiDoanCua(s.title) === "KHAC") roi.push(`${ma}: ${s.title}`);
    }
  }
  assert.deepEqual(
    roi,
    [],
    "Mục mới chưa có giai đoạn — thêm từ khoá vào giaiDoanCua, " +
      "đừng để nó lặng lẽ trôi xuống cuối phiếu:\n  " + roi.join("\n  "),
  );
});

test("không mất và không lặp mục nào khi chia giai đoạn", () => {
  for (const ma of PHIEU) {
    const schema = getFormSchema(ma)!;
    const sauChia = chiaGiaiDoan(schema.sections).flatMap((g) => g.muc);
    assert.equal(sauChia.length, schema.sections.length, `${ma}: số mục lệch`);
    assert.deepEqual(
      new Set(sauChia.map((s) => s.title)),
      new Set(schema.sections.map((s) => s.title)),
      `${ma}: tập mục lệch`,
    );
  }
});

test("giai đoạn đi đúng trình tự lâm sàng", () => {
  const thuTu = ["LY_DO", "TIEN_SU", "KHAM", "CAN_LAM_SANG", "CHAN_DOAN", "THEO_DOI"];
  for (const ma of PHIEU) {
    const cac = chiaGiaiDoan(getFormSchema(ma)!.sections).map((g) => g.ma);
    const viTri = cac.map((c) => thuTu.indexOf(c));
    assert.deepEqual(viTri, [...viTri].sort((a, b) => a - b), `${ma}: ${cac.join(" → ")}`);
  }
});

test("thứ tự mục TRONG một giai đoạn giữ nguyên như schema", () => {
  // Bác sĩ đã đặt "Hướng xử trí — A / B / C / D" theo thứ tự có lý do.
  const hmvs = getFormSchema("HMVS")!;
  const chanDoan = chiaGiaiDoan(hmvs.sections).find((g) => g.ma === "CHAN_DOAN")!;
  const trongSchema = hmvs.sections.filter((s) => chanDoan.muc.includes(s));
  assert.deepEqual(chanDoan.muc, trongSchema);
});

test("các ca dễ nhầm", () => {
  // Mở đầu bằng "Khám…" nhưng là cận lâm sàng: phải kiểm cận lâm sàng trước.
  assert.equal(giaiDoanCua("Điều kiện lấy mẫu tinh dịch"), "CAN_LAM_SANG");
  assert.equal(giaiDoanCua("Nội tiết & xét nghiệm máu"), "CAN_LAM_SANG");
  assert.equal(giaiDoanCua("Hình ảnh & di truyền (ghi kết quả đã có)"), "CAN_LAM_SANG");
  // Chứa chữ "trị" nhưng là tiền sử, không phải điều trị.
  assert.equal(giaiDoanCua("Tiền sử trị hiếm muộn"), "TIEN_SU");
  // Phiếu Sản đặt tên ngắn.
  assert.equal(giaiDoanCua("Khám"), "KHAM");
  assert.equal(giaiDoanCua("Kết luận"), "CHAN_DOAN");
  assert.equal(giaiDoanCua("Lời dặn"), "THEO_DOI");
  assert.equal(giaiDoanCua("Hành chính bổ sung"), "LY_DO");
});
