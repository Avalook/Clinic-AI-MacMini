// MỘT DÒNG SSE CHO CẢ TRÌNH DUYỆT — máy kiểm phạm vi (21/08/2026).
//
// Bất biến này không tự lộ khi bị phá. Thêm một `new EventSource` ở một màn nào
// đó chạy đúng, test đơn vị xanh, staging nhìn bình thường — cái giá chỉ hiện ra
// ở phòng khám thật, dưới dạng "hệ thống đơ, bấm nút không ăn", và mọi phép đo
// phía máy chủ vẫn báo khoẻ trong lúc ấy.
//
// SỐ ĐO. EventSource là kết nối HTTP/1.1 không bao giờ đóng, mà trình duyệt chỉ
// cho 6 kết nối tới một origin. Đo trên staging 21/08 bằng cách bắn 6 request
// /home cùng lúc rồi đếm số chạy song song: 1 tab còn 5 chỗ, 2 tab còn 4, 4 tab
// còn 2, tới tab thứ SÁU là hết sạch — tab mới không tải nổi trang (navigate
// treo 300 giây) trong khi CPU máy chủ là 0.03%.
//
// Đúng chuyện đó đã xảy ra một lần: `BookingHub` mở dòng thứ hai vì lý do chính
// đáng (nó chỉ muốn hỏi lại một endpoint nhẹ thay vì dựng lại cả trang), và hậu
// quả là một tab ở màn Đặt lịch nuốt HAI trong sáu chỗ. Muốn nghe một bảng cụ
// thể thì nghe `SU_KIEN_BANG` do `RealtimeRefresher` phát ra, đừng mở dòng mới.

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import test from "node:test";

const GOC = new URL("../", import.meta.url);

function moiFileNguon(thuMuc: URL, ra: string[] = []): string[] {
  for (const ten of readdirSync(thuMuc)) {
    if (ten === "node_modules" || ten === ".next" || ten.startsWith(".")) continue;
    const duong = new URL(ten, thuMuc);
    if (statSync(duong).isDirectory()) {
      moiFileNguon(new URL(`${ten}/`, thuMuc), ra);
    } else if (/\.(ts|tsx|mts)$/.test(ten)) {
      ra.push(duong.pathname);
    }
  }
  return ra;
}

const boChuThich = (ma: string) =>
  ma.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

const NGUON = moiFileNguon(GOC).map((p) => ({
  duong: p.slice(GOC.pathname.length),
  ma: boChuThich(readFileSync(p, "utf8")),
}));

test("chỉ RealtimeRefresher được mở EventSource", () => {
  const moDong = NGUON.filter((f) => /new EventSource\(/.test(f.ma)).map(
    (f) => f.duong,
  );
  assert.deepEqual(
    moDong,
    ["app/(dashboard)/RealtimeRefresher.tsx"],
    "mỗi dòng thêm là một trong sáu kết nối của trình duyệt bị giữ vĩnh viễn; " +
      "muốn nghe một bảng thì nghe SU_KIEN_BANG, đừng mở dòng mới",
  );
});

test("dòng ấy được bầu chủ, không phải mỗi tab một dòng", () => {
  const ma = NGUON.find(
    (f) => f.duong === "app/(dashboard)/RealtimeRefresher.tsx",
  )!.ma;
  assert.match(
    ma,
    /moDongSuKien\(\{/,
    "phải đi qua moDongSuKien — nó là chỗ bầu MỘT tab giữ dòng cho cả trình duyệt",
  );
  assert.match(
    ma,
    /navigator\.locks/,
    "bầu tab chủ bằng Web Locks: tab chủ đóng thì khoá tự nhả, không cần ai canh",
  );
  assert.match(
    ma,
    /new BroadcastChannel\(/,
    "tab chủ phải phát lại tin, không thì các tab kia mù",
  );
});

test("tab đang ẩn không được dựng lại trang", () => {
  const ma = NGUON.find(
    (f) => f.duong === "app/(dashboard)/RealtimeRefresher.tsx",
  )!.ma;
  assert.match(
    ma,
    /taoNhipLamMoi\(\{/,
    "router.refresh() phải qua nhịp gộp, không gọi thẳng",
  );
  assert.equal(
    ma.match(/router\.refresh\(\)/g)?.length,
    1,
    "đúng MỘT chỗ gọi router.refresh(), và nó nằm trong nhịp — " +
      "một chỗ gọi thẳng là một đường vòng qua cả gộp nhịp lẫn luật tab ẩn",
  );
  assert.match(
    ma,
    /visibilitychange/,
    "nợ làm mới phải được trả lúc người ta quay lại nhìn",
  );
});
