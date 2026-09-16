import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

import { LOAI_KHAM } from "../lib/loai-kham.ts";

// Các màn khám RIÊNG và hai quầy thu ngân (Tuyền chốt 16/09/2026).
//
// Một loại khám cần có mặt ở BỐN chỗ: danh mục (lib/loai-kham.ts), một mục ở
// thanh bên, một luật vai, và một phiếu thật. Thiếu một chỗ thì hỏng một kiểu
// khác nhau — mục không hiện, hoặc hiện mà bấm vào bị đá về trang chủ, hoặc mở
// ra một màn không có phiếu. Bài này canh cả bốn cùng lúc.

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const nav = doc("../app/(dashboard)/nav-items.ts");
const roles = doc("../lib/roles.ts");
const trangKham = doc("../app/(dashboard)/kham/[loai]/page.tsx");

test("mỗi loại khám có mục thanh bên, luật vai, và phiếu thật", () => {
  const PHIEU: Record<string, string> = {
    PK: "pk",
    SK: "sk",
    NT: "nt",
    HMVS: "hmvs",
    NK: "nk",
  };
  for (const l of LOAI_KHAM) {
    const href = `/kham/${l.slug}`;
    assert.match(nav, new RegExp(`href: "${href}"`), `${href} thiếu mục thanh bên`);
    assert.match(roles, new RegExp(`"${href}": \\[`), `${href} thiếu luật vai`);
    assert.ok(PHIEU[l.formCode], `${l.ten}: mã phiếu ${l.formCode} không có trong năm phiếu`);
    assert.ok(
      existsSync(new URL(`../lib/form-schemas/${PHIEU[l.formCode]}.ts`, import.meta.url)),
      `${l.ten}: thiếu tệp phiếu`,
    );
  }
});

test("năm loại khám dùng năm phiếu KHÁC NHAU, không trùng", () => {
  const ma = LOAI_KHAM.map((l) => l.formCode);
  assert.equal(new Set(ma).size, ma.length);
});

test("màn khám lọc khách theo MÃ PHIẾU, không dò chữ trong tên dịch vụ", () => {
  // Dò theo tên là con đường đã cho "Sản 1" hai câu trả lời ở hai màn.
  assert.match(trangKham, /i\.form_code === loai\.formCode/);
  assert.doesNotMatch(trangKham, /service_name/);
  assert.doesNotMatch(trangKham, /resolveServiceCode/);
});

test("màn khám dùng lại Bàn khám bác sĩ, không có thân màn thứ hai", () => {
  assert.match(trangKham, /import DoctorBoard from "\.\.\/\.\.\/doctor\/board\/DoctorBoard"/);
});

test("siêu âm ghi rõ là 'Khám siêu âm'", () => {
  assert.match(nav, /href: "\/sieu-am",[\s\S]{0,120}label: "Khám siêu âm"/);
});

test("hai quầy thu ngân: mỗi màn cố định một quầy, cùng một thân quầy", () => {
  for (const [duong, quay] of [
    ["dich-vu", "dich_vu"],
    ["thuoc", "thuoc"],
  ] as const) {
    const trang = doc(`../app/(dashboard)/thu-ngan/${duong}/page.tsx`);
    assert.match(trang, new RegExp(`<QuayThuNgan quay="${quay}" />`));
    assert.match(trang, new RegExp(`requireNavAccess\\("/thu-ngan/${duong}"\\)`));
    assert.match(nav, new RegExp(`href: "/thu-ngan/${duong}"`));
  }
});

test("menu dự phòng theo LUẬT GỐC, không theo công tắc mở quyền", () => {
  // Không có dòng này thì ngày không có ca, thanh bên của một điều dưỡng dài
  // gần bốn mươi mục vì công tắc mở quyền đang bật.
  const i = roles.indexOf("export function hienTrenThanhBen");
  assert.match(roles.slice(i, i + 1400), /canSeeNavGoc\(role, href\)/);
});
