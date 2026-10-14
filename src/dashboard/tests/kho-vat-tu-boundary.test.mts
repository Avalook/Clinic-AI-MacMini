import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";

// KHO VẬT TƯ (G8a, 14/10/2026) — ranh giới giao diện:
//   · proxy chỉ chuyển tiếp qua DANH SÁCH TRẮNG, lệnh ghi lập phiếu / đảo phiếu mang Idempotency-Key;
//   · tồn âm, dưới mức, phiếu huỷ là việc BÌNH THƯỜNG → màn không vẽ hộp / chip / số vàng-đỏ
//     (Tuyền 14/10); đỏ chỉ ở câu lỗi máy chủ trả (`text-danger` trong role="alert");
//   · không luật nghiệp vụ trong TSX, không window.confirm, không dấu * ở nhãn.

const thuMuc = new URL("../app/(dashboard)/kho-vat-tu/", import.meta.url);
const doc = (u: URL) => readFileSync(u, "utf8");
const tsx = readdirSync(thuMuc).filter((f) => f.endsWith(".tsx") || f.endsWith(".ts"));
const route = doc(new URL("../app/api/vat-tu-kho/[action]/route.ts", import.meta.url));

test("màn Kho vật tư có đủ các tệp (chống xanh giả)", () => {
  for (const f of ["page.tsx", "KhoVatTu.tsx", "TonVatTu.tsx", "LapPhieuVatTu.tsx", "DanhSachPhieuVatTu.tsx"]) {
    assert.ok(tsx.includes(f), `thiếu ${f}`);
  }
});

test("không hộp / chip vàng-đỏ cho việc bình thường", () => {
  for (const f of tsx) {
    const ma = doc(new URL(f, thuMuc));
    assert.doesNotMatch(ma, /bg-warning|bg-danger|text-warning|tone="(warning|danger)"/, `${f} dùng màu cảnh báo`);
    // `text-danger` chỉ được ở câu lỗi máy chủ (role="alert").
    for (const m of ma.matchAll(/<p[^>]*text-danger[^>]*>/g)) {
      assert.match(m[0], /role="alert"/, `${f}: text-danger ngoài role="alert"`);
    }
  }
});

test("không window.confirm, không dấu * ở nhãn, nút luôn có type", () => {
  for (const f of tsx) {
    const ma = doc(new URL(f, thuMuc));
    assert.doesNotMatch(ma, /window\.confirm|\bconfirm\(/, `${f} dùng confirm`);
    assert.doesNotMatch(ma, /<span[^>]*>[^<]*\*<\/span>/, `${f} có dấu * ở nhãn`);
    assert.doesNotMatch(ma, /<button(?![^>]*type=)/, `${f}: <button> thiếu type`);
  }
});

test("proxy danh sách trắng + chuyển Idempotency-Key cho lập phiếu / đảo phiếu", () => {
  for (const a of ["ton", "canh-bao", "phieu", "hoan", "muc-toi-thieu"]) {
    assert.ok(route.includes(a), `proxy thiếu ${a}`);
  }
  assert.match(route, /Idempotency-Key/);
  // Không có đường mở trần: mọi thao tác đi qua bảng DOC hoặc so khớp chữ cố định.
  assert.match(route, /Thao tác không hợp lệ/);
});

test("giao diện lập phiếu gửi qua proxy, không gọi thẳng FastAPI", () => {
  const gui = doc(new URL("gui-vat-tu.ts", thuMuc));
  assert.match(gui, /\/api\/vat-tu-kho\//);
  assert.doesNotMatch(gui, /\/api\/v1\//);
});
