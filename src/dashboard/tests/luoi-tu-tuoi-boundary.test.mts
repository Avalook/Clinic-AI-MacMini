// Hai lưới đặt chỗ tự tươi khi ca trực đổi (17/08/2026).
//
// router.refresh() chỉ vẽ lại server component; hai lưới sống bằng dữ liệu
// client-fetch có cache — quản lý xoá ca xong, cảnh báo CSKH nhảy mà lưới
// vẫn vẽ ca cũ tới khi đổi ngày/F5. Chuông SU_KIEN_DOI_CA (CustomEvent, do
// RealtimeRefresher — người nghe SSE duy nhất — rung có debounce) là đường
// nối; các effect fetch bỏ useDoiCa() vào deps là tự hỏi lại.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) =>
  readFileSync(new URL(p, import.meta.url), "utf8")
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");

test("RealtimeRefresher là người rung chuông duy nhất, có debounce", () => {
  const ma = doc("../app/(dashboard)/RealtimeRefresher.tsx");
  assert.match(ma, /t === "work_roster"/, "chuông chỉ rung vì ca trực");
  // Nhịp gộp chuyển vào `lib/nhip-lam-moi` ngày 21/08/2026 (cùng lúc với việc
  // gộp dòng SSE về một tab). Bất biến không đổi — chỉ đổi chỗ ép nó: `setTimeout`
  // tại chỗ thành `taoNhipLamMoi`, thứ vừa gộp nhịp vừa bỏ tab đang ẩn, và có
  // test riêng ở `lib/nhip-lam-moi.test.mts`.
  assert.match(
    ma,
    /const chuongCa = taoNhipLamMoi\(\{[\s\S]*?SU_KIEN_DOI_CA/,
    "rung phải qua taoNhipLamMoi — áp dụng cả tuần là một tràng notify, không được thành một tràng refetch",
  );
  assert.equal(
    ma.match(/dispatchEvent\(new CustomEvent\(SU_KIEN_DOI_CA/g)?.length,
    1,
    "chỉ MỘT chỗ rung chuông, và nó nằm trong nhịp gộp — thêm chỗ thứ hai là đi vòng qua nhịp",
  );
});

test("cả HAI lưới cùng nghe chuông — vá một trong hai là bài học ba lưới lặp lại", () => {
  const hub = doc("../app/(dashboard)/appointments/BookingHub.tsx");
  assert.match(hub, /useDoiCa\(\)/, "BookingHub phải nghe chuông");
  assert.match(
    hub,
    /bookingSeq, doiCa\]/,
    "effect quote phải có doiCa trong deps",
  );
  assert.match(
    hub,
    /setFetchedByDate\(\{\}\)/,
    "xoá ca là lịch bị huỷ theo — cache lịch ngày-khác phải xả",
  );

  const khoang = doc("../app/(dashboard)/patients/dung-khoang-ca.ts");
  assert.match(khoang, /useDoiCa\(\)/, "useKhoangCa phải nghe chuông");
  assert.match(khoang, /doiCa\]/, "deps của effect khoảng ca phải có doiCa");

  const form = doc("../app/(dashboard)/patients/new/NewPatientForm.tsx");
  assert.match(
    form,
    /\[dutyDate, doiCa\]/,
    "danh sách bác sĩ trực của form khách mới cũng phải nạp lại theo chuông",
  );
});
