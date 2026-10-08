// Lịch làm việc (weekly roster) — cấu hình phòng/trạm + helper ngày/tuần.
// Danh mục vị trí đọc từ database (`vi_tri_lam_viec`, CORE-C4 23/09/2026) —
// không chỉnh ở đây; quản lý đổi cách phân công trong database.


// Cookie lưu "tôi là ai" cho vai trò không phải bác sĩ (lọc lịch cá nhân).
export const ROSTER_STAFF_COOKIE = "roster_staff_id";

export interface Station {
  key: string;
  /** Tên đầy đủ (`vi_tri_lam_viec.ten`) — tooltip / ô chọn. */
  label: string;
  /** Nhãn in ở đầu hàng bảng lịch (`ten_ngan`, trống thì = tên). */
  short: string;
  /** Phòng — cột "Phòng" của bảng lịch. Máy chủ trả TÊN PHÒNG HIỆN TẠI
   *  (`clinic_room.name` theo `room_id`, rơi về chữ cũ `vi_tri_lam_viec.phong`),
   *  nên quản lý đổi tên phòng ở Cấu hình phòng khám là lịch đổi theo. Rỗng =
   *  vị trí không gắn phòng (Trưởng ca) — vẫn có hàng. */
  phong: string;
  /** Mã phòng (`clinic_room.code`) — khoá màu nền. Rỗng = không gắn phòng. */
  maPhong: string;
  /** Tầng — cột "Tầng" của bảng lịch. Máy chủ trả TẦNG CỦA PHÒNG THẬT
   *  (`clinic_room.floor` theo `room_id`, rơi về chữ `vi_tri_lam_viec.tang`).
   *  Rỗng = không khai tầng (Trưởng ca) — vẫn có hàng. */
  tang: string;
  /** Ai đứng được chỗ này. Khớp `vi_tri_lam_viec.nhom_nghe` trong database. */
  /** CHUNG = bác sĩ hay điều dưỡng đều đứng được (xem migration 20260916000012). */
  nhom: "BAC_SI" | "DIEU_DUONG" | "DOI_TAC" | "CHUNG";
}

// ── DANH MỤC VỊ TRÍ ĐỌC TỪ DATABASE (CORE-C4, 23/09/2026) ───────────────────
//
// Trước hôm nay 34 vị trí của PK Kim Ngưu viết cứng ở đây, trong khi database
// đã có `vi_tri_lam_viec` từ 16/09 — hai nguồn cho một danh mục, và quản lý
// thêm/đổi một vị trí thì bảng lịch không biết. Nay máy chủ trả danh mục trong
// `GET /me/vi-tri-hom-nay` → `danh_muc` (xếp theo `sort` = thứ tự dòng trong
// Excel), và trang truyền xuống bảng. Nhãn hàng ngắn kiểu Excel ("BS", "Thư
// ký") nằm ở cột `ten_ngan` (migration 20260923000019).
//
// CỘT TẦNG TRỞ LẠI (01/10/2026). 27/09 phòng khám bỏ tầng vì "bố cục phòng thay
// đổi liên tục"; bảng lịch tuần 28/09 Tuyền gửi lại có cột Tầng → Phòng → Vị trí.
// Lần này tầng KHÔNG đọc chữ `vi_tri_lam_viec.tang` (chữ tự do, không màn nào
// sửa) mà đọc tầng của PHÒNG THẬT — đổi tầng ở Cấu trúc phòng khám là bảng lịch
// đổi theo, cùng luật với tên phòng.

/** Một dòng danh mục như máy chủ trả. */
export interface ViTriDb {
  code: string;
  ten: string;
  ten_ngan: string;
  /** Tầng của phòng thật (máy chủ đã rơi về chữ cũ khi không gắn phòng). */
  tang?: string;
  phong: string;
  /** Mã phòng gắn với vị trí (`clinic_room.code`); rỗng = không gắn phòng. */
  ma_phong?: string;
  nhom: string;
}

const NHOM_HOP_LE = new Set(["BAC_SI", "DIEU_DUONG", "DOI_TAC", "CHUNG"]);

/** Danh mục máy chủ trả → vị trí cho bảng lịch. Giữ nguyên thứ tự. */
export function viTriTuDb(ds: readonly ViTriDb[] | null | undefined): Station[] {
  return (ds ?? []).map((v) => ({
    key: v.code,
    label: v.ten,
    short: v.ten_ngan || v.ten,
    phong: v.phong ?? "",
    maPhong: v.ma_phong ?? "",
    tang: v.tang ?? "",
    nhom: (NHOM_HOP_LE.has(v.nhom) ? v.nhom : "DIEU_DUONG") as Station["nhom"],
  }));
}

