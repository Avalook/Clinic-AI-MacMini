// GOM TẢI LẠI ĐỒNG LOẠT — máy kiểm phạm vi (14/10/2026).
//
// Đo prod 30 phút, ~14 request/giây: CPU dashboard + api + db vọt đồng loạt rồi tụt
// về ~0 trong vài giây — một tin làm mọi màn đang mở cùng tải lại một lúc. Bất biến
// ở đây không tự lộ khi bị phá (màn vẫn đúng, chỉ tốn gấp N lần), nên canh bằng
// cách đọc mã.

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import test from "node:test";

import { laManTuTai } from "../lib/man-tu-tai.ts";

const GOC = new URL("../", import.meta.url);

const boChuThich = (ma: string) =>
  ma.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

const doc = (p: string) => boChuThich(readFileSync(new URL(p, GOC), "utf8"));

function moiTrang(thuMuc: URL, ra: string[] = []): string[] {
  for (const ten of readdirSync(thuMuc)) {
    const duong = new URL(ten, thuMuc);
    if (statSync(duong).isDirectory()) moiTrang(new URL(`${ten}/`, thuMuc), ra);
    else if (ten === "page.tsx") ra.push(duong.pathname);
  }
  return ra;
}

/** `/…/app/(dashboard)/phong/[ma]/page.tsx` → `/phong/x`. */
function routeCua(duong: string): string {
  const sau = duong.slice(duong.indexOf("/app/(dashboard)") + "/app/(dashboard)".length);
  return sau.replace(/\/page\.tsx$/, "").replace(/\[[^\]]+\]/g, "x") || "/";
}

const TRANG = moiTrang(new URL("app/(dashboard)/", GOC)).map((duong) => ({
  duong,
  route: routeCua(duong),
  ma: boChuThich(readFileSync(duong, "utf8")),
}));

