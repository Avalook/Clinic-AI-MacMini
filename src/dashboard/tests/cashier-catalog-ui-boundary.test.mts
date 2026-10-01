import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

const view = read("../app/(dashboard)/cashier/CashierView.tsx");
const medicinePage = read("../app/(dashboard)/cashier/thuoc/page.tsx");
const servicePage = read("../app/(dashboard)/cashier/dich-vu/page.tsx");
const indexPage = read("../app/(dashboard)/cashier/page.tsx");

test("cashier catalog uses the V2 workspace and editor regions", () => {
  assert.match(view, /aria-label="Danh mục bảng giá"/);
  assert.match(view, /aria-label="Thêm dòng bảng giá"/);
  assert.match(
    view,
    /2xl:grid-cols-\[minmax\(0,1fr\)_minmax\(300px,360px\)\]/,
  );
});

test("catalog controls operate on real rows and expose missing prices", () => {
  for (const label of [
    "Tìm theo mã hoặc tên",
    "Tất cả trạng thái",
    "Thiếu giá",
    "Đang áp dụng",
    "Tạm ngưng",
  ]) {
    assert.match(view, new RegExp(label));
  }
  assert.match(view, /rows\.filter\(\(row\) => row\.unit_price === null\)\.length/);
  assert.match(view, /rows\.filter\(\(row\) => row\.active\)\.length/);
});

test("catalog preserves the existing API mutations without bypassing backend", () => {
  assert.match(view, /fetch\("\/api\/service-price"/);
  for (const method of ['send\("POST"', 'send\("PATCH"', 'send\("DELETE"']) {
    assert.match(view, new RegExp(method.replace("(", "\\(")));
  }
  assert.doesNotMatch(view, /supabase|#[0-9a-f]{3,8}|bg-white/iu);
});

test("the two routes stay server-filtered and the legacy index remains a redirect", () => {
  // Điều cần canh là LỌC Ở MÁY CHỦ, không phải cách viết truy vấn.
  //
  // Bản cũ ghim vào `.eq("group", "thuoc")` — cú pháp của PostgREST. Hai trang
  // nay đọc qua FastAPI (`/api/v1/service-prices?group=…`) vì đọc thẳng bảng
  // cần một vai Postgres mà database cho thuê không cho tạo. Cùng tính chất —
  // máy chủ lọc, trình duyệt không nhận cả bảng giá rồi tự lọc — chỉ khác chỗ
  // thực hiện. Ghim vào cách viết thì mọi lần đổi tầng đều đỏ dù luật y nguyên.
  assert.match(medicinePage, /service-prices\?group=thuoc/);
  assert.match(medicinePage, /group="thuoc"/);
  // Bảng giá dịch vụ & phòng (01/10/2026): máy chủ trả RIÊNG dịch vụ kèm
  // phòng làm được (`/service-prices/danh-muc`) — vẫn lọc ở máy chủ.
  assert.match(servicePage, /service-prices\/danh-muc/);
  assert.match(servicePage, /DanhMucDichVuPhong/);
  assert.doesNotMatch(`${medicinePage}\n${servicePage}`, /error\.message/);
  assert.match(indexPage, /redirect\("\/cashier\/thuoc"\)/);
});

test("bảng giá dịch vụ & phòng: lọc chưa có phòng, gán phòng qua cấu hình, không xoá", () => {
  const dv = read("../app/(dashboard)/cashier/DanhMucDichVuPhong.tsx");
  assert.match(dv, /chua_co_phong/);
  assert.match(dv, /what: "service-rooms"/);
  assert.match(dv, /sua_phong_duoc/);
  // Thôi bán = bỏ tick "Đang bán" — không nút xoá, không window.confirm.
  assert.doesNotMatch(dv, /"DELETE"|window\.confirm|style=\{\{/);
  assert.doesNotMatch(dv, /supabase|#[0-9a-f]{3,8}\b|bg-white/iu);
});
