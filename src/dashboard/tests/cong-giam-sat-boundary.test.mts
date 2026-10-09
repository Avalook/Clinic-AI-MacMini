// Cổng trung tâm giám sát theo tên miền (09/10/2026) — lib/cong-giam-sat.ts.
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { hostGiamSat, laHostGiamSat, quyetDinhCong } from "../lib/cong-giam-sat.ts";

const DS = ["giamsat.dr4women.io.vn", "giamsat.localhost"];

test("host giám sát nhận cả khi kèm cổng, không phân biệt hoa thường", () => {
  assert.equal(laHostGiamSat("giamsat.dr4women.io.vn", DS), true);
  assert.equal(laHostGiamSat("GIAMSAT.localhost:3286", DS), true);
  assert.equal(laHostGiamSat("dr4women.io.vn", DS), false);
  assert.equal(laHostGiamSat("giamsat.dr4women.io.vn.evil.com", DS), false);
  assert.equal(laHostGiamSat(null, DS), false);
});

test("ở host giám sát: chỉ trang giám sát + đăng nhập; còn lại quay về /giam-sat", () => {
  const h = "giamsat.dr4women.io.vn";
  assert.equal(quyetDinhCong(h, "/giam-sat", DS, false), "di_tiep");
  assert.equal(quyetDinhCong(h, "/api/ops/agent", DS, false), "di_tiep");
  assert.equal(quyetDinhCong(h, "/login", DS, false), "di_tiep");
  assert.equal(quyetDinhCong(h, "/chon-co-so", DS, false), "di_tiep");
  assert.equal(quyetDinhCong(h, "/", DS, false), "ve_giam_sat");
  assert.equal(quyetDinhCong(h, "/home", DS, false), "ve_giam_sat");
  assert.equal(quyetDinhCong(h, "/forgot-password", DS, false), "ve_giam_sat");
  // API khác không mở ở tên miền này — không đi vòng qua đây gọi cả hệ.
  assert.equal(quyetDinhCong(h, "/api/patients", DS, false), "khong_thay");
  // "/giam-satx" không phải "/giam-sat".
  assert.equal(quyetDinhCong(h, "/giam-satx", DS, false), "ve_giam_sat");
});

test("ở tên miền chính: không thấy lối vào giám sát, trừ khi staging/dev mở", () => {
  const h = "dr4women.io.vn";
  assert.equal(quyetDinhCong(h, "/giam-sat", DS, false), "khong_thay");
  assert.equal(quyetDinhCong(h, "/api/ops/agent", DS, false), "khong_thay");
  assert.equal(quyetDinhCong(h, "/api/ops/agent?xem=tong-quan", DS, false), "khong_thay");
  assert.equal(quyetDinhCong(h, "/ops", DS, false), "di_tiep");
  assert.equal(quyetDinhCong(h, "/home", DS, false), "di_tiep");
  assert.equal(quyetDinhCong(h, "/giam-sat", DS, true), "di_tiep");
});

test("env rỗng → danh sách mặc định; env có → dùng env", () => {
  assert.deepEqual(hostGiamSat(""), ["giamsat.dr4women.io.vn", "giamsat.localhost"]);
  assert.deepEqual(hostGiamSat(" A.com , b.com "), ["a.com", "b.com"]);
});

test("proxy.ts thật sự gọi cổng này (không để hàm nằm không)", () => {
  const src = readFileSync(new URL("../proxy.ts", import.meta.url), "utf8");
  assert.match(src, /quyetDinhCong\(/);
});
