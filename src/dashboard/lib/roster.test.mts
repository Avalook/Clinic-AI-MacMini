import assert from "node:assert/strict";
import test from "node:test";

import {
  SHIFTS,
  SHIFT_LABEL,
  chiaHaiHang,
  currentWeekStartVn,
  demBacSiTruc,
  weekDates,
  weekStartOf,
  gomTheoNguoi,
  mauPhong,
  phanPhong,
  tinhGopDoc,
  viTriTuDb,
  type ThongTinO,
} from "./roster.ts";
import { coChucDanh, vaiKemTen } from "./doctor-name.ts";

// Hai luật này là chỗ dễ đoán sai nhất của bảng lịch làm việc, và đoán sai thì
// bảng vẫn vẽ ra bình thường — chỉ nội dung là sai. Nên ghim bằng test.

test("chiaHaiHang: người đầu ở hàng trên, phần còn lại dồn xuống hàng dưới", () => {
  assert.deepEqual(chiaHaiHang([]), [[], []]);
  assert.deepEqual(chiaHaiHang(["A"]), [["A"], []]);
  assert.deepEqual(chiaHaiHang(["A", "B"]), [["A"], ["B"]]);
  // KHÔNG cắt bớt người thứ ba: Excel cũng viết "Thư/Hà Vũ" chung một ô. Cắt đi
  // nghĩa là bảng nói dối về ai đang trực hôm đó.
  assert.deepEqual(chiaHaiHang(["A", "B", "C"]), [["A"], ["B", "C"]]);
});

