// Lưới đặt chỗ VẼ THEO SỐ CỦA MÁY CHỦ — không tự cộng, không lấy trần chung.
//
// Tuyền 29/09/2026 ("sửa đi"): sức chứa tính hai nơi. Trigger chặn theo
// `resolve_effective_cap` (bác sĩ × khung, có luật riêng); lưới thì tự cộng lịch
// rồi so với `policy.regularCap/walkinCap` của cả phòng khám. Kịch bản thật:
// quản lý hạ BS X 18:00 xuống 1 chỗ → lưới vẫn cho bấm ghế 2 rồi máy chủ báo
// đầy; nâng lên 4 → lưới chỉ vẽ 2 ghế.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  hangCua,
  khungChua,
  khungDay,
  phutCua,
  soGhe,
  soHangGhe,
  type HangSucChua,
  type KhungSucChua,
  type SucChuaNgay,
} from "../lib/suc-chua-luoi.ts";

function khung(p: Partial<KhungSucChua> = {}): KhungSucChua {
  return {
    time: "18:00",
    minute_of_day: 18 * 60,
    slot_minutes: 15,
    regular_cap: 2,
    walkin_cap: 1,
    regular_used: 0,
    walkin_used: 0,
    con_lai: 2,
    state: "free",
    ...p,
  };
}

function hang(p: Partial<HangSucChua> = {}): HangSucChua {
  return {
    doctor_id: "bs-x",
    closed: false,
    off_duty: false,
    roster_week_published: true,
    dat_tu_do: false,
    regular_chan: true,
    walkin_chan: true,
    shift_windows: [],
    slots: [khung()],
    ...p,
  };
}

test("hạ BS X 18:00 xuống 1 chỗ → lưới vẽ ĐÚNG 1 ghế hẹn, ghế 2 không tồn tại", () => {
  const h = hang({ slots: [khung({ regular_cap: 1, regular_used: 1 })] });
  const k = khungChua(h, 18 * 60)!;
  assert.equal(soGhe(h, k, "regular"), 1);
  assert.equal(soHangGhe(h, "regular", [18 * 60]), 1);
  assert.equal(khungDay(h, 18 * 60, "regular"), true, "đã có 1 người → đầy, như trigger");
});

test("nâng lên 4 chỗ → lưới vẽ 4 ghế, không bị trần chung 2 cắt", () => {
  const h = hang({ slots: [khung({ regular_cap: 4, regular_used: 2 })] });
  assert.equal(soHangGhe(h, "regular", [18 * 60]), 4);
  assert.equal(khungDay(h, 18 * 60, "regular"), false);
});

test("mỗi khung một trần: số hàng = khung nhiều ghế nhất", () => {
  const h = hang({
    slots: [
      khung({ minute_of_day: 17 * 60 + 45, regular_cap: 2 }),
      khung({ minute_of_day: 18 * 60, regular_cap: 5 }),
    ],
  });
  assert.equal(soHangGhe(h, "regular", [17 * 60 + 45, 18 * 60]), 5);
  assert.equal(soGhe(h, khungChua(h, 17 * 60 + 45)!, "regular"), 2);
});

test("trần KHÔNG chặn (tuần chưa công bố / chưa gán bác sĩ) → luôn còn một ô sau người cuối", () => {
  const h = hang({
    regular_chan: false,
    dat_tu_do: true,
    slots: [khung({ regular_cap: 2, regular_used: 3 })],
  });
  const k = khungChua(h, 18 * 60)!;
  assert.equal(soGhe(h, k, "regular"), 4, "3 người đã đặt + 1 ô để đặt vượt");
  assert.equal(khungDay(h, 18 * 60, "regular"), false, "trigger nhận → không báo đầy");
});

test("ghế trực tiếp đếm theo walkin_cap/used của máy chủ", () => {
  const h = hang({ slots: [khung({ walkin_cap: 0 })] });
  assert.equal(soHangGhe(h, "walkin", [18 * 60]), 0, "luật riêng tắt ghế trực tiếp");
  const h2 = hang({ slots: [khung({ walkin_cap: 2, walkin_used: 2 })] });
  assert.equal(khungDay(h2, 18 * 60, "walkin"), true);
});

test("giờ gõ tay giữa khung quy về khung chứa nó; ngoài khung/giờ hỏng → không biết", () => {
  const h = hang();
  assert.equal(khungChua(h, phutCua("18:07"))?.minute_of_day, 18 * 60);
  assert.equal(khungChua(h, phutCua("18:15")), null, "nửa mở [18:00, 18:15)");
  assert.equal(khungDay(h, phutCua("rác"), "regular"), null, "giờ hỏng không ném");
  assert.ok(Number.isNaN(phutCua("")));
});

test("hàng chưa phân bác sĩ là doctor_id null; bác sĩ chưa có hàng → null, không đoán", () => {
  const sc: SucChuaNgay = {
    date: "2026-09-30",
    hang: [hang(), hang({ doctor_id: null, regular_chan: false })],
  };
  assert.equal(hangCua(sc, "")?.doctor_id, null);
  assert.equal(hangCua(sc, "bs-x")?.doctor_id, "bs-x");
  assert.equal(hangCua(sc, "bs-khac"), null);
  assert.equal(hangCua(null, "bs-x"), null);
  assert.equal(soHangGhe(null, "regular", [18 * 60]), 0);
});

const doc = (p: string) =>
  readFileSync(new URL(p, import.meta.url), "utf8")
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");

test("4 chỗ vẽ ghế không tự lấy trần chung, không tự cộng lịch", () => {
  const man = {
    CinemaSlotPicker: doc("../app/(dashboard)/patients/CinemaSlotPicker.tsx"),
    AppointmentBooking: doc("../app/(dashboard)/patients/AppointmentBooking.tsx"),
    NewPatientForm: doc("../app/(dashboard)/patients/new/NewPatientForm.tsx"),
    WeeklyAppointmentsTable: doc("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx"),
  };
  for (const [ten, ma] of Object.entries(man)) {
    assert.doesNotMatch(ma, /policy\??\.(regularCap|walkinCap)/, `${ten} còn dùng trần chung`);
    assert.doesNotMatch(ma, /\b(buildSlotUsage|usageAt|isDeadStatus)\b/, `${ten} còn tự đếm`);
  }
  assert.match(
    man.WeeklyAppointmentsTable,
    /ghe_truc_tiep_con/,
    "ô xanh 'đặt vào đây' phải theo số ghế trực tiếp máy chủ trả",
  );
});

test("slot-capacity không còn phần đếm ghế và danh sách trạng thái chết", () => {
  const ma = doc("../lib/slot-capacity.ts");
  assert.doesNotMatch(ma, /buildSlotUsage|usageAt|DEAD_STATUSES|"CANCELLED"/);
});

test("một lượt gọi cho cả lưới — hook không hỏi từng bác sĩ", () => {
  const hook = doc("../app/(dashboard)/patients/dung-suc-chua-ngay.ts");
  assert.equal((hook.match(/fetch\(/g) ?? []).length, 1, "đúng một lời gọi");
  assert.doesNotMatch(hook, /\.map\([^)]*fetch/, "không gọi trong vòng lặp bác sĩ");
  assert.match(hook, /doctor_ids/);
});
