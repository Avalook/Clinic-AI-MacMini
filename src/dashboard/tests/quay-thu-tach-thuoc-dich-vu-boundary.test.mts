import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// THUỐC VÀ DỊCH VỤ THU RIÊNG HẲN (Tuyền 01/10/2026: "không cho node thuốc thu hộ
// tiền dịch vụ"). Luật ở máy chủ (`kiem_quay` → 409 QUAY_KHAC_LOAI); bài này khoá
// phía màn: mọi lệnh tiền gửi kèm `quay`, sổ giao dịch lọc theo quầy, quầy không
// còn khối thu hộ khoản của quầy kia.

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const quay = doc("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
const giaoDich = doc("../app/(dashboard)/thu-ngan/GiaoDich.tsx");
const tab = doc("../app/(dashboard)/thu-ngan/TabThuNgan.tsx");
const banLe = doc("../app/(dashboard)/pharmacy/BanLeThu.tsx");
const hoanTac = doc("../app/(dashboard)/thu-ngan/NutHoanTac.tsx");
const route = doc("../app/api/payment/route.ts");

test("quầy thu không còn khối thu hộ khoản của quầy kia", () => {
  assert.doesNotMatch(quay, /NoKhac|DongNoKhac|no_khac|Thu luôn/);
});

test("mọi lệnh thu / xác minh ở quầy gửi kèm quay", () => {
  assert.match(quay, /const quayThu = quay === "ca_hai" \? undefined : quay;/);
  assert.equal((quay.match(/quay: quayThu,/g) ?? []).length, 3); // thu · thuMot · xác minh
  assert.match(banLe, /kind: "thuoc",\s*quay: "thuoc",\s*billRevision/);
  assert.match(banLe, /kind: "thuoc",\s*quay: "thuoc",\s*reference/);
});

test("hoàn tác gửi quay; proxy chuyển quay xuống máy chủ", () => {
  assert.match(hoanTac, /\.\.\.\(quay \? \{ quay \} : \{\}\)/);
  assert.equal((route.match(/quay: p\.quay \?\? null/g) ?? []).length, 4); // hoàn tác · xác minh · huỷ chờ · thu
});

test("sổ giao dịch lọc theo quầy đang đứng", () => {
  assert.match(giaoDich, /xem=giao-dich&kind=\$\{quay\}/);
  assert.match(tab, /<GiaoDich key=\{tab\} lichSu=\{tab === "lich_su"\} quay=\{quay\} \/>/);
});
