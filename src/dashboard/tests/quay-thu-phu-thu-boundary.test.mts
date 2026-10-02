import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { dongDangChon, giaNhapBang, tongTheoLuaChon } from "../lib/hoa-don-quay.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const quay = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
const hoaDon = read("../app/(dashboard)/thu-ngan/HoaDonMot.tsx");

test("phụ thu theo tick dịch vụ cha và rời ô cùng giá không tạo thay đổi", () => {
  const chon = new Set<string>();
  const dong = [
    { id: "o1", loai: "chi_dinh" as const, gia: 250_000, chon: true, trong_lua_chon: true },
    {
      id: "pt1",
      order_id: "o1",
      loai: "phu_thu" as const,
      gia: 300_000,
      chon: true,
      trong_lua_chon: false,
    },
  ];
  assert.equal(dongDangChon(dong[1], chon), false);
  assert.equal(tongTheoLuaChon(dong, chon), 0);
  assert.equal(giaNhapBang("300.000", 300_000), true);
  assert.equal(giaNhapBang("300001", 300_000), false);
});

test("phụ thu của dịch vụ cha bị khóa vẫn giữ theo trạng thái máy chủ", () => {
  const chon = new Set<string>();
  const idsCoTheDoi = new Set<string>(["o2"]);
  const phuThuBiKhoa = {
    id: "pt1",
    order_id: "o1",
    loai: "phu_thu" as const,
    gia: 300_000,
    chon: true,
    trong_lua_chon: false,
  };

  assert.equal(dongDangChon(phuThuBiKhoa, chon, idsCoTheDoi), true);
  assert.equal(tongTheoLuaChon([phuThuBiKhoa], chon, idsCoTheDoi), 300_000);
});

test("quầy khóa Thu lúc lưu vật tư và không remount theo revision", () => {
  assert.match(hoaDon, /disabled=\{dangThu \|\| dangLuuVatTu \|\| chanThu\}/);
  assert.match(quay, /dangLuuVatTu=\{vatTuDangLuu\.has\(l\.visit_id\)\}/);
  assert.match(quay, /key=\{`\$\{l\.visit_id\}:\$\{l\.quay_thu\.lua_chon\.order_ids_seen\.join/);
  assert.match(quay, /l\.quay_thu\.lua_chon\.revision/);
  assert.doesNotMatch(quay, /key=\{`\$\{l\.visit_id\}:\$\{l\.quay_thu\.revision/);
  assert.match(quay, /className="min-w-0 overflow-hidden rounded-card/);
  assert.match(quay, /className="min-w-0 rounded-card border border-line bg-surface shadow-card"/);
});

test("khối Món kèm cũ đã gỡ: không còn component, proxy hay state; vật tư thay chỗ", () => {
  assert.doesNotMatch(quay, /PhuThuKem|phuThuDangLuu|setPhuThuDangLuu/);
  assert.doesNotMatch(hoaDon, /dangLuuPhuThu/);
  assert.doesNotMatch(
    read("../app/api/luot-kham/route.ts"),
    /phu-thu|PhuThu/,
  );
  assert.match(quay, /<VatTuQuay/);
});
