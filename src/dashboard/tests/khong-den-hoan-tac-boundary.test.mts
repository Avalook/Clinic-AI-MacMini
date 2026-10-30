// NÚT "KHÔNG ĐẾN" CÓ LÝ DO + HOÀN TÁC HUỶ / KHÔNG ĐẾN (30/10/2026).
//
// Trước: "Không đến" bấm là ghi luôn, không lý do, không đường quay lại — trái
// luật "mọi thao tác nhân viên bấm phải hoàn tác được". Nay: bấm → hộp nhỏ
// chạm một lý do là ghi (giữ nguyên chỗ nút); xong có toast "Hoàn tác"; dòng đã
// huỷ / không đến có nút Hoàn tác ở danh sách tiếp đón và khung khách. Ai được,
// về trạng thái nào, khung còn chỗ không: MÁY CHỦ quyết (action "reopen").

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { LY_DO_HUY, LY_DO_HUY_THU_TU, LY_DO_KHONG_DEN_THU_TU } from "../lib/ly-do-huy.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

const bang = doc("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx");
const taiCho = doc("../app/(dashboard)/_lam-viec/ThaoTacLichTaiCho.tsx");
const queue = doc("../app/(dashboard)/reception/queue/QueueBoard.tsx");
const khungKhach = doc("../app/(dashboard)/_lam-viec/KhungKhach.tsx");
const route = doc("../app/api/appointments/route.ts");
const moLai = doc("../app/(dashboard)/_lam-viec/mo-lai-lich.ts");
const lichSu = doc("../app/(dashboard)/customers/LichSuCacLanKham.tsx");
const kenh = doc("../app/(dashboard)/customers/KenhDoiHuy.tsx");

const khongDen = taiCho.slice(
  taiCho.indexOf("export function KhongDenTaiCho("),
  taiCho.indexOf("/* ───────────────────────── Gọi / ghi chăm sóc"),
);

test("hai danh sách chip: mỗi mã có nhãn, Khác cuối, chỉ Khác dùng chung", () => {
  for (const ds of [LY_DO_HUY_THU_TU, LY_DO_KHONG_DEN_THU_TU]) {
    for (const m of ds) assert.ok(LY_DO_HUY[m], `thiếu nhãn ${m}`);
    assert.equal(ds.at(-1), "KHAC");
  }
  const chung = LY_DO_HUY_THU_TU.filter((m) => LY_DO_KHONG_DEN_THU_TU.includes(m));
  assert.deepEqual(chung, ["KHAC"]);
});

test("nút Không đến giữ chỗ cũ, mở hộp lý do thay vì ghi thẳng", () => {
  assert.doesNotMatch(bang, /act\(a\.id, "no_show"\)/);
  assert.doesNotMatch(bang, /"checkin" \| "undo_checkin" \| "no_show"/);
  const i = bang.indexOf(">\n                                        Không đến");
  assert.ok(i > 0, "không thấy nút Không đến");
  const nut = bang.slice(bang.lastIndexOf("<button", i), i);
  assert.match(nut, /setTaiCho\(\{ loai: "khongDen", lich, neo: tr \}\)/);
  assert.match(bang, /<KhongDenTaiCho/);
});

test("hộp Không đến: chạm một lý do là gửi no_show kèm mã; Khác phải viết", () => {
  assert.ok(khongDen.length > 0);
  assert.match(khongDen, /LY_DO_KHONG_DEN_THU_TU\.map/);
  assert.match(khongDen, /action: "no_show"/);
  assert.match(khongDen, /ly_do_huy_ma: ma/);
  assert.match(khongDen, /onClick=\{\(\) => void danhDau\(m\)\}/);
  assert.match(khongDen, /disabled=\{dang \|\| ghi\.trim\(\) === ""\}/);
  // Không tự chép mã lý do — đọc danh mục chung.
  assert.doesNotMatch(khongDen, /QUEN_LICH|KHACH_BAO_BAN|KHONG_LIEN_LAC_DUOC/);
  assert.doesNotMatch(khongDen, /window\.confirm|style=\{\{/);
});

test("huỷ và không đến xong đều có toast Hoàn tác gọi đúng lệnh mở lại", () => {
  assert.match(moLai, /export async function moLaiLich\(/);
  assert.match(moLai, /JSON\.stringify\(\{ id, action: "reopen" \}\)/);
  assert.equal((bang.match(/onXong=\{xongCoHoanTac\(taiCho\.lich\.id\)\}/g) ?? []).length, 2);
  assert.match(bang, /setHoanTac\(\{ cau, goi: \(\) => moLaiLich\(id\) \}\)/);
  assert.match(bang, /<ThongBaoHoanTac\s+thongBao=\{hoanTac\}/);
  // Proxy chỉ chuyển tiếp — nhưng phải nhận action ấy.
  assert.match(route, /\| "reopen";/);
  assert.match(route, /"no_show",\s*"reopen",\s*\]\);/);
});

test("nút Hoàn tác trên dòng theo cờ máy chủ, cùng một lệnh", () => {
  assert.match(queue, /d\.mo_lai_lich_duoc \? \(\s*<NutHoanTac\s+goi=\{\(\) => moLaiLich\(d\.appointment_id\)\}/);
  assert.match(khungKhach, /l\.mo_lai_duoc \? \(\s*<NutHoanTac\s+goi=\{\(\) => moLaiLich\(l\.id\)\}/);
  // Không màn nào tự gọi "reopen" ngoài ống chung.
  for (const src of [bang, queue, khungKhach, taiCho]) {
    assert.doesNotMatch(src, /action: "reopen"/);
  }
});

test("lý do không đến hiện ở mọi chỗ đang hiện lý do huỷ", () => {
  assert.match(queue, /chuLyDoHuy\(d\.ly_do_ma, d\.ly_do_chu\)/);
  assert.match(queue, /Lý do: \{lyDo\}/);
  assert.match(lichSu, /luot\.status === "NO_SHOW" \? "Lý do không đến: " : "Lý do huỷ: "/);
  assert.match(kenh, /d\.loai === "KHONG_DEN" \? "Không đến"/);
});