test("demBacSiTruc: đếm NGƯỜI ở trạm Lịch khám, không đếm dòng", () => {
  const rows = [
    // Cùng một bác sĩ, trực cả sáng lẫn chiều = HAI dòng work_roster.
    { work_date: "2026-08-04", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
    { work_date: "2026-08-04", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
    { work_date: "2026-08-04", station: "LICH_KHAM", staff_id: "b", staff_name: "BS Nam" },
    // Trạm khác không tính vào cột "Số BS".
    { work_date: "2026-08-04", station: "LE_TAN", staff_id: "c", staff_name: "Quỳnh Anh" },
    { work_date: "2026-08-05", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
  ];
  assert.equal(demBacSiTruc(rows, "2026-08-04"), 2);
  assert.equal(demBacSiTruc(rows, "2026-08-05"), 1);
  assert.equal(demBacSiTruc(rows, "2026-08-06"), 0);
});

// ĐẦU VÀO RÁC. Ba lần hệ thống trả 500 vì cùng một họ lỗi — `new Date(<chuỗi
// người dùng>)` cho Invalid Date, rồi `toISOString()` NÉM `RangeError` — và cả
// ba lần đều được vá tại chỗ nó nổ, không ai viết bài test này. Nên con thứ ba
// mọc trong `lib/roster.ts`, tức là ở TRANG CHỦ. Bài test dưới đây là thứ canh
// họ lỗi ấy, thay cho việc phải nhớ.
test("weekStartOf: ngày không đọc được thì trả null, KHÔNG ném", () => {
  for (const rac of [
    "abc",
    "99-99-9999",
    "2026-13-45",
    "",
    "null",
    "undefined",
    "2026-02-30T00:00",
    "<script>",
  ]) {
    assert.equal(
      weekStartOf(rac),
      null,
      `"${rac}" phải cho null chứ không ném hay trả bừa một ngày`,
    );
  }
});

test("weekStartOf: ngày hợp lệ vẫn ra đúng thứ Hai của tuần đó", () => {
  // 05/08/2026 là thứ Tư → thứ Hai của tuần là 03/08.
  assert.equal(weekStartOf("2026-08-05"), "2026-08-03");
  // Chủ nhật thuộc về tuần TRƯỚC nó, không phải tuần bắt đầu ngày hôm sau.
  assert.equal(weekStartOf("2026-08-09"), "2026-08-03");
  // Chính thứ Hai thì trả về chính nó.
  assert.equal(weekStartOf("2026-08-03"), "2026-08-03");
  // Qua mốc tháng.
  assert.equal(weekStartOf("2026-09-01"), "2026-08-31");
});

test("currentWeekStartVn: luôn ra một thứ Hai đọc được", () => {
  const w = currentWeekStartVn();
  assert.match(w, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(new Date(w + "T00:00:00Z").getUTCDay(), 1, "phải là thứ Hai");
  // Và nó phải khớp với chính weekStartOf khi đưa lại vào — hai đường một kết quả.
  assert.equal(weekStartOf(w), w);
});

test("weekDates: 7 ngày liên tiếp bắt đầu từ thứ Hai", () => {
  assert.deepEqual(weekDates("2026-08-03"), [
    "2026-08-03",
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-08",
    "2026-08-09",
  ]);
});

test("demBacSiTruc: dòng nạp từ Excel chưa nối được staff_id vẫn được đếm", () => {
  // 2 ô trên prod có staff_id NULL (tên gõ tay từ file Excel). Bỏ qua chúng là
  // cột "Số BS" nói ít hơn số người đứng ngay bên cạnh nó trong cùng hàng.
  const rows = [
    { work_date: "2026-08-03", station: "LICH_KHAM", staff_id: null, staff_name: "BS LINH Nam khoa" },
    { work_date: "2026-08-03", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
  ];
  assert.equal(demBacSiTruc(rows, "2026-08-03"), 2);
});

// Ba test dưới đây canh cùng MỘT lỗi: bản cũ liệt kê tay "SANG"/"CHIEU" ở
// app/api/roster/route.ts, nên khi thêm ca TỐI (21/08/2026) route lặng lẽ đổi ca
// tối thành "cả ngày" — quản lý xếp ca tối, hệ ghi cả ngày, không lỗi nào bật ra.
// Vá bằng cách để route đọc SHIFTS từ đây; test giữ cho nguồn ấy không lệch.

test("SHIFTS: đủ 4 lựa chọn, có ca tối", () => {
  assert.equal(SHIFTS.length, 4, "đổi số ca thì phải sửa cả nhãn lẫn API");
  assert.deepEqual([...SHIFTS].sort(), ["CHIEU", "FULL", "SANG", "TOI"]);
});

test("SHIFT_LABEL: mọi ca đều có nhãn tiếng Việt, không sót cái nào", () => {
  const thieu = SHIFTS.filter((ca) => !SHIFT_LABEL[ca]);
  assert.deepEqual(thieu, [], `ca chưa có nhãn: ${thieu.join(", ")}`);
  assert.equal(Object.keys(SHIFT_LABEL).length, SHIFTS.length, "nhãn thừa/thiếu so với SHIFTS");
  assert.equal(SHIFT_LABEL.TOI, "Tối");
});

test("luật ép ca của /api/roster: ca tối được giữ, ca lạ mới lùi về cả ngày", () => {
  // Chính là biểu thức trong app/api/roster/route.ts, tách ra để kiểm được.
  const epCa = (gui: string | undefined) =>
    (SHIFTS as readonly string[]).includes(gui ?? "") ? (gui as string) : "FULL";

  for (const ca of SHIFTS) assert.equal(epCa(ca), ca, `${ca} không được bị đổi`);
  assert.equal(epCa("TOI"), "TOI", "ca tối KHÔNG được lặng lẽ thành cả ngày");
  assert.equal(epCa("NUA_DEM"), "FULL");
  assert.equal(epCa(undefined), "FULL");
  assert.equal(epCa(""), "FULL");
});

// ── 27/09/2026 đợt 3: bỏ tầng, tên phòng theo cấu hình, vai cạnh tên ──────

const DANH_MUC = viTriTuDb([
  { code: "T1_LETAN", ten: "Lễ tân", ten_ngan: "", tang: "Tầng 1", phong: "Quầy tiếp đón", ma_phong: "KN-TIEPDON", nhom: "DIEU_DUONG" },
  { code: "T1_THUNGAN", ten: "Thu ngân", ten_ngan: "", tang: "Tầng 1", phong: "Quầy tiếp đón", ma_phong: "KN-TIEPDON", nhom: "DIEU_DUONG" },
  { code: "T1_TT_BS", ten: "BS thủ thuật", ten_ngan: "BS", tang: "Tầng 1", phong: "Thủ thuật/Sàn chậu", ma_phong: "KN-THUTHUAT", nhom: "BAC_SI" },
  // Vị trí KHÔNG tầng, KHÔNG phòng — bản cũ (`phanTang`) lọc bỏ khỏi bảng.
  { code: "DIEU_PHOI", ten: "Trưởng ca (điều phối)", ten_ngan: "Trưởng ca", tang: "", phong: "", ma_phong: "", nhom: "DIEU_DUONG" },
  // Vị trí quản lý thêm ở màn Dây nối: mã VT-…, không ô tầng, có phòng.
  { code: "VT-1a2b3c4d", ten: "Phụ siêu âm", ten_ngan: "", phong: "Phòng siêu âm 1", ma_phong: "KN-SA-T1", nhom: "rác" },
]);

test("phanPhong: MỌI vị trí có hàng — kể cả Trưởng ca và VT-* không tầng", () => {
  const nhom = phanPhong(DANH_MUC);
  const ma = nhom.flatMap((n) => n.stations.map((s) => s.key));
  assert.deepEqual(ma, ["T1_LETAN", "T1_THUNGAN", "T1_TT_BS", "DIEU_PHOI", "VT-1a2b3c4d"]);
  // Hai vị trí liền nhau cùng phòng → một nhóm (ô Phòng gộp).
  assert.equal(nhom[0].stations.length, 2);
  assert.equal(nhom[0].phong, "Quầy tiếp đón");
  // Nhóm nghề rác → rơi về DIEU_DUONG, không ném.
  assert.equal(DANH_MUC[4].nhom, "DIEU_DUONG");
  assert.deepEqual(phanPhong([]), []);
});

test("phanPhong: cùng tên phòng mà nằm cách nhau là HAI nhóm (không xáo thứ tự)", () => {
  const [a, , c] = DANH_MUC;
  const nhom = phanPhong([a, c, { ...a, key: "X" }]);
  assert.deepEqual(nhom.map((n) => n.stations.length), [1, 1, 1]);
});

test("mauPhong: khoá theo MÃ phòng — đổi tên phòng không mất màu", () => {
  // "Phòng thủ thuật" đã đổi tên thành "Thủ thuật/Sàn chậu" ở cấu hình.
  assert.equal(mauPhong(DANH_MUC[2].maPhong), "bg-lich-thu-thuat");
  assert.equal(mauPhong("KN-TIEPDON"), "bg-lich-tiep-don");
  // Không gắn phòng / mã lạ / rác → nền thẻ, không ném.
  for (const rac of ["", null, undefined, "KN-KHONG-CO", "constructor", "__proto__"]) {
    assert.equal(mauPhong(rac), "bg-surface", String(rac));
  }
});

const MO = (khoa: string): ThongTinO => ({ dong: null, khoa });
const NGHI: ThongTinO = { dong: "NGHI", khoa: "" };
const DEN: ThongTinO = { dong: "DONG", khoa: "" };

test("tinhGopDoc: cùng người liền nhau → một ô; NGHỈ nối nhau → một khối; ô đen không gộp", () => {
  const span = tinhGopDoc([
    [MO("Hà"), NGHI, DEN],
    [MO("Hà"), NGHI, DEN],
    [MO("Lan"), MO("Hà"), MO("")],
    [MO(""), MO("Hà"), MO("")],
  ]);
  assert.deepEqual(span, [
    [2, 2, 1],
    [0, 0, 1],
    [1, 2, 1],
    [1, 0, 1],
  ]);
  assert.deepEqual(tinhGopDoc([]), []);
});

test("gomTheoNguoi: mỗi người một dòng, vai từ máy chủ, ngày → chỗ đứng + ca", () => {
  const nhan = { T1_LETAN: "Lễ tân", T1_THUNGAN: "Thu ngân" };
  const ds = gomTheoNguoi(
    [
      { work_date: "2026-09-28", station: "T1_THUNGAN", shift: "TOI", staff_id: "b", staff_name: "Hà", vai: "Lễ tân" },
      { work_date: "2026-09-28", station: "T1_LETAN", shift: "SANG", staff_id: "b", staff_name: "Hà", vai: "Lễ tân" },
      // Trùng dòng → in một lần.
      { work_date: "2026-09-28", station: "T1_LETAN", shift: "SANG", staff_id: "b", staff_name: "Hà", vai: "Lễ tân" },
      { work_date: "2026-09-29", station: "MA_LA", shift: "XYZ", staff_id: null, staff_name: "An", vai: null },
      // Ô chưa xếp (không tên) → bỏ qua.
      { work_date: "2026-09-29", station: "T1_LETAN", shift: "TOI", staff_id: null, staff_name: "  " },
    ],
    nhan,
  );
  assert.deepEqual(ds.map((n) => n.ten), ["An", "Hà"]);
  const ha = ds[1];
  assert.equal(ha.vai, "Lễ tân");
  assert.deepEqual(ha.theoNgay["2026-09-28"], [
    { viTri: "Lễ tân", ca: "Sáng" },
    { viTri: "Thu ngân", ca: "Tối" },
  ]);
  // Mã vị trí lạ / ca lạ → in nguyên mã, không ném.
  assert.deepEqual(ds[0].theoNgay["2026-09-29"], [{ viTri: "MA_LA", ca: "XYZ" }]);
  assert.equal(ds[0].vai, "");
  assert.deepEqual(gomTheoNguoi([], {}), []);
});

test("vaiKemTen: tên đã có chức danh thì KHÔNG lặp chip vai", () => {
  assert.equal(vaiKemTen("Quỳnh Anh", "Lễ tân"), "Lễ tân");
  assert.equal(vaiKemTen("Thư", "ĐD"), "ĐD");
  assert.equal(vaiKemTen("Bác sĩ Phan Chí Thành", "BS"), "");
  assert.equal(vaiKemTen("Bác sĩ · BSNT. Lê Thiệu Quyết", "BS"), "");
  assert.equal(vaiKemTen("BS NAM", "BS"), "");
  assert.equal(vaiKemTen("ĐD. Thuý", "ĐD"), "");
  // Rác → rỗng, không ném.
  assert.equal(vaiKemTen("Hà", ""), "");
  assert.equal(vaiKemTen(null, null), "");
  assert.equal(vaiKemTen(undefined, "  "), "");
  assert.equal(coChucDanh(""), false);
  assert.equal(coChucDanh("BS"), false, "chỉ viết tắt, không tên → không coi là tên có chức danh");
  assert.equal(coChucDanh("Thùy Linh"), false);
});
