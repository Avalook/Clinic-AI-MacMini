// Ranh giới của màn phòng dịch vụ và phiếu kết quả (Lifecycle v1 Slice 5–6).
//
// Bốn bất biến dưới đây không phải chuyện thẩm mỹ — mỗi cái đã có một cách
// hỏng cụ thể ở đời thật, và bài kiểm này giữ cho cách hỏng ấy không quay lại.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

/** Bỏ chú thích: nhắc tên một quyền trong lời giải thích là tốt, CHÉP luật vào
 *  mã mới là lỗi. Bài kiểm phải phân biệt được hai chuyện đó. */
const chiMa = (nguon: string) =>
  nguon.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

const PHONG = doc("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
const PHIEU = doc("../app/(dashboard)/_lam-viec/PhieuKetQua.tsx");
const PROXY_PHIEU = doc("../app/api/phieu/route.ts");
const PROXY_LUOT = doc("../app/api/luot-kham/route.ts");
const PROXY_QUYEN = doc("../app/api/phan-quyen/route.ts");
const NHOM = doc("../app/(dashboard)/phan-quyen/NhomQuyenMau.tsx");

test("năm lệnh thực hiện đều gửi kèm revision đang thấy", () => {
  // Bấm bằng số cũ = ghi đè việc người khác vừa làm. Máy chủ chỉ từ chối được
  // nếu màn CÓ GỬI số nó đang thấy.
  for (const lenh of [
    "bat-dau-v1",
    "xong-v1",
    "khong-lam-v1",
    "gian-doan-v1",
    "lam-lai-v1",
  ]) {
    assert.ok(
      PHONG.includes(`"${lenh}"`),
      `màn phòng phải bấm được lệnh ${lenh}`,
    );
  }
  const soLanGuiRevision = PHONG.match(/expected_execution_revision/g) ?? [];
  assert.ok(
    soLanGuiRevision.length >= 5,
    "mỗi lệnh phải kèm expected_execution_revision",
  );
  assert.match(
    PHONG,
    /expected_routing_revision: th\.routing_revision/,
    "Bắt đầu còn phải khớp cả revision xếp phòng",
  );
});

test("Xong và Dừng giữa chừng luôn chỉ đúng lần làm đang chạy", () => {
  // Request cũ của lần làm #1 tới muộn KHÔNG được đóng lần làm #2. Màn phải
  // gửi attempt_id lấy từ trạng thái vừa đọc, không tự bịa.
  assert.match(PHONG, /attempt_id: th\.lan_dang_chay!\.id/);
  assert.match(PHONG, /interrupted_attempt_id: th\.lan_da_dung!\.id/);
  assert.ok(
    !/attempt_no: /.test(PHONG),
    "không được định danh lần làm bằng số thứ tự",
  );
});

test("proxy phiếu chỉ mở đúng ba đường, và mã phiếu phải là UUID", () => {
  assert.match(PROXY_PHIEU, /\/api\/v1\/phieu\/mo/);
  assert.match(PROXY_PHIEU, /\$\{id\}\/luu/);
  assert.match(PROXY_PHIEU, /\$\{id\}\/hoan-tat/);
  assert.match(PROXY_PHIEU, /UUID_RE\.test\(id\)/);
  // Luật quyền ở service, không chép sang tầng proxy — bản sao thứ hai là bản
  // sao sẽ lệch.
  const ma = chiMa(PROXY_PHIEU);
  assert.ok(!/result\.form\.fill/.test(ma));
  assert.ok(!/DOCTOR|NURSE|MANAGEMENT/.test(ma));
});

test("đọc trạng thái thực hiện đi qua danh sách trắng, mã phải là UUID", () => {
  assert.match(PROXY_LUOT, /xem === "thuc-hien"/);
  assert.match(
    PROXY_LUOT,
    /UUID_RE\.test\(cd\)\s*\n?\s*\? `\/api\/v1\/luot-kham\/orders\/\$\{cd\}\/execution`/,
  );
});

test("phiếu lưu lần cuối trước khi chốt, và khai rõ nguồn giá trị", () => {
  // Gõ xong bấm ngay [Hoàn tất] trong khoảng lặng tự lưu thì câu vừa viết chưa
  // tới máy chủ — chốt xong là mất đúng câu ấy.
  const viTriLuu = PHIEU.indexOf('thao_tac: "luu"', PHIEU.indexOf("const hoanTat"));
  const viTriChot = PHIEU.indexOf('thao_tac: "hoan-tat"');
  assert.ok(viTriLuu > 0 && viTriLuu < viTriChot, "phải lưu trước khi hoàn tất");
  assert.match(PHIEU, /nguon: "USER"/);
  // "Hoàn tất = xác nhận toàn bộ" phải nói ra trên màn, không chỉ nằm trong
  // tài liệu — đây là lúc người nhận trách nhiệm.
  assert.match(PHIEU, /xác nhận toàn bộ/i);
});

test("màn phòng không còn gửi nội dung kết quả kèm lệnh Xong", () => {
  // "Đã làm xong" ≠ "đã có kết quả". Kết quả đi qua phiếu, có vòng đời riêng.
  assert.ok(!/result_note/.test(PHONG), "result_note thuộc đường cũ");
  assert.ok(!/"xong-dich-vu"/.test(PHONG), "đường cũ không còn dùng ở màn này");
});

test("phòng dịch vụ chỉ có MỘT nút kết thúc", () => {
  // ChatGPT tin số 156, Tuyền tin số 157: *"chỉ cần 1 nút bắt đầu … nút chỉ 1"*.
  // Nút [Hoàn tất] của phiếu đóng luôn dịch vụ; nút gọi thẳng lệnh đóng chỉ
  // hiện khi dịch vụ KHÔNG có phiếu kết quả nào (lấy mẫu gửi đi).
  const ma = chiMa(PHONG);
  assert.equal(
    (ma.match(/"xong-v1"/g) ?? []).length,
    1,
    "chỉ được một chỗ gọi lệnh đóng dịch vụ",
  );
  assert.match(
    ma,
    /th\.mau_ket_qua\.length === 0/,
    "nút đóng thẳng chỉ dành cho dịch vụ không có phiếu",
  );
  // Ba ngoại lệ không được là nút chính.
  assert.doesNotMatch(
    ma,
    /variant="primary"[\s\S]{0,400}(gian-doan-v1|khong-lam-v1)/,
  );
});

test("hoàn tất rồi vẫn sửa được, và lần sửa được ghi lại", () => {
  // Tuyền 23/09: "vẫn cho sửa được vì audit log được mà".
  assert.match(PHIEU, /thao_tac: "mo-sua"/);
  assert.match(PHIEU, /Sửa lại/);
  assert.match(PHIEU, /Xác nhận sửa/);
  // Trong lúc sửa, bản cũ vẫn là kết quả chính thức — màn phải nói ra.
  assert.match(PHIEU, /bản cũ vẫn là kết quả chính thức/);
  assert.match(PROXY_PHIEU, /\$\{id\}\/mo-sua/);
});

test("quản lý sửa được nhóm quyền mẫu, và màn nói rõ nó không phải quyền", () => {
  assert.match(PROXY_QUYEN, /"luu-nhom"/);
  assert.match(PROXY_QUYEN, /"xoa-nhom"/);
  // Mã nhóm do người đặt nên KHÔNG phải UUID — vẫn phải kiểm hình dạng.
  assert.match(PROXY_QUYEN, /\^\[A-Za-z0-9_\]\{2,32\}\$/);
  // Câu cảnh báo quan trọng nhất trên màn ấy.
  assert.match(NHOM, /không<\/strong>\s*đổi\s*\n?\s*quyền của người đã được cấp/);
});

test("mở sửa phải nạp lại phiếu từ máy chủ, không giữ nội dung cũ", () => {
  // A gõ dở; B bấm [Sửa lại] khi màn còn bản cũ. Nếu chỉ lấy `revision` thì B
  // nhận SỐ mới với NỘI DUNG cũ, và lần tự lưu tới ghi đè chữ của A — bằng một
  // số hợp lệ, nên không lớp chống ghi đè nào bắt được.
  assert.match(
    PHIEU,
    /const kq = await goi<Phieu>\(\{ thao_tac: "mo-sua"/,
    "mo-sua phải nhận cả phiếu, không chỉ revision",
  );
  assert.match(PHIEU, /nhan\(kq\.data\)/);
});

test("huỷ sửa cũng phải kèm revision đang thấy", () => {
  // Bản nháp là của CHUNG. Lệnh GHI đã chống ghi đè; lệnh PHÁ HUỶ mà không
  // chống thì một màn hình cũ xoá được cái người khác vừa gõ.
  const i = PHIEU.indexOf('thao_tac: "huy-sua"');
  assert.ok(i > 0);
  assert.match(
    PHIEU.slice(i, i + 220),
    /expected_revision: revision\.current/,
  );
});

test("đổi người thực hiện thì tự lưu ngay", () => {
  // Người thực hiện là dữ liệu nghiệp vụ, không phải trạng thái màn hình.
  const i = PHIEU.indexOf("setThucHienBoi(ai)");
  assert.ok(i > 0, "onChange phải giữ lựa chọn");
  assert.match(PHIEU.slice(i, i + 500), /tuLuu\(gia, phieu, ai\)/);
});

test("nút Xác nhận sửa KHÔNG khoá vì chưa gõ lý do", () => {
  // Máy chủ hỏi "có đổi gì không" TRƯỚC rồi mới đòi lý do. Khoá nút ở đây là
  // bắt người ta gõ lý do cho một thay đổi không tồn tại.
  assert.doesNotMatch(PHIEU, /disabled=\{dangHoanTat \|\| \(dangSuaLai && !lyDoSua/);
});
