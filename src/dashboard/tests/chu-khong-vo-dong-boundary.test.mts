// Chữ không xuống dòng vô tội vạ (Tuyền 29/10/2026, bấm staging 375 / ~1040):
// tên dịch vụ trên thẻ chỉ định và tên khối ở cột bước bị bóp vì nút / chip
// đứng thành cột cạnh chữ.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("thẻ chỉ định: tên trọn một dòng ở màn hẹp, nút xếp dọc bên phải", () => {
  const the = doc("../app/(dashboard)/_lam-viec/phieu-kham/KetQuaChiDinh.tsx");
  assert.match(the, /<div className="col-span-2 min-w-0 sm:col-span-1">/);
  assert.match(the, /col-start-2 row-start-2 flex flex-col items-stretch gap-1 sm:row-span-2/);
});

test("cột bước phiếu khám: chip 'mới' nằm dưới tên, không chiếm cột thứ ba", () => {
  const pk = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKham.tsx");
  assert.doesNotMatch(pk, /grid-cols-\[2rem_minmax\(0,1fr\)_auto\]/);
  assert.match(pk, /lg:grid-cols-\[minmax\(0,1fr\)_14rem\]/);
});
