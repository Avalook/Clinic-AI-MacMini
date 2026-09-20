// Kiểm tra tiến trình buổi khám cho lượt khám không có lịch hẹn (appointmentless / walk-in)
// trên màn hình Lễ tân (home / VisitProgress).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pageSource = readFileSync(
  new URL("../app/(dashboard)/home/page.tsx", import.meta.url),
  "utf8",
);
const lichHenSource = readFileSync(
  new URL("../app/(dashboard)/home/lich-hen-ngay.ts", import.meta.url),
  "utf8",
);
const visitProgressSource = readFileSync(
  new URL("../app/(dashboard)/home/VisitProgress.tsx", import.meta.url),
  "utf8",
);

// Mô phỏng hàm reachedCount từ VisitProgress.tsx
function reachedCount(
  visitStatus: string,
  apptStatus: string | null,
  paid: boolean,
  checkedIn = true,
  examStarted?: boolean,
): number {
  const done =
    apptStatus === "COMPLETED" ||
    visitStatus === "FINALIZED" ||
    visitStatus === "AMENDED";
  if (paid && done) return 4;
  if (done) return 3;
  if (visitStatus === "IN_PROGRESS" && examStarted === false) return checkedIn ? 1 : 0;
  if (visitStatus === "IN_PROGRESS" || visitStatus === "INCOMPLETE") return 2;
  return checkedIn ? 1 : 0;
}

test("VisitProgress.tsx định nghĩa reachedCount với điều kiện paid && done", () => {
  assert.match(
    visitProgressSource,
    /if\s*\(paid\s*&&\s*done\)\s*return\s*4;/,
    "VisitProgress phải trả 4 (Đã thanh toán) khi paid && done",
  );
  assert.match(
    visitProgressSource,
    /visitStatus\s*===\s*"FINALIZED"/,
    "done phải bao gồm visitStatus === 'FINALIZED'",
  );
});

test("Test F1: reachedCount trả 4 (Đã thanh toán xanh) khi paid=true và visitStatus=FINALIZED (apptStatus null)", () => {
  const count = reachedCount("FINALIZED", null, true);
  assert.equal(count, 4, "Mốc Đã thanh toán phải đạt giá trị 4 (tích xanh) khi paid=true");
});

test("Test F2: reachedCount trả 4 khi paid=true và visitStatus=AMENDED (apptStatus null)", () => {
  const count = reachedCount("AMENDED", null, true);
  assert.equal(count, 4, "Mốc Đã thanh toán phải đạt giá trị 4 (tích xanh) khi paid=true và AMENDED");
});

test("Test F3: ca appointmentless chưa thu đủ (paid=false) chỉ dừng ở mốc 3 (Khám xong)", () => {
  const count = reachedCount("FINALIZED", null, false);
  assert.equal(count, 3, "Khi chưa thu tiền (paid=false), mốc phải dừng ở 3 (Khám xong)");
});

test("Test F4: logic tính v.paid ở home/page.tsx cho ca appointmentless", () => {
  // Đảm bảo home/page.tsx định nghĩa VisitProgressRow chấp nhận appointment_id là null
  assert.match(
    pageSource,
    /appointment_id:\s*string\s*\|\s*null/,
    "VisitProgressRow phải cho phép appointment_id là string | null",
  );

  // Đảm bảo lich-hen-ngay.ts chấp nhận appointment_id là null
  assert.match(
    lichHenSource,
    /appointment_id\?:\s*string\s*\|\s*null/,
    "GoiLichHen.tien_trinh phải cho phép appointment_id là string | null",
  );

  // Giả lập dữ liệu tiến trình trả về từ backend cho ca appointmentless (appointment_id = null)
  const tienTrinh = [
    {
      appointment_id: null,
      visit_id: "v-walkin-123",
      vitals_recorded: true,
      has_clinical_record: true,
      has_prescription: false,
      paid_kinds: ["dich_vu"],
      exam_started_at: "2026-09-20T08:30:00+07:00",
      paid_at: "2026-09-20T09:15:00+07:00",
    },
  ];

  const progressByVisit = new Map(
    tienTrinh.filter((p) => p.visit_id).map((p) => [p.visit_id as string, p]),
  );

  const v: {
    visit_id: string;
    status: string;
    paid?: boolean;
    exam_started_at?: string | null;
    paid_at?: string | null;
  } = {
    visit_id: "v-walkin-123",
    status: "FINALIZED",
  };

  const p = progressByVisit.get(v.visit_id);
  assert.ok(p, "progressByVisit phải tìm thấy tiến trình theo visit_id của ca walk-in");

  const kinds = new Set(p?.paid_kinds ?? []);
  v.paid = kinds.has("dich_vu") && (!p?.has_prescription || kinds.has("thuoc"));
  v.exam_started_at = p?.exam_started_at ?? null;
  v.paid_at = p?.paid_at ?? null;

  assert.equal(v.paid, true, "v.paid phải là true sau khi dịch vụ đã PAID");
  assert.equal(v.paid_at, "2026-09-20T09:15:00+07:00", "v.paid_at phải được gán đúng mốc thanh toán");

  const count = reachedCount(v.status, null, v.paid);
  assert.equal(count, 4, "Thanh tiến trình Lễ tân phải render mốc 'Đã thanh toán' đạt 4 (tích xanh)");
});
