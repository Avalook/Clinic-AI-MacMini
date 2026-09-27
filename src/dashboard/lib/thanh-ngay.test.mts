import assert from "node:assert/strict";
import test from "node:test";

import {
  congNgay,
  daiNgay,
  docKhoang,
  docNgay,
  khoangNhanh,
  khoangTuKy,
  maCuaKhoang,
  nhanKhoang,
} from "./thanh-ngay.ts";

// Chủ nhật 27/09/2026.
const HOM_NAY = "2026-09-27";

test("ngày rác → null / rỗng, không ném", () => {
  for (const rac of [null, undefined, "", "  ", "rác", "2026-02-31", "27/09/2026", 5, {}, []]) {
    assert.equal(docNgay(rac), null);
    assert.equal(docKhoang(rac, rac), null);
  }
  assert.equal(congNgay("rác", 1), "");
  assert.equal(congNgay(HOM_NAY, Number.NaN), "");
  assert.equal(khoangNhanh("hom-qua", "rác"), null);
  assert.deepEqual(daiNgay("rác", 3, 3), []);
  assert.equal(khoangTuKy("today", "rác"), null);
});

test("docNgay bỏ phần giờ, giữ ngày", () => {
  assert.equal(docNgay("2026-09-27T23:30:00+07:00"), "2026-09-27");
});

test("congNgay qua tháng / năm", () => {
  assert.equal(congNgay("2026-09-30", 1), "2026-10-01");
  assert.equal(congNgay("2026-01-01", -1), "2025-12-31");
});

test("chip bấm nhanh", () => {
  assert.deepEqual(khoangNhanh("hom-nay", HOM_NAY), { tu: HOM_NAY, den: HOM_NAY });
  assert.deepEqual(khoangNhanh("hom-qua", HOM_NAY), { tu: "2026-09-26", den: "2026-09-26" });
  assert.deepEqual(khoangNhanh("hom-kia", HOM_NAY), { tu: "2026-09-25", den: "2026-09-25" });
  assert.deepEqual(khoangNhanh("7-ngay", HOM_NAY), { tu: "2026-09-21", den: HOM_NAY });
  // Tuần trước = T2–CN của tuần liền trước (tuần bắt đầu thứ Hai).
  assert.deepEqual(khoangNhanh("tuan-truoc", HOM_NAY), { tu: "2026-09-14", den: "2026-09-20" });
  assert.deepEqual(khoangNhanh("tuan-truoc", "2026-09-21"), { tu: "2026-09-14", den: "2026-09-20" });
  assert.deepEqual(khoangNhanh("30-ngay", HOM_NAY), { tu: "2026-08-29", den: HOM_NAY });
});

test("docKhoang: thiếu một đầu, ngược chiều, quá dài", () => {
  assert.deepEqual(docKhoang("2026-09-26", "rác"), { tu: "2026-09-26", den: "2026-09-26" });
  assert.deepEqual(docKhoang(null, "2026-09-26"), { tu: "2026-09-26", den: "2026-09-26" });
  assert.deepEqual(docKhoang("2026-09-27", "2026-09-20"), { tu: "2026-09-20", den: "2026-09-27" });
  assert.deepEqual(docKhoang("2020-01-01", HOM_NAY), { tu: "2025-09-26", den: HOM_NAY });
});

test("maCuaKhoang tô đúng chip, khoảng lạ → null", () => {
  assert.equal(maCuaKhoang({ tu: "2026-09-26", den: "2026-09-26" }, HOM_NAY), "hom-qua");
  assert.equal(maCuaKhoang({ tu: "2026-09-14", den: "2026-09-20" }, HOM_NAY), "tuan-truoc");
  assert.equal(maCuaKhoang({ tu: "2026-09-01", den: "2026-09-03" }, HOM_NAY), null);
  assert.equal(maCuaKhoang(null, HOM_NAY), null);
});

test("khoangTuKy đổi kỳ cũ", () => {
  assert.deepEqual(khoangTuKy("today", HOM_NAY), { tu: HOM_NAY, den: HOM_NAY });
  assert.deepEqual(khoangTuKy("week", HOM_NAY), { tu: "2026-09-21", den: HOM_NAY });
  assert.deepEqual(khoangTuKy("month", "2026-02-10"), { tu: "2026-02-01", den: "2026-02-28" });
  assert.equal(khoangTuKy("all", HOM_NAY), null);
  assert.equal(khoangTuKy(undefined, HOM_NAY), null);
});

test("nhãn + dải ngày", () => {
  assert.equal(nhanKhoang(null), "Tất cả");
  assert.equal(nhanKhoang({ tu: HOM_NAY, den: HOM_NAY }), "27/09");
  assert.equal(nhanKhoang({ tu: "2026-09-21", den: HOM_NAY }), "21/09 – 27/09");
  const dai = daiNgay(HOM_NAY, 2, 1);
  assert.deepEqual(
    dai.map((o) => [o.ngay, o.thu, o.homNay]),
    [
      ["2026-09-25", "T6", false],
      ["2026-09-26", "T7", false],
      ["2026-09-27", "CN", true],
      ["2026-09-28", "T2", false],
    ],
  );
});
