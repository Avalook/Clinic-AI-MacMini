// C.3 — luật đặt lịch (độ dài khung, số chỗ kênh thường, số chỗ vãng lai) là
// CẤU HÌNH CỦA TỪNG PHÒNG KHÁM, sống ở clinic.settings.booking. Ba nơi enforce
// nó: trigger enforce_slot_capacity (PL/pgSQL), BookingService (Python), và lưới
// giờ ở trình duyệt. Hai nơi đầu đọc cùng một hàng DB; nơi thứ ba chỉ VẼ.
//
// Bug mà file này tồn tại để chặn: một hằng số 15 / 2 / 1 mọc lại trong trình
// duyệt. Nó không gây lỗi biên dịch, không gây lỗi test đơn, và không ai thấy
// cho tới khi phòng khám thứ hai chạy khung 30 phút — lúc đó lễ tân bấm vào ô
// mà server sẽ từ chối, với thông báo không giải thích được ô đó sai chỗ nào.
//
// Test quét NGUỒN chứ không import, và suy ra danh sách thay vì ghim tên file:
// màn mới thêm vào mai sau cũng bị soi y hệt.

import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const REPO = fileURLToPath(new URL("../../..", import.meta.url));

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (/\.(ts|tsx|mts)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

const sources = [join(ROOT, "app"), join(ROOT, "lib")]
  .flatMap(walk)
  .filter((f) => !f.endsWith(".test.mts") && !f.endsWith(".test.ts"))
  .map((f) => ({ path: relative(ROOT, f), text: readFileSync(f, "utf8") }));

test("no file declares its own copy of the slot length or the seat counts", () => {
  // Tên cũ của ba hằng số đã bị xoá, cộng các biến thể hiển nhiên. Khai báo
  // lại bất kỳ cái nào = bản sao thứ tư của luật.
  const decl =
    /\b(?:const|let|var)\s+(SLOT_MIN|SLOT_MINS|SLOT_MINUTES|SLOT_MS|REGULAR_CAP|WALKIN_CAP|SEAT_CAP)\b/;
  const offenders = sources
    .filter((s) => decl.test(s.text))
    .map((s) => s.path);
  assert.deepEqual(
    offenders,
    [],
    `luật đặt lịch phải đến từ useBookingPolicy(), không khai báo tại chỗ: ${offenders.join(", ")}`,
  );
});

test("no screen hardcodes the minute grid of a slot", () => {
  // Lưới phút phải sinh từ slotMinutes (slotMinuteOptions). Một mảng
  // ["00","15","30","45"] viết tay là lưới 15 phút đóng đinh vào JSX.
  const grid = /\[\s*"00"\s*,\s*"\d{2}"/;
  const offenders = sources.filter((s) => grid.test(s.text)).map((s) => s.path);
  assert.deepEqual(
    offenders,
    [],
    `mốc phút phải suy từ policy.slotMinutes: ${offenders.join(", ")}`,
  );
});

test("every screen that buckets or counts slots reads the clinic's rule", () => {
  // Các helper dưới đây KHÔNG chạy được nếu thiếu policy (TS đã chặn), nhưng
  // TS không chặn được việc dựng policy giả tại chỗ. Ai gọi chúng thì phải
  // lấy luật từ đúng một nguồn: context của layout, hoặc tham số truyền vào.
  const usesRule = /\b(?:slotMs|slotBucketMs|slotBucketRange|buildSlotUsage|slotMinuteOptions)\s*\(/;
  const readsRule = /useBookingPolicy\(\)|policy:\s*BookingPolicy/;
  const offenders = sources
    .filter((s) => s.path !== join("lib", "slot-capacity.ts"))
    .filter((s) => usesRule.test(s.text) && !readsRule.test(s.text))
    .map((s) => s.path);
  assert.deepEqual(
    offenders,
    [],
    `phải nhận luật qua useBookingPolicy() hoặc tham số BookingPolicy: ${offenders.join(", ")}`,
  );
});

test("slot-capacity stays pure: it takes the rule, it does not know it", () => {
  const text = readFileSync(join(ROOT, "lib/slot-capacity.ts"), "utf8");
  // Không I/O: file này là hàm thuần, dùng được cả ở server lẫn client.
  assert.ok(!/\bfetch\s*\(|supabase/i.test(text), "slot-capacity must stay pure");
  // Và không giữ số nào của luật: mọi hàm phụ thuộc luật đều nhận policy.
  for (const fn of text.matchAll(/export function (\w+)\(([^)]*)\)/g)) {
    const [, name, params] = fn;
    const body = text.slice(fn.index ?? 0);
    const usesPolicy = /policy\./.test(body.slice(0, body.indexOf("\n}") + 2));
    if (usesPolicy) {
      assert.match(
        params,
        /policy:\s*BookingPolicy/,
        `${name}() dùng luật thì phải nhận policy làm tham số`,
      );
    }
  }
});

test("the browser has no fallback rule when the backend does not answer", () => {
  const text = readFileSync(join(ROOT, "lib/booking-policy.ts"), "utf8");
  // Một bộ 15/2/1 "đỡ khi backend chết" là bản sao thứ tư đúng vào lúc nguy
  // hiểm nhất. Đọc không được → null, và màn phải nói thẳng.
  assert.ok(
    !/\?\?\s*\d/.test(text),
    "booking-policy.ts must not default any of the three numbers",
  );
  assert.match(text, /return null/, "failure must surface as null, not a guess");
  // Nguồn duy nhất: endpoint của backend. Trình duyệt không đọc clinic.settings
  // (A.5 đã bỏ cột đó khỏi GRANT cho `authenticated`).
  assert.match(text, /\/api\/v1\/appointments\/policy/);
  assert.ok(
    !/from\s+["']\.\/supabase/.test(text),
    "the rule must not be read straight from clinic.settings in the browser",
  );
});

test("the browser validates slot_minutes exactly as the database CHECK does", () => {
  // Cross-language: nếu SQL nới lên 90 phút mà trình duyệt vẫn chặn ở 60, lễ
  // tân thấy "chưa đọc được luật" trên một cấu hình hoàn toàn hợp lệ.
  const sql = readFileSync(
    join(
      REPO,
      "supabase/migrations/20260803000001_clinic_booking_policy.sql",
    ),
    "utf8",
  );
  const ts = readFileSync(join(ROOT, "lib/booking-policy.ts"), "utf8");

  const sqlRange = sql.match(
    /clinic_policy_int_ok\(\s*booking,\s*'slot_minutes',\s*(\d+),\s*(\d+)\)/,
  );
  assert.ok(sqlRange, "SQL must range-check slot_minutes");
  const tsMin = ts.match(/slotMinutes\s*<\s*(\d+)/);
  const tsMax = ts.match(/slotMinutes\s*>\s*(\d+)/);
  assert.ok(tsMin && tsMax, "TS must range-check slotMinutes");
  assert.equal(tsMin[1], sqlRange[1], "lower bound of slot_minutes disagrees");
  assert.equal(tsMax[1], sqlRange[2], "upper bound of slot_minutes disagrees");

  // Chia hết 60' là điều kiện để floor theo epoch UTC trùng ranh giới khung
  // giờ VN. Cả hai phía phải cùng đòi, nếu không lưới lệch múi giờ.
  assert.match(sql, /60\s*%\s*minutes\s*<>\s*0/);
  assert.match(ts, /60\s*%\s*slotMinutes\s*!==\s*0/);

  // Số chỗ: kênh thường tối thiểu 1 (0 chỗ = không đặt được), vãng lai cho
  // phép 0 (phòng khám không nhận khách vãng lai).
  const sqlRegular = sql.match(
    /clinic_policy_int_ok\(\s*booking,\s*'regular_cap',\s*(\d+),/,
  );
  const sqlWalkin = sql.match(
    /clinic_policy_int_ok\(\s*booking,\s*'walkin_cap',\s*(\d+),/,
  );
  assert.ok(sqlRegular && sqlWalkin);
  assert.match(ts, new RegExp(`regularCap\\s*<\\s*${sqlRegular[1]}`));
  assert.match(ts, new RegExp(`walkinCap\\s*<\\s*${sqlWalkin[1]}`));
});
