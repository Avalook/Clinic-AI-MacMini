import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import test from "node:test";
import {
  giaNhapPhieuHopLe,
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
  for (const f of ["page.tsx", "KhoVatTu.tsx", "TonVatTu.tsx", "LapPhieuVatTu.tsx", "DanhSachPhieuVatTu.tsx", "TieuHaoVatTu.tsx", "KiemKeCaVatTu.tsx", "ChoDuyetVatTu.tsx"]) {
    assert.ok(tsx.includes(f), `thiếu ${f}`);
  }
});

test("không hộp / chip vàng-đỏ cho việc bình thường", () => {
  for (const f of tsx) {
    const ma = doc(new URL(f, thuMuc));
    // Tab tồn có một dải hổ phách chỉ xuất hiện khi có vị trí tồn cần kiểm tra.
    const maKhongCanhBao = f === "TonVatTu.tsx"
      ? ma.replace("border-warning bg-warning-bg px-3 py-2 text-body text-warning", "")
      : ma;
    if (f === "TonVatTu.tsx") assert.match(ma, /role="status"[\s\S]*?Sắp hết \/ cần kiểm tra/);
    assert.doesNotMatch(maKhongCanhBao, /bg-warning|bg-danger|text-warning|tone="(warning|danger)"/, `${f} dùng màu cảnh báo`);
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

test("proxy từ chối phieu_id kiểm kê sai định dạng thay vì trả danh sách", () => {
  assert.match(
    route,
    /action === "kiem-ke-ca" && query\.has\("phieu_id"\) && !UUID_RE\.test\(query\.get\("phieu_id"\) \?\? ""\)[\s\S]*?Mã phiếu không hợp lệ\./,
  );
});

test("giao diện lập phiếu gửi qua proxy, không gọi thẳng FastAPI", () => {
  const gui = doc(new URL("gui-vat-tu.ts", thuMuc));
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(gui, /\/api\/vat-tu-kho\//);
  assert.doesNotMatch(gui, /\/api\/v1\//);
  assert.match(lap, /loai === "NHAP" \? \(/);
  assert.match(lap, /gia_nhap: loai === "NHAP" \?/);
  assert.match(lap, /giaNhapPhieuHopLe/);
  assert.match(lap, /don_vi: vatTuDaChonDong\.unit \?\? null/);
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

test("giá nhập vật tư chỉ nhận số hữu hạn không âm", () => {
  assert.equal(giaNhapPhieuHopLe(""), true);
  assert.equal(giaNhapPhieuHopLe("12000"), true);
  assert.equal(giaNhapPhieuHopLe("12,5"), true);
  assert.equal(giaNhapPhieuHopLe("0"), true);
  for (const value of ["-1", "NaN", "Infinity", "1e3", "1000000000000000"]) {
    assert.equal(giaNhapPhieuHopLe(value), false, value);
  }
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

test("điều hướng tách tồn, báo cáo, duyệt và danh mục; thao tác thường ngày nằm trong tồn", () => {
  const khung = doc(new URL("KhoVatTu.tsx", thuMuc));
  assert.match(khung, /nhan: "Tồn kho"/);
  assert.match(khung, /nhan: "Lịch sử & báo cáo"/);
  assert.match(khung, /nhan: "Danh mục"/);
  assert.match(khung, /nhan: laQuanLy \? "Chờ duyệt" : "Yêu cầu của tôi"/);
  assert.doesNotMatch(khung, /nhan: "Phiếu"/);
});

test("nút cấu hình phân loại và yêu cầu duyệt chỉ hiện trong giao diện Quản lý", () => {
  const danhMuc = doc(new URL("DanhMucVatTu.tsx", thuMuc));
  const thuocTinh = doc(new URL("../cashier/VatTuThuocTinh.tsx", thuMuc));
  const page = doc(new URL("page.tsx", thuMuc));
  assert.match(danhMuc, /suaDuoc && laQuanLy \? <DatCoTheoLoai/);
  assert.match(danhMuc, /\{laQuanLy \? \([\s\S]*Phân loại và phê duyệt/);
  assert.match(thuocTinh, /CO\.filter\(\(\[key\]\) => laQuanLy \|\| key === "chon_nhanh"\)/);
  assert.match(danhMuc, /\? \{[\s\S]*can_ql_duyet: duyetBanMoi/);
  assert.match(page, /laQuanLyDuyetVatTu/);
  assert.match(page, /laQuanLy=\{laQuanLy\}/);
});

test("màn tồn bỏ khối giải thích thừa, giữ lối tắt và không đưa cài đặt ngưỡng vào bảng rỗng", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  assert.doesNotMatch(ton, /Giải thích tồn kho|Còn bao nhiêu vật tư ở từng kho và phòng/);
  assert.match(ton, /Nhập hàng/);
  assert.match(ton, /Kiểm kê/);
  assert.match(ton, /onClick=\{\(\) => setMoNhapHang\(true\)\}/);
  assert.match(ton, /Mặt hàng mới cần được thêm trong Danh mục trước/);
  assert.doesNotMatch(ton, /Đặt mức tối thiểu cho vật tư chưa có trong bảng/);
});

test("bộ lọc tồn thấp dùng nhãn ngắn, dễ hiểu", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  assert.match(ton, /Sắp hết \/ cần kiểm tra/);
  assert.doesNotMatch(ton, /Dưới mức \/ cần kiểm đếm/);
});

test("các luồng trả vật tư và chuyển phòng mở trực tiếp từ dòng tồn", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(ton, /nhan: "Trả về kho"/);
  assert.match(ton, /nhan: "Chuyển sang phòng khác"/);
  assert.match(ton, /nhan: "Kiểm kê"/);
  assert.match(ton, /nhan: "Báo hỏng \/ huỷ"/);
  assert.match(lap, /loaiBanDau: "NHAP" \| "XUAT_PHONG" \| "TRA_KHO" \| "TRA_NCC"/);
  assert.match(lap, /initialRoomId\?: string \| null/);
  assert.match(lap, /fixedMaterial\?: string/);
});

test("kho vật tư bỏ tiêu đề và lời giải thích người dùng đã yêu cầu xoá", () => {
  const khung = doc(new URL("KhoVatTu.tsx", thuMuc));
  assert.doesNotMatch(khung, /<h1[^>]*>Kho vật tư<\/h1>/);
  assert.doesNotMatch(khung, /Xem vật tư còn ở kho cơ sở/);
  assert.doesNotMatch(khung, /Quản lý danh mục, đơn vị, giá/);
  assert.doesNotMatch(khung, /Ai làm, lúc nào, mặt hàng nào/);
  assert.doesNotMatch(khung, /Ghi số lượng vật tư hỏng hoặc huỷ cùng lý do/);
  assert.doesNotMatch(khung, /Ghi nhận vật tư chuyển giữa các phòng/);
  assert.doesNotMatch(khung, /Ghi nhận vật tư phòng trả về kho/);
  assert.doesNotMatch(khung, /Điều chỉnh tồn theo số đếm/);
});

test("chọn phòng báo rõ khi chưa có phòng hợp lệ", () => {
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(lap, /Chưa có phòng đang hoạt động/);
  assert.match(lap, /Chưa có phòng đã cấu hình/);
});

test("lịch sử có lọc loại thao tác, nơi và người thực hiện", () => {
  const ds = doc(new URL("DanhSachPhieuVatTu.tsx", thuMuc));
  const api = doc(new URL("../../../../clinicai/services/vat_tu_kho_man_service.py", thuMuc));
  assert.match(ds, /Lọc thao tác/);
  assert.match(ds, /Từ nơi/);
  assert.match(ds, /Đến nơi/);
  assert.match(ds, /Lọc người thực hiện/);
  assert.match(ds, /nguoi_tao_id/);
  assert.match(ds, /room_id/);
  assert.match(api, /'room_id', t\.room_id::text/);
  assert.match(ds, /tenVatTuHien/);
  assert.match(ds, /tenNoiChua\(d\.noi_chua\)/);
});

test("quản lý theo nhóm dùng nhãn và thao tác thêm hoặc gỡ nhãn", () => {
  const quanLy = doc(new URL("DatCoTheoLoai.tsx", thuMuc));
  assert.match(quanLy, /<span>Nhãn<\/span>/);
  assert.match(quanLy, /Thao tác với nhãn/);
  assert.match(quanLy, /Gắn nhãn/);
  assert.match(quanLy, /Gỡ nhãn/);
  assert.doesNotMatch(quanLy, /<span>Cờ<\/span>|<span>Đặt thành<\/span>/);
});

test("lọc vị trí gọn, hướng dẫn xuất kho và kiểm kê phân biệt sổ với số đếm", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(ton, /aria-label="Chọn nơi xem tồn"/);
  assert.doesNotMatch(ton, /nhan="Nơi chứa"/);
  assert.match(lap, /Tồn sổ/);
  assert.match(lap, /số đếm thực tế/);
  assert.match(lap, /chênh lệch/);
});

test("tồn kho tách Văn phòng phẩm và Vật tư y tế, chỉ đếm dòng tồn có thật", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  assert.match(ton, /Văn phòng phẩm/);
  assert.match(ton, /Vật tư y tế/);
  assert.match(ton, /aria-pressed=\{dangChon\}/);
  assert.match(ton, /const dangChon = nhom === muc\.ma/);
  assert.match(ton, /t\.gia_tri_ton/);
  assert.doesNotMatch(ton, /t\.so_luong \* hang\.gia_nhap/);
  assert.match(ton, /GIÁ TRỊ ƯỚC TÍNH/);
  assert.doesNotMatch(ton, /NƠI CHỨA/);
  assert.match(ton, /NHÃN/);
  assert.match(ton, /vatTu/);
  assert.doesNotMatch(ton, /“Cảnh báo dưới” là mức nhắc/);
});

test("quản lý có thể thêm vật tư vào danh mục; ngừng dùng là lưu trữ mềm", () => {
  const danhMuc = doc(new URL("DanhMucVatTu.tsx", thuMuc));
  const bangGia = doc(new URL("../cashier/VatTuBangGia.tsx", thuMuc));
  const proxy = doc(new URL("../app/api/service-price/route.ts", import.meta.url));
  const api = doc(new URL("../../../../clinicai/api/v1/routers/config.py", thuMuc));
  const service = doc(new URL("../../../../clinicai/services/config_service.py", thuMuc));
  assert.match(danhMuc, /Thêm vật tư vào danh mục/);
  assert.match(bangGia, /Tạm ngưng/);
  assert.match(proxy, /body\.group === "vat_tu"/);
  assert.match(proxy, /loai_vat_tu/);
  assert.match(api, /loai_vat_tu: str \| None/);
  assert.match(service, /group == "vat_tu"/);
  assert.match(service, /gia_nhap_vat_tu/);
});

test("tồn kho chọn riêng kho hoặc một phòng, không trộn số lượng giữa các nơi", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  assert.match(ton, /nutPhamVi\("kho", "Kho"\)/);
  assert.doesNotMatch(ton, /Kho cơ sở/);
  assert.match(ton, /Theo phòng/);
  assert.match(ton, /Phòng đang xem/);
  assert.doesNotMatch(ton, /Tất cả kho và phòng/);
  assert.match(ton, /Phòng \$\{phongDangXem\?\.ten/);
});

test("thao tác theo dòng mở hộp thoại và nhãn Kho thống nhất trên màn", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  const choDuyet = doc(new URL("ChoDuyetVatTu.tsx", thuMuc));
  const ds = doc(new URL("DanhSachPhieuVatTu.tsx", thuMuc));
  assert.match(ton, /<HopChiTiet/);
  assert.match(lap, /<option value="">Kho<\/option>/);
  assert.match(choDuyet, /: "Kho"/);
  assert.match(ds, /ten === "Kho cơ sở" \? "Kho" : ten/);
  assert.match(ds, /\["kho", "Kho"\]/);
});

test("bổ sung cho phòng luôn là cấp kho → phòng, không tự tăng tồn phòng bằng phiếu nhập", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(ton, /loai: "XUAT_PHONG", nhan: "Cấp thêm từ kho"/);
  assert.match(ton, /loaiBanDau=\{phamVi === "kho" \? "NHAP" : "XUAT_PHONG"\}/);
  assert.match(lap, /den: loaiBanDau === "NHAP" \|\| loaiBanDau === "XUAT_PHONG" \? initialRoomId/);
});

test("thao tác tồn bắt đầu từ dòng vật tư đang xem", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  assert.match(ton, /Thao tác/);
  assert.match(ton, /Cấp cho phòng/);
  assert.match(ton, /Trả về kho/);
  assert.match(ton, /Chuyển sang phòng khác/);
  assert.match(ton, /Kiểm kê/);
  assert.match(ton, /<LapPhieuVatTu/);
  assert.match(ton, /TRA_NCC/);
  assert.match(ton, /fixedMaterial=\{vatTuDangMo\.ten\}/);
});

test("điều hướng chính không lặp từng kiểu phiếu thành tab riêng", () => {
  const khung = doc(new URL("KhoVatTu.tsx", thuMuc));
  assert.match(khung, /ma: "ton", nhan: "Tồn kho"/);
  assert.match(khung, /ma: "bao_cao", nhan: "Lịch sử & báo cáo"/);
  assert.match(khung, /ma: "cho_duyet",[\s\S]*nhan: laQuanLy \? "Chờ duyệt" : "Yêu cầu của tôi"/);
  assert.match(khung, /ma: "danh_muc", nhan: "Danh mục"/);
  assert.doesNotMatch(khung, /nhan: "Cấp từ kho cho phòng"/);
  assert.doesNotMatch(khung, /nhan: "Phòng trả về kho"/);
  assert.doesNotMatch(khung, /nhan: "Chuyển giữa các phòng"/);
});

test("nút ghi nhận phiếu huỷ không lặp cụm 'Ghi nhận'", () => {
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(lap, /loai === "HUY" \|\| loai === "TRA_NCC"\s*\?\s*kieu\.nhan/);
});

test("trả nhà sản xuất là giao dịch riêng có nhà cung cấp, lý do và có thể hoàn tác", () => {
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  const ds = doc(new URL("DanhSachPhieuVatTu.tsx", thuMuc));
  const service = doc(new URL("../../../../clinicai/services/vat_tu_kho_service.py", thuMuc));
  const router = doc(new URL("../../../../clinicai/api/v1/routers/vat_tu_kho.py", thuMuc));
  assert.match(lap, /Trả nhà sản xuất/);
  assert.match(lap, /Nhà sản xuất/);
  assert.match(lap, /nha_cung_cap/);
  assert.match(service, /TRA_NCC/);
  assert.match(service, /nha_cung_cap/);
  assert.match(router, /nha_cung_cap/);
  assert.match(ds, /TRA_NCC/);
  assert.match(ds, /tuNoi/);
  assert.match(ds, /denNoi/);
});

test("kiểm kê cho chọn chỉ lưu số đếm hoặc cập nhật tồn theo số đếm", () => {
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(lap, /Chỉ lưu số đếm/);
  assert.match(lap, /Cập nhật tồn theo số đếm/);
  assert.match(lap, /\bKIEM\b/);
  assert.match(lap, /\bDIEU_CHINH\b/);
});

test("tồn theo phòng phân biệt lượng được cấp, đã dùng, tồn sổ và số đếm thực tế", () => {
  const ton = doc(new URL("TonVatTu.tsx", thuMuc));
  assert.match(ton, /ĐƯỢC CẤP/);
  assert.match(ton, /ĐÃ DÙNG/);
  assert.match(ton, /CÒN LẠI/);
  assert.match(ton, /THỰC TẾ/);
  assert.match(ton, /cap_trong_ky/);
  assert.match(ton, /da_dung/);
  assert.match(ton, /thuc_te_gan_nhat/);
  assert.match(ton, /baoCao/);
});

test("ngày báo cáo nằm cùng hàng tab mức dùng và được chia sẻ với bảng tồn", () => {
  const khung = doc(new URL("KhoVatTu.tsx", thuMuc));
  const mucDung = doc(new URL("TieuHaoVatTu.tsx", thuMuc));
  assert.match(khung, /aria-label="Từ ngày"/);
  assert.match(khung, /aria-label="Đến ngày"/);
  assert.match(khung, /baoCao=\{baoCao\}/);
  assert.match(khung, /<TonVatTu[\s\S]*baoCao=\{baoCao\}/);
  assert.match(khung, /<TieuHaoVatTu[\s\S]*baoCao=\{baoCao\}/);
  assert.doesNotMatch(mucDung, /Kỳ \{ngay\(goi\.tu\)\}[\s\S]*Số liệu tính từ hai lần kiểm đếm/);
  assert.doesNotMatch(mucDung, /Kỳ báo cáo/);
  const choDuyet = doc(new URL("ChoDuyetVatTu.tsx", thuMuc));
  assert.doesNotMatch(choDuyet, /Phiếu nhập có mặt hàng đặt “cần duyệt nhập” chưa vào kho/);
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

test("tab Chờ duyệt có số đếm khi có yêu cầu đang chờ", () => {
  const khung = doc(new URL("KhoVatTu.tsx", thuMuc));
  assert.match(khung, /laQuanLy && dangCho > 0 \? dangCho : undefined/);
  assert.match(khung, /<ChoDuyetVatTu goi=\{choDuyet\}/);
});

test("kiểm kê vật tư gắn phòng/ca; chốt lưu số đếm và lệch, không tự sửa tồn", () => {
  const khung = doc(new URL("KhoVatTu.tsx", thuMuc));
  const kiemKe = doc(new URL("KiemKeCaVatTu.tsx", thuMuc));
  const api = doc(new URL("../../../../clinicai/api/v1/routers/vat_tu_kho.py", thuMuc));
  assert.match(khung, /ma: "kiem_ke_ca", nhan: "Kiểm kê ca"/);
  assert.match(khung, /<KiemKeCaVatTu noiChua=\{noiChua\}/);
  assert.match(kiemKe, /room_id: roomId,[\s\S]*ngay,[\s\S]*ca,[\s\S]*loai/);
  assert.match(kiemKe, /Số tồn không tự điều chỉnh/);
  assert.match(kiemKe, /Tồn sổ lúc chốt/);
  assert.ok(kiemKe.includes("/api/vat-tu-kho/kiem-ke-ca-chot"));
  assert.match(route, /"kiem-ke-ca-mo"/);
  assert.match(route, /"kiem-ke-ca-dem"/);
  assert.match(route, /"kiem-ke-ca-chot"/);
  assert.match(api, /@router\.post\("\/vat-tu-kho\/kiem-ke-ca\/\{phieu_id\}\/chot"\)/);
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


test("kiểm chỉ lưu số đếm có cấu hình và thao tác lặp giữ phạm vi", () => {
  const lap = doc(new URL("LapPhieuVatTu.tsx", thuMuc));
  assert.match(lap, /KIEM: \{ nhan:/);
  assert.match(lap, /setDong\(\[taoDongTrongPhamVi\(\)\]\)/);
  assert.match(lap, /\.\.\.ds, taoDongTrongPhamVi\(\)/);
  assert.match(lap, /fixedMaterialId/);
  assert.match(lap, /cungTen.length === 1/);
});
test("lịch sử gồm mọi nơi trong phiếu và công khai giới hạn tải", () => {
  const ma = doc(new URL("DanhSachPhieuVatTu.tsx", thuMuc));
  assert.match(ma, /diem.tu.includes\(tuNoi\)/);
  assert.match(ma, /diem.den.includes\(denNoi\)/);
  assert.match(ma, /gioi_han=50&bo_qua=\$\{tatCa.length\}/);
  assert.match(ma, /Bộ lọc áp dụng trong danh sách đã tải/);
});