test("useNgheBang: lệch ngẫu nhiên + trần chờ + một lượt một lúc", () => {
  const ma = doc("app/(dashboard)/dung-nghe-bang.ts");
  assert.match(ma, /taoNhipLamMoi\(\{/, "phải đi qua nhịp gộp, không tự hẹn giờ");
  assert.match(ma, /\.\.\.NHIP_NGHE_TIN/, "mọi người nghe tin phải lệch ngẫu nhiên + có trần chờ");
  assert.match(ma, /taoMotLuot\(\)/, "lượt tải lại phải một lượt một lúc");
  assert.match(ma, /await khiDoiRef\.current\(\)/, "phải chờ callback (nếu trả lời hứa) xong mới chạy lượt kế");
  assert.doesNotMatch(ma, /visibilitychange/, "tab ẩn do taoNhipLamMoi lo, không tự nghe thêm");
});

test("NHIP_NGHE_TIN: trần + lệch giữ xấu nhất ≤ ~1 giây", async () => {
  const { NHIP_NGHE_TIN, TRE_MAC_DINH } = await import("../lib/nhip-lam-moi.ts");
  assert.ok(NHIP_NGHE_TIN.choToiDa + NHIP_NGHE_TIN.jitter <= 1000);
  assert.ok(NHIP_NGHE_TIN.choToiDa >= TRE_MAC_DINH, "trần phải cho nhịp gộp đủ chỗ");
});

test("RealtimeRefresher: dòng SSE KHÔNG gỡ-gắn theo `lamMoiQuyenLuc` hay đường dẫn", () => {
  const ma = doc("app/(dashboard)/RealtimeRefresher.tsx");
  assert.match(
    ma,
    /\}, \[router, tables\]\);/,
    "effect giữ dòng SSE chỉ được phụ thuộc router + tables: prop từ cuộc gọi " +
      "/phan-quyen/toi đổi (hỏng lúc quá tải) mà mở lại EventSource là tự nhân tải",
  );
  assert.doesNotMatch(ma, /usePathname/, "đổi trang không được gỡ-gắn dòng; đọc window.location lúc cần");
  assert.equal(ma.match(/new EventSource\(/g)?.length, 1);
  assert.equal(ma.match(/router\.refresh\(\)/g)?.length, 1, "đúng MỘT chỗ dựng lại trang");
});

test("RealtimeRefresher: nối lại có lùi khi dòng hỏng hẳn, và dừng khi gỡ", () => {
  const ma = doc("app/(dashboard)/RealtimeRefresher.tsx");
  assert.match(ma, /taoNoiLai\(\{/);
  assert.match(ma, /readyState === EventSource\.CLOSED/, "chỉ tự nối lại khi trình duyệt đã bỏ cuộc");
  assert.match(ma, /noiLai\.dung\(\)/, "tab ẩn / rời màn phải huỷ hẹn nối lại");
  assert.match(ma, /noiLai\.thanhCong\(\)/, "mở được rồi phải quên các lần hỏng");
});

test("RealtimeRefresher: màn tự tải không dựng trang theo tin, theo nhịp, hay lúc hiện lại", () => {
  const ma = doc("app/(dashboard)/RealtimeRefresher.tsx");
  assert.match(ma, /canDungLaiTrang\(window\.location\.pathname, t, wanted\)/);
  assert.match(ma, /if \(!dangOManTuTai\(\)\) nhip\.batKip\(\)/);
  assert.match(ma, /if \(!dangOManTuTai\(\)\) nhip\.nhan\(\)/);
  // Đổi quyền/ca vẫn dựng lại ở MỌI màn — menu và phạm vi quầy phải đổi đúng giờ.
  assert.match(ma, /nhipRef\.current\?\.nhip\.nhan\(\)/);
});

test("trang tự tải KHÔNG gắn LiveBoardSync và KHÔNG đọc dữ liệu sống ở server", () => {
  const tuTai = TRANG.filter((t) => laManTuTai(t.route));
  assert.ok(tuTai.length >= 5, `phải thấy đủ các trang tự tải, thấy ${tuTai.length}`);
  for (const t of tuTai) {
    assert.doesNotMatch(
      t.ma,
      /LiveBoardSync/,
      `${t.route}: LiveBoardSync dựng thêm một lượt SSR lúc vào màn mà trang không có gì để làm mới`,
    );
    assert.doesNotMatch(
      t.ma,
      /fetchFromBackend\(/,
      `${t.route}: trang đọc dữ liệu sống ở server thì KHÔNG được liệt vào man-tu-tai — ` +
        "nó chỉ cập nhật nhờ router.refresh()",
    );
  }
});

test("trang gắn LiveBoardSync (đọc sống ở server) KHÔNG nằm trong danh sách tự tải", () => {
  for (const t of TRANG.filter((x) => /LiveBoardSync/.test(x.ma))) {
    assert.equal(laManTuTai(t.route), false, `${t.route} cần router.refresh()`);
  }
});

test("docBang dùng chung một lượt một lúc; chuông thông báo + ca của tôi cũng vậy", () => {
  assert.match(doc("app/(dashboard)/_lam-viec/api.ts"), /gopDoc\(url,/);
  const chuong = doc("app/(dashboard)/NotificationContext.tsx");
  assert.match(chuong, /taoMotLuot/);
  assert.match(chuong, /canHoiDuPhong\(trangThaiDong\.doc\(\)/, "nhịp dự phòng thưa khi dòng SSE sống");
});

test("không còn tay nghe SU_KIEN_BANG tự hẹn giờ ở màn kê phiếu / hành trình lượt", () => {
  for (const f of [
    "app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx",
    "app/(dashboard)/_lam-viec/phieu-kham/HanhTrinhLuot.tsx",
  ]) {
    const ma = doc(f);
    assert.doesNotMatch(ma, /addEventListener\(SU_KIEN_BANG/, `${f}: nghe qua useNgheBang`);
    assert.match(ma, /useNgheBang\(/);
  }
});

test("chuông ngày trực: tab ẩn không hỏi (không còn setInterval trần)", () => {
  const ma = doc("app/(dashboard)/thu-ngan/NgayTruc.tsx");
  assert.doesNotMatch(ma, /setInterval\(/);
  assert.match(ma, /nhipKhiHien\(tai, 30_000/);
});
