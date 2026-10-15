import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { nhanLanChamCuoi } from "../app/(dashboard)/customers/mot-cham.ts";

// 15/10/2026 (Tuyền): khách mới chỉ có tên + "Chỉ lưu hồ sơ — chưa đặt lịch" thì lưu
// xong NHẢY SANG Quản lý khách hàng (mở đúng khách), không ra màn khác; khách ấy mang
// việc "Gọi điện xác nhận" để CSKH gọi, gọi xong thì việc mất, rút lại được.
const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const form = doc("../app/(dashboard)/patients/new/NewPatientForm.tsx");
const trangMoi = doc("../app/(dashboard)/patients/new/page.tsx");
const trangHen = doc("../app/(dashboard)/appointments/page.tsx");
const hub = doc("../app/(dashboard)/appointments/BookingHub.tsx");
const vung = doc("../app/(dashboard)/customers/VungLamViecKhach.tsx");

const thanHam = form.match(
  /function goToProfile\(id: string, code\?: string, moi = false\) \{([\s\S]*?)\n  \}/,
)?.[1];

function dich(o: {
  role: string;
  walkin: boolean;
  appointment: boolean;
  tiepDon: boolean;
  quanLy: boolean;
  moi: boolean;
}): string[] {
  assert.ok(thanHam, "goToProfile có mặt");
  const make = new Function(
    "role",
    "walkin",
    "wantsAppointment",
    "veTiepDon",
    "veQuanLyKhach",
    "router",
    "khoaNhapKhach",
    `return function(id, code, moi) {${thanHam}}`,
  );
  const dichDen: string[] = [];
  make(
    o.role,
    o.walkin,
    o.appointment,
    o.tiepDon,
    o.quanLy,
    { push: (u: string) => dichDen.push(u) },
    null,
  )("khach 1", undefined, o.moi);
  return dichDen;
}

test("chỉ lưu hồ sơ → Quản lý khách hàng, mở đúng khách, MỌI vai vào được màn ấy", () => {
  for (const role of ["RECEPTION", "TRUONG_CA", "MANAGEMENT", "CSKH"]) {
    for (const tiepDon of [true, false]) {
      assert.deepEqual(
        dich({ role, walkin: false, appointment: false, tiepDon, quanLy: true, moi: true }),
        ["/customers?selected=khach%201"],
        `${role} tiepDon=${tiepDon}`,
      );
    }
  }
});

test("lưu + đặt lịch giữ đường cũ (không sang Quản lý khách hàng)", () => {
  assert.deepEqual(
    dich({ role: "RECEPTION", walkin: false, appointment: true, tiepDon: true, quanLy: true, moi: true }),
    ["/reception/queue"],
  );
  assert.deepEqual(
    dich({ role: "RECEPTION", walkin: false, appointment: true, tiepDon: false, quanLy: true, moi: true }),
    ["/patient-list"],
  );
});

test("'Dùng bệnh nhân này' (khách có sẵn, moi=false) giữ đường cũ", () => {
  assert.deepEqual(
    dich({ role: "RECEPTION", walkin: false, appointment: false, tiepDon: true, quanLy: true, moi: false }),
    ["/reception/queue"],
  );
  assert.deepEqual(
    dich({ role: "RECEPTION", walkin: false, appointment: false, tiepDon: false, quanLy: true, moi: false }),
    ["/patient-list"],
  );
});

test("người không vào được /customers giữ đường cũ; luồng vãng lai không đổi", () => {
  assert.deepEqual(
    dich({ role: "RECEPTION", walkin: false, appointment: false, tiepDon: true, quanLy: false, moi: true }),
    ["/reception/queue"],
  );
  assert.deepEqual(
    dich({ role: "RECEPTION", walkin: false, appointment: false, tiepDon: false, quanLy: false, moi: true }),
    ["/patient-list"],
  );
  assert.deepEqual(
    dich({ role: "NURSE", walkin: true, appointment: false, tiepDon: false, quanLy: true, moi: true }),
    ["/patients/khach 1?new=1"],
  );
});

test("chỉ đường LƯU MỚI truyền moi=true; cửa do trang quyết bằng lego /customers", () => {
  assert.match(
    form,
    /await proceed\(\s*json\.patient\.clinic_patient_id as string,\s*json\.patient\.patient_code as string,\s*true,\s*\)/,
  );
  assert.match(form, /onClick=\{\(\) => proceed\(m\.clinic_patient_id\)\}/);
  assert.match(trangMoi, /moDuocMan\("\/customers"\)/);
  assert.match(trangMoi, /veQuanLyKhach=\{veQuanLyKhach\}/);
  // Tab "Thêm" của /appointments cùng component — sửa đủ cả hai lối.
  assert.match(trangHen, /veQuanLyKhach=\{await moDuocMan\("\/customers"\)\}/);
  assert.match(hub, /veQuanLyKhach=\{veQuanLyKhach\}/);
});

test("việc 'Gọi điện xác nhận': gọi được khách thì chip kể 'Đã gọi xác nhận', chưa gặp thì không kể", () => {
  const cham = (ket_qua: string) => ({
    trang_thai_ma: "CHO_DAT_LICH",
    loai: "HOI_THAM",
    ket_qua,
  });
  assert.equal(nhanLanChamCuoi(cham("DA_LIEN_HE")), "Đã gọi xác nhận");
  for (const kq of ["CHUA_NGHE_MAY", "KHONG_LIEN_LAC_DUOC", "HEN_GOI_LAI"]) {
    assert.equal(nhanLanChamCuoi(cham(kq)), null, kq);
  }
  // Cuộc gọi hỏi thăm tự do (không mang mã việc) vẫn như cũ.
  assert.equal(
    nhanLanChamCuoi({ loai: "HOI_THAM", ket_qua: "CHUA_NGHE_MAY" }),
    "Đã gọi hỏi thăm",
  );
});

test("khách chưa có lượt vẫn rút lại được cuộc gọi vừa ghi, nền trung tính", () => {
  assert.match(vung, /\(!lich\.id \|\| chamMoiNhat\.appointment_id !== lich\.id\)/);
  const i = vung.indexOf("rutNgoaiLuot && chuaCoLuot");
  assert.ok(i > 0);
  const khoi = vung.slice(i, vung.indexOf("rutNgoaiLuot && !chuaCoLuot", i));
  assert.match(khoi, /bg-surface-muted/);
  assert.ok(!/warning/.test(khoi), "việc bình thường không tô vàng/đỏ");
  assert.match(khoi, /hoanTac\(rutNgoaiLuot\.id\)/);
  assert.match(vung, /khongGanDuocLuot && !rutNgoaiLuot/);
});
