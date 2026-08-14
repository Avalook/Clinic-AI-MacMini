// Thống kê "số slot theo mốc khung giờ" — phép ĐẾM, và đếm sai thì không ai
// thấy bằng mắt. Bảng vẫn đầy đủ, chỉ là một con số hơi khác, và người đọc tin
// nó. Đó là lý do phần này nằm trong lib chứ không nằm trong tsx.

import assert from "node:assert/strict";
import test from "node:test";

import {
  khungGioVN,
  thongKeTheoKhungGio,
  tongKet,
  type LichDeDem,
} from "../lib/thong-ke-khung-gio.ts";
import { laKhamCu, laKhamMoi, nhanPhanLoaiKham } from "../lib/phan-loai-kham.ts";

function lich(p: Partial<LichDeDem> = {}): LichDeDem {
  return {
    slot_start: "2026-08-14T03:00:00+00:00", // 10:00 giờ VN
    status: "SCHEDULED",
    phan_loai: "Khám lần đầu",
    service: { name: "Phụ khoa" },
    ...p,
  };
}

test("gom theo GIỜ VIỆT NAM, không theo giờ quốc tế", () => {
  // Cái bẫy đã cắn hệ thống này nhiều lần. Một lịch 06:30 sáng giờ VN là 23:30
  // UTC HÔM TRƯỚC — gom theo giờ UTC thì nó rơi vào khung 23:30 của một ngày
  // khác, và bảng nói phòng khám có lịch lúc nửa đêm.
  assert.equal(khungGioVN("2026-08-13T23:30:00Z"), "06:30");
  assert.equal(khungGioVN("2026-08-14T03:00:00Z"), "10:00");
  assert.equal(khungGioVN("2026-08-14T16:00:00Z"), "23:00");
  assert.equal(khungGioVN("rác"), "", "chuỗi giờ hỏng thì trả rỗng, không ném");
});

test("một dòng giờ hỏng KHÔNG làm trắng cả bảng", () => {
  const ra = thongKeTheoKhungGio([lich(), lich({ slot_start: "rác" }), lich()]);
  assert.equal(ra.length, 1);
  assert.equal(ra[0].tong, 2, "hai dòng tốt vẫn được đếm");
});

test("LỊCH ĐÃ HUỶ KHÔNG ĐƯỢC ĐẾM", () => {
  // Ranh giới quan trọng nhất của bảng này. Bảng trả lời "khung nào đang kín";
  // một lịch huỷ không giữ chỗ của ai, và đếm nó vào là báo đầy chỗ còn trống —
  // rồi người trực từ chối một khách mà đáng lẽ xếp được.
  const ra = thongKeTheoKhungGio([
    lich(),
    lich({ status: "CANCELLED" }),
    lich({ status: "NO_SHOW" }),
    lich({ status: "DOCTOR_DECLINED" }),
  ]);
  assert.equal(ra[0].tong, 1);
});

test("tách khám mới / khám cũ / chưa rõ — ba ngăn, không phải hai", () => {
  // "Chưa rõ" KHÔNG được gộp vào khám cũ. Gộp thì mọi lịch chưa suy ra được
  // phân loại đều làm phồng số khách quay lại, và tỉ lệ mới/cũ — con số duy
  // nhất người quản lý nhìn ở bảng này — sai theo hướng lạc quan.
  const ra = thongKeTheoKhungGio([
    lich({ phan_loai: "Khám lần đầu" }),
    lich({ phan_loai: "Tái khám" }),
    lich({ phan_loai: "Tái khám" }),
    lich({ phan_loai: "" }),
  ]);
  assert.deepEqual(
    { tong: ra[0].tong, moi: ra[0].khamMoi, cu: ra[0].khamCu, chuaRo: ra[0].chuaRo },
    { tong: 4, moi: 1, cu: 2, chuaRo: 1 },
  );
  assert.equal(
    ra[0].khamMoi + ra[0].khamCu + ra[0].chuaRo,
    ra[0].tong,
    "ba ngăn phải cộng đúng bằng tổng",
  );
});

