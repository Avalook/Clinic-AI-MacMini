import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { MA_CA_KHAM_BAC_SI } from "../lib/ca-kham-bac-si.ts";

test("mã ca khám bác sĩ ở giao diện KHỚP bản máy chủ", () => {
  const py = readFileSync(
    new URL("../../clinicai/services/config_service.py", import.meta.url),
    "utf8",
  );
  const khoi = py.slice(py.indexOf("MA_CA_KHAM_BAC_SI: frozenset"), py.indexOf("})", py.indexOf("MA_CA_KHAM_BAC_SI: frozenset")));
  const maPy = [...khoi.matchAll(/"([A-Z0-9_]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual([...MA_CA_KHAM_BAC_SI].sort(), maPy);
});

test("màn đặt lịch không đọc bảng lịch trực qua PostgREST — hỏi backend", () => {
  // 24/09/2026: `/api/roster?date=` chuyển sang `GET /api/v1/roster/bac-si-ngay`;
  // lọc theo mã ca khám bác sĩ nằm ở `RosterService.bac_si_trong_ngay`.
  const route = readFileSync(new URL("../app/api/roster/route.ts", import.meta.url), "utf8");
  assert.doesNotMatch(route, /from\("vi_tri_lam_viec"\)/);
  assert.doesNotMatch(route, /from\("work_roster"\)/);
  assert.match(route, /\/api\/v1\/roster\/bac-si-ngay/);
  const py = readFileSync(
    new URL("../../clinicai/services/config_service.py", import.meta.url),
    "utf8",
  );
  assert.match(py, /station = ANY\(\$3::text\[\]\)[\s\S]*?sorted\(MA_CA_KHAM_BAC_SI\)/);
});
