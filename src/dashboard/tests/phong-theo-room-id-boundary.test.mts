// PHÒNG LÀ TÀI NGUYÊN — thanh bên và cửa trang theo room_id (CORE-C, 23/09/2026).
//
// Ví dụ Tuyền: hôm nay "Siêu âm 1", mai quản lý đổi thành "Phòng Hoa", hoặc thêm
// "Phòng ABC". Trước đây thanh bên khai chín phòng theo mã viết cứng
// (`/phong/KN-SA1`…) — phòng mới không có lối vào, đổi tên thì thanh bên vẫn
// tên cũ. Bài này canh để mã phòng viết cứng không quay lại.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { ALL_ROLES, canSeeNavGoc, roleLanding } from "../lib/roles.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const nav = doc("../app/(dashboard)/nav-items.ts");
const roles = doc("../lib/roles.ts");
const ROOM = "5f0c7a2e-0000-4000-8000-000000000001";

test("không còn mã phòng viết cứng trong thanh bên, luật vai, chế độ CSKH", () => {
  const maPhong = /"\/(?:phong|ban-kham)\/KN-/;
  assert.doesNotMatch(nav, maPhong, "nav-items.ts");
  assert.doesNotMatch(roles, maPhong, "roles.ts");
  assert.doesNotMatch(doc("../lib/feature-mode-client.ts"), maPhong, "feature-mode-client.ts");
  for (const f of ["tasks", "sono", "sieu-am", "lab-queue", "service-queue"]) {
    assert.doesNotMatch(doc(`../app/(dashboard)/${f}/page.tsx`), /KN-/, f);
  }
});

test("vị trí trỏ tới PHÒNG CỦA NÓ, máy chủ giải ra room_id", () => {
  const khoi = nav.slice(
    nav.indexOf("export const MAN_THEO_VI_TRI"),
    nav.indexOf("// ── NHÓM VAI TRÊN THANH BÊN"),
  );
  // "Duyệt kết quả" OFF 23/09 tối — vị trí chỉ còn phòng / bàn khám của nó.
  assert.match(khoi, /T4_SA_BS1: \[PHONG\]/);
  assert.match(khoi, /T1_BS_NOITIET: \[BAN_KHAM\]/);
  assert.doesNotMatch(khoi, /duyet-ket-qua/);
  // Tên mục = tên phòng hiện tại, không phải nhãn khai sẵn.
  assert.match(nav, /if \(goc === "phong"\) return \{ href, label: p\.ten/);
  // Máy chủ trả phòng của từng vị trí cùng lời gọi vị trí hôm nay.
  const py = doc("../../clinicai/api/v1/routers/identity.py");
  assert.match(py, /"phong": phong/);
});

test("mọi /phong/<room_id> và /ban-kham/<room_id> dùng đúng luật gốc", () => {
  for (const r of ALL_ROLES) {
    assert.equal(canSeeNavGoc(r, `/phong/${ROOM}`), canSeeNavGoc(r, "/phong"), `${r} /phong`);
    assert.equal(
      canSeeNavGoc(r, `/ban-kham/${ROOM}`),
      canSeeNavGoc(r, "/ban-kham"),
      `${r} /ban-kham`,
    );
  }
  assert.equal(canSeeNavGoc("NURSE_ULTRASOUND", `/phong/${ROOM}`), true);
  assert.equal(canSeeNavGoc("CSKH", `/phong/${ROOM}`), false);
  assert.equal(canSeeNavGoc("RECEPTION", `/phong/${ROOM}`), false);
  assert.equal(roleLanding("ULTRASOUND_DOCTOR"), "/phong");
});

test("khớp tiền tố CHỈ cho hai đường theo phòng — không suy rộng sang màn khác", () => {
  assert.match(roles, /const TIEN_TO_THEO_PHONG = \["\/phong", "\/ban-kham"\] as const;/);
  // /phongxyz không phải con của /phong.
  assert.equal(canSeeNavGoc("NURSE_ULTRASOUND", "/phongxyz"), canSeeNavGoc(null, "/phongxyz"));
});

test("màn phòng nhận room_id, mã cũ vẫn mở được", () => {
  const phong = doc("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
  assert.match(phong, /x\.id === ma \|\| x\.code === ma/);
  const ban = doc("../app/(dashboard)/ban-kham/BanKham.tsx");
  assert.match(ban, /p\.id === maPhong \|\| p\.code === maPhong/);
  assert.match(ban, /<option key=\{p\.id\} value=\{p\.id\}>/);
  const ds = doc("../app/(dashboard)/phong/page.tsx");
  assert.match(ds, /requireNavAccess\("\/phong"\)/);
  assert.match(ds, /href=\{`\/phong\/\$\{p\.id\}`\}/);
});