/** CỘT "LỊCH KHÁM" — KHÔNG phải vị trí. "Bác sĩ nào trực hôm ấy" để lưới đặt
 *  lịch (`week_appointments_service`) biết nhận lịch cho ai; không có trong
 *  Excel và không nằm trong `vi_tri_lam_viec`. Gộp nó vào danh mục vị trí là
 *  hỏng đặt lịch — nên nó là hằng số riêng ở đây. */
export const VI_TRI_LICH_KHAM: Station = {
  key: "LICH_KHAM",
  label: "Lịch khám (bác sĩ trực)",
  short: "Lịch khám",
  phong: "",
  maPhong: "",
  tang: "",
  nhom: "BAC_SI",
};

/** Vị trí LIỀN NHAU cùng phòng gom thành một nhóm — cột "Phòng" gộp ô. */
export interface NhomPhong {
  phong: string;
  maPhong: string;
  stations: Station[];
}

/** Gom vị trí theo PHÒNG, giữ nguyên thứ tự danh mục.
 *
 *  KHÔNG LỌC GÌ. Bản 23/09 (`phanTang` cũ) gom theo tầng và BỎ mọi vị trí không
 *  khai tầng — Trưởng ca (điều phối) và mọi vị trí quản lý thêm ở màn Dây nối
 *  (mã `VT-…`, không có ô tầng) biến khỏi bảng lịch mà không ai biết. Danh mục
 *  máy chủ trả đã lọc `is_active`; ở đây vị trí nào có trong danh mục là có hàng.
 *
 *  Chỉ gộp hai vị trí LIỀN NHAU cùng phòng: cùng tên mà nằm cách nhau thì là hai
 *  nhóm (thứ tự dòng do quản lý đặt, không tự xáo lại). */
export function phanPhong(stations: readonly Station[]): NhomPhong[] {
  const ra: NhomPhong[] = [];
  for (const s of stations) {
    const cuoi = ra[ra.length - 1];
    const khoa = s.maPhong || s.phong;
    if (cuoi && (cuoi.maPhong || cuoi.phong) === khoa) cuoi.stations.push(s);
    else ra.push({ phong: s.phong, maPhong: s.maPhong, stations: [s] });
  }
  return ra;
}

/** Vị trí LIỀN NHAU cùng tầng → một nhóm — cột "Tầng" gộp ô, bên trong gom
 *  theo phòng như `phanPhong`. */
export interface NhomTang {
  tang: string;
  phongs: NhomPhong[];
  /** Tổng số hàng (vị trí) của tầng — rowSpan ô Tầng. */
  soViTri: number;
}

/** Gom vị trí theo TẦNG rồi theo PHÒNG, giữ nguyên thứ tự danh mục (01/10/2026).
 *
 *  Cùng luật `phanPhong`: KHÔNG LỌC (vị trí không tầng — Trưởng ca — vẫn có
 *  hàng, ô Tầng để "—"), chỉ gộp hàng LIỀN NHAU. Một nhóm phòng không bao giờ
 *  vắt qua hai tầng: tách tầng trước, gom phòng trong từng tầng sau. */
export function phanTang(stations: readonly Station[]): NhomTang[] {
  const khoi: Station[][] = [];
  for (const s of stations) {
    const cuoi = khoi[khoi.length - 1];
    if (cuoi && cuoi[0].tang === s.tang) cuoi.push(s);
    else khoi.push([s]);
  }
  return khoi.map((ds) => ({
    tang: ds[0].tang,
    phongs: phanPhong(ds),
    soViTri: ds.length,
  }));
}

/** Màu nền theo PHÒNG — đúng mã màu cột "Phòng" của file Excel (xem token
 *  `--color-lich-*` trong globals.css). Phòng không có ở đây thì nền trắng, như
 *  Quầy thuốc và Phòng Sản / Siêu âm trong Excel.
 *
 *  KHOÁ THEO MÃ PHÒNG (`clinic_room.code`), KHÔNG THEO TÊN (27/09/2026 đợt 3).
 *  Bản trước khoá "Phòng thủ thuật" — quản lý đổi tên thành "Thủ thuật/Sàn
 *  chậu" ở Cấu hình phòng khám là ô mất màu, không lỗi nào báo. Mã phòng không
 *  đổi khi đổi tên. Đo chỉ số và Lấy mẫu là phòng riêng nhưng trong Excel nằm
 *  dưới "Quầy tiếp đón", nên mang cùng màu. */
