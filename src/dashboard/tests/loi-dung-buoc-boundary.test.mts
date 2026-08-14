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

test("chốt 'chưa gửi tệp' đã gỡ khỏi backend", () => {
  // Bài kiểm này SÁNG 14/08 canh "chốt phải nằm trong nhánh TRA_KQ" — lúc ấy
  // lỗi là câu chặn hiện dưới mọi bước, và chốt vẫn được coi là đúng.
  //
  // CHIỀU CÙNG NGÀY Tuyền chốt gỡ hẳn: *"mình đang chỉ cần CSKH và quản lý hệ
  // thống dùng thôi nên là tick là được… có lịch sử là coi như làm rồi"*. Chốt
  // đòi một tệp đã gửi, trong khi luồng gửi tệp còn đang xây — tức là một điều
  // kiện không cách nào đạt được.
  //
  // Giữ bài kiểm thay vì xoá: nó là thứ ngăn ai đó dựng lại chốt mà quên dựng
  // luồng gửi tệp trước.
  const svc = readFileSync(
    new URL("../../clinicai/services/tuong_tac_cskh_service.py", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(
    svc,
    /"Chưa có tệp kết quả nào/,
    "chốt đòi tệp đã gửi đã được gỡ — dựng lại nó thì phải dựng luồng gửi tệp " +
      "trước, nếu không hai bước trả kết quả lại đứng im vĩnh viễn",
  );
  // Luật CÒN GIỮ: một cuộc gọi hụt vẫn không được mang nhãn đã trả kết quả.
  assert.match(
    svc,
    /loai == "TRA_KQ" and ket_qua != "DA_LIEN_HE"/,
    "vẫn phải chặn ghi 'đã trả kết quả' cho một lần gọi chưa thành công",
  );
});
