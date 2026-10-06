"use client";

// BookingHub — Hub Đặt lịch hẹn CSKH 3 cột hoàn chỉnh.
// Cột 1 (Trái - 280px): Khách hàng đang chọn (xếp trên) + Tìm kiếm khách hàng có sẵn (dài hơn) + Thông tin y tế & Lịch sử đặt hẹn.
// Cột 2 (Giữa - 1fr): Bảng lưới giờ chuẩn mockup (Cột đầu = Giờ, các ô KHÔNG ghi lại giờ, màu & trạng thái Có thể đặt / Còn 1 chỗ / Đã đầy / Đang giữ / Đang chọn ✓).
// Cột 3 (Phải - 320px): Panel Xác nhận thông tin đặt lịch (Sức chứa 1/3 đã đặt, Checklist, Đặt lịch hẹn).

import { useEffect, useState, useMemo, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Calendar as CalendarIcon,
  Clock,
  User,
  Users,
  CheckCircle2,
  X,
  Search,
  Phone,
  ChevronLeft,
  ChevronRight,
  UserPlus,
  MapPin,
  Pencil,
} from "lucide-react";
import {
  giuaTruaVn,
  slotRange,
  VN_OFFSET,
  VN_TZ,
  vnLocalToUtcISO,
} from "@/lib/datetime";
import { dayLabel } from "@/lib/roster";
import { useDoiCa } from "../dung-doi-ca";
import { useBookingPolicy } from "../BookingPolicyContext";
import LichSapToiCuaKhach, {
  type LichCu,
  type TrangThaiTra,
} from "./LichSapToiCuaKhach";
import BangBacSiTuan from "./BangBacSiTuan";
import { CHANNELS_CHON, KENH_GIOI_THIEU } from "../form-ui";
import { type ClinicRole } from "../../../lib/roles";
import { useCheckInDuoc } from "../QuyenContext";
import { useGiuCho } from "./dung-giu-cho";
import { type ThongTinKhung } from "./cho-trong";
import NewPatientForm, {
  type Option,
  type ProvinceOpt,
} from "../patients/new/NewPatientForm";
import { loiDocDuoc } from "../../../lib/loi-doc-duoc";

export interface PatientLite {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  phone_primary: string | null;
  /** Cột gộp MỌI số (chính + người nhà + số thêm) — chỉ để TÌM, không hiện. */
  sdt_tim_kiem?: string | null;
  date_of_birth: string | null;
  gender: string | null;
  address: string | null;
  location_id?: string | null;
}

export interface ApptLite {
  id: string;
  slot_start: string;
  status: string;
  doctor_id: string | null;
  service_type_id: string | null;
  clinic_patient_id: string | null;
}

interface Props {
  locations: Option[];
  /** Cơ sở của người đang đặt — mặc định cho form khách mới. */
  coSoMacDinhId?: string | null;
  services: Option[];
  doctors: Option[];
  provinces: ProvinceOpt[];
  patients: PatientLite[];
  appts: ApptLite[];
  /** Vai của người đang mở màn — quyết định kênh đặt nào hiện ra. */
  vai?: ClinicRole | null;
  /** Khách này đã khám mấy lần, và có đang trong chuỗi tái khám không.
   *  Khoá = clinic_patient_id. Thiếu khoá = chưa khám lần nào. */
  lanKham?: Record<string, { soLanKham: number; laTaiKham: boolean }>;
}

/** Nhãn "khám lần mấy". CÙNG LUẬT với `nhanLanKham` ở màn Quản lý khách hàng —
 *  hai màn nói khác nhau về cùng một khách thì tệ hơn là không nói gì.
 *
 *  "Tái khám" thắng con số: cả hai đều đúng, nhưng "tái khám" nói thêm được
 *  rằng lượt này nối tiếp lượt trước cùng một dịch vụ. Không hiện "lần 1" —
 *  khách nào cũng từng là lần 1. */
function nhanLanKham(
  o?: { soLanKham: number; laTaiKham: boolean },
): string | null {
  if (!o) return null;
  if (o.laTaiKham) return "tái khám";
  if (o.soLanKham >= 2) return `khám lần ${o.soLanKham}`;
  return null;
}

const DAY_NAMES = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

/** Phút trong ngày giờ VN của một mốc ms. */
function phutVn(ms: number): number {
  const [h, m] = new Date(ms)
    .toLocaleTimeString("en-GB", { timeZone: VN_TZ, hour: "2-digit", minute: "2-digit" })
    .split(":");
  return Number(h) * 60 + Number(m);
}

/** Ngày hôm nay theo giờ VN, dạng "YYYY-MM-DD".
 *
 *  KHÔNG dùng toISOString().slice(0,10): nó cho ngày UTC, nên từ 00:00 đến
 *  07:00 giờ VN nó trả về NGÀY HÔM QUA — đúng khung giờ ca đêm đang làm việc. */
function vnToday(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: VN_TZ });
}

/** Tuần (T2→CN) chứa `anchor`, lệch đi `offset` tuần.
 *
 *  TRƯỚC ĐÂY BẢY NGÀY NÀY LÀ HẰNG SỐ: 11/05–17/05/2026, viết cứng trong mã.
 *  Màn "Đặt lịch" vì thế luôn mở ra một tuần của tháng Năm và KHÔNG có cách nào
 *  chọn ngày khác — CSKH không đặt được lịch cho hôm nay từ chính màn đặt lịch.
 *  Nó không báo lỗi, chỉ hiện sai ngày, nên nhìn qua vẫn như đang chạy. */
function weekOf(anchorIso: string, offset: number): {
  dayName: string;
  dateStr: string;
  isoDate: string;
}[] {
  const anchor = giuaTruaVn(anchorIso);
  // getUTCDay trên mốc 12:00 VN vẫn ra đúng thứ trong ngày VN (12:00+07 = 05:00Z).
  const dow = anchor.getUTCDay(); // 0=CN
  const mondayShift = (dow + 6) % 7; // CN→6, T2→0
  const monday = new Date(anchor);
  monday.setUTCDate(monday.getUTCDate() - mondayShift + offset * 7);

  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setUTCDate(d.getUTCDate() + i);
    const iso = d.toLocaleDateString("en-CA", { timeZone: VN_TZ });
    const [, mm, dd] = iso.split("-");
    return {
      dayName: DAY_NAMES[(dow - mondayShift + i + 7) % 7] ?? "",
      dateStr: `${dd}/${mm}`,
      isoDate: iso,
    };
  });
}

/** Một ngày bất kỳ nằm cách tuần HÔM NAY bao nhiêu tuần.
 *
 * Lưới giờ chạy theo `weekOffset` (số tuần lệch so với tuần hiện tại), nên chọn
 * một ngày từ lịch tháng phải quy về con số ấy. Tính bằng mốc THỨ HAI của hai
 * tuần chứ không bằng hiệu số ngày chia bảy: 03/08 và 09/08 cách nhau 6 ngày
 * nhưng cùng một tuần, còn 09/08 (CN) và 10/08 (T2) cách nhau 1 ngày mà khác
 * tuần.
 */
function tuanLechSoVoiHomNay(isoDate: string): number {
  const thuHai = (iso: string): number => {
    const d = giuaTruaVn(iso);
    const dow = d.getUTCDay(); // 0=CN
    d.setUTCDate(d.getUTCDate() - ((dow + 6) % 7));
    return Math.floor(d.getTime() / 86_400_000);
  };
  return Math.round((thuHai(isoDate) - thuHai(vnToday())) / 7);
}

/** Lịch THÁNG để nhảy nhanh tới một ngày xa.
 *
 * Trước đây chỉ có mũi tên tuần trước / tuần sau. Đặt lịch cho khách vào tháng
 * sau nghĩa là bấm mũi tên bốn, năm lần và đếm nhẩm — mỗi lần bấm lại tải lại
 * lưới giờ.
 */