export const MAU_PHONG: Record<string, string> = {
  "KN-TIEPDON": "bg-lich-tiep-don",
  "KN-DOCHISO": "bg-lich-tiep-don",
  "KN-LAYMAU": "bg-lich-tiep-don",
  "KN-NOITIET": "bg-lich-noi-tiet",
  "KN-THUTHUAT": "bg-lich-thu-thuat",
  // KN-SA-T1 đã gộp vào KN-SA1 "Phòng siêu âm 2 máy" (01/10/2026) — giữ màu
  // cho lịch tuần cũ còn trỏ phòng ấy.
  "KN-SA-T1": "bg-lich-sieu-am",
  "KN-SA1": "bg-lich-sieu-am",
  "KN-SA2": "bg-lich-sieu-am",
  "KN-TTNG": "bg-lich-ngoai-gio",
  "KN-SANCHAU": "bg-lich-san-chau",
};

/** Nền ô theo mã phòng; phòng không có màu riêng → nền thẻ. */
export function mauPhong(maPhong: string | null | undefined): string {
  if (!maPhong) return "bg-surface";
  if (Object.hasOwn(MAU_PHONG, maPhong)) return MAU_PHONG[maPhong];
  // Phòng cơ sở khác (`HN-SA1`, bản sơ đồ `HN-SA1-B`) tô như phòng mẫu Kim Ngưu.
  const mau = `KN-${maPhong.replace(/^[A-Z0-9]+-/, "").replace(/-B$/, "")}`;
  return Object.hasOwn(MAU_PHONG, mau) ? MAU_PHONG[mau] : "bg-surface";
}

/** Tên vị trí ĐỦ NGHĨA khi đứng một mình (ngoài lưới lịch): "Phòng · Vị trí".
 *
 *  Tên theo bảng lịch Tuyền gửi (01/10/2026) là nhãn của một HÀNG trong một
 *  PHÒNG — "BS", "Điều dưỡng 1", "Thư ký" lặp ở nhiều phòng. Trong lưới lịch
 *  cột Phòng đứng cạnh nên đủ; ở chỗ in tên vị trí một mình (góc nhìn Theo
 *  người, ô chọn đổi người, tiêu đề ô xếp ca, bảng phạm vi vị trí) phải kèm
 *  phòng, không thì "BS · Tối" không biết phòng nào. Tên đã chứa tên phòng thì
 *  không lặp. */
export function nhanDayDu(s: Pick<Station, "label" | "phong">): string {
  if (!s.phong || s.label.includes(s.phong)) return s.label;
  return `${s.phong} · ${s.label}`;
}

/** Tên đủ nghĩa theo mã vị trí (kèm cột Lịch khám) — xem `nhanDayDu`. */
export function nhanViTri(stations: readonly Station[]): Record<string, string> {
  return Object.fromEntries(
    [VI_TRI_LICH_KHAM, ...stations].map((s) => [s.key, nhanDayDu(s)]),
  );
}

// ── GỘP DỌC Ô LỊCH ─────────────────────────────────────────────────────────

export type TrangThaiO = "DONG" | "NGHI" | null;

export interface ThongTinO {
  /** Ô đen / khối nghỉ / bình thường. */
  dong: TrangThaiO;
  /** Khoá so sánh để gộp dọc: cùng khoá (khác rỗng) = cùng người. */
  khoa: string;
}

/** rowSpan từng ô: `o[hàng][cột]` → `span[hàng][cột]` (0 = ô đã gộp vào ô trên).
 *
 *  Hai luật, cả hai chỉ gộp các hàng LIỀN NHAU trong cùng một cột:
 *  * ô mở cùng người (khoá khác rỗng, bằng nhau) → một ô — "Lễ tân + Thu ngân"
 *    của file Excel;
 *  * ô NGHỈ nối nhau → một khối NGHỈ.
 *
 *  Bản trước gộp trong từng TẦNG, và khối NGHỈ chỉ khi CẢ tầng nghỉ. Bỏ tầng
 *  (27/09/2026 đợt 3) thì đoạn liền nhau là đơn vị: phòng nào nghỉ, các hàng
 *  liền nhau của nó thành một khối, không cần biết nó ở tầng nào. Ô đen (DONG)
 *  không gộp — mỗi ô một ý "vị trí này không làm ca ấy". */
