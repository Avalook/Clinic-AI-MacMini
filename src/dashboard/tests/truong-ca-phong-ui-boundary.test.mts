import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const rooms = read("../app/(dashboard)/phong/page.tsx");
const dispatch = read("../app/(dashboard)/truong-ca/page.tsx");
const queues = read("../app/(dashboard)/truong-ca/QueuesClient.tsx");
const dispatchCss = read("../app/(dashboard)/truong-ca/dispatch.css");
const dispatchShared = read("../app/(dashboard)/truong-ca/shared.tsx");
const tv = read("../app/(dashboard)/truong-ca/tv/page.tsx");

test("cards on /phong use larger text and a taller touch target", () => {
  assert.match(rooms, /min-h-20/);
  assert.match(rooms, /text-title font-semibold text-ink/);
  assert.match(rooms, /text-body tabular-nums text-ink-soft/);
  assert.match(rooms, /text-body text-ink-muted/);
});

test("/truong-ca removes drag hints, hides the live-success badge, and heading description", () => {
  assert.doesNotMatch(dispatch, /Từng phòng, ai đang chờ và chờ bao lâu/);
  assert.doesNotMatch(queues, /Kéo một khách thả vào phòng sáng lên/);
  assert.doesNotMatch(queues, /title=\{do_ \? "Chờ quá ngưỡng — kéo sang phòng khác/);
  assert.match(queues, /<LiveBadge seconds=\{live\.staleSeconds\} ok=\{live\.ok\} showCurrent=\{false\} \/>/);
  assert.match(dispatchShared, /if \(!stale && !showCurrent\) return null;/);
  assert.match(dispatchShared, /`Dữ liệu cũ \$\{seconds\} giây`/);
});

test("/truong-ca centers three metrics without a vacant fourth cell", () => {
  assert.equal([...queues.matchAll(/<StatCard\b/g)].length, 3);
  assert.match(queues, /className="dispatch-stats/);
  assert.match(
    dispatchCss,
    /\.dispatch-stats > div\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/,
  );
  assert.match(
    dispatchCss,
    /@media \(min-width: 768px\)[\s\S]*?\.dispatch-stats > div\s*\{[^}]*grid-template-columns:\s*repeat\(3, minmax\(0, 1fr\)\)/,
  );
  assert.match(
    dispatchCss,
    /\.dispatch-stats > div > \*\s*\{[\s\S]*?text-align:\s*center/,
  );
});

test("TV room cards use larger text and omit the heading description", () => {
  assert.doesNotMatch(tv, /Mỗi phòng một TV — mở link trên máy TV/);
  assert.match(tv, /truncate text-emph font-semibold text-ink/);
  assert.match(tv, /truncate text-body text-ink-muted/);
});
