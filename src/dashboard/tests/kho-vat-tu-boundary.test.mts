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
  for (const f of ["page.tsx", "KhoVatTu.tsx", "TonVatTu.tsx", "LapPhieuVatTu.tsx", "DanhSachPhieuVatTu.tsx", "TieuHaoVatTu.tsx", "ChoDuyetVatTu.tsx"]) {
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
  for (const a of ["ton", "canh-bao", "phieu", "tieu-hao", "hoan", "muc-toi-thieu"]) {
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

test("điều hướng dùng việc nhân viên làm, không bắt họ hiểu từ 'phiếu'", () => {
  const khung = doc(new URL("KhoVatTu.tsx", thuMuc));
  assert.match(khung, /nhan: "Tồn kho"/);
  assert.match(khung, /nhan: "Nhập hàng"/);
  assert.match(khung, /nhan: "Cấp cho phòng"/);
  assert.match(khung, /nhan: "Kiểm kê"/);
  assert.match(khung, /nhan: "Lịch sử & báo cáo"/);
  assert.match(khung, /nhan: "Quản lý"/);
  assert.match(khung, /nhan: "Yêu cầu nhập cần duyệt"/);
  assert.match(khung, /<LapPhieuVatTu\s+key=\{tab\}/);
  assert.doesNotMatch(khung, /nhan: "Phiếu"/);
});

test("màn tồn giải thích kết quả thao tác và không đưa cài đặt ngưỡng vào bảng rỗng", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  assert.match(ton, /Còn bao nhiêu vật tư ở từng kho và phòng/);
  assert.match(ton, /Nhập hàng/);
  assert.match(ton, /Kiểm kê tồn ban đầu/);
  assert.match(ton, /Bắt đầu nhập hàng/);
  assert.match(ton, /onClick=\{\(\) => onLamNhanh\("nhap"\)\}/);
  assert.doesNotMatch(ton, /Đặt mức tối thiểu cho vật tư chưa có trong bảng/);
});

test("lọc vị trí gọn, hướng dẫn xuất kho và kiểm kê phân biệt sổ với số đếm", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(ton, /Xem tồn tại/);
  assert.doesNotMatch(ton, /nhan="Nơi chứa"/);
  assert.match(lap, /Tồn sổ/);
  assert.match(lap, /số đếm thực tế/);
  assert.match(lap, /chênh lệch/);
});

test("nút ghi nhận phiếu huỷ không lặp cụm 'Ghi nhận'", () => {
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(lap, /loai === "HUY"\s*\?\s*kieu\.nhan\s*:\s*`Ghi nhận \$\{kieu\.nhan\.toLocaleLowerCase\("vi"\)\}`/);
});

// ── G8b (15/10/2026): tab "Chờ duyệt" — phiếu NHẬP có dòng cần duyệt ────────────────────────
// Máy chủ quyết quyền (lego Duyệt vật tư), lý do, "chỉ quyết một lần"; màn chỉ vẽ + gửi.

const choDuyet = doc(new URL("ChoDuyetVatTu.tsx", thuMuc));

test("tab Chờ duyệt: xác nhận tại chỗ, nút theo cờ máy chủ trả, không luật quyền trong TSX", () => {
  assert.match(choDuyet, /XacNhanTaiCho/);
  // Nút Duyệt / Từ chối chỉ hiện khi máy chủ báo `duoc_duyet`; Rút lại theo `cua_toi` hoặc `duoc_duyet`.
  assert.match(choDuyet, /goi\.duoc_duyet \?/);
  assert.match(choDuyet, /y\.cua_toi \|\| goi\.duoc_duyet/);
  // Không tự suy quyền từ vai / mã quyền trong TSX.
  assert.doesNotMatch(choDuyet, /vat_tu\.approve|MANAGEMENT|role\s*===|vai\s*===|quyenCuaToi|useQuyen/);
  // Từ chối bắt lý do (nút đồng ý khoá tới khi đủ ký tự); lý do đi nguyên văn qua proxy.
  assert.match(choDuyet, /choDongY=\{lyDo\.trim\(\)\.length >= 5\}/);
  // Tự vẽ lại khi người khác quyết (bảng có trigger notify).
  assert.match(choDuyet, /useNgheBang\(\["vat_tu_nhap_cho_duyet"\]/);
});

test("tab Chờ duyệt: tab có số đếm chỉ khi có yêu cầu chờ, và tab luôn có mặt cho người chỉ xem", () => {
  const khung = doc(new URL("KhoVatTu.tsx", thuMuc));
  assert.match(khung, /ma: "cho_duyet", nhan: "Yêu cầu nhập cần duyệt", dem: dangCho > 0 \? dangCho : undefined/);
  assert.match(khung, /<ChoDuyetVatTu goi=\{choDuyet\}/);
});

test("lập phiếu NHẬP: báo 'gửi xin duyệt, chưa vào kho' / 'tự duyệt và nhập kho' theo kết quả máy chủ", () => {
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(lap, /Phiếu có dòng cần duyệt — đã gửi xin duyệt/);
  assert.match(lap, /chưa vào kho/);
  assert.match(lap, /đã tự duyệt và nhập kho/);
  // Chọn câu chữ theo trả lời của máy chủ, không tự đoán mặt hàng nào cần duyệt.
  assert.match(lap, /d\.cho_duyet/);
  assert.doesNotMatch(lap, /can_duyet_nhap_vat_tu/);
});

test("proxy: chỉ đọc cho-duyet + ba lệnh quyết qua danh sách trắng, mã yêu cầu phải là UUID", () => {
  for (const a of ["cho-duyet", "nhap-duyet", "nhap-tu-choi", "nhap-rut-lai"]) {
    assert.ok(route.includes(`"${a}"`), `proxy thiếu ${a}`);
  }
  assert.match(route, /\/api\/v1\/vat-tu-kho\/cho-duyet\/\$\{q\.yeu_cau_id\}/);
  assert.match(route, /Mã yêu cầu không hợp lệ/);
  // Không có đường nào nhận id yêu cầu mà không qua UUID_RE.
  assert.match(route, /UUID_RE\.test\(q\.yeu_cau_id\)/);
});
