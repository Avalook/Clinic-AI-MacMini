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

test("the queue list provides the documented navigation and finding controls", () => {
  for (const label of [
    "Tất cả",
    "Ưu tiên",
    "Cần xác minh",
    "Tìm tên, mã BN hoặc số thứ tự",
    "Bộ lọc",
    "Sắp xếp",
  ]) {
    assert.match(board, new RegExp(label));
  }
});

test("trạng thái chỉ còn HAI bước, và cả hai đều có dữ liệu thật", () => {
  // Bản trước có năm bước, ba trong số đó không bao giờ đổi trạng thái vì
  // không có dữ liệu đứng sau: "Đã gán quầy — chưa có dữ liệu quầy", "Gọi bệnh
  // nhân — chưa có mốc gọi số", "Hoàn tất tiếp nhận". Ba vòng tròn xám vĩnh
  // viễn không kể được điều gì, chỉ dạy người dùng bỏ qua cả thanh trạng thái.
  assert.match(board, /"Check-in"/);
  assert.match(board, /"Gọi vào khám"/);

  for (const buocDaBo of ["Đã gán quầy", "Xác nhận có mặt", "Hoàn tất tiếp nhận"]) {
    assert.doesNotMatch(maThucThi, new RegExp(buocDaBo));
  }

  // Cả hai bước phải đọc từ dữ liệu thật, không phải hằng số.
  assert.match(board, /item\.checked_in_at/);
  assert.match(board, /item\.status === "IN_PROGRESS"/);
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

  assert.match(board, /Xong tiếp nhận — mời vào khám/);
  assert.doesNotMatch(maThucThi, /issue\("skip"/);
  assert.match(board, /tab === "verify" && item\.node_code === "LUOTKHAM-02"/);
  assert.match(board, /"Bắt đầu xử lý"/);
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
