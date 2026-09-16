// Lịch làm việc (weekly roster) — cấu hình phòng/trạm + helper ngày/tuần.
// Danh sách trạm suy ra từ bảng Google Sheet của phòng khám; chỉnh ở đây nếu
// phòng khám đổi cách phân công.


// Cookie lưu "tôi là ai" cho vai trò không phải bác sĩ (lọc lịch cá nhân).
export const ROSTER_STAFF_COOKIE = "roster_staff_id";

export interface Station {
  key: string;
  /** Tên đầy đủ, đúng chữ trong file Excel (tooltip / ô chọn). */
  label: string;
  /** Nhãn ngắn in ở đầu hàng. */
  short: string;
  /** Nhóm MÀU. */
  group: string;
  /** Tầng — dùng để gộp hàng, đúng như cột "Tầng" của Excel. */
  floor: string;
  /** Phòng — nhóm con trong tầng, đúng cột "Phòng" của Excel. */
  phong: string;
  /** Ai đứng được chỗ này. Khớp `vi_tri_lam_viec.nhom_nghe` trong database. */
  /** CHUNG = bác sĩ hay điều dưỡng đều đứng được (xem migration 20260916000012). */
  nhom: "BAC_SI" | "DIEU_DUONG" | "DOI_TAC" | "CHUNG";
}

