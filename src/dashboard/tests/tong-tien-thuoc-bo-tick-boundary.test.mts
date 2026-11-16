// TỔNG TIỀN THUỐC KHI BỎ TICK NHANH — máy kiểm (16/11/2026).
//
// Lỗi: bỏ tick bớt thuốc ở Bán lẻ (/pharmacy) hay quầy thuốc (/thu-ngan/thuoc)
// mà tổng tiền đứng ở số cũ. Máy chủ tính đúng (`bill_service.ghep_thuoc`); gốc
// là màn: mỗi lần tick có HAI lượt nạp chồng nhau (tin bảng `prescription` qua
// useNgheBang + `onDoi` của khối chỉnh đơn), lượt cũ về SAU đè `doc` mới.
// Luật: mọi lượt nạp của một màn đi chung MỘT hàng `taoMotLuot`.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { taoMotLuot } from "../lib/mot-luot.ts";

const GOC = new URL("../", import.meta.url);
const boChuThich = (ma: string) =>
  ma.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
const doc = (p: string) => boChuThich(readFileSync(new URL(p, GOC), "utf8"));

for (const [tep, duong] of [
  ["app/(dashboard)/pharmacy/BanLeThu.tsx", "/api/pharmacy/ban-le"],
  ["app/(dashboard)/thu-ngan/ChinhDonQuay.tsx", "/api/quay-thuoc"],
] as const) {
  test(`${tep}: mọi lượt nạp ${duong} đi qua MỘT hàng taoMotLuot`, () => {
    const ma = doc(tep);
    assert.match(ma, /const \[motLuot\] = useState\(taoMotLuot\)/, "một hàng cho cả màn");
    assert.match(ma, /const tai = useCallback\(\s*\(\) =>\s*motLuot\(async/, "tai() phải đi qua hàng");
    const soNap = ma.split(`fetch(\`${duong}`).length - 1;
    const soQuaHang = ma.match(/motLuot\(async/g)?.length ?? 0;
    assert.ok(soNap >= 1);
    assert.equal(
      soQuaHang,
      soNap,
      `mỗi chỗ gọi ${duong} (kể cả nạp lần đầu) phải nằm trong motLuot — ` +
        "một lượt nạp ngoài hàng về muộn là đè tổng mới",
    );
  });
}

test("QuayThuNgan: tai() của quầy vẫn đi qua taoMotLuot", () => {
  const ma = doc("app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
  assert.match(ma, /const \[motLuot\] = useState\(taoMotLuot\)/);
  assert.match(ma, /\(\) => motLuot\(async \(\) => nhan\(await doc\(\)\)\)/);
});

// Tái hiện đúng ca lỗi: ba thao tác bỏ tick nhanh, mỗi thao tác bắn hai lượt nạp
// (tin bảng + onDoi). Máy chủ trả tổng theo số đã ghi LÚC ĐỌC; lượt đọc sớm trả
// chậm nhất. Không có hàng → màn hiện số cũ; có hàng → luôn bằng tổng cuối.
async function moPhong(quaHang: boolean): Promise<number> {
  const gia = [100, 200, 300];
  const conTick = [true, true, true];
  const tongMayChu = () => gia.reduce((s, g, i) => s + (conTick[i] ? g : 0), 0);
  let tongTrenMan = tongMayChu();
  const motLuot = taoMotLuot();
  let lan = 0;
  const docMayChu = async () => {
    const soDoc = tongMayChu();
    const tre = 30 - lan++ * 5; // lượt đọc trước về sau
    await new Promise((r) => setTimeout(r, Math.max(tre, 0)));
    tongTrenMan = soDoc;
  };
  const tai = () => (quaHang ? motLuot(docMayChu) : docMayChu());

  const cho: Promise<void>[] = [];
  for (let i = 0; i < 3; i++) {
    conTick[i] = i === 0; // bỏ tick dần, chỉ giữ thuốc đầu
    cho.push(tai(), tai());
  }
  await Promise.all(cho);
  return tongTrenMan;
}

test("bỏ tick nhanh 3 thuốc: không có hàng thì tổng đứng số cũ (đối chứng)", async () => {
  assert.notEqual(await moPhong(false), 100, "đối chứng phải tái hiện được lỗi");
});

test("bỏ tick nhanh 3 thuốc: đi qua taoMotLuot thì tổng = các dòng còn tick", async () => {
  assert.equal(await moPhong(true), 100);
});