function LichThang({
  ngayChon,
  onChon,
}: {
  ngayChon: string;
  onChon: (iso: string) => void;
}) {
  const [thang, setThang] = useState(() => ngayChon.slice(0, 7));
  const [nam, thg] = thang.split("-").map(Number);

  const soNgay = new Date(Date.UTC(nam, thg, 0)).getUTCDate();
  // Ô trống đầu tháng để ngày 1 rơi đúng cột thứ của nó (tuần bắt đầu từ T2).
  const trong = (new Date(Date.UTC(nam, thg - 1, 1)).getUTCDay() + 6) % 7;

  const doiThang = (buoc: number) => {
    const d = new Date(Date.UTC(nam, thg - 1 + buoc, 1));
    setThang(
      `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`,
    );
  };

  return (
    <div className="w-64 rounded-2xl border border-line bg-surface p-3 shadow-lg">
      <div className="flex items-center justify-between">
        <button
          type="button"
          aria-label="Tháng trước"
          onClick={() => doiThang(-1)}
          className="rounded-lg p-1 text-ink-muted hover:bg-surface-muted hover:text-brand-600"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-sm font-semibold text-ink tabular-nums">
          Tháng {thg}/{nam}
        </span>
        <button
          type="button"
          aria-label="Tháng sau"
          onClick={() => doiThang(1)}
          className="rounded-lg p-1 text-ink-muted hover:bg-surface-muted hover:text-brand-600"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      <div className="mt-2 grid grid-cols-7 gap-0.5 text-center text-label text-ink-faint">
        {["T2", "T3", "T4", "T5", "T6", "T7", "CN"].map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>

      <div className="mt-1 grid grid-cols-7 gap-0.5">
        {Array.from({ length: trong }, (_, i) => (
          <span key={`trong-${i}`} />
        ))}
        {Array.from({ length: soNgay }, (_, i) => {
          const ngay = i + 1;
          const iso = `${thang}-${String(ngay).padStart(2, "0")}`;
          const dangChon = iso === ngayChon;
          const homNay = iso === vnToday();
          return (
            <button
              key={iso}
              type="button"
              onClick={() => onChon(iso)}
              className={`rounded-lg py-1 text-xs tabular-nums transition-colors ${
                dangChon
                  ? "bg-teal-600 font-bold text-white"
                  : homNay
                    ? "bg-teal-50 font-semibold text-teal-700"
                    : "text-ink hover:bg-surface-muted"
              }`}
            >
              {ngay}
            </button>
          );
        })}
      </div>
    </div>
  );
}





/** Một mốc trên thanh ba bước của việc đặt lịch. */
function MocDatLich({
  so,
  nhan,
  xong,
  dangLam,
  ghiChu,
}: {
  so: number;
  nhan: string;
  xong: boolean;
  dangLam: boolean;
  ghiChu?: string;
}) {
  const vien = xong
    ? "bg-emerald-600 text-white"
    : dangLam
      ? "bg-brand-600 text-white"
      : "bg-surface-sunken text-ink-muted";
  const chu = xong
    ? "font-semibold text-ink"
    : dangLam
      ? "font-bold text-brand-700"
      : "";
  return (
    <div className="flex items-center gap-2">
      <span
        className={`grid size-5 place-items-center rounded-full text-label font-bold ${vien}`}
      >
        {xong ? "✓" : so}
      </span>
      <span className={chu}>{nhan}</span>
      {ghiChu ? (
        <span className="text-label font-normal text-ink-faint">({ghiChu})</span>
      ) : null}
    </div>
  );
}

export default function BookingHub({
  locations,
  coSoMacDinhId = null,
  services,
  doctors,
  provinces,
  patients,
  appts,
  lanKham,
  vai = null,
}: Props) {
  const router = useRouter();
  // Kênh "Trực tiếp" (tự check-in) theo LEGO Tiếp đón — mở full lego 30/09/2026.
  const checkInDuoc = useCheckInDuoc(vai);
  const policy = useBookingPolicy();
  const PROVISIONAL_STEP_MIN = 15;
  const slotMinutes = policy?.slotMinutes ?? PROVISIONAL_STEP_MIN;

  const [mode, setMode] = useState<"grid" | "new_patient">("grid");
  // KHUNG ĐIỀN SẴN từ "Đặt lịch vào đây" ở trang chủ: ?ngay=&gio=&bac_si=
  // (16/09/2026). Chỉ đọc lúc mở màn; ngày sai định dạng thì bỏ qua.
  const sp = useSearchParams();
  const [khungSan] = useState(() => {
    const ngay = sp.get("ngay") ?? "";
    const gio = sp.get("gio") ?? "";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(ngay) || !/^\d{2}:\d{2}$/.test(gio)) return null;
    const bacSi = sp.get("bac_si");
    const ten = bacSi ? (doctors.find((d) => d.id === bacSi)?.label ?? null) : null;
    return { ngay, gio, bacSi: ten ? bacSi : null, ten: ten ?? "Chưa phân bác sĩ" };
  });
  const [weekOffset, setWeekOffset] = useState(() =>
    khungSan ? tuanLechSoVoiHomNay(khungSan.ngay) : 0,
  );
  const [moLichThang, setMoLichThang] = useState(false);

  // MỐC "BÂY GIỜ" NẰM TRONG STATE, không gọi Date.now() lúc render.
  //
  // Hai lý do, và cái thứ hai mới là cái quan trọng:
  //   · `Date.now()` trong render là hàm không thuần — trình biên dịch React
  //     chặn thẳng, và nó đúng.
  //   · Quan trọng hơn: nếu đọc đồng hồ lúc render thì lưới CHỈ đúng tại
  //     khoảnh khắc tải trang. CSKH mở màn lúc 17:55 rồi ngồi tư vấn tới 18:20
  //     sẽ vẫn thấy khung 18:00 xanh và mời đặt — backend từ chối, nhưng người
  //     dùng chỉ biết sau khi đã bấm.
  const [bayGio, setBayGio] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setBayGio(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);
  const [selectedDateIso, setSelectedDateIso] = useState(() => khungSan?.ngay ?? vnToday());

  const weekDays = useMemo(() => weekOf(vnToday(), weekOffset), [weekOffset]);


  // Clean Service Names
  const cleanServices = useMemo(
    () =>
      services.map((s) => ({
        ...s,
        label: s.label.replace(/^[\*\#\s]+/, "").trim(),
      })),
    [services],
  );

  // MẶC ĐỊNH LÀ CHƯA CHỌN, không phải "dịch vụ đầu danh sách".
  //
  // Bản cũ tự chọn sẵn `cleanServices[0]` và ô lọc hiện tên dịch vụ ấy như thể
  // người dùng đã chọn. Ai không để ý là đặt lịch vào một dịch vụ mình chưa hề
  // chọn — và panel bên phải cũng ghi tên nó, nên trông càng giống một lựa chọn
  // có chủ ý.
  const [selectedServiceId, setSelectedServiceId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");

  // `?bn=<mã bệnh nhân>` — CSKH bấm "Đặt lịch mới" từ màn Quản lý khách hàng
  // thì sang đây phải thấy ĐÚNG người vừa mở, không phải người đầu danh sách.
  // Trước đây nút ấy mở một modal dựng sẵn nên không cần truyền gì; nay nó đi
  // tới màn thật, và mất người đang chọn giữa đường là bắt CSKH tìm lại.
  //
  // Chỉ đọc MỘT LẦN làm giá trị khởi tạo: sau đó người dùng đổi khách trong
  // màn này là quyền của họ, URL không được kéo ngược lựa chọn về.
  const bnParam = sp.get("bn");
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(
    () =>
      (bnParam
        ? (patients.find((p) => p.patient_code === bnParam)
            ?.clinic_patient_id ?? null)
        : null) ??
      patients[0]?.clinic_patient_id ??
      null,
  );

  // BỎ CHỌN LÀ BỎ CHỌN THẬT.
  //
  // Bản cũ rơi về `patients[0]` khi `selectedPatientId` là null, nên ba nút
  // "Hủy chọn", "Đặt cho khách khác" và "+ Đặt lịch hẹn cho khách mới" đều
  // KHÔNG bỏ chọn được: màn hình lập tức chọn lại người đầu danh sách. Bấm
  // "Đặt cho khách khác" xong bấm luôn "Đặt lịch hẹn" là đặt cho một người
  // mình không hề chọn — và panel bên phải vẫn ghi tên họ nên trông như đúng.
  //
  // Giá trị KHỞI TẠO của state mới là chỗ chọn sẵn người đầu tiên (xem
  // useState ở trên); ở đây thì null nghĩa là null.
  //
  // Khách chọn từ KẾT QUẢ TÌM (06/10/2026) có thể không nằm trong 200 khách
  // nạp sẵn — nhớ họ ở `khachTuTim` để thẻ khách / panel / nút đặt vẫn thấy.
  const [khachTuTim, setKhachTuTim] = useState<Record<string, PatientLite>>({});
  const [lanKhamTuTim, setLanKhamTuTim] = useState<
    Record<string, { soLanKham: number; laTaiKham: boolean }>
  >({});
  const activePatient = useMemo(
    () =>
      selectedPatientId === null
        ? null
        : (patients.find((p) => p.clinic_patient_id === selectedPatientId) ??
          khachTuTim[selectedPatientId] ??
          null),
    [patients, khachTuTim, selectedPatientId],
  );
  // Nhãn "khám lần mấy": của hub cho 200 khách nạp sẵn, của ô tìm cho khách
  // chọn từ kết quả tìm — cùng một hàm máy chủ (`dem_lan_kham`) tính cả hai.
  const lanKhamGop = useMemo(
    () => ({ ...lanKham, ...lanKhamTuTim }),
    [lanKham, lanKhamTuTim],
  );

  // Selected Slot
  const [selectedSlot, setSelectedSlot] = useState<{
    doctorId: string;
    doctorName: string;
    time: string;
  }>({
    // CHƯA CHỌN GÌ LÀ CHƯA CHỌN (16/09/2026). Bản cũ mặc định bác sĩ đầu danh
    // sách + 18:00, nên cột phải hiện sẵn một khung người dùng chưa từng bấm.
    doctorId: khungSan?.bacSi ?? "",
    doctorName: khungSan?.ten ?? "",
    time: khungSan?.gio ?? "",
  });

  /** ĐỔI NGÀY THÌ BỎ CHỌN KHUNG GIỜ.
   *
   * LỖI ĐÃ ĐO ĐƯỢC (Quang báo 09/08/2026): "ấn chuyển ngày rồi nhưng các ô
   * chọn khung khám vẫn không chuyển, vẫn bị ở khung cũ".
   *
   * `selectedSlot` chỉ có {bác sĩ, giờ} — KHÔNG có ngày. Nên chọn 10:00 thứ Hai
   * rồi bấm sang thứ Ba là ô 10:00 của thứ Ba lập tức hiện dấu tích "đang chọn",
   * dù người dùng chưa hề chọn nó. Ba hệ quả, và cái thứ ba là hỏng thật:
   *
   *   · lưới trông như không đổi theo ngày;
   *   · hiệu ứng giữ chỗ bắn một lần POST giữ đúng khung ấy của ngày MỚI, nên
   *     màn hình người bên cạnh thấy một chỗ đang bị giữ mà không ai định giữ;
   *   · nút "Đặt lịch hẹn" sáng sẵn với một khung chưa ai chọn — bấm là ra lịch
   *     đúng giờ, SAI NGÀY.
   *
   * Mọi chỗ đổi ngày (tab thứ, nút "Hôm nay", lịch tháng) đều đi qua đây.
   */
  function chonNgay(iso: string) {
    setSelectedDateIso(iso);
    setSelectedSlot((prev) => ({ ...prev, time: "" }));
    setOChon(null);
    // Sức chứa đi theo KHUNG, không theo ngày: bỏ ô đang chọn mà giữ lại nó thì
    // panel phải còn ghi "còn 2 chỗ" của một khung không ai chọn nữa.
    setThongTinKhung(null);
    setJustBooked(null);
  }

  /** Ô (bác sĩ × ngày) đang làm việc — do bảng tuần chọn (16/09/2026).
   *  null = chưa chọn ô nào, nút đặt lịch tắt. `doctorId` null = "Chưa phân
   *  bác sĩ" (lịch rơi vào hàng Chờ xếp bác sĩ). */
  const [oChon, setOChon] = useState<{
    doctorId: string | null;
    doctorName: string;
    date: string;
  } | null>(() =>
    khungSan ? { doctorId: khungSan.bacSi, doctorName: khungSan.ten, date: khungSan.ngay } : null,
  );
  /** Sức chứa của khung đang chọn — popup của bảng tuần gửi kèm lúc bấm khung
   *  (16/09/2026). Trước đó do ô "3. Khung giờ khả dụng" báo lên, ô ấy đã bỏ. */
  const [thongTinKhung, setThongTinKhung] = useState<ThongTinKhung | null>(null);

  function chonKhungTuBang(v: {
    doctorId: string | null;
    doctorName: string;
    date: string;
    time: string;
    thongTin: ThongTinKhung;
  }) {
    if (v.date !== selectedDateIso) setSelectedDateIso(v.date);
    setOChon({ doctorId: v.doctorId, doctorName: v.doctorName, date: v.date });
    setSelectedSlot({ doctorId: v.doctorId ?? "", doctorName: v.doctorName, time: v.time });
    // Sức chứa đi kèm cú bấm: popup vừa đọc quote của đúng ngày/bác sĩ ấy.
    setThongTinKhung(v.thongTin);
    setJustBooked(null);
  }

  /** ĐỔI KHÁCH THÌ DỌN SẠCH DẤU VẾT CỦA LẦN ĐẶT TRƯỚC.
   *
   *  Quang 09/08/2026: *"chuyển bệnh nhân khác rồi mà cái thông báo kia không
   *  mất đi là sao"*. Chỗ bấm chọn khách trước đây chỉ đặt `selectedPatientId`,
   *  nên băng xanh "Đã đặt lịch hẹn thành công cho Nguyễn Thị Lan" và khối "Đã
   *  đặt lịch xong" trong panel vẫn còn nguyên trong khi panel đã mang tên
   *  người khác — hai người trong cùng một khung hình, và người đọc phải đoán
   *  câu nào nói về ai.
   *
   *  Nó còn làm sai cả thanh ba mốc: `justBooked` khiến mốc "Đặt lịch" tích
   *  xanh cho một khách chưa đặt gì.
   *
   *  MỌI chỗ đổi khách phải đi qua đây — cùng lý do với chonNgay ở trên. */
  function chonKhach(id: string | null) {
    setSelectedPatientId(id);
    setJustBooked(null);
    setConfirmedMsg(null);
    setBookingError(null);
  }

  const [note, setNote] = useState("");
  /** Kênh khách liên hệ đặt lịch (Tuyền chốt danh sách 16/09/2026). Trước đây
   *  mọi lịch CSKH đặt đều gán cứng "HOTLINE". */
  const [kenhDat, setKenhDat] = useState("DIEN_THOAI");
  const [gioiThieu, setGioiThieu] = useState("");
  const [confirmedMsg, setConfirmedMsg] = useState<string | null>(null);
  // ĐẶT XONG THÌ PHẢI THẤY NGAY TẠI CHỖ VỪA BẤM.
  //
  // Trên prod ngày 04/08 có một bệnh nhân bị đặt BA lịch cùng khung 17:15,
  // cách nhau 10 và 5 giây. Không phải double-click (nút đã khoá lúc đang gửi)
  // — mà là bấm, chờ, không thấy gì, bấm lại.
  //
  // Lý do: chữ "Đã đặt lịch thành công" hiện ở ĐẦU TRANG (dòng ~815), còn nút
  // nằm ở panel phải cuối trang. CSKH bấm ở dưới, phản hồi hiện ở trên, ngoài
  // tầm mắt. Nên nó hiện cả ở đây, và khung giờ được BỎ CHỌN để bấm lại lần
  // nữa cũng không ra thêm lịch.
  const [justBooked, setJustBooked] = useState<{
    name: string;
    time: string;
    doctor: string;
  } | null>(null);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingLoading, setBookingLoading] = useState(false);

  /** LỊCH SẮP TỚI CỦA KHÁCH ĐANG CHỌN — để không đặt trùng.
   *
   *  Quang 09/08/2026: *"ấn vào 1 bệnh nhân đã đặt lịch rồi thì trang bên phải
   *  phải hiện cái lịch đã đặt ra… chứ đặt trùng liên tục à"*.
   *
   *  Không dùng `appts` có sẵn được: nó chỉ chứa lịch HÔM NAY (xem
   *  appointments/page.tsx), trong khi đặt trùng hay xảy ra nhất khi lịch cũ
   *  nằm ở một NGÀY KHÁC — đúng cái mà lưới trước mặt không hiện.
   *
   *  KẾT QUẢ ĐI KÈM MÃ KHÁCH nó thuộc về, và phần hiển thị chỉ nhận khi hai mã
   *  khớp. Nhờ vậy đổi khách là khối này tự trống, không cần một lệnh dọn chạy
   *  ngay trong thân effect — và không có khoảnh khắc nào panel mang tên người
   *  này mà kèm lịch của người kia. Đó đúng là hạng lỗi vừa phải sửa ở băng xanh.
   *
   *  `null` = chưa có câu trả lời cho khách này; `[]` = hỏi rồi, chưa có lịch. */
  // Đổi lịch tại chỗ từ khung vàng xong → nạp lại danh sách lịch sắp tới.
  const [lanDoiLich, setLanDoiLich] = useState(0);
  const [lichDaNap, setLichDaNap] = useState<{
    khach: string;
    ket: { ok: true; items: LichCu[] } | { ok: false };
  } | null>(null);

  useEffect(() => {
    if (!selectedPatientId) return;
    const khach = selectedPatientId;
    let con = true;
    fetch(`/api/appointments?clinic_patient_id=${encodeURIComponent(khach)}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(String(r.status));
        return (await r.json()) as { appointments?: LichCu[] };
      })
      .then((d) => {
        if (con) setLichDaNap({ khach, ket: { ok: true, items: d.appointments ?? [] } });
      })
      // HỎNG THÌ PHẢI GHI LẠI LÀ HỎNG. Nuốt lỗi ở đây là để màn hình im lặng
      // đúng như lúc khách sạch lịch — xem ghi chú ở LichSapToiCuaKhach.
      .catch(() => {
        if (con) setLichDaNap({ khach, ket: { ok: false } });
      });
    return () => {
      con = false;
    };
    // `justBooked` trong danh sách phụ thuộc để lịch vừa đặt hiện ra ngay,
    // không phải đợi tải lại trang.
  }, [selectedPatientId, justBooked, lanDoiLich]);

  const traLichCu: TrangThaiTra =
    selectedPatientId && lichDaNap?.khach === selectedPatientId
      ? lichDaNap.ket.ok
        ? { kind: "xong", items: lichDaNap.ket.items }
        : { kind: "hong" }
      : { kind: "dang-hoi" };
  // Chốt chống bấm hai lần. useRef chứ không useState: state chỉ đổi sau lần
  // render kế tiếp, mà hai cú click của một double-click nằm gọn TRƯỚC lần
  // render đó. Xem handleConfirmBooking.
  const submittingRef = useRef(false);
  // Khoá idempotency của LẦN ĐẶT hiện tại. Giữ qua lần thử lại của cùng một lần
  // đặt; xoá khi server đã trả lời (dù thành công hay lỗi).
  const idemKeyRef = useRef<string | null>(null);







  // LỌC TẠI CHỖ trên 200 khách nạp sẵn — chỉ là thứ hiện NGAY trong lúc chờ
  // máy chủ (và khi ô tìm < 2 ký tự / máy chủ không trả lời). Kết quả thật
  // của ô tìm là `ketQuaTim` bên dưới.
  const filteredPatients = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) =>
        p.full_name.toLowerCase().includes(q) ||
        // Gộp mọi số của hồ sơ — khách đọc số nào (kể cả số thêm) cũng ra.
        (p.sdt_tim_kiem ?? p.phone_primary ?? "").includes(q) ||
        p.patient_code.toLowerCase().includes(q),
    );
  }, [patients, searchQuery]);

  // TÌM TRÊN TOÀN BỘ HỒ SƠ (06/10/2026).
  //
  // Sáng 06/10 nạp ~8.600 khách cũ từ Notion; 200 khách nạp sẵn là khách MỚI
  // TẠO gần nhất, nên lễ tân gõ tên / số một khách cũ thì không ra và tạo hồ sơ
  // trùng. Từ 2 ký tự, sau 300 ms ngừng gõ, hỏi máy chủ
  // (`GET /api/appointments/tim-khach` → `man_dat_lich_doc.tim_khach`: tên
  // không dấu / mã / một phần SĐT, khớp đúng mã-số lên trước, tối đa 20).
  //
  // KẾT QUẢ ĐI KÈM CHUỖI ĐÃ HỎI và chỉ hiện khi khớp ô tìm hiện tại — cùng cách
  // với `lichDaNap`: gõ tiếp thì kết quả cũ tự thôi hiện, không cần lệnh dọn
  // trong thân effect, và một câu trả lời về muộn không đè lên chuỗi mới.
  const TIM_TOI_THIEU = 2;
  const qTim = searchQuery.trim();
  const timMayChu = qTim.length >= TIM_TOI_THIEU;
  const [ketQuaTim, setKetQuaTim] = useState<
    | {
        q: string;
        ok: true;
        patients: PatientLite[];
        lanKham: Record<string, { soLanKham: number; laTaiKham: boolean }>;
      }
    | { q: string; ok: false }
    | null
  >(null);
  useEffect(() => {
    if (!timMayChu) return;
    const q = qTim;
    let con = true;
    const hen = setTimeout(() => {
      fetch(`/api/appointments/tim-khach?q=${encodeURIComponent(q)}`)
        .then(async (r) => {
          if (!r.ok) throw new Error(String(r.status));
          return (await r.json()) as {
            patients?: PatientLite[];
            lan_kham?: Record<string, { soLanKham: number; laTaiKham: boolean }>;
          };
        })
        .then((d) => {
          if (con)
            setKetQuaTim({
              q,
              ok: true,
              patients: d.patients ?? [],
              lanKham: d.lan_kham ?? {},
            });
        })
        // Hỏng thì NÓI là hỏng (dòng dưới ô tìm) và vẫn hiện lọc tại chỗ — im
        // lặng thì lễ tân tưởng "không có khách này" rồi tạo hồ sơ trùng.
        .catch(() => {
          if (con) setKetQuaTim({ q, ok: false });
        });
    }, 300);
    return () => {
      con = false;
      clearTimeout(hen);
    };
  }, [qTim, timMayChu]);
  const ketQuaHienTai = timMayChu && ketQuaTim?.q === qTim ? ketQuaTim : null;
  const danhSachKhach =
    ketQuaHienTai && ketQuaHienTai.ok ? ketQuaHienTai.patients : filteredPatients;
  const TRAN_TIM = 20;
  const dongTrangThaiTim: string | null = !timMayChu
    ? null
    : !ketQuaHienTai
      ? "Đang tìm trên toàn bộ hồ sơ…"
      : !ketQuaHienTai.ok
        ? "Không tìm được trên toàn bộ hồ sơ — đang hiện trong 200 khách gần nhất."
        : ketQuaHienTai.patients.length === 0
          ? "Không có khách nào khớp."
          : ketQuaHienTai.patients.length >= TRAN_TIM
            ? `Hiện ${TRAN_TIM} khách khớp nhất — gõ thêm để thu hẹp.`
            : null;

  /** Chọn một khách trong danh sách tìm: nhớ hồ sơ + nhãn "khám lần mấy" của
   *  họ nếu họ đến từ kết quả máy chủ (có thể ngoài 200 khách nạp sẵn). */
  function nhoKhachTuTim(p: PatientLite) {
    if (!ketQuaHienTai || !ketQuaHienTai.ok) return;
    const id = p.clinic_patient_id;
    setKhachTuTim((cu) => ({ ...cu, [id]: p }));
    const lk = ketQuaHienTai.lanKham[id];
    if (lk) setLanKhamTuTim((cu) => ({ ...cu, [id]: lk }));
  }


  // SỐ KHÔNG TĂNG SAU KHI ĐẶT — đây là chỗ gây ra nó.
  //
  // `router.refresh()` chỉ nạp lại prop từ server, mà prop đó CHỈ CHỨA LỊCH
  // HÔM NAY. Lịch của ngày khác nằm trong `fetchedByDate`, là state của trình
  // duyệt: nó không biết vừa có một lịch mới, nên ô vừa đặt vẫn vẽ "0/8" ngay
  // sau dòng chữ "Đã đặt lịch hẹn thành công". Người đặt tin vào con số đó và
  // đặt tiếp — đúng cái mà lưới sức chứa sinh ra để ngăn.
  //
  // Cách sửa: sau khi đặt xong, XOÁ ô nhớ đệm của ngày đó. Effect bên dưới đã
  // sẵn sàng nạp lại khi giá trị là `undefined`, nên không cần thêm cờ nào —
  // và tránh setState trong thân effect, thứ mà react-hooks chặn ở repo này.
  // `bookingSeq` thì để bắt effect sức chứa đọc lại phần ĐÃ DÙNG.
  const [bookingSeq, setBookingSeq] = useState(0);
  // Ca trực đổi (quản lý thêm/xoá/đổi ca) → hỏi lại sức chứa + nhãn ca.
  // Xem dung-doi-ca.ts — cùng vai bookingSeq, khác nguồn.
  const doiCa = useDoiCa();




  // CHỖ NGƯỜI KHÁC ĐANG GIỮ — khoá "docId|ngày|giờ".
  //
  // Khối nhịp/SSE đã chuyển sang `dung-giu-cho.ts` (16/09/2026) để popup khung
  // giờ của bảng tuần dùng chung: nó mở được một NGÀY KHÁC ngày đang xem, nên
  // trước đó nó mù hẳn chuyện ai đang giữ chỗ.
  const heldByOthers = useGiuCho(selectedDateIso);

  // RỜI MÀN THÌ THẢ CHỖ ĐANG GIỮ.
  //
  // `DELETE /api/appointments/slot-hold` có đủ cả hai đầu — route Next
  // (slot-hold/route.ts:75) và endpoint FastAPI (booking.py:318) — nhưng chưa
  // từng có ai gọi. Hệ quả: CSKH chọn một khung rồi đóng tab, và ô đó hiện
  // "đang giữ" trên màn hình mọi người khác đủ 10 phút (HOLD_MINUTES) cho một
  // người đã đi khỏi. Ở giờ cao điểm đó là những ô còn trống bị báo là bận.
  //
  // Deps rỗng — CHỈ chạy lúc gỡ component, không chạy khi đổi khung. Đổi khung
  // thì SlotHoldService.hold() đã tự thả cái cũ trong cùng transaction
  // (_release_mine(keep=slot_start)); gọi thêm DELETE ở đây sẽ đua với POST mới
  // và có thể thả nhầm chỗ vừa giữ, vì release() thả TẤT CẢ chỗ của người này.
  //
  // keepalive: trình duyệt huỷ fetch thường khi trang đang đóng; cờ này cho
  // request đi tiếp. Đây là lý do không dùng sendBeacon: beacon chỉ POST được.
  useEffect(() => {
    return () => {
      void fetch("/api/appointments/slot-hold", {
        method: "DELETE",
        keepalive: true,
      }).catch(() => {
        // Thả chỗ hỏng thì chỗ tự hết hạn sau 10 phút. Giữ chỗ là tư vấn,
        // không phải khoá — không đáng để chặn việc gì.
      });
    };
  }, []);

  // GIỮ CHỖ KHI ĐANG CHỌN. Bỏ chọn / đổi khung thì backend tự thả cái cũ.
  useEffect(() => {
    if (!selectedSlot.time || !selectedDateIso) return;
    const startIso = vnLocalToUtcISO(selectedDateIso, selectedSlot.time);
    const endIso = new Date(
      new Date(startIso).getTime() + slotMinutes * 60000,
    ).toISOString();
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      void fetch("/api/appointments/slot-hold", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot_start: startIso,
          slot_end: endIso,
          doctor_id: selectedSlot.doctorId || null,
          // Đi kèm CHỈ để nhật ký thao tác gọi được tên người. Bảng `slot_hold`
          // không lưu trường này; thiếu nó thì màn Lịch sử thao tác in
          // "slot_hold · 938d4f94" ở cột Khách hàng (xem v_audit_log).
          clinic_patient_id: activePatient?.clinic_patient_id ?? null,
        }),
        signal: ctrl.signal,
      }).catch(() => {
        // Giữ chỗ là tư vấn, không phải khoá — hỏng thì vẫn đặt lịch được.
        // Chốt chặn sức chứa thật nằm ở trigger lúc INSERT.
      });
    }, 400);
    return () => {
      ctrl.abort();
      clearTimeout(t);
    };
  }, [
    selectedSlot.time,
    selectedSlot.doctorId,
    selectedDateIso,
    slotMinutes,
    activePatient?.clinic_patient_id,
  ]);





  async function handleConfirmBooking() {
    // Ngày CHƯA XẾP CA thì không có bác sĩ để chọn, và đó là hợp lệ: lịch đi ra
    // với doctor_id = null rồi rơi vào màn "Chờ xếp bác sĩ". Chặn ở đây như cũ
    // nghĩa là nút bấm không làm gì cả trong đúng trường hợp Quang vừa mô tả.
    if (!activePatient) return;
    if (!oChon) return;
    // Không có luật thì không có lưới, và không có lưới thì không đặt được: gửi
    // đi lúc này chỉ tạo một lịch dài sai giờ. Nút đã bị vô hiệu hoá ở phần
    // render; đây là chốt chặn thứ hai.
    if (!policy) {
      setBookingError("Chưa đọc được luật đặt lịch của phòng khám — thử tải lại trang.");
      return;
    }
    // KHÔNG rơi về `cleanServices[0]` nữa: đặt lịch vào một dịch vụ người dùng
    // chưa chọn là ghi sai hồ sơ mà không ai biết cho tới lúc khách tới nơi.
    const serviceId = selectedServiceId;
    if (!serviceId) {
      setBookingError("Chưa chọn dịch vụ khám.");
      return;
    }

    // CHỐT ĐỒNG BỘ, KHÔNG PHẢI STATE.
    //
    // Nút đã có `disabled={bookingLoading || …}`, nhưng `setBookingLoading(true)`
    // chỉ có hiệu lực sau khi React render lại. Hai cú click trong cùng một nhịp
    // (double-click bình thường của con người, ~150ms) đều vào được hàm này vì
    // DOM lúc đó vẫn là nút chưa bị vô hiệu hoá. useRef đổi giá trị NGAY, nên
    // cú thứ hai quay đầu ở đây.
    //
    // Đây là lớp một trong ba. Lớp hai là Idempotency-Key bên dưới (chặn khi
    // request đã rời trình duyệt). Lớp ba là chốt ở database — chưa có, xem
    // báo cáo: prod đang còn 5 dòng trùng nên chỉ mục duy nhất chưa dựng được.
    if (submittingRef.current) return;
    submittingRef.current = true;

    // MỘT KHOÁ CHO MỘT LẦN ĐẶT, giữ nguyên qua mọi lần thử lại của cùng lần đặt
    // đó. Sinh khoá mới ở mỗi lần bấm thì không chặn được gì; sinh ở server thì
    // càng vô nghĩa vì mỗi request là một khoá.
    if (!idemKeyRef.current) {
      idemKeyRef.current =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }

    setBookingLoading(true);
    setBookingError(null);
    try {
      const slotMins = policy.slotMinutes;
      const timeDisplay = slotRange(selectedSlot.time, slotMins);

      const targetDate = selectedDateIso || vnToday();
      const [startH, startM] = selectedSlot.time.split(":").map(Number);
      const totalStartMin = (startH ?? 0) * 60 + (startM ?? 0);
      const totalEndMin = totalStartMin + slotMins;
      // `% 24` để khung cuối ngày không sinh ra "24:00", một giờ không tồn tại
      // trong ISO-8601 mà Date.parse trả về NaN. Khung 23:45 + 15' là 00:00 hôm
      // sau; vnLocalToUtcISO nhận ngày kế tiếp nên mốc UTC vẫn đúng.
      const endDayShift = Math.floor(totalEndMin / (24 * 60));
      const endH = String(Math.floor(totalEndMin / 60) % 24).padStart(2, "0");
      const endM = String(totalEndMin % 60).padStart(2, "0");
      const endDate = endDayShift
        ? new Date(
            Date.parse(`${targetDate}T00:00:00${VN_OFFSET}`) +
              endDayShift * 86_400_000,
          ).toLocaleDateString("en-CA", { timeZone: VN_TZ })
        : targetDate;

      const res = await fetch("/api/appointments", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idemKeyRef.current,
        },
        body: JSON.stringify({
          clinic_patient_id: activePatient.clinic_patient_id,
          doctor_id: selectedSlot.doctorId || null,
          service_type_id: serviceId,
          // KHÔNG gửi location_id. Server dùng cơ sở của người đang đăng nhập
          // (identity.location_id) — nó biết chắc, còn trình duyệt thì đoán.
          slot_start: vnLocalToUtcISO(targetDate, selectedSlot.time),
          slot_end: vnLocalToUtcISO(endDate, `${endH}:${endM}`),
          // ĐẶT TRƯỚC, KHÔNG PHẢI VÃNG LAI. Màn này không gửi trường nào và
          // backend mặc định "WALK_IN", nên mọi lịch CSKH đặt đều ăn vào ô để
          // dành cho khách đến thẳng quầy, còn ô đặt trước thì trống. Nói rõ ra.
          booking_channel: kenhDat,
          nguoi_gioi_thieu:
            kenhDat === KENH_GIOI_THIEU ? gioiThieu.trim() || undefined : undefined,
          notes: note,
        }),
      });

      if (res.ok) {
        // Cảnh báo đi CÙNG thông báo thành công, không thay nó: lịch đã được
        // ghi thật. Ví dụ hay gặp nhất là bác sĩ không có ca trực hôm đó —
        // không sai đủ để từ chối, nhưng người đặt phải biết ngay bây giờ chứ
        // không phải lúc bệnh nhân tới nơi.
        const body = (await res.json().catch(() => ({}))) as {
          warnings?: string[];
        };
        const warn = (body.warnings ?? []).join(" ");
        setConfirmedMsg(
          `Đã đặt lịch hẹn thành công cho ${activePatient.full_name} vào khung giờ ${timeDisplay}` +
            (selectedSlot.doctorId
              ? ` với ${selectedSlot.doctorName}!`
              : " — chờ quản lý xếp bác sĩ.") +
            (warn ? ` ⚠️ ${warn}` : ""),
        );
        setNote("");
        setJustBooked({
          name: activePatient.full_name,
          time: timeDisplay,
          doctor: selectedSlot.doctorId
            ? selectedSlot.doctorName
            : "chờ xếp bác sĩ",
        });
        // BỎ CHỌN KHUNG GIỜ. Giữ nguyên lựa chọn nghĩa là nút "Đặt lịch hẹn"
        // sáng lại với y hệt thông tin cũ — bấm thêm lần nữa là ra lịch thứ
        // hai, và đó đúng là chuyện đã xảy ra.
        setSelectedSlot((prev) => ({ ...prev, time: "" }));
        // BA THỨ PHẢI ĐỌC LẠI, không phải một.
        //
        // `router.refresh()` một mình là chưa đủ và đó chính là lỗi "đặt xong
        // số không tăng": nó chỉ nạp lại prop từ server, mà prop đó chỉ chứa
        // lịch HÔM NAY. Đặt cho ngày khác thì con số đến từ `fetchedByDate`
        // (bộ nhớ trình duyệt) và từ /quote — cả hai đều không biết gì.
        setBookingSeq((n) => n + 1);
        router.refresh();
      } else {
        const err = await res.json().catch(() => ({}));
        // alert() chặn luồng, không đọc được trên điện thoại và là chỗ duy nhất
        // trong toàn app dùng nó. Lỗi hiện ngay cạnh nút đã bấm.
        //
        // `message` TRƯỚC `error`. Thân lỗi của backend là
        // `{"error": "CONFLICT_ERROR", "message": "Khung giờ đã đầy: tối đa 2
        // chỗ lịch hẹn cho bác sĩ này trong khung 15 phút."}` — `error` là MÃ
        // cho máy đọc, `message` là câu cho người đọc. Đọc `error` trước nghĩa
        // là hai CSKH tranh chỗ cuối thì người thua nhìn thấy dòng chữ
        // "CONFLICT_ERROR" và không biết phải làm gì tiếp.
        //
        // Đo được trên staging 14/08/2026: 409 với đúng thân lỗi ấy. Cùng họ
        // với lỗi đã vá hôm 13/08 — backend nói "không tìm thấy nhân viên",
        // màn hình dịch thành "máy chủ hỏng".
        setBookingError(loiDocDuoc(err, "Không thể đặt lịch."));
      }
      // SERVER ĐÃ TRẢ LỜI ⇒ BỎ KHOÁ, dù là 201 hay 409.
      //
      // Lần bấm sau là một lần đặt KHÁC (đổi khung, đổi khách, hoặc thử lại sau
      // khi bị từ chối), nên phải mang khoá mới. Dùng lại khoá cũ sẽ đâm vào
      // hàng đã ở trạng thái PROCESSING trong bảng idempotency_key và nhận
      // "Yêu cầu với Idempotency-Key này đang được xử lý" — kẹt đủ 5 phút
      // (PROCESSING_TTL_MINUTES), tức là chốt chống trùng tự biến thành lỗi.
      idemKeyRef.current = null;
    } catch {
      // MẤT MẠNG GIỮA CHỪNG ⇒ GIỮ NGUYÊN KHOÁ. Đây là trường hợp duy nhất
      // không biết request có tới nơi hay không. Bấm lại với cùng khoá là cách
      // duy nhất an toàn: nếu lần trước đã ghi thành công, backend phát lại
      // đúng response cũ thay vì tạo lịch thứ hai.
      setBookingError("Mất kết nối tới máy chủ — lịch chưa được lưu.");
    } finally {
      setBookingLoading(false);
      submittingRef.current = false;
    }
  }

  const selectedServiceName =
    cleanServices.find((s) => s.id === selectedServiceId)?.label ?? "";

  return (
    <div className="space-y-4">


      {/* Không đọc được luật đặt lịch thì lưới KHÔNG được đoán. Trước đây nó âm
          thầm rơi về 15 phút / 3 chỗ — những con số không phải của phòng khám
          nào — rồi mời lễ tân bấm vào các ô mà database sẽ từ chối. */}
      {!policy && (
        <div
          role="alert"
          className="rounded-2xl border border-warning/40 bg-warning-bg p-3.5 text-xs text-warning"
        >
          <span className="font-semibold">Chưa đọc được luật đặt lịch.</span>{" "}
          Lưới giờ và số chỗ đến từ cấu hình phòng khám; khi chưa đọc được, màn
          này không vẽ lưới thay vì vẽ một lưới sai. Thử tải lại trang — nếu vẫn
          vậy thì máy chủ xử lý đang không phản hồi và hiện chưa đặt lịch được.
        </div>
      )}

      {confirmedMsg && (
        <div className="flex items-center justify-between rounded-2xl border border-success/30 bg-success/10 p-3.5 text-xs text-success shadow-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} />
            <span className="font-semibold">{confirmedMsg}</span>
          </div>
          <button
            onClick={() => setConfirmedMsg(null)}
            className="text-success hover:underline"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* MỘT bố cục duy nhất. Biểu mẫu khách mới hiện Ở CỘT GIỮA, chỗ lưới
          giờ — không thay cả trang.

          Trước đây `mode === "new_patient"` thay toàn bộ màn: bốn ô số, thanh ba
          bước, cột khách hàng và panel xác nhận đều biến mất. Người dùng bấm
          "khách mới" là mất hết ngữ cảnh vừa nhìn, và bấm nhầm thì phải đi
          đường vòng để quay lại. */}
      <div className="space-y-4">
          {/* BỐN Ô SỐ NÀY TỪNG LÀ SỐ BỊA — 42 / 18 / 4 / 20 viết cứng trong mã
              nguồn, không đọc từ đâu cả. Chúng đứng ngay trên đầu màn CSKH dùng
              hằng ngày, nên người dùng tin và đối chiếu theo. Đây đúng loại lỗi
              commit 30706ab đã dọn ở màn CSKH ("bốn ô số đọc nguồn chết") —
              chỉ là màn Đặt lịch chưa ai soát.

              Vi phạm thẳng tiêu chí khách hàng: "Áp dụng cho chạy thực tế —
              không có chế độ demo song song" và "Màn hình báo rõ dữ liệu cũ X
              giây thay vì im lặng hiển thị số sai".

              "Còn chỗ" hiện là dấu gạch, KHÔNG phải quên: sức chứa còn lại phụ
              thuộc số khách online + trực tiếp quản lý đặt cho mỗi khung, lịch trực của từng bác sĩ và cấu hình
              riêng của bác sĩ Thành (18h–18h15 nhận 10 ca, sau đó 4). Tính
              nhẩm ở frontend là ra một con số thứ hai lệch với backend. Thà để
              trống còn hơn nói sai — bảng lưới bên dưới đã hiện đúng từng ô. */}
          {/* Top 4 Summary Stat Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-700">
                <CalendarIcon className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Lịch hôm nay</p>
                <p className="text-xl font-bold text-ink">{appts.length}</p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-emerald-50 text-emerald-600">
                <User className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Còn chỗ</p>
                <p
                  className="text-xl font-bold text-ink-muted"
                  title="Sức chứa còn lại phụ thuộc số khách quản lý đặt cho từng bác sĩ, lịch trực và cấu hình riêng từng bác sĩ — xem trực tiếp trên lưới giờ bên dưới."
                >
                  —
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-sky-50 text-sky-600">
                <Clock className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">
                  Đang giữ · ngày đang xem
                </p>
                <p className="text-xl font-bold text-ink">
                  {heldByOthers.size}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-teal-50 text-teal-600">
                <CheckCircle2 className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Đã xác nhận</p>
                <p className="text-xl font-bold text-ink">
                  {appts.filter((a) => a.status === "CONFIRMED").length}
                </p>
              </div>
            </div>
          </div>

          {/* BA MỐC, VÀ CHÚNG PHẢN ÁNH TRẠNG THÁI THẬT.
              
              Bản trước viết cứng: mốc 1 luôn có dấu tích, mốc 2 luôn sáng, mốc 3
              luôn xám — bất kể người dùng đã làm gì. Một thanh tiến trình không
              đổi theo việc mình vừa làm thì tệ hơn không có: nó dạy người dùng
              bỏ qua nó.
              
              "Chọn khách hàng" không còn là một mốc: nó là điều kiện để lưới giờ
              hiện ra, chứ không phải một chặng của việc đặt lịch. */}
          {/* KHÔNG THẺ TRẮNG quanh ba mốc (Tuyền 16/09/2026): *"xoá bo trắng
              đằng sau chỉ hiện timeline node ở trên cho đẹp"*. Ba mốc là chỉ
              dẫn, không phải một khối nội dung cần khung riêng. */}
          <div className="flex items-center justify-center gap-4 py-1 text-xs font-medium text-ink-muted">
            <MocDatLich
              so={1}
              nhan="Khung giờ"
              xong={Boolean(selectedSlot.time && selectedSlot.doctorId)}
              dangLam={!justBooked}
            />
            <div className="h-px w-16 bg-line" />
            <MocDatLich
              so={2}
              nhan="Đặt lịch"
              xong={Boolean(justBooked)}
              dangLam={Boolean(selectedSlot.time && !justBooked)}
            />
            <div className="h-px w-16 bg-line" />
            {/* Mốc 3 KHÔNG BAO GIỜ tự tích ở màn này. CSKH tích xác nhận ở
                "Quản lý khách hàng" — nên ở đây nó chỉ nói ra việc còn lại. */}
            <MocDatLich
              so={3}
              nhan="Xác nhận lịch"
              xong={false}
              dangLam={false}
              ghiChu={justBooked ? "ở Quản lý khách hàng" : undefined}
            />
          </div>

          {/* 3-Column Layout: Left (Patient Cards) + Middle (Grid) + Right (Panel) */}
          {/* KHÁCH MỚI THÌ CHỈ CÒN HAI CỘT.
              Quang 09/08/2026: bấm "Đặt lịch hẹn cho khách mới" thì bỏ thẻ
              "đang nhập hồ sơ", bỏ nút "Quay lại lưới giờ" và bỏ cả panel
              "Thông tin đặt lịch" bên phải — *"nếu đặt cho khách có trong danh
              sách thì click sẵn bên ô tìm kiếm khách hàng có sẵn rồi"*.
              Đúng: lịch hẹn đầu tiên của khách mới nằm NGAY TRONG biểu mẫu ở
              giữa, nên panel phải không có việc gì để làm ngoài chiếm chỗ và
              mời bấm một nút không dùng tới. Bỏ nó đi thì biểu mẫu rộng ra. */}
          <div
            className={`grid items-start gap-4 ${
              mode === "new_patient"
                ? "xl:grid-cols-[240px_1fr]"
                : "xl:grid-cols-[240px_1fr_280px]"
            }`}
          >
            {/* COLUMN 1 (LEFT - 280px): New Patient Button + Active Patient Card + Search List */}
            <aside className="space-y-3">
              {/* HAI TAB "KHÁCH HÀNG CÓ SẴN / KHÁCH HÀNG MỚI" (ảnh Tuyền 16/09/2026)
                  thay nút "+ Đặt lịch hẹn cho khách mới". Chuyển sang "Khách
                  mới" vẫn BỎ CHỌN khách cũ — không thì panel phải còn tên người
                  trước và nút "Đặt lịch hẹn" ra lịch cho đúng người cũ. */}
              <div role="tablist" aria-label="Loại khách" className="grid grid-cols-2 gap-1 rounded-2xl border border-line bg-surface p-1 shadow-card">
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === "grid"}
                  onClick={() => setMode("grid")}
                  className={`rounded-xl py-2 text-xs font-semibold ${
                    mode === "grid" ? "bg-brand-600 text-white" : "text-ink-soft hover:bg-surface-muted"
                  }`}
                >
                  Khách hàng
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === "new_patient"}
                  onClick={() => {
                    setMode("new_patient");
                    chonKhach(null);
                  }}
                  className={`inline-flex items-center justify-center gap-1.5 rounded-xl py-2 text-xs font-semibold ${
                    mode === "new_patient" ? "bg-brand-600 text-white" : "text-ink-soft hover:bg-surface-muted"
                  }`}
                >
                  <UserPlus className="size-3.5" />
                  Thêm
                </button>
              </div>

              {/* 1. KHÁCH HÀNG ĐANG CHỌN — hoặc thẻ "khách mới" khi đang nhập.
                     Ô này không bao giờ được để trống trong lúc người dùng
                     đang làm việc: trống nghĩa là "không rõ đang đặt cho ai". */}
              {activePatient && (
                <div className="rounded-2xl border border-brand-300 bg-brand-50/50 p-3.5 shadow-card space-y-3">
                  <div className="flex items-start justify-between">
                    <span className="text-label font-bold text-brand-700 uppercase tracking-wide">
                      Khách hàng đang chọn
                    </span>
                    <button
                      className="text-ink-muted hover:text-brand-600"
                      title="Chỉnh sửa"
                    >
                      <Pencil size={13} />
                    </button>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="grid size-11 place-items-center rounded-full bg-brand-600 text-sm font-bold text-white shadow-xs">
                      {activePatient.full_name
                        .split(" ")
                        .slice(-2)
                        .map((w) => w[0])
                        .join("")}
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold text-ink truncate">
                        {activePatient.full_name}
                      </h3>
                      <p className="text-xs text-brand-700 font-mono font-semibold">
                        {activePatient.patient_code}
                      </p>
                    </div>
                  </div>
                  <div className="space-y-1.5 pt-2 text-xs text-ink-soft border-t border-brand-200/60">
                    <div className="flex items-center gap-2">
                      <Phone size={13} className="text-brand-600 shrink-0" />
                      <span>{activePatient.phone_primary ?? "Chưa có SĐT"}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <MapPin size={13} className="text-brand-600 shrink-0" />
                      <span className="truncate">
                        {activePatient.address ?? "Chưa có địa chỉ"}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* 2. TÌM KIẾM KHÁCH HÀNG CÓ SẴN (Kéo dài tối đa max-h-95) */}
              <div className="rounded-2xl border border-line bg-surface p-3.5 shadow-card space-y-2.5">
                <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">
                  Tìm kiếm khách hàng có sẵn
                </span>
                <label className="flex items-center gap-2 rounded-xl border border-line bg-surface-muted px-3 py-2 text-xs text-ink focus-within:border-brand-500">
                  <Search className="size-4 text-ink-muted shrink-0" />
                  <input
                    type="search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Tên, SĐT, mã bệnh nhân..."
                    className="w-full bg-transparent text-xs outline-none"
                  />
                </label>
                {dongTrangThaiTim ? (
                  <p role="status" className="text-label text-ink-muted">
                    {dongTrangThaiTim}
                  </p>
                ) : null}
                {/* Expanded scroll list */}
                <div className="max-h-95 overflow-y-auto divide-y divide-line text-xs pr-0.5">
                  {danhSachKhach.map((p) => {
                    const selected = p.clinic_patient_id === selectedPatientId;
                    return (
                      <button
                        key={p.clinic_patient_id}
                        type="button"
                        onClick={() => {
                          // ĐỔI Ý GIỮA CHỪNG THÌ PHẢI QUAY VỀ LƯỚI GIỜ.
                          //
                          // Đang mở biểu mẫu khách mới mà bấm một khách CÓ SẴN
                          // ở danh sách này là nói rõ: "thôi, đặt cho người
                          // này". Trước đây màn hình chỉ đổi thẻ "Khách hàng
                          // đang chọn" ở cột trái rồi đứng im — giữa màn vẫn là
                          // biểu mẫu khách mới, panel phải vẫn ẩn, nên không có
                          // cách nào đặt lịch cho người vừa chọn. Người dùng
                          // chọn xong lại phải đi tìm đường ra.
                          nhoKhachTuTim(p);
                          chonKhach(p.clinic_patient_id);
                          setMode("grid");
                        }}
                        className={`w-full text-left p-2.5 rounded-xl transition-colors ${
                          selected
                            ? "bg-brand-100/80 font-bold text-brand-800"
                            : "hover:bg-surface-sunken"
                        }`}
                      >
                        <div className="truncate font-semibold text-ink">
                          {p.full_name}
                        </div>
                        <div className="text-label text-ink-muted">
                          {p.patient_code} · {p.phone_primary ?? "Chưa có SĐT"}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </aside>

            {/* COLUMN 2 (MIDDLE - 1fr): biểu mẫu khách mới HOẶC lưới giờ */}
            <div className="space-y-3 min-w-0">
              {mode === "new_patient" ? (
                <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
                  <div className="mb-3 flex items-center justify-between gap-2 border-b border-line pb-3">
                    <h2 className="flex items-center gap-2 text-sm font-bold text-ink">
                      <UserPlus className="size-4 text-brand-600" />
                      Khách hàng mới
                    </h2>

                  </div>
                  {/* `nhung` = ẩn tiêu đề và thanh ba bước RIÊNG của biểu mẫu:
                      trang này đã có thanh ba bước của nó ở trên đầu, hai thanh
                      chồng nhau thì không thanh nào đáng tin. */}
                  <NewPatientForm
                    role={vai ?? "CSKH"}
                    locations={locations}
                    coSoMacDinhId={coSoMacDinhId}
                    services={cleanServices}
                    doctors={doctors}
                    provinces={provinces}
                    variant="full"
                    nhung
                    onHuy={() => setMode("grid")}
                  />
                </div>
              ) : (
                <>
              {/* Filter controls row */}
              <div className="flex flex-wrap items-center gap-2.5 rounded-2xl border border-line bg-surface p-3 shadow-card">
                {/* Service dropdown */}
                <div className="flex items-center gap-1 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs text-ink font-medium">
                  <span className="text-ink-muted">🩺</span>
                  <select
                    value={selectedServiceId}
                    onChange={(e) => setSelectedServiceId(e.target.value)}
                    className="bg-transparent text-xs font-semibold text-ink outline-none cursor-pointer"
                  >
                    <option value="">— Chọn dịch vụ —</option>
                    {cleanServices.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* HAI Ô ĐÃ BỎ KHỎI HÀNG NÀY (Tuyền 16/09/2026): *"nút tất cả
                    bác sĩ và nút lịch làm việc đâu còn ý nghĩa gì ở đây nữa"*.

                      · ô lọc "Tất cả bác sĩ" — đã ĐI XUỐNG chính cột "Bác sĩ"
                        của bảng tuần (BangBacSiTuan): bấm tên cột là ra ô tìm
                        + danh sách tên. Bộ lọc nằm trên đúng cột nó lọc, và
                        nó ở lại khi đổi khách — chốt một bác sĩ rồi đặt cùng
                        một khung cho nhiều khách liên tiếp.
                      · nút "📅 Lịch làm việc" (`<Link href="/schedule">`) —
                        lịch trực đã nằm trong chính bảng tuần. Muốn trả lại thì
                        dựng lại ở đúng chỗ này.

                    Chỗ hai ô ấy nay là bộ chọn tuần + nút "Hôm nay", trước nằm
                    trên một tấm thẻ trắng riêng bên dưới (đã bỏ luôn tấm thẻ). */}
                <div className="relative ml-auto flex items-center rounded-xl border border-line bg-surface px-2 py-1 text-xs">
                    <button
                      type="button"
                      aria-label="Tuần trước"
                      onClick={() => setWeekOffset((w) => w - 1)}
                      className="p-1 hover:text-brand-600"
                    >
                      <ChevronLeft size={14} />
                    </button>
                    {/* Bấm vào nhãn tuần để mở LỊCH THÁNG. Đặt lịch cho khách
                        vào tháng sau mà chỉ có mũi tên tuần thì phải bấm bốn,
                        năm lần và đếm nhẩm — mỗi lần lại tải lại lưới giờ. */}
                    <button
                      type="button"
                      onClick={() => setMoLichThang((v) => !v)}
                      aria-expanded={moLichThang}
                      className="px-2 font-bold text-ink tabular-nums hover:text-brand-600"
                    >
                      {weekDays[0]?.dateStr}–{weekDays[6]?.dateStr}/
                      {weekDays[0]?.isoDate.slice(0, 4)}
                    </button>
                    <button
                      type="button"
                      aria-label="Tuần sau"
                      onClick={() => setWeekOffset((w) => w + 1)}
                      className="p-1 hover:text-brand-600"
                    >
                      <ChevronRight size={14} />
                    </button>

                    {moLichThang ? (
                      <>
                        {/* Lớp phủ để bấm ra ngoài là đóng. Không có nó thì
                            lịch chỉ đóng khi bấm đúng cái nhãn đã mở nó. */}
                        <button
                          type="button"
                          aria-label="Đóng lịch tháng"
                          onClick={() => setMoLichThang(false)}
                          className="fixed inset-0 z-40 cursor-default"
                        />
                        <div className="absolute left-1/2 top-full z-50 mt-2 -translate-x-1/2">
                          <LichThang
                            ngayChon={selectedDateIso}
                            onChon={(iso) => {
                              chonNgay(iso);
                              setWeekOffset(tuanLechSoVoiHomNay(iso));
                              setMoLichThang(false);
                            }}
                          />
                        </div>
                      </>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setWeekOffset(0);
                    chonNgay(vnToday());
                    setMoLichThang(false);
                  }}
                  className="rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-muted"
                >
                  Hôm nay
                </button>
              </div>

              {/* 2. BẢNG BÁC SĨ × TUẦN + POPUP (Tuyền duyệt 16/09/2026) — thay
                  hàng nút ngày và lưới giờ × bác sĩ cũ. Lưới cũ TỰ ĐẾM CHỖ ở
                  trình duyệt theo con số chung của phòng khám; bảng này đọc
                  "còn chỗ" từ backend (capacity_service), cùng nguồn với trigger. */}
              <div className="rounded-2xl border border-line bg-surface p-3 shadow-card">
                <BangBacSiTuan
                  weekStart={weekDays[0]?.isoDate ?? vnToday()}
                  lamMoi={bookingSeq + doiCa}
                  homNay={vnToday()}
                  bayGioPhut={phutVn(bayGio)}
                  chon={
                    oChon
                      ? { doctorId: oChon.doctorId, date: oChon.date, time: selectedSlot.time }
                      : null
                  }
                  onChonKhung={chonKhungTuBang}
                />
              </div>

              {/* Ô "3. KHUNG GIỜ KHẢ DỤNG" ĐÃ BỎ (Tuyền 16/09/2026).

                  Nó và popup của bảng tuần gọi CÙNG endpoint `/appointments/
                  quote?date=&doctor_id=` và in nhãn bằng cùng hàm `chuKhung` —
                  mỗi lần chọn khung là hai lượt gọi cho cùng một câu trả lời.
                  Đổi giờ nay bấm lại ô ngày trong bảng (ô đang chọn có viền).

                  Sức chứa của khung đang chọn nay đi kèm cú bấm trong popup
                  (`onChonKhung(...).thongTin`), không còn ô nào báo lên. */}
              {!oChon && (
                <p className="rounded-2xl border border-dashed border-line bg-surface px-4 py-6 text-center text-xs text-ink-muted">
                  Bấm một ô trong bảng để chọn bác sĩ, ngày và khung giờ.
                </p>
              )}
                </>
              )}
            </div>

            {/* COLUMN 3 (RIGHT - 320px): Thông tin đặt lịch. Ẩn hẳn khi đang
                nhập khách mới — xem ghi chú ở lưới bên trên. */}
            <aside
              className={`space-y-3.5 rounded-2xl border border-line bg-surface p-4 shadow-card ${
                mode === "new_patient" ? "hidden" : ""
              }`}
            >
              <div className="flex items-center justify-between border-b border-line pb-2.5">
                <h3 className="text-sm font-bold text-ink">Thông tin đặt lịch</h3>
                <span className="rounded-chip bg-teal-50 px-2.5 py-0.5 text-label font-bold text-teal-700">
                  Đang chọn
                </span>
              </div>

              {/* Patient info box */}
              {activePatient && (
                <div className="rounded-xl border border-line bg-surface-muted/60 p-3 space-y-2 text-xs">
                  {/* BA DÒNG, KHÔNG HAI CỘT (Tuyền 16/09/2026): tên — mã —
                      số điện thoại. Panel rộng 220px, nên tên và số chen một
                      dòng thì tên dài bị cắt giữa chừng đúng lúc người trực
                      đang đọc để gọi cho khách. */}
                  <div>
                    <div className="flex items-start gap-2">
                      <User size={15} className="mt-0.5 text-ink-muted shrink-0" />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-bold text-ink">
                            {activePatient.full_name}
                          </span>
                          {/* KHÁM LẦN MẤY — cùng nhãn, cùng luật với màn Quản
                              lý khách hàng. Người đang đặt lịch cần biết đây là
                              lần đầu hay khách đang theo một chuỗi tái khám,
                              TRƯỚC khi chọn dịch vụ. */}
                          {nhanLanKham(lanKhamGop[activePatient.clinic_patient_id]) && (
                            <span className="rounded-chip bg-brand-100 px-1.5 py-0.5 text-label font-semibold text-brand-800">
                              {nhanLanKham(
                                lanKhamGop[activePatient.clinic_patient_id],
                              )}
                            </span>
                          )}
                        </div>
                        <div className="text-label text-ink-muted font-mono">
                          {activePatient.patient_code}
                        </div>
                        <div className="mt-0.5 flex items-center gap-1 text-ink-muted font-mono">
                          <Phone size={12} className="shrink-0" />
                          <span>{activePatient.phone_primary ?? "—"}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  {/* Nút "Đổi khách hàng" đã bỏ (Quang chốt 09/08/2026): nó chỉ
                      gọi setMode("grid"), mà cột trái đã có sẵn danh sách khách
                      bấm-là-đổi. Hai đường tới cùng một chỗ, một cái thừa. */}
                </div>
              )}

              {/* LỊCH KHÁCH NÀY ĐÃ CÓ — đứng NGAY DƯỚI tên khách, trên mọi ô
                  chọn dịch vụ/bác sĩ/giờ. Để xuống cuối thì nó nằm sau nút "Đặt
                  lịch hẹn", tức là người ta chỉ đọc được sau khi đã bấm. */}
              {activePatient && (
                <LichSapToiCuaKhach
                  tra={traLichCu}
                  onDaDoi={() => setLanDoiLich((n) => n + 1)}
                  tenDichVu={(id) =>
                    cleanServices.find((sv) => sv.id === id)?.label ?? ""
                  }
                  tenBacSi={(id) => doctors.find((d) => d.id === id)?.label ?? ""}
                />
              )}

              <div className="space-y-2 text-xs">
                <div className="flex justify-between border-b border-line/60 pb-1.5">
                  <span className="text-ink-muted">Dịch vụ:</span>
                  <span
                    className={
                      selectedServiceName
                        ? "font-bold text-ink"
                        : "font-semibold text-warning"
                    }
                  >
                    {selectedServiceName || "Chưa chọn"}
                  </span>
                </div>
                <div className="flex justify-between border-b border-line/60 pb-1.5">
                  <span className="text-ink-muted">Bác sĩ:</span>
                  <span
                    className={
                      selectedSlot.doctorId
                        ? "font-bold text-ink"
                        : "font-semibold text-warning"
                    }
                  >
                    {!oChon
                      ? "Chưa chọn"
                      : selectedSlot.doctorId
                        ? selectedSlot.doctorName
                        : "Quản lý sẽ xếp"}
                  </span>
                </div>
              </div>

              {/* Selected Slot Time Box */}
              <div className="rounded-xl border border-teal-200 bg-teal-50/60 p-3 flex items-center gap-3">
                <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-teal-600 text-white shadow-xs">
                  <CalendarIcon size={18} />
                </div>
                <div>
                  {/* NGÀY THẬT, KHÔNG PHẢI CHUỖI VIẾT CỨNG. Chỗ này từng ghi
                      thẳng "Thứ Sáu, 15/05/2026" và độ dài khung 15 phút, nên
                      thẻ xác nhận nói một ngày khác hẳn ngày đang chọn trên
                      lưới. Người đặt đọc dòng này ngay trước khi bấm — nó là
                      cơ hội cuối để phát hiện đặt nhầm ngày, và nó đang nói
                      dối. */}
                  <div className="text-xs font-bold text-teal-800">
                    {oChon && selectedSlot.time
                      ? slotRange(selectedSlot.time, slotMinutes)
                      : "Chưa chọn khung giờ"}
                  </div>
                  {oChon && (
                    <div className="text-label text-teal-700 font-medium">
                      {dayLabel(oChon.date)},{" "}
                      {oChon.date.split("-").reverse().join("/")}
                    </div>
                  )}
                </div>
              </div>

              {/* SỨC CHỨA — cùng nguồn với lưới khung giờ (quote), không tự đếm. */}
              <div className="flex items-center justify-between text-xs rounded-xl bg-surface-muted p-2.5 border border-line">
                <span className="text-ink-muted font-medium flex items-center gap-1.5">
                  <Users size={13} className="text-brand-600" />
                  Sức chứa:
                </span>
                <span className="font-bold text-ink">
                  {!oChon || !thongTinKhung
                    ? "—"
                    : // Tuần chưa công bố lịch trực thì KHÔNG có trần nào để
                      // so — chỉ nói "đặt tự do". Con số "0 đã đặt" đứng trước
                      // nó đọc như một hạn mức đang đếm dần (Tuyền 16/09/2026).
                      thongTinKhung.datTuDo
                      ? "đặt tự do"
                      : thongTinKhung.khung
                        ? `${thongTinKhung.khung.regular_used}/${thongTinKhung.khung.regular_cap} đã đặt · còn ${thongTinKhung.khung.con_lai} chỗ`
                        : "—"}
                </span>
              </div>

              {/* KÊNH ĐẶT — không còn gán cứng HOTLINE (16/09/2026). */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-ink" htmlFor="kenh-dat">
                  Kênh đặt
                </label>
                <select
                  id="kenh-dat"
                  value={kenhDat}
                  onChange={(e) => setKenhDat(e.target.value)}
                  className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-xs text-ink"
                >
                  {CHANNELS_CHON.filter(
                    (c) => c.id !== "WALK_IN" || checkInDuoc,
                  ).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
                {kenhDat === KENH_GIOI_THIEU ? (
                  <input
                    value={gioiThieu}
                    onChange={(e) => setGioiThieu(e.target.value)}
                    maxLength={200}
                    placeholder="Ai giới thiệu? (lưu vào hồ sơ khám)"
                    aria-label="Người giới thiệu"
                    className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-xs text-ink"
                  />
                ) : null}
              </div>

              {/* Note */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-ink">Ghi chú</label>
                <textarea
                  rows={2}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Thêm ghi chú cho phòng khám..."
                  className="w-full rounded-xl border border-line p-2.5 text-xs text-ink outline-none focus:border-brand-500"
                />
              </div>

              {/* Khối "Thông tin xác nhận" đã bỏ (Quang chốt 09/08/2026).
                  Ba ô tích mặc định BẬT và không nơi nào đọc tới — chúng không
                  chặn nút Đặt lịch hẹn, không đi vào payload, không được ghi
                  lại. Người dùng nhìn thấy ba dấu tích và tin rằng mình vừa xác
                  nhận điều gì đó; thật ra không có gì xảy ra cả. */}

              {/* Lỗi hiện ngay cạnh nút vừa bấm, thay cho alert() — hộp thoại
                  native chặn luồng, không theo giao diện chung và trên điện
                  thoại thì gần như không đọc được. */}
              {bookingError ? (
                <p
                  role="alert"
                  className="rounded-xl border border-danger/30 bg-danger-bg px-3 py-2 text-xs text-danger"
                >
                  {bookingError}
                </p>
              ) : null}

              {/* XÁC NHẬN NGAY TẠI PANEL — xem ghi chú ở justBooked. */}
              {justBooked ? (
                <div className="rounded-xl border border-success/40 bg-success/10 p-3 text-xs text-success">
                  <div className="flex items-center gap-2 font-bold">
                    <CheckCircle2 size={16} />
                    Đã đặt lịch xong
                  </div>
                  <div className="mt-1.5 leading-relaxed text-ink">
                    <b>{justBooked.name}</b> · {justBooked.time} ·{" "}
                    {justBooked.doctor}
                  </div>
                  <p className="mt-1.5 text-label text-ink-muted">
                    Lịch đã có hiệu lực, không cần bấm lại. Muốn đổi hoặc huỷ
                    thì vào Quản lý khách hàng → Lịch hẹn sắp tới.
                  </p>
                  <div className="mt-2.5 flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        chonKhach(null);
                      }}
                      className="flex-1 rounded-lg bg-brand-600 py-2 text-xs font-bold text-white hover:bg-brand-700"
                    >
                      Đặt cho khách khác
                    </button>
                    <button
                      type="button"
                      onClick={() => setJustBooked(null)}
                      className="flex-1 rounded-lg border border-line bg-surface py-2 text-xs font-semibold text-ink hover:bg-surface-sunken"
                    >
                      Đặt thêm cho khách này
                    </button>
                  </div>
                </div>
              ) : (
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => chonKhach(null)}
                  className="flex-1 rounded-xl border border-line bg-surface py-2.5 text-xs font-semibold text-ink hover:bg-surface-sunken"
                >
                  Hủy chọn
                </button>
                <button
                  type="button"
                  onClick={handleConfirmBooking}
                  // Bác sĩ không có lịch ⇒ backend sẽ từ chối. Tắt nút ở đây để
                  // người dùng biết TRƯỚC khi bấm, thay vì gõ xong ghi chú rồi
                  // mới nhận một câu từ chối.
                  disabled={
                    bookingLoading ||
                    !activePatient ||
                    !policy ||
                    // Sau khi đặt xong khung giờ bị bỏ chọn (xem justBooked).
                    // Không chặn ở đây thì bấm "Đặt thêm cho khách này" rồi bấm
                    // luôn sẽ gửi một giờ rỗng xuống backend.
                    !selectedSlot.time ||
                    // Chưa chọn dịch vụ thì backend sẽ từ chối; nói trước ở đây.
                    !selectedServiceId ||
                    !oChon ||
                    Boolean(
                      thongTinKhung?.khung &&
                        !thongTinKhung.datTuDo &&
                        thongTinKhung.khung.con_lai <= 0,
                    )
                  }
                  className="flex-[1.5] rounded-xl bg-brand-600 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 disabled:opacity-50"
                >
                  {bookingLoading ? "Đang xử lý..." : "Đặt lịch hẹn"}
                </button>
              </div>
              )}
            </aside>
          </div>
      </div>
    </div>
  );
}