// ── 27 VỊ TRÍ THẬT CỦA PK KIM NGƯU ─────────────────────────────────────────
//
// Nguồn: "[Dr4women] PK Kim Ngưu - Lịch làm việc nhân sự theo tuần.xlsx"
// (Tuyền gửi 16/09/2026). Mã trùng KHÍT `vi_tri_lam_viec.code` ở database
// (migration 20260916000008) — lệch một mã là ô ấy mất người mà không báo gì.
//
// THỨ TỰ LÀ THỨ TỰ DÒNG TRONG EXCEL, có chủ ý: người xếp lịch đọc bảng này
// hằng tuần, và đổi thứ tự là bắt họ học lại một thứ họ đã thuộc.
//
// DANH SÁCH CŨ ĐÃ BỎ, và nó đáng được ghi lại vì sao: nó chép từ MỘT FILE
// KHÁC — bảng làm việc đời Hào Nam, với "Máy trong E10", "Phòng ngoài +
// Monitoring", "HSS + Thủ thuật trong giờ", "Trợ lý y khoa". Không một vị trí
// nào trong đó tồn tại ở Kim Ngưu, nên màn xếp lịch suốt thời gian qua mời
// người dùng điền vào những cột của một phòng khám khác.
export const STATIONS: Station[] = [
  // Cột riêng, KHÔNG thuộc tầng nào và KHÔNG có trong Excel: "bác sĩ nào trực
  // hôm ấy". Lưới đặt lịch (`week_appointments_service`) đọc đúng mã này để
  // biết hôm đó nhận lịch cho ai — gộp nó vào danh mục vị trí là hỏng đặt lịch.
  { key: "LICH_KHAM", label: "Lịch khám (bác sĩ trực)", short: "Lịch khám", group: "Bác sĩ", floor: "", phong: "", nhom: "BAC_SI" },

  { key: "T1_LETAN", label: "Lễ tân", short: "Lễ tân", group: "Tầng 1", floor: "Tầng 1", phong: "Quầy tiếp đón", nhom: "DIEU_DUONG" },
  { key: "T1_THUNGAN", label: "Thu ngân", short: "Thu ngân", group: "Tầng 1", floor: "Tầng 1", phong: "Quầy tiếp đón", nhom: "DIEU_DUONG" },
  { key: "T1_DOCHISO", label: "Đo chỉ số sức khoẻ (HA, MĐX, test nước tiểu)", short: "Đo chỉ số sức khoẻ (HA, MĐX, test nước tiểu), dịch cơ thể", group: "Tầng 1", floor: "Tầng 1", phong: "", nhom: "DIEU_DUONG" },
  { key: "T1_LAYMAU", label: "Lấy mẫu (máu)", short: "Lấy mẫu (máu)", group: "Tầng 1", floor: "Tầng 1", phong: "", nhom: "DOI_TAC" },

  { key: "T1_BS_NOITIET", label: "BS Nội tiết", short: "BS Nội tiết", group: "Tầng 1", floor: "Tầng 1", phong: "Phòng Nội tiết", nhom: "BAC_SI" },
  { key: "T1_HOIBENH", label: "Hỏi bệnh ban đầu", short: "Hỏi bệnh ban đầu", group: "Tầng 1", floor: "Tầng 1", phong: "Phòng Nội tiết", nhom: "CHUNG" },
  { key: "T1_TKYK", label: "Thư ký y khoa", short: "Thư ký y khoa", group: "Tầng 1", floor: "Tầng 1", phong: "Phòng Nội tiết", nhom: "DIEU_DUONG" },

  { key: "T1_TT_BS", label: "BS thủ thuật", short: "BS", group: "Tầng 1", floor: "Tầng 1", phong: "Phòng thủ thuật", nhom: "BAC_SI" },
  { key: "T1_TT_DD", label: "Điều dưỡng thủ thuật", short: "Điều dưỡng", group: "Tầng 1", floor: "Tầng 1", phong: "Phòng thủ thuật", nhom: "DIEU_DUONG" },

  { key: "T1_SA_BS", label: "BS siêu âm (tầng 1)", short: "BS", group: "Tầng 1", floor: "Tầng 1", phong: "Phòng Siêu âm", nhom: "BAC_SI" },
  { key: "T1_SA_DD", label: "Điều dưỡng siêu âm (tầng 1)", short: "Điều dưỡng", group: "Tầng 1", floor: "Tầng 1", phong: "Phòng Siêu âm", nhom: "DIEU_DUONG" },

  { key: "T1_TTNG_BS", label: "BS thủ thuật ngoài giờ", short: "BS", group: "Ngoài giờ", floor: "Tầng 1", phong: "Thủ thuật ngoài giờ", nhom: "BAC_SI" },
  { key: "T1_TTNG_DD1", label: "Điều dưỡng ngoài giờ 1", short: "Điều dưỡng 1", group: "Ngoài giờ", floor: "Tầng 1", phong: "Thủ thuật ngoài giờ", nhom: "DIEU_DUONG" },
  { key: "T1_TTNG_DD2", label: "Điều dưỡng ngoài giờ 2", short: "Điều dưỡng 2", group: "Ngoài giờ", floor: "Tầng 1", phong: "Thủ thuật ngoài giờ", nhom: "DIEU_DUONG" },

  { key: "T2_XEPTHUOC", label: "Xếp thuốc + Giải thích thuốc", short: "Xếp thuốc + Giải thích thuốc", group: "Tầng 2", floor: "Tầng 2", phong: "Quầy thuốc", nhom: "DIEU_DUONG" },
  { key: "T2_TAODON", label: "Tạo đơn thuốc + Thu ngân", short: "Tạo đơn thuốc + Thu ngân", group: "Tầng 2", floor: "Tầng 2", phong: "Quầy thuốc", nhom: "DIEU_DUONG" },

  { key: "T4_SANCHAU_BS", label: "BS Sàn chậu", short: "BS Sàn chậu", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng Sàn chậu", nhom: "BAC_SI" },
  { key: "T4_SANCHAU_BSTT", label: "BS Thủ thuật (soi âm hộ/âm vật/CTC, nong/tách)", short: "BS Thủ thuật (soi âm hộ/âm vật/CTC, nong/tách bao quy đầu âm vật)", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng Sàn chậu", nhom: "BAC_SI" },
  { key: "T4_SANCHAU_DD", label: "Điều dưỡng Sàn chậu (phụ khám, ghế Starformer, thủ thuật)", short: "Điều dưỡng Sàn chậu (Phụ khám Sàn chậu, Ghế Starformer, Thủ thuật)", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng Sàn chậu", nhom: "DIEU_DUONG" },

  { key: "T4_SAN_BS", label: "BS Sản", short: "BS Sản", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng Sản - Biofeedback", nhom: "BAC_SI" },
  { key: "T4_SAN_DD", label: "Điều dưỡng Sản", short: "Điều dưỡng Sản", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng Sản - Biofeedback", nhom: "DIEU_DUONG" },
  { key: "T4_BIO_DD", label: "Điều dưỡng Bio", short: "Điều dưỡng Bio", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng Sản - Biofeedback", nhom: "DIEU_DUONG" },

  { key: "T4_SA_BS1", label: "BS siêu âm 1", short: "BS 1", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng siêu âm", nhom: "BAC_SI" },
  { key: "T4_SA_DD1", label: "Điều dưỡng siêu âm 1", short: "Điều dưỡng 1", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng siêu âm", nhom: "DIEU_DUONG" },
  { key: "T4_SA_BS2", label: "BS siêu âm 2", short: "BS 2", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng siêu âm", nhom: "BAC_SI" },
  { key: "T4_SA_DD2", label: "Điều dưỡng siêu âm 2", short: "Điều dưỡng 2", group: "Tầng 4", floor: "Tầng 4", phong: "Phòng siêu âm", nhom: "DIEU_DUONG" },

  // Sheet3 đòi MỌI loại buổi khám đều có: "Trưởng ca · Điều phối · 0-1 người".
  { key: "DIEU_PHOI", label: "Trưởng ca (điều phối)", short: "Trưởng ca", group: "Điều phối", floor: "Điều phối", phong: "—", nhom: "DIEU_DUONG" },
];

/** Vị trí gom theo TẦNG rồi PHÒNG — đúng ba cột đầu của file Excel. */
export interface NhomPhong {
  phong: string;
  stations: Station[];
}
export interface FloorSegment {
  floor: string;
  phongs: NhomPhong[];
  /** Tổng số vị trí trong tầng — dùng cho rowSpan của ô "Tầng". */
  soViTri: number;
}
// CHỈ các tầng CÓ TRONG EXCEL. "Lịch khám" (bác sĩ nhận lịch) và "Trưởng ca
// (điều phối)" vẫn là vị trí trong hệ thống — thanh bên và đặt lịch dùng chúng —
// nhưng file Excel không có hai dòng ấy, và bảng phải y hệt file.
export const TANG_EXCEL = new Set(["Tầng 1", "Tầng 2", "Tầng 4"]);
export const STATION_SEGMENTS: FloorSegment[] = STATIONS.filter((s) =>
  TANG_EXCEL.has(s.floor),
).reduce<FloorSegment[]>((segs, s) => {
  let tang = segs[segs.length - 1];
  if (!tang || tang.floor !== s.floor) {
    tang = { floor: s.floor, phongs: [], soViTri: 0 };
    segs.push(tang);
  }
  const cuoi = tang.phongs[tang.phongs.length - 1];
  if (cuoi && cuoi.phong === s.phong) cuoi.stations.push(s);
  else tang.phongs.push({ phong: s.phong, stations: [s] });
  tang.soViTri += 1;
  return segs;
}, []);

/** Màu nền theo PHÒNG — đúng mã màu cột "Phòng" của file Excel (xem token
 *  `--color-lich-*` trong globals.css). Phòng không có ở đây thì nền trắng, như
 *  Quầy thuốc và Phòng Sản - Biofeedback trong Excel. */
export const MAU_PHONG: Record<string, string> = {
  "Quầy tiếp đón": "bg-lich-tiep-don",
  "Phòng Nội tiết": "bg-lich-noi-tiet",
  "Phòng thủ thuật": "bg-lich-thu-thuat",
  "Phòng Siêu âm": "bg-lich-sieu-am",
  "Thủ thuật ngoài giờ": "bg-lich-ngoai-gio",
  "Phòng Sàn chậu": "bg-lich-san-chau",
  "Phòng siêu âm": "bg-lich-sieu-am",
};

// Màu nhấn theo TẦNG. Khoá phải là chuỗi `floor` THẬT ở trên — bản trước viết
// tắt nên hai tầng không bao giờ khớp và rơi về màu mặc định: một bảng màu
// hỏng một nửa mà không có lỗi nào để thấy.
export const FLOOR_BORDER: Record<string, string> = {
  "Tầng 1": "border-t-specialty-service",
  "Tầng 2": "border-t-success",
  "Tầng 4": "border-t-warning",
  "Điều phối": "border-t-brand-600",
};

export const STATION_LABEL: Record<string, string> = Object.fromEntries(
  STATIONS.map((s) => [s.key, s.label]),
);




// ===== HAI HÀNG CON MỖI NGÀY =====
//
// File Excel "BẢNG LÀM VIỆC" (sheet LLV) dành HAI dòng cho mỗi ngày, và hai
// dòng ấy KHÔNG phải ca sáng / ca chiều — mỗi dòng là MỘT NGƯỜI.
//
//   Quang, 09/08/2026: *"có nghĩa là ngày hôm ấy có 2 bác sĩ trực, giờ sáng hay
//   chiều thì chi tiết trong trang nhỏ hiện ra lúc ấn vào dấu cộng"*.
//
// Đoán nhầm chỗ này là dựng cả cái bảng cho một mô hình sai: nếu hai hàng là
// hai CA thì một bác sĩ trực cả ngày phải nằm ở cả hai hàng, và cột "số bác sĩ
// trực" luôn đếm gấp đôi.

// ── CỘT CỦA BẢNG: NGÀY × CA ────────────────────────────────────────────────
//
// Kim Ngưu chạy BUỔI TỐI trong tuần, cả ngày cuối tuần — đọc ra từ chính hai
// tuần lịch thật: T2→T6 chỉ có ô ở cột "Tối"; T7 và CN có Sáng · Chiều · Tối.
// Mười một cột, đúng bằng file Excel.
//
// KHÔNG VIẾT CỨNG HẲN. Đây là nếp thường, không phải luật: hôm nào phòng khám
// mở thêm ca sáng giữa tuần thì cột ấy phải hiện ra, chứ không được nuốt mất
// người đã xếp. Nên cột = (nếp thường) ∪ (mọi ca THẬT SỰ có dòng trong tuần).
const CA_THEO_THU: Record<number, Shift[]> = {
  0: ["SANG", "CHIEU", "TOI"], // Chủ nhật
  1: ["TOI"],
  2: ["TOI"],
  3: ["TOI"],
  4: ["TOI"],
  5: ["TOI"],
  6: ["SANG", "CHIEU", "TOI"], // Thứ Bảy
};

export interface CotLich {
  date: string;
  shift: Shift;
  /** Cột đầu tiên của ngày — dùng để kẻ vạch ngăn ngày. */
  dauNgay: boolean;
  /** Số cột của ngày này, đặt ở cột đầu để gộp ô tiêu đề ngày. */
  soCotNgay: number;
}

/** Cột của một tuần: nếp thường, cộng mọi ca thật sự đã có người. */
export function cotCuaTuan(
  weekStart: string,
  rows: { work_date: string; shift?: string | null }[] = [],
): CotLich[] {
  const theoNgay = new Map<string, Set<Shift>>();
  for (const d of weekDates(weekStart)) {
    const thu = new Date(`${d}T00:00:00Z`).getUTCDay();
    theoNgay.set(d, new Set(CA_THEO_THU[thu] ?? ["TOI"]));
  }
  for (const r of rows) {
    const co = theoNgay.get(r.work_date);
    // `FULL` vẫn được xếp ở nơi khác; hiện nó thành một cột riêng thay vì
    // giấu đi — giấu là để một người đã xếp biến mất khỏi bảng.
    if (co && r.shift && SHIFTS.includes(r.shift as Shift)) co.add(r.shift as Shift);
  }
  const ra: CotLich[] = [];
  for (const d of weekDates(weekStart)) {
    const cas = SHIFTS.filter((c) => theoNgay.get(d)?.has(c));
    cas.forEach((c, i) =>
      ra.push({ date: d, shift: c, dauNgay: i === 0, soCotNgay: cas.length }),
    );
  }
  return ra;
}

/** Chia phân công của một ô thành ĐÚNG hai hàng con: người đầu ở hàng trên,
 *  phần còn lại dồn xuống hàng dưới.
 *
 *  Dồn chứ không cắt bớt — Excel cũng viết "Thư/Hà Vũ" chung một ô khi ngày đó
 *  có ba người. Cắt mất người thứ ba nghĩa là bảng nói dối về ai đang trực. */
export function chiaHaiHang<T>(list: T[]): [T[], T[]] {
  return list.length <= 1 ? [list, []] : [[list[0]], list.slice(1)];
}

/** Số bác sĩ trực của một ngày = số NGƯỜI khác nhau ở trạm Lịch khám.
 *
 *  Đếm theo người, không theo dòng: một bác sĩ trực cả sáng lẫn chiều là HAI
 *  dòng `work_roster` nhưng vẫn là MỘT bác sĩ. Cột này trong Excel do quản lý
 *  gõ tay; ở đây nó được TÍNH RA, nên không thể lệch với các ô bên cạnh. */
export function demBacSiTruc(
  rows: {
    work_date: string;
    station: string;
    shift?: string | null;
    staff_id?: string | null;
    staff_name?: string | null;
  }[],
  date: string,
  /** Bỏ trống = đếm cả ngày. Có ca = chỉ đếm người trực ca ấy (hoặc cả ngày). */
  shift?: Shift,
): number {
  const nguoi = new Set<string>();
  for (const r of rows) {
    if (r.work_date !== date || r.station !== "LICH_KHAM") continue;
    // `FULL` luôn được tính: người trực cả ngày thì có mặt ở mọi ca.
    if (shift && r.shift && r.shift !== "FULL" && r.shift !== shift) continue;
    const khoa = r.staff_id ?? r.staff_name;
    if (khoa) nguoi.add(khoa);
  }
  return nguoi.size;
}

// BA CA, không phải hai (Tuyền 21/08/2026). Thứ tự CÓ Ý NGHĨA: sớm trước,
// muộn sau — thanh chọn ca in theo đúng thứ tự này, và "Cả ngày" đứng đầu vì
// nó là lựa chọn hay dùng nhất của quản lý.
//
// Giờ của từng ca KHÔNG nằm ở đây: nó là cấu hình của phòng khám
// (`clinic.settings->ca_lam_viec`, xem `core/shifts.py`). Frontend chỉ biết
// TÊN ca — viết giờ vào đây là dựng bản thứ hai của một sự thật, và bản
// TypeScript chép lại luật xếp hàng đã từng lệch đúng như vậy rồi bị xoá.
export type Shift = "FULL" | "SANG" | "CHIEU" | "TOI";
export const SHIFTS: Shift[] = ["FULL", "SANG", "CHIEU", "TOI"];
export const SHIFT_LABEL: Record<Shift, string> = {
  FULL: "Cả ngày",
  SANG: "Sáng",
  CHIEU: "Chiều",
  TOI: "Tối",
};

const WEEKDAY = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

/** "Thứ 2".."Thứ 7" / "Chủ nhật" cho 1 ngày yyyy-mm-dd (tính UTC, roster là DATE). */
export function dayLabel(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00Z");
  const w = d.getUTCDay();
  return w === 0 ? "Chủ nhật" : `Thứ ${w + 1}`;
}

/** Nhãn ngắn T2..CN. */
export function dayShort(dateStr: string): string {
  return WEEKDAY[new Date(dateStr + "T00:00:00Z").getUTCDay()] ?? "";
}

/** dd/mm cho 1 ngày yyyy-mm-dd. */
export function fmtDayMonth(dateStr: string): string {
  const [, m, d] = dateStr.split("-");
  return `${d}/${m}`;
}

function toISO(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Thứ 2 của tuần chứa `d`. Chỉ dùng nội bộ, với Date đã chắc chắn hợp lệ. */
function mondayOfUtc(d: Date): string {
  const dow = d.getUTCDay(); // 0=CN
  const diff = dow === 0 ? -6 : 1 - dow; // về thứ 2
  const monday = new Date(d);
  monday.setUTCDate(d.getUTCDate() + diff);
  return toISO(monday);
}

/**
 * Thứ 2 của tuần chứa `dateStr` (yyyy-mm-dd). `null` = `dateStr` không đọc được.
 *
 * TRẢ `null` CHỨ KHÔNG NÉM, VÌ CHUỖI NÀY ĐẾN TỪ THANH ĐỊA CHỈ. `/home?weekAppt=…`
 * và `/schedule?week=…` lấy thẳng tham số URL rồi đưa vào đây. Bản cũ dựng
 * `new Date("abcT00:00:00Z")` thành Invalid Date, đi tiếp bình thường, rồi
 * `toISO()` gọi `toISOString()` — và CHÍNH `toISOString()` là thứ ném
 * `RangeError: Invalid time value`. Server component ném thì cả TRANG CHỦ rơi
 * vào error.tsx: một link hỏng hay một lần sửa tay trên thanh địa chỉ là màn
 * hình đầu ngày của mọi nhân viên không mở được.
 *
 * ĐÂY LÀ CON THỨ BA CÙNG MỘT HỌ. Hai lần trước (`/api/roster?date=99-99-9999`,
 * và `/api/appointments` thiếu `date`) đều được vá TẠI CHỖ NÓ NỔ, nên bản dùng
 * chung trong lib này sống sót qua cả hai lần — và nó phục vụ trang chủ. Luật
 * rút ra: hàm nhận ngày từ người dùng phải trả giá trị rỗng thay vì ném, và chỗ
 * kiểm phải nằm ở BIÊN (nơi chuỗi đi vào), không rải rác ở từng nơi gọi.
 *
 * `mondayOfUtc` bên dưới vẫn ném nếu bị đưa Date hỏng — cố ý: tới đó thì đó là
 * lỗi lập trình, không phải dữ liệu người dùng, và im lặng trả sai còn tệ hơn.
 */
export function weekStartOf(dateStr: string): string | null {
  const d = new Date(dateStr + "T00:00:00Z");
  if (Number.isNaN(d.getTime())) return null;
  return mondayOfUtc(d);
}

/** 7 ngày của tuần bắt đầu từ `weekStart` (T2..CN). */
export function weekDates(weekStart: string): string[] {
  const base = new Date(weekStart + "T00:00:00Z");
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(base);
    d.setUTCDate(base.getUTCDate() + i);
    return toISO(d);
  });
}

/** Tuần kế trước/sau (±7 ngày). */
export function shiftWeek(weekStart: string, weeks: number): string {
  const d = new Date(weekStart + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + weeks * 7);
  return toISO(d);
}

/** Thứ 2 của tuần hiện tại theo giờ VN (server chạy UTC). */
export function currentWeekStartVn(): string {
  const nowVn = new Date(Date.now() + 7 * 60 * 60 * 1000);
  // Đi thẳng vào `mondayOfUtc`: ngày này do chính hàm dựng nên luôn hợp lệ, nên
  // không phải xử lý một `null` không bao giờ xảy ra ở mọi nơi gọi.
  return mondayOfUtc(nowVn);
}

/** Hôm nay (yyyy-mm-dd) theo giờ VN. */
export function todayVn(): string {
  return new Date(Date.now() + 7 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

// ===== GIỜ MỞ CỬA PHÒNG KHÁM =====
//
// CẤU HÌNH, KHÔNG PHẢI HẰNG SỐ. File này từng trả cứng T2–T6 17:00–23:00 và
// cuối tuần 08:00–23:00, còn BookingHub trả 22:00 cho giờ đóng cửa. Hai nguồn,
// hai con số: bác sĩ đăng ký được ca 22:00–23:00 mà CSKH không đặt lịch vào
// được, và không có lỗi nào chỉ ra điều đó.
//
// Giờ cả hai đọc `clinic.settings.hours` (migration 20260803000011), truyền
// vào qua BookingPolicy. `hours` là bắt buộc — không có tham số mặc định, vì
// một mặc định ở đây chính là cách hai con số cũ sống sót lâu như vậy.
export type { ClinicHours } from "./booking-policy";
import type { ClinicHours } from "./booking-policy";

/** Giờ mở cửa của một ngày; `null` = phòng khám đóng cửa hôm đó. */
export function clinicHoursForDate(
  isoDate: string,
  hours: Record<string, ClinicHours>,
): ClinicHours | null {
  const dow = new Date(isoDate + "T00:00:00Z").getUTCDay(); // 0=CN, 6=T7
  const today = hours[String(dow)];
  if (!today || today.open === today.close) return null;
  return today;
}

/**
 * Kiểm giờ hẹn có nằm trong giờ mở cửa của NGÀY đó không. null = hợp lệ.
 * So sánh chuỗi "HH:MM" (cùng độ dài) là đủ. Giờ bắt đầu phải < giờ đóng cửa.
 */
export function clinicHoursError(
  isoDate: string,
  time: string,
  hours: Record<string, ClinicHours>,
): string | null {
  if (!isoDate || !time) return null;
  const today = clinicHoursForDate(isoDate, hours);
  if (!today) return "Phòng khám không làm việc ngày này.";
  if (time < today.open || time >= today.close) {
    // Câu cũ phân biệt "cuối tuần" với "T2–T6" — đúng với lịch Dr4Women và sai
    // với bất kỳ phòng khám nào chia lịch khác. Nói thẳng giờ của ĐÚNG ngày đó.
    return `Ngày này phòng khám nhận khám ${today.open}–${today.close}. Hãy chọn giờ trong khoảng này.`;
  }
  return null;
}

// ===== TRẠM HỢP LỆ THEO VAI TRÒ — ĐÃ CHUYỂN VÀO DATABASE =====
//
// `stationsForRole` và `defaultStationForRole` từng ở đây. Cả hai đã bỏ
// (20260809000002), vì hai lý do:
//
// 1. LUẬT CỦA CHÚNG SAI SO VỚI ĐỜI THẬT. `stationsForRole` nói: bác sĩ → đúng
//    một trạm, MỌI VAI CÒN LẠI → mười một trạm còn lại. Gọn tới mức không chặn
//    được gì: lễ tân chọn được "Máy trong E10 + VLTL/thủ thuật". Còn chiều
//    ngược lại thì quá chặt — lễ tân Dr4Women đi LẤY MÁU 234 ca trong lịch
//    thật, thứ mà `defaultStationForRole` không hề biết.
//
// 2. LỌC Ở TRÌNH DUYỆT KHÔNG PHẢI LÀ CHẶN. Một lời gọi API tự chế không đi qua
//    hàm này. Backend mới là nơi từ chối (`RosterService._kiem_pham_vi_tram`).
//
// Nay hỏi `GET /api/roster?staff_id=…`, trả lời lấy từ bảng
// `vai_duoc_vao_tram` — cùng bảng mà backend dùng để từ chối, nên giao diện
// không thể mời một vị trí rồi lưu mới báo lỗi. Ma trận gieo từ chính lịch trực
// của phòng khám và quản lý sửa được.
