// Check-in must take its queue number from ONE atomic database call.
//
// Two patients checking in at the same second must not be handed the same
// number, so the number is assigned inside check_in_appointment(), which holds a
// per-day advisory lock. The failure this guards against is the obvious
// rewrite: read max(number) for today, add one, write it back.
//
// That call used to live in this Next route. It now lives in FastAPI
// (booking_service._check_in) because the route became a thin proxy, so the
// assertion moved with it — the invariant is about the system, not about which
// file happens to hold it today. The route is checked for the opposite: that it
// does not reimplement any of this on the way past.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const route = readFileSync(
  new URL("../app/api/appointments/route.ts", import.meta.url),
  "utf8",
);

const bookingService = readFileSync(
  new URL("../../clinicai/services/booking_service.py", import.meta.url),
  "utf8",
);

test("check-in obtains its queue number through one atomic database function", () => {
  assert.match(
    bookingService,
    /check_in_appointment\(\$1::uuid, \$2::text\[\]\)/,
    "booking_service must call check_in_appointment() — that function is where " +
      "the per-day advisory lock and the queue number live",
  );
});

test("the Next route delegates check-in instead of reimplementing it", () => {
  // No hand-rolled numbering, and no direct table access on the way past.
  assert.doesNotMatch(route, /max\(số đã cấp hôm nay\) \+ 1/);
  assert.doesNotMatch(route, /queue_number\s*:\s*\w+\s*\+\s*1/);
  assert.doesNotMatch(
    route,
    /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/,
    "the appointments route must not hold the service-role key any more",
  );
  assert.match(
    route,
    /proxyJsonToBackend\("PATCH", `\/api\/v1\/appointments\/\$\{id\}`/,
    "the PATCH path must proxy to FastAPI",
  );
});
