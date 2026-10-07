// C22 (Tuyền 02/10/2026): "cái wording tự động xếp phòng ấy, bỏ hết mọi chỗ đi
// nhé, phải là nếu chưa chọn phòng thì ghi vui lòng chọn phòng". Máy chủ chỉ xếp
// theo phòng quầy / lễ tân đã chọn — màn không được hứa máy tự chọn phòng.
// Chỉ đổi CHỮ: ô rỗng vẫn gửi "" như cũ (máy chủ hiểu là chưa chọn / bỏ chọn).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

const MAN = [
  "../app/(dashboard)/thu-ngan/ChonDichVu.tsx",
  "../app/(dashboard)/thu-ngan/HoaDonMot.tsx",
  "../app/(dashboard)/thu-ngan/QuayThuNgan.tsx",
  "../app/(dashboard)/thu-ngan/XepPhongDaThu.tsx",
  "../app/(dashboard)/_lam-viec/DoiPhong.tsx",
  "../app/print/phieu-thu/[id]/InPhieuThu.tsx",
];

const CHU_CU = [/tự\s+(động\s+)?xếp\s+phòng/i, /tự\s+(động\s+)?chọn\s+phòng/i, /vắng\s+nhất/i];

test("không màn nào còn chữ hứa máy tự xếp / tự chọn phòng vắng nhất", () => {
  for (const tep of MAN) {
    const nd = read(tep);
    for (const re of CHU_CU) {
      assert.doesNotMatch(nd, re, `${tep} còn chữ ${re}`);
    }
  }
});

test("ô chọn phòng chưa chọn ghi 'Vui lòng chọn phòng', vẫn gửi giá trị rỗng", () => {
  const chonDv = read("../app/(dashboard)/thu-ngan/ChonDichVu.tsx");
  assert.match(chonDv, /<option value="">— Vui lòng chọn phòng —<\/option>/);

  const hoaDon = read("../app/(dashboard)/thu-ngan/HoaDonMot.tsx");
  // Dây Nhận tại phòng bật (07/10/2026): ô là HƯỚNG DẪN, không bắt buộc.
  assert.match(
    hoaDon,
    /d\.huong_dan\s*\?\s*"— Hướng dẫn phòng \(không bắt buộc\) —"\s*:\s*doiTac\s*\?\s*"— Lấy mẫu: vui lòng chọn phòng —"\s*:\s*"— Vui lòng chọn phòng —"/,
  );
  // Số người chờ từng phòng vẫn hiện — chỉ bỏ nhãn "vắng nhất".
  assert.match(hoaDon, /\{p\.ten\}\s*\{p\.chuyen \? " ★" : ""\} · \{p\.dang_cho\} đang chờ/);
  assert.match(hoaDon, /datPhong\(d\.id, e\.target\.value\)/);

  const doiPhong = read("../app/(dashboard)/_lam-viec/DoiPhong.tsx");
  // Phòng dự kiến (trưởng ca) + xếp phòng lần đầu đều ghi "Vui lòng chọn phòng".
  assert.equal(doiPhong.match(/— Vui lòng chọn phòng —/g)?.length, 2);
  assert.match(doiPhong, /room_id: roomId \|\| null/);
  assert.match(doiPhong, /\{phongHienTaiId \? "Đổi sang phòng…" : "— Vui lòng chọn phòng —"\}/);
});

test("dòng chưa có phòng ở màn nhân viên ghi 'vui lòng chọn phòng'", () => {
  assert.match(
    read("../app/(dashboard)/thu-ngan/XepPhongDaThu.tsx"),
    /c\.phong \?\? \(c\.huong_dan \? "chưa vào phòng nào" : "vui lòng chọn phòng"\)/,
  );
  assert.match(read("../app/print/phieu-thu/[id]/InPhieuThu.tsx"), /: "vui lòng chọn phòng"\}/);
});