test("đếm theo dịch vụ, xếp giảm dần, lịch chưa chọn dịch vụ vẫn hiện", () => {
  const ra = thongKeTheoKhungGio([
    lich({ service: { name: "Phụ khoa" } }),
    lich({ service: { name: "Phụ khoa" } }),
    lich({ service: { name: "Sản khoa" } }),
    lich({ service: null }),
  ]);
  assert.deepEqual(ra[0].dichVu, [
    { ten: "Phụ khoa", so: 2 },
    { ten: "(chưa chọn dịch vụ)", so: 1 },
    { ten: "Sản khoa", so: 1 },
  ]);
});

test("các khung xếp theo thứ tự thời gian", () => {
  const ra = thongKeTheoKhungGio([
    lich({ slot_start: "2026-08-14T09:00:00+00:00" }), // 16:00
    lich({ slot_start: "2026-08-14T00:30:00+00:00" }), // 07:30
    lich({ slot_start: "2026-08-14T03:00:00+00:00" }), // 10:00
  ]);
  assert.deepEqual(ra.map((r) => r.khung), ["07:30", "10:00", "16:00"]);
});

test("dòng Tổng cộng đúng bằng tổng các khung", () => {
  const ds = [
    lich({ slot_start: "2026-08-14T00:30:00+00:00", phan_loai: "Tái khám" }),
    lich({ slot_start: "2026-08-14T03:00:00+00:00" }),
    lich({ slot_start: "2026-08-14T03:00:00+00:00", status: "CANCELLED" }),
  ];
  const dong = thongKeTheoKhungGio(ds);
  const t = tongKet(ds);
  assert.equal(t.tong, dong.reduce((s, d) => s + d.tong, 0));
  assert.equal(t.tong, 2, "lịch huỷ không vào tổng");
  assert.equal(t.khamMoi, 1);
  assert.equal(t.khamCu, 1);
});

test("cách gọi tên: Khám lần đầu → Khám mới, Tái khám → Khám cũ", () => {
  assert.equal(nhanPhanLoaiKham("Khám lần đầu"), "Khám mới");
  assert.equal(nhanPhanLoaiKham("Tái khám"), "Khám cũ");
  // "Chưa khám" (màn Danh sách bệnh nhân) là ngăn thứ ba, đi thẳng qua.
  assert.equal(nhanPhanLoaiKham("Chưa khám"), "Chưa khám");
  assert.equal(nhanPhanLoaiKham(""), "");
  assert.equal(nhanPhanLoaiKham(null), "");
  // Nhận CẢ cách gọi mới: dữ liệu đã đổi tên ở đâu đó vẫn hiện đúng thay vì
  // rơi xuống nhánh mặc định và mất màu.
  assert.equal(nhanPhanLoaiKham("Khám mới"), "Khám mới");
  assert.equal(nhanPhanLoaiKham("Khám cũ"), "Khám cũ");
});

test("đổi chữ hiển thị KHÔNG được làm phép đếm sai", () => {
  // `laKhamMoi`/`laKhamCu` là thứ bảng thống kê và màu nhãn dựa vào. Chúng phải
  // hiểu cả hai cách gọi, và phải LOẠI chuỗi rỗng ra khỏi cả hai bên.
  for (const v of ["Khám lần đầu", "Khám mới"]) {
    assert.ok(laKhamMoi(v), `${v} phải tính là khám mới`);
    assert.ok(!laKhamCu(v));
  }
  for (const v of ["Tái khám", "Khám cũ"]) {
    assert.ok(laKhamCu(v), `${v} phải tính là khám cũ`);
    assert.ok(!laKhamMoi(v));
  }
  for (const v of ["", null, undefined, "Chưa khám"]) {
    assert.ok(!laKhamMoi(v) && !laKhamCu(v), `${v} không thuộc bên nào`);
  }
});
