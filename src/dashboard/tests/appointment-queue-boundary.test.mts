import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../app/api/appointments/route.ts", import.meta.url),
  "utf8",
);

test("check-in obtains its queue number through one atomic database function", () => {
  assert.match(source, /rpc\("check_in_appointment"/);
  assert.doesNotMatch(source, /max\(số đã cấp hôm nay\) \+ 1/);
});
