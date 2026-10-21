import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

test("shared chrome uses the ClinicAI token system instead of a second palette", () => {
  const badge = source("../app/(dashboard)/StatusBadge.tsx");
  const pane = source("../app/(dashboard)/SplitPane.tsx");
  const notice = source("../app/(dashboard)/DeclinedNotice.tsx");
  const bottomNav = source("../app/(dashboard)/BottomNav.tsx");
  const nav = source("../app/(dashboard)/Nav.tsx");
  const roster = source("../lib/roster.ts");

  assert.match(badge, /bg-status-ready-bg text-status-ready/);
  assert.match(badge, /rounded-chip/);
  assert.match(pane, /w-px bg-line/);
  assert.match(notice, /border-danger bg-surface/);
  assert.match(bottomNav, /shadow-panel/);
  assert.match(nav, /text-brand-700/);

  for (const content of [badge, pane, notice, bottomNav, nav, roster]) {
    assert.doesNotMatch(content, /#[0-9a-fA-F]{3,8}/);
    assert.doesNotMatch(content, /pink|rose|fuchsia|rgba/i);
  }
});

test("global header shows a full Vietnamese date and a separated clock", () => {
  const header = source("../app/(dashboard)/GlobalHeader.tsx");

  assert.ok(header.includes("formatToParts(selectedDate)"));
  assert.ok(header.includes('datePart("weekday").toLocaleLowerCase("vi-VN")'));
  assert.ok(header.includes("const formattedDateStr = `${weekdayCap}, ngày ${day}-${month}-${year}`;"));
  assert.ok(header.includes('<span>{formattedDateStr}</span>'));
  assert.ok(header.includes("grid-cols-[minmax(0,1fr)_auto]"));
  assert.ok(header.includes("xl:flex"));
  assert.ok(header.includes('className="relative col-span-2 row-start-2 justify-self-end xl:order-2"'));
  assert.ok(header.includes('className="flex flex-col items-end gap-2 whitespace-nowrap sm:flex-row sm:items-center"'));
  assert.ok(header.includes('<span>{liveTime || "--:--"}</span>'));
  assert.doesNotMatch(header, /shortDateStr/);

  const selectedDate = new Date("2026-10-18T12:00:00+07:00");
  const parts = new Intl.DateTimeFormat("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  }).formatToParts(selectedDate);
  const part = (type: "weekday" | "day" | "month" | "year") =>
    parts.find((value) => value.type === type)?.value ?? "";
  const weekday = part("weekday").toLocaleLowerCase("vi-VN");
  const weekdayCap = weekday.charAt(0).toLocaleUpperCase("vi-VN") + weekday.slice(1);
  assert.equal(
    `${weekdayCap}, ngày ${part("day")}-${part("month")}-${part("year")}`,
    "Chủ nhật, ngày 18-10-2026",
  );
});
