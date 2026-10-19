import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";
import {
  khoaChongGuiTrung,
  soLuongPhieuHopLe,
  xoaKhoaChongGuiTrung,
} from "../app/(dashboard)/kho-vat-tu/gui-vat-tu.ts";

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
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(gui, /\/api\/vat-tu-kho\//);
  assert.doesNotMatch(gui, /\/api\/v1\//);
  assert.match(lap, /loai === "NHAP" \? \(/);
  assert.match(lap, /gia_nhap: loai === "NHAP" \?/);
  assert.match(lap, /don_vi: vatTu\.find/);
});

test("số lượng phiếu chặn số không hợp lệ ngay trên form theo loại phiếu", () => {
  assert.equal(soLuongPhieuHopLe("NHAP", "2"), true);
  assert.equal(soLuongPhieuHopLe("NHAP", "1,25"), true);
  assert.equal(soLuongPhieuHopLe("NHAP", "0"), false);
  assert.equal(soLuongPhieuHopLe("XUAT_PHONG", "-1"), false);
  assert.equal(soLuongPhieuHopLe("NHAP", "NaN"), false);
  assert.equal(soLuongPhieuHopLe("NHAP", "Infinity"), false);
  assert.equal(soLuongPhieuHopLe("NHAP", "1.0001"), false);
  assert.equal(soLuongPhieuHopLe("NHAP", "1000000000000000"), false);
  assert.equal(soLuongPhieuHopLe("KIEM", "0"), true);
  assert.equal(soLuongPhieuHopLe("DIEU_CHINH", "0"), true);
  assert.equal(soLuongPhieuHopLe("DIEU_CHINH", "-1"), false);
});

test("Idempotency-Key của phiếu được giữ qua tải lại và chỉ xoá sau khi thành công", () => {
  let raw: string | null = null;
  const storage = {
    getItem: () => raw,
    setItem: (_key: string, value: string) => { raw = value; },
    removeItem: () => { raw = null; },
  };
  const body = { loai: "NHAP", dong: [{ vat_tu_id: "vt-1", so_luong: "2" }] };
  const khoa1 = khoaChongGuiTrung(body, storage, 1000);
  assert.equal(khoaChongGuiTrung(body, storage, 2000), khoa1);
  const khoa2 = khoaChongGuiTrung({ ...body, ghi_chu: "khác" }, storage, 3000);
  assert.notEqual(khoa2, khoa1);

  xoaKhoaChongGuiTrung(khoa1, storage);
  assert.notEqual(khoaChongGuiTrung(body, storage, 4000), khoa1);
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
  assert.match(khung, /ma: "cho_duyet", nhan: "Chờ duyệt", dem: dangCho > 0 \? dangCho : undefined/);
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
