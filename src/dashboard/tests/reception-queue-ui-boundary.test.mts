import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const board = readFileSync(
  new URL("../app/(dashboard)/reception/queue/QueueBoard.tsx", import.meta.url),
  "utf8",
);

/** Mã THỰC THI, đã bóc hết chú thích.
 *
 * Dùng cho mọi phép `doesNotMatch`. Chú thích được phép NHẮC tới thứ đã bỏ — đó
 * chính là chỗ giải thích vì sao nó bị bỏ — nhưng nhắc trong chú thích thì bài
 * kiểm lại báo vi phạm. Bản đầu của bài này đỏ đúng vì lý do ấy, và một bài
 * canh bắt nhầm là một bài canh sẽ bị người ta tắt đi.
 */
const maThucThi = board
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .split("\n")
  .map((d) => d.split("//")[0])
  .join("\n");

test("the reception queue keeps the reference design's three working regions", () => {
  assert.match(board, /aria-label="Danh sách hàng đợi"/);
  assert.match(board, /aria-label="Thông tin người bệnh"/);
  assert.match(board, /aria-label="Điều phối tại quầy"/);
  assert.match(
    board,
    /xl:grid-cols-\[minmax\(280px,0\.9fr\)_minmax\(380px,1\.25fr\)_minmax\(240px,0\.8fr\)\]/,
  );
  assert.doesNotMatch(maThucThi, /Chưa có: điều phối quầy/);
});

test("danh sách hàng đợi chỉ còn ô tìm — không tab, không bộ lọc", () => {
  // Tuyền 16/09/2026: bỏ tab "Khách ưu tiên" (dấu sao trên từng dòng đã nói),
  // bỏ "Cần xác minh" (nó dò một mã bước viết cứng), bỏ hai ô "Bộ lọc" /
  // "Sắp xếp" — hàng đợi chỉ có MỘT thứ tự đúng là thứ tự gọi khám, cho đổi
  // cách xếp là tạo ra một cái nhìn không khớp với thứ tự thật.
  assert.match(board, /Tìm tên, mã BN hoặc số thứ tự/);
  for (const daBo of ["Khách ưu tiên", "Cần xác minh", "Bộ lọc", "Sắp xếp"]) {
    assert.doesNotMatch(maThucThi, new RegExp(daBo), `"${daBo}" đáng lẽ đã bỏ`);
  }
  // Dấu sao ưu tiên PHẢI còn — nó là thứ thay cho cái tab vừa bỏ.
  assert.match(board, /item\.khach_uu_tien/);
});

test("panel bệnh nhân: MỘT mốc giờ, không thanh bước", () => {
  // Tuyền 16/09/2026: *"check-in đồng nghĩa là thời điểm vào hàng đợi rồi mà"*.
  // Ba dòng "Thời điểm đến / Vào hàng đợi lúc / Bắt đầu xử lý" kể gần như cùng
  // một chuyện; mốc bắt đầu khám là thời gian CON trong khoảng check-in →
  // check-out. Thanh bước hai vòng tròn cũng đi theo: nó chỉ vẽ lại đúng hai
  // thứ mà dòng "Check-in" và nút "Vào khám" đã nói.
  assert.match(board, /label="Check-in"/);
  for (const daBo of ["Thời điểm đến", "Vào hàng đợi lúc", "Trạng thái xử lý", "Stepper"]) {
    assert.doesNotMatch(maThucThi, new RegExp(daBo), `"${daBo}" đáng lẽ đã bỏ`);
  }
  assert.match(board, /item\.checked_in_at/);
});

test("hành động ở quầy nói đúng việc Lễ tân thật sự làm", () => {
  // CHECK-IN cho khách đặt lịch trước — khách đến trực tiếp đã được check-in
  // sẵn lúc tạo lịch.
  assert.match(board, /Check-in — khách đã đến/);
  assert.match(board, /Đã check-in lúc/);
  // Đi qua ĐÚNG đường mà nút "Đã đến" ở Trang chủ đi. Hai đường check-in là
  // hai luật cấp số thứ tự chờ ngày lệch nhau.
  assert.match(board, /action: "checkin"/);

  // CHƯA ĐẾN ≠ VẮNG MẶT. Người chưa có mặt vẫn ở trong hàng đợi, chỉ bị bỏ qua
  // lượt này; đến sau vẫn check-in được và luật đến-muộn tự áp dụng.
  assert.match(board, /Chưa đến — gọi người tiếp theo/);
  for (const nhanCu of ["Đánh dấu vắng mặt", "Tạm giữ", "Xử lý ngoại lệ"]) {
    assert.doesNotMatch(maThucThi, new RegExp(nhanCu));
  }

  // MỘT NÚT "VÀO KHÁM" thay cho cặp "Bắt đầu xử lý" + "Xong tiếp nhận" (Tuyền
  // 16/09/2026) — ở quầy hai nút ấy luôn bấm liền nhau. Nhưng vẫn gửi ĐỦ hai
  // lệnh xuống kernel: bỏ lệnh `complete` là bước tiếp nhận không bao giờ đóng
  // và khách kẹt ở quầy.
  assert.match(board, /"Vào khám"/);
  assert.match(maThucThi, /issue\("start", v\)/);
  assert.match(maThucThi, /issue\("complete", v\)/);
  for (const daBo of ["Xong tiếp nhận", "Bắt đầu xử lý"]) {
    assert.doesNotMatch(maThucThi, new RegExp(daBo));
  }
  assert.doesNotMatch(maThucThi, /issue\("skip"/);
  assert.match(board, /filtered\.find\(\(item\) => item\.id === selectedId\) \?\?/);
});

test("MỜI TÊN, không mời số", () => {
  // Ở quầy tiếp nhận, Lễ tân gọi TÊN người bệnh — số thứ tự chỉ để đối chiếu.
  assert.match(board, /Mời</);
  assert.match(board, /item\.patient\.full_name/);
  assert.doesNotMatch(maThucThi, /Mời số</);
});

test("không bịa dữ liệu vận hành", () => {
  // Phần giá trị nhất của bài kiểm cũ, giữ nguyên: màn hình không được vẽ ra
  // tên người, số quầy hay số thẻ BHYT mà hệ thống chưa hề có.
  assert.doesNotMatch(maThucThi, /Trần Ngọc Mai|A021|Quầy 0[1-9]|BHYT:\s*\d/);
});