export function tinhGopDoc(o: readonly (readonly ThongTinO[])[]): number[][] {
  const span = o.map((hang) => hang.map(() => 1));
  const soCot = o[0]?.length ?? 0;
  for (let ci = 0; ci < soCot; ci++) {
    let dau = 0;
    for (let i = 1; i < o.length; i++) {
      const tren = o[dau][ci];
      const duoi = o[i][ci];
      const cungNguoi =
        tren.dong === null &&
        duoi.dong === null &&
        tren.khoa !== "" &&
        tren.khoa === duoi.khoa;
      const cungNghi = tren.dong === "NGHI" && duoi.dong === "NGHI";
      if (cungNguoi || cungNghi) {
        span[dau][ci] += 1;
        span[i][ci] = 0;
      } else {
        dau = i;
      }
    }
  }
  return span;
}

// ── GÓC NHÌN "THEO NGƯỜI" (27/09/2026 đợt 3, A9) ────────────────────────────
//
// Phòng khám: *"Cần lịch trực + tên nhân sự kèm vai trò của mỗi người"*. Bảng
// theo vị trí trả lời "chỗ này ai đứng"; nhân viên hỏi câu ngược lại — "tuần
// này tôi (và cô A) đứng đâu" — và phải dò cả bảng 30 hàng × 11 cột.

/** Một dòng lịch như máy chủ trả (đã đồng bộ tên). */
export interface DongLichNguoi {
  work_date: string;
  station: string;
  shift: string;
  staff_id?: string | null;
  staff_name: string | null;
  /** Vai đầy đủ do máy chủ trả (`clinic_membership.role` → nhãn). */
  vai?: string | null;
}

export interface ViecTrongNgay {
  viTri: string;
  ca: string;
}

export interface NguoiTrongTuan {
  /** staff_id, hoặc tên khi dòng nhập tay không nối được ai. */
  khoa: string;
  ten: string;
  vai: string;
  /** ngày yyyy-mm-dd → các chỗ đứng trong ngày, ca sớm trước. */
  theoNgay: Record<string, ViecTrongNgay[]>;
}

const THU_TU_CA: Record<string, number> = { FULL: 0, SANG: 1, CHIEU: 2, TOI: 3 };

/** Gom lịch tuần theo NGƯỜI: mỗi người một dòng, mỗi ngày các chỗ đứng.
 *
 *  Dòng không có tên (ô chưa xếp) bỏ qua. Cùng một chỗ + ca lặp (hai dòng
 *  `work_roster` trùng) chỉ in một lần. Xếp theo tên (tiếng Việt). */
export function gomTheoNguoi(
  rows: readonly DongLichNguoi[],
  nhanViTriTheoMa: Readonly<Record<string, string>>,
): NguoiTrongTuan[] {
  const theoKhoa = new Map<string, NguoiTrongTuan>();
  for (const r of rows) {
    const ten = (r.staff_name ?? "").trim();
    if (!ten) continue;
    const khoa = r.staff_id || `ten:${ten}`;
    let n = theoKhoa.get(khoa);
    if (!n) {
      n = { khoa, ten, vai: r.vai ?? "", theoNgay: {} };
      theoKhoa.set(khoa, n);
    } else if (!n.vai && r.vai) {
      n.vai = r.vai;
    }
    const viTri = Object.hasOwn(nhanViTriTheoMa, r.station)
      ? nhanViTriTheoMa[r.station]
      : r.station;
    const ca = SHIFTS.includes(r.shift as Shift) ? SHIFT_LABEL[r.shift as Shift] : r.shift;
    const ngay = (n.theoNgay[r.work_date] ??= []);
    if (!ngay.some((v) => v.viTri === viTri && v.ca === ca)) {
      ngay.push({ viTri, ca });
    }
  }
  const ra = [...theoKhoa.values()];
  for (const n of ra) {
    for (const ds of Object.values(n.theoNgay)) {
      ds.sort(
        (a, b) =>
          thuTuCaTheoNhan(a.ca) - thuTuCaTheoNhan(b.ca) ||
          a.viTri.localeCompare(b.viTri, "vi"),
      );
    }
  }
  return ra.sort((a, b) => a.ten.localeCompare(b.ten, "vi"));
}

function thuTuCaTheoNhan(nhan: string): number {
  const ma = SHIFTS.find((s) => SHIFT_LABEL[s] === nhan);
  return ma ? THU_TU_CA[ma] : 9;
}




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
