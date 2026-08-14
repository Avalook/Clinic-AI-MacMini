// Dòng đỏ phải nằm ở ĐÚNG BƯỚC gây ra nó.
//
// Tuyền báo 14/08/2026 kèm ảnh: câu *"Chưa có tệp kết quả nào được xác nhận đã
// gửi cho khách"* hiện dưới MỌI bước — "Đã check-in", "Gọi nhắc hẹn", "Huỷ
// lịch", "Không cần follow up sau thủ thuật". Không bước nào trong số đó liên
// quan tới tệp kết quả.
//
// Chốt ấy ở backend chỉ áp cho MỘT loại: `if loai == "TRA_KQ"` trong
// tuong_tac_cskh_service.py. Lỗi nằm ở màn hình: `loiGhiLoiRa` là một biến
// dùng chung cho cả màn, và điều kiện vẽ không hỏi lỗi thuộc bước nào.
//
// MỘT DÒNG ĐỎ NÓI SAI CHỖ TỆ HƠN KHÔNG CÓ DÒNG NÀO. Nó bảo người trực rằng mọi
// bước đều đang hỏng, nên họ ngừng tin mọi dòng đỏ — kể cả dòng đúng. Cùng bài
// học với "một bước hỏng tô đỏ cả chuỗi".

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const nguon = readFileSync(
  new URL("../app/(dashboard)/customers/VungLamViecKhach.tsx", import.meta.url),
  "utf8",
);
const ma = nguon.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

test("lỗi ghi bước MANG THEO mã bước, không chỉ mang câu chữ", () => {
  assert.match(
    ma,
    /useState<\s*\{\s*ma:\s*string;\s*cau:\s*string\s*\}\s*\|\s*null\s*>/,
    "loiGhiLoiRa phải nhớ lỗi thuộc bước nào",
  );
});

test("mỗi bước CHỈ vẽ lỗi của chính nó", () => {
  // Điều kiện cũ `motCham && loiGhiLoiRa && …` không so mã bước — đó chính là
  // chỗ một câu lỗi nhân bản ra mười mấy thẻ.
  assert.match(
    ma,
    /loiGhiLoiRa\?\.ma === tt\.ma/,
    "Node phải so mã bước trước khi vẽ dòng đỏ",
  );
  assert.doesNotMatch(
    ma,
    /motCham && loiGhiLoiRa && dangGhiLoiRa/,
    "điều kiện cũ (không so bước) không được quay lại",
  );
});

test("không chỗ nào nhận thẳng câu lỗi mà bỏ qua mã bước", () => {
  // `loi={loiGhiLoiRa?.cau ?? null}` biên dịch được và trông vô hại, nhưng nó
  // dựng lại đúng lỗi cũ ở một component con.
  assert.doesNotMatch(
    ma,
    /loi=\{loiGhiLoiRa\?\.cau \?\? null\}/,
    "phải lọc theo mã bước trước khi truyền câu lỗi xuống",
  );
  const truyen = [...ma.matchAll(/loi=\{loiGhiLoiRa[^}]*\}/g)].map((m) => m[0]);
  for (const t of truyen) {
    assert.match(t, /\.ma ===/, `"${t}" — truyền câu lỗi mà không so bước`);
  }
});

test("chốt 'chưa gửi tệp' ở backend CHỈ áp cho bước trả kết quả", () => {
  // Nếu chốt ấy lan sang loại khác thì màn hình sửa đúng vẫn ra kết quả sai —
  // dòng đỏ hiện ở một bước không liên quan, chỉ khác là lần này nó thật.
  const svc = readFileSync(
    new URL("../../clinicai/services/tuong_tac_cskh_service.py", import.meta.url),
    "utf8",
  );
  const dau = svc.indexOf('if loai == "TRA_KQ"');
  assert.ok(dau > 0, "không còn nhánh riêng cho TRA_KQ?");
  const cau = svc.indexOf("Chưa có tệp kết quả nào");
  assert.ok(
    cau > dau,
    "câu chặn phải nằm TRONG nhánh TRA_KQ, không nằm ngoài",
  );
});
