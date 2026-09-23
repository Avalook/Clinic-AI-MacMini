import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

// MỘT BÀN KHÁM THEO PHÒNG + PHÒNG DỊCH VỤ (Tuyền chốt 16/09/2026).
//
// Thay cho năm màn /kham/* (đặt tên theo PHIẾU) và bốn màn /sono, /sieu-am,
// /service-queue, /lab-queue (bốn nguồn dữ liệu cho cùng một việc). Bài này canh
// để các màn trùng không sống lại: đường cũ chỉ còn chuyển hướng, và mọi mục
// thanh bên mới đều có luật vai.

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const nav = doc("../app/(dashboard)/nav-items.ts");
const roles = doc("../lib/roles.ts");

test("đường cũ chỉ còn chuyển hướng, không còn thân màn", () => {
  for (const [trang, dich] of [
    ["../app/(dashboard)/doctor/board/page.tsx", "/ban-kham"],
    ["../app/(dashboard)/kham/[loai]/page.tsx", "/ban-kham"],
    ["../app/(dashboard)/doctor/orders/[visitId]/page.tsx", "/ban-kham"],
    // Phòng là tài nguyên (CORE-C, 23/09/2026): về danh sách phòng, không về
    // một mã phòng đoán sẵn.
    ["../app/(dashboard)/sono/page.tsx", "/phong"],
    ["../app/(dashboard)/sieu-am/page.tsx", "/phong"],
    ["../app/(dashboard)/service-queue/page.tsx", "/phong"],
    ["../app/(dashboard)/lab-queue/page.tsx", "/phong"],
    ["../app/(dashboard)/result-review/page.tsx", "/duyet-ket-qua"],
    ["../app/(dashboard)/luot-kham/page.tsx", "/ban-kham"],
  ] as const) {
    const src = doc(trang);
    assert.match(src, new RegExp(`redirect\\("${dich.replace(/\//g, "\\/")}"\\)`), trang);
    assert.doesNotMatch(src, /<[A-Z][A-Za-z]+/, `${trang} còn vẽ một màn`);
  }
  for (const cu of [
    "../app/(dashboard)/doctor/board/DoctorBoard.tsx",
    "../app/(dashboard)/sono/SonoView.tsx",
    "../app/(dashboard)/service-queue/ServiceQueueView.tsx",
    "../app/(dashboard)/lab-queue/LabQueueView.tsx",
    "../app/(dashboard)/sieu-am/UltrasoundBoard.tsx",
    "../app/(dashboard)/luot-kham/LuotKhamBoard.tsx",
  ]) {
    assert.equal(existsSync(new URL(cu, import.meta.url)), false, `${cu} phải đã gỡ`);
  }
});

test("thanh bên không còn mục của màn cũ", () => {
  for (const cu of ["/doctor/board", "/kham/", "/sono", "/sieu-am", "/service-queue", "/lab-queue", "/result-review"]) {
    assert.doesNotMatch(nav, new RegExp(`href: "${cu.replace(/\//g, "\\/")}`), cu);
  }
});

test("mọi mục bàn khám / phòng / duyệt kết quả đều có luật vai", () => {
  const moi = [...nav.matchAll(/href: "(\/(?:ban-kham|phong|duyet-ket-qua)[^"]*)"/g)].map(
    (m) => m[1],
  );
  // Hai mục cố định: Bàn khám, Phòng dịch vụ. "Duyệt kết quả" OFF khỏi thanh bên
  // 23/09/2026 tối (kết quả đọc/điền trong phiếu khám). Mục của từng phòng dựng
  // từ database theo room_id (CORE-C) — không còn khai trong NAV.
  assert.deepEqual(moi.sort(), ["/ban-kham", "/phong"]);
  for (const href of moi) {
    assert.match(roles, new RegExp(`"${href}": \\[`), `${href} thiếu luật vai`);
  }
});

test("bàn khám mở phiếu theo MÃ PHIẾU của dịch vụ, không dò chữ trong tên", () => {
  const ban = doc("../app/(dashboard)/ban-kham/BanKham.tsx");
  assert.match(ban, /serviceCode=\{dong\.form_code\}/);
  assert.doesNotMatch(ban, /resolveServiceCode/);
});

test("hai quầy thu ngân: mỗi màn cố định một quầy, cùng một thân quầy", () => {
  for (const [duong, quay] of [
    ["dich-vu", "dich_vu"],
    ["thuoc", "thuoc"],
  ] as const) {
    const trang = doc(`../app/(dashboard)/thu-ngan/${duong}/page.tsx`);
    // Batch pilot 18/09: trang ghim quầy vào TabThuNgan (thêm hai tab chỉ
    // đọc), và TabThuNgan chuyển NGUYÊN quầy ấy xuống đúng một QuayThuNgan.
    assert.match(trang, new RegExp(`<TabThuNgan quay="${quay}" />`));
    assert.match(
      readFileSync(new URL("../app/(dashboard)/thu-ngan/TabThuNgan.tsx", import.meta.url), "utf8"),
      /<QuayThuNgan quay=\{quay\} \/>/,
    );
    assert.match(trang, new RegExp(`requireNavAccess\\("/thu-ngan/${duong}"\\)`));
    assert.match(nav, new RegExp(`href: "/thu-ngan/${duong}"`));
  }
});

test("menu dự phòng theo LUẬT GỐC, không theo công tắc mở quyền", () => {
  const i = roles.indexOf("export function hienTrenThanhBen");
  assert.match(roles.slice(i, i + 1400), /canSeeNavGoc\(role, href\)/);
});
