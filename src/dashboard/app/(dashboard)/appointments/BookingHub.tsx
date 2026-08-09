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
import Link from "next/link";
import { fmtTime, slotRange, VN_TZ, vnLocalToUtcISO } from "@/lib/datetime";
import { isDeadStatus } from "@/lib/slot-capacity";
import { dayLabel } from "@/lib/roster";
import { useBookingPolicy } from "../BookingPolicyContext";
import NewPatientForm, {
  type Option,
  type ProvinceOpt,
} from "../patients/new/NewPatientForm";

export interface PatientLite {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  phone_primary: string | null;
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
  services: Option[];
  doctors: Option[];
  provinces: ProvinceOpt[];
  patients: PatientLite[];
  appts: ApptLite[];
}

const DAY_NAMES = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

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
  const anchor = new Date(`${anchorIso}T12:00:00+07:00`);
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
    const d = new Date(`${iso}T12:00:00+07:00`);
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

      <div className="mt-2 grid grid-cols-7 gap-0.5 text-center text-[10px] text-ink-faint">
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

/** Các khung giờ của một ngày, theo GIỜ MỞ CỬA CỦA PHÒNG KHÁM.
 *
 *  Trước đây hàm này viết cứng `startHour = isWeekend ? 8 : 17; endHour = 22`
 *  — lịch của Dr4Women nung vào bundle. Hai vấn đề, và cái đầu đã xảy ra:
 *
 *   * lib/roster.ts nói phòng khám đóng cửa lúc 23:00, hàm này nói 22:00. Bác
 *     sĩ đăng ký được ca 22:00–23:00 mà CSKH không đặt lịch vào được — một
 *     tiếng mỗi tối biến mất giữa hai file, không ai báo lỗi;
 *   * phòng khám thứ hai không thể có giờ khác chừng nào nó còn là hằng số.
 *
 *  Giờ cả hai đọc `clinic.settings.hours` qua BookingPolicy. `stepMinutes`
 *  cũng từ đó — lưới 15 phút trong một phòng khám cấu hình 30 phút là mời lễ
 *  tân bấm vào ô mà trigger sẽ từ chối. */
function generateSlotsForDate(
  isoDate: string,
  stepMinutes: number,
  hours: Record<string, { open: string; close: string }>,
): string[] {
  const dow = new Date(`${isoDate}T12:00:00+07:00`).getUTCDay();
  const today = hours[String(dow)];
  if (!today) return []; // thứ không có trong cấu hình = đóng cửa

  const toMin = (hhmm: string): number => {
    const [h, m] = hhmm.split(":").map(Number);
    return (h ?? 0) * 60 + (m ?? 0);
  };
  const open = toMin(today.open);
  const close = toMin(today.close);
  if (close <= open) return []; // open === close = nghỉ

  const slots: string[] = [];
  // Nửa mở: khung cuối BẮT ĐẦU trước giờ đóng cửa, không phải kết thúc đúng nó.
  for (let m = open; m < close; m += stepMinutes) {
    slots.push(
      `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`,
    );
  }
  return slots;
}

type SlotTone =
  | "available"
  | "few"
  | "holding"
  | "loading"
  | "full"
  | "selected";

/** Trả lời của GET /api/appointments/quote — sức chứa hiệu lực từng khung. */
interface QuoteResponse {
  closed?: boolean;
  /** Ngày đó đã xếp ca và bác sĩ này KHÔNG có tên trong lịch. */
  off_duty?: boolean;
  /** Ngày đó ĐÃ có lịch trực được duyệt hay chưa. `false` = phòng khám chưa
   *  xếp ca cho ngày này, nên chưa biết ai khám — khác hẳn "đã xếp và bác sĩ
   *  này nghỉ" (`off_duty`). */
  roster_known?: boolean;
  /** Ca trực của bác sĩ hôm đó, theo phút-trong-ngày `[[bắt đầu, kết thúc]]`.
   *  Rỗng = không giới hạn (ngày chưa xếp ca, hoặc lưới không lọc bác sĩ). */
  shift_windows?: [number, number][];
  /** Ca trực KHÔNG phủ trọn giờ mở cửa — backend tính, vì chỉ nó biết giờ mở
   *  cửa của ngày đó. */
  partial_shift?: boolean;
  slots?: {
    time: string;
    regular_cap: number;
    walkin_cap: number;
  }[];
}

interface CellStatus {
  tone: SlotTone;
  label: string;
  sub: string;
  bookedCount: number;
  maxCap: number;
}

/** Một chỗ đang được người khác giữ — trả từ /api/appointments/slot-hold. */
interface SlotHoldLite {
  doctor_id: string | null;
  slot_start: string;
  held_by_name: string | null;
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
        className={`grid size-5 place-items-center rounded-full text-[11px] font-bold ${vien}`}
      >
        {xong ? "✓" : so}
      </span>
      <span className={chu}>{nhan}</span>
      {ghiChu ? (
        <span className="text-[11px] font-normal text-ink-faint">({ghiChu})</span>
      ) : null}
    </div>
  );
}

export default function BookingHub({
  locations,
  services,
  doctors,
  provinces,
  patients,
  appts,
}: Props) {
  const router = useRouter();
  const policy = useBookingPolicy();
  // SỐ CHỖ KHÔNG CÓ MẶC ĐỊNH. Trước đây là `(policy?.regularCap ?? 3) +
  // (policy?.walkinCap ?? 0)` — số 3 không trùng với mặc định 2 ở bất kỳ chỗ nào
  // khác trong hệ thống, nên khi backend im lặng thì lưới mời đặt vào chỗ thứ ba
  // mà trigger sẽ từ chối. Thiếu luật ⇒ 0 ⇒ lưới khoá (xem gridLocked bên dưới).
  const dynamicCap = policy ? policy.regularCap + policy.walkinCap : 0;

  // LƯỚI VẪN PHẢI HIỆN KHI CHƯA ĐỌC ĐƯỢC LUẬT — CHỈ LÀ KHÔNG ĐẶT ĐƯỢC.
  //
  // Tôi từng để `slotMinutes ? generateSlots(...) : []`, và đó là một lỗi tệ hơn
  // cái nó định sửa: backend không trả lời thì màn "Đặt lịch" hiện ra TRỐNG
  // TRƠN. Một màn trắng không nói được nó đang hỏng hay đang tải hay hôm nay
  // không có ca — người dùng chỉ thấy hệ thống biến mất.
  //
  // Hai điều cần đồng thời đúng:
  //   * KHÔNG mời đặt vào một lưới vẽ theo con số bịa (booking-policy.ts);
  //   * KHÔNG xoá màn hình của người đang làm việc.
  //
  // Nên khi thiếu luật, lưới vẫn vẽ ở bước 15 phút NHƯNG mọi ô bị khoá và nút
  // đặt lịch tắt. Không có gì sai có thể được ghi xuống, mà bố cục vẫn còn đó để
  // người dùng biết mình đang ở đâu. Đây là khung xương, không phải một luật —
  // khác biệt nằm ở chỗ không bấm được.
  const gridLocked = !policy;
  const PROVISIONAL_STEP_MIN = 15;
  const slotMinutes = policy?.slotMinutes ?? PROVISIONAL_STEP_MIN;

  const [mode, setMode] = useState<"grid" | "new_patient">("grid");
  const [weekOffset, setWeekOffset] = useState(0);
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
  const [selectedDateIso, setSelectedDateIso] = useState(vnToday);

  const weekDays = useMemo(() => weekOf(vnToday(), weekOffset), [weekOffset]);

  const timeSlots = useMemo(
    () =>
      policy
        ? generateSlotsForDate(selectedDateIso, slotMinutes, policy.hours)
        : [],
    [selectedDateIso, slotMinutes, policy],
  );

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
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // `?bn=<mã bệnh nhân>` — CSKH bấm "Đặt lịch mới" từ màn Quản lý khách hàng
  // thì sang đây phải thấy ĐÚNG người vừa mở, không phải người đầu danh sách.
  // Trước đây nút ấy mở một modal dựng sẵn nên không cần truyền gì; nay nó đi
  // tới màn thật, và mất người đang chọn giữa đường là bắt CSKH tìm lại.
  //
  // Chỉ đọc MỘT LẦN làm giá trị khởi tạo: sau đó người dùng đổi khách trong
  // màn này là quyền của họ, URL không được kéo ngược lựa chọn về.
  const bnParam = useSearchParams().get("bn");
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
  const activePatient = useMemo(
    () =>
      selectedPatientId === null
        ? null
        : (patients.find((p) => p.clinic_patient_id === selectedPatientId) ??
          null),
    [patients, selectedPatientId],
  );

  // Selected Slot
  const [selectedSlot, setSelectedSlot] = useState<{
    doctorId: string;
    doctorName: string;
    time: string;
  }>({
    doctorId: doctors[0]?.id ?? "",
    doctorName: doctors[0]?.label ?? "Bác sĩ",
    time: "18:00",
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
    setJustBooked(null);
  }

  const [note, setNote] = useState("");
  const [chkCustomer, setChkCustomer] = useState(true);
  const [chkService, setChkService] = useState(true);
  const [chkDocSlot, setChkDocSlot] = useState(true);
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
  // Chốt chống bấm hai lần. useRef chứ không useState: state chỉ đổi sau lần
  // render kế tiếp, mà hai cú click của một double-click nằm gọn TRƯỚC lần
  // render đó. Xem handleConfirmBooking.
  const submittingRef = useRef(false);
  // Khoá idempotency của LẦN ĐẶT hiện tại. Giữ qua lần thử lại của cùng một lần
  // đặt; xoá khi server đã trả lời (dù thành công hay lỗi).
  const idemKeyRef = useRef<string | null>(null);

  // Ba cột bác sĩ ở chế độ "Tất cả" — ĐÚNG THIẾT KẾ, không phải giới hạn nhầm.
  //
  // Tôi đã có lần đổi chỗ này thành `doctors` (bỏ slice) vì tưởng nó khiến các
  // bác sĩ còn lại không đặt lịch được. Sai: ô lọc bác sĩ ngay phía trên liệt kê
  // ĐỦ danh sách (`doctors.map` ở phần render), chọn ai thì lưới đổi sang đúng
  // người đó. `slice` chỉ quyết định xem lưới tổng quan hiện mấy cột.
  //
  // Và ba là con số của bố cục: lưới ba cột nằm vừa khung giữa mà không cuộn
  // ngang. Đổ mười lăm cột vào đó làm hỏng màn hình để giải quyết một vấn đề
  // không tồn tại.
  // SỐ CHỖ THẬT CỦA TỪNG Ô, đọc từ chính hàm mà trigger dùng để chặn.
  //
  // Trước đây mọi ô dùng chung `dynamicCap` = số chỗ mặc định của phòng khám,
  // nên luật riêng của một bác sĩ KHÔNG hiện ra: Trưởng ca đặt BS Thành 18:00
  // được 10 ca, lưới vẫn vẽ 3/3 rồi khoá ô ở ca thứ tư — cấu hình lưu thành
  // công mà màn hình không đổi, đúng loại "chỉnh xong chẳng thấy gì" tệ nhất.
  //
  // /appointments/quote gọi resolve_effective_cap cho TỪNG khung của ngày, nên
  // ô dãn hay co theo đúng luật ba tầng. Một request cho mỗi bác sĩ đang hiện
  // (tối đa ba cột), huỷ khi đổi ngày.
  const [capByCell, setCapByCell] = useState<
    Record<string, { regular: number; walkin: number }>
  >({});
  // Bác sĩ nào KHÔNG có lịch làm việc ngày đang chọn. Khoá theo `bác sĩ|ngày`
  // để đổi ngày không kéo theo câu trả lời của ngày cũ.
  const [offDuty, setOffDuty] = useState<Record<string, boolean>>({});
  // Ca trực, để nói "chỉ trực 08:00–12:00" thay vì lặng lẽ bớt nửa lưới. Một
  // nửa lưới biến mất không lời giải thích trông y hệt lỗi tải dữ liệu.
  const [shiftLabel, setShiftLabel] = useState<Record<string, string>>({});
  // ĐÃ ĐỌC XONG SỨC CHỨA CỦA (bác sĩ, ngày) NÀY CHƯA.
  //
  // Cần vì "chưa tải" và "ngoài ca trực" đều biểu hiện là KHÔNG CÓ dữ liệu cho
  // ô đó, mà hai thứ ấy phải hiện hai câu khác nhau: một bên là "đợi chút",
  // một bên là "bác sĩ không có mặt giờ này". Thiếu cờ này thì mọi khung ngoài
  // ca trực lại rơi về số mặc định và tiếp tục mời đặt — đúng cái vừa sửa.
  const [capLoaded, setCapLoaded] = useState<Record<string, boolean>>({});

  // CHỈ HIỆN BÁC SĨ CÓ CA NGÀY ĐANG XEM, và hiện HẾT.
  //
  // Bản cũ cắt còn ba cột đầu danh sách bất kể ai trực: bác sĩ thứ tư có ca hôm
  // nay thì không có cột nào để đặt, còn ba người đầu nghỉ vẫn chiếm chỗ kèm
  // dòng "Không có lịch làm việc ngày này" — ba cột chết giữa màn hình.
  //
  // `offDuty` chỉ bật khi ngày đó ĐÃ xếp ca và người này không có tên. Chưa đọc
  // xong thì giữ lại cột: giấu một bác sĩ vì chưa tải xong là giấu một chỗ còn
  // trống. Lưới cuộn ngang nên bao nhiêu người cũng vừa.
  const activeDoctors = useMemo(() => {
    if (selectedDoctorId !== "all") {
      const doc = doctors.find((d) => d.id === selectedDoctorId);
      return doc ? [doc] : [];
    }
    return doctors.filter(
      (d) => offDuty[`${d.id}|${selectedDateIso}`] !== true,
    );
  }, [doctors, selectedDoctorId, offDuty, selectedDateIso]);

  // NGÀY NÀY ĐÃ XẾP CA CHƯA — khoá theo ngày, không theo bác sĩ (lịch trực là
  // của cả phòng khám). `undefined` = chưa đọc xong.
  const [daXepCa, setDaXepCa] = useState<Record<string, boolean>>({});

  // CHƯA XẾP CA NGÀY NÀY ⇒ KHÔNG ĐƯA TÊN BÁC SĨ RA.
  //
  // Quang chốt 09/08/2026: *"nếu chưa có bác sĩ phân ca hôm đó thì chỉ cần hiện
  // là chọn khung giờ mong muốn — form vẫn thế nhưng không cho tên các bác sĩ
  // vào nữa. Lịch này sẽ báo về cho quản lý hệ thống, họ sẽ tự xếp bác sĩ."*
  //
  // Trước đây lưới vẫn dựng ba cột mang tên ba bác sĩ cho một ngày chưa ai
  // được xếp ca. CSKH chọn "BS Thành 09:00", nói với khách "chị được xếp BS
  // Thành", rồi tuần sau quản lý xếp ca và người khám là ai đó khác. Cái tên
  // ấy là một lời hứa mà hệ thống không có cơ sở để giữ.
  //
  // Lịch đặt trong trạng thái này đi ra với `doctor_id = null` và rơi vào màn
  // "Chờ xếp bác sĩ" (/appointments/cho-xep-bac-si) — đúng chỗ quản lý xếp.
  const chuaXepCa = daXepCa[selectedDateIso] === false;

  /** Các CỘT của lưới giờ. Ngày chưa xếp ca thì đúng MỘT cột, không tên ai. */
  const cotLuoi = useMemo(
    () =>
      chuaXepCa
        ? [{ id: "", label: "Khung giờ mong muốn" }]
        : activeDoctors.map((d) => ({ id: d.id, label: d.label })),
    [chuaXepCa, activeDoctors],
  );

  // Handle doctor filter selection
  function handleDoctorFilterChange(docId: string) {
    setSelectedDoctorId(docId);
    if (docId !== "all") {
      const doc = doctors.find((d) => d.id === docId);
      if (doc) {
        setSelectedSlot((prev) => ({
          ...prev,
          doctorId: doc.id,
          doctorName: doc.label,
        }));
      }
    }
  }

  // Filtered patients for search list
  const filteredPatients = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) =>
        p.full_name.toLowerCase().includes(q) ||
        (p.phone_primary ?? "").includes(q) ||
        p.patient_code.toLowerCase().includes(q),
    );
  }, [patients, searchQuery]);

  // Lịch của NGÀY ĐANG CHỌN.
  //
  // `appts` từ server chỉ chứa lịch HÔM NAY (page.tsx dùng vnTodayRangeUtc).
  // Chừng nào dải ngày còn là bảy hằng số của tháng Năm thì điều đó không lộ ra;
  // khi lưới đi được sang ngày khác, mọi ngày không phải hôm nay sẽ hiện trống
  // trơn — tệ hơn hẳn con số sai, vì nó trông như một ngày thật sự còn chỗ.
  //
  // GET /api/appointments?date= đã có sẵn (và giờ đã có gate vai + trần 500
  // dòng). Ngày hôm nay dùng luôn dữ liệu server để không tốn một vòng mạng cho
  // thứ vừa render xong.
  // DẪN XUẤT, KHÔNG SAO CHÉP VÀO STATE. Bản đầu giữ một `apptsForDate` rồi
  // đồng bộ nó trong effect bằng setState cho nhánh "hôm nay" — đúng thứ
  // react-hooks/set-state-in-effect chặn, và có lý do: nó render hai lần cho một
  // dữ liệu vốn đã có sẵn trong props.
  /** Phút-trong-ngày → "HH:MM", cho nhãn ca trực. */
  const minLabel = (m: number) =>
    `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

  const [todayIso] = useState(vnToday);
  const [fetchedByDate, setFetchedByDate] = useState<
    Record<string, ApptLite[]>
  >({});
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

  const isToday = selectedDateIso === todayIso;
  const apptsForDate = isToday ? appts : fetchedByDate[selectedDateIso];
  // undefined = CHƯA BIẾT, khác hẳn [] = "ngày này trống". Phân biệt hai thứ đó
  // là điều quan trọng nhất ở đây: coi "chưa tải xong" là "còn chỗ" thì lưới
  // mời đặt vào một khung có thể đã kín.
  const dateLoading = !isToday && apptsForDate === undefined;

  useEffect(() => {
    if (isToday || fetchedByDate[selectedDateIso] !== undefined) return;
    const ctrl = new AbortController();
    fetch(`/api/appointments?date=${selectedDateIso}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("load failed"))))
      .then((d: { appointments?: ApptLite[] }) =>
        setFetchedByDate((prev) => ({
          ...prev,
          [selectedDateIso]: d.appointments ?? [],
        })),
      )
      .catch(() => {
        // Để nguyên `undefined` → lưới tiếp tục nói "đang tải" thay vì tự tin
        // báo còn chỗ. Chỉ báo realtime ở đầu màn nói kênh có hỏng hay không.
      });
    return () => ctrl.abort();
  }, [selectedDateIso, isToday, fetchedByDate]);

  const activeDoctorIds = activeDoctors.map((d) => d.id).join(",");

  useEffect(() => {
    if (!policy || !activeDoctorIds) return;
    const ctrl = new AbortController();
    // Chuỗi rỗng = HỎI SỨC CHỨA CHUNG, không lọc bác sĩ. Cần cho cột "khung giờ
    // mong muốn" của ngày chưa xếp ca — ô ở đó không thuộc bác sĩ nào, nên số
    // chỗ của nó cũng phải là số chung chứ không phải của một người cụ thể.
    const ids = [...activeDoctorIds.split(","), ""];
    Promise.all(
      ids.map((docId) =>
        fetch(
          `/api/appointments/quote?date=${selectedDateIso}` +
            (docId ? `&doctor_id=${docId}` : ""),
          { signal: ctrl.signal },
        )
          .then((r) => (r.ok ? r.json() : null))
          .then((d: QuoteResponse | null) => [docId, d] as const)
          .catch(() => [docId, null] as const),
      ),
    ).then((pairs) => {
      if (ctrl.signal.aborted) return;
      const next: Record<string, { regular: number; walkin: number }> = {};
      const off: Record<string, boolean> = {};
      const shifts: Record<string, string> = {};
      const loaded: Record<string, boolean> = {};
      // Lịch trực là của cả ngày, nên bất kỳ câu trả lời nào cũng nói được —
      // lấy câu ĐẦU TIÊN đọc được, và bỏ qua nếu cả loạt đều hỏng.
      const daXep = pairs.find(([, d]) => d?.roster_known !== undefined)?.[1]
        ?.roster_known;
      for (const [docId, d] of pairs) {
        // `d === null` = request hỏng ⇒ KHÔNG đánh dấu đã tải, để lưới nói
        // "đang tải" thay vì kết luận cả ngày ngoài ca trực.
        loaded[`${docId}|${selectedDateIso}`] = d !== null;
        off[`${docId}|${selectedDateIso}`] = d?.off_duty === true;
        // Chỉ nói khi ca KHÔNG phủ trọn giờ mở cửa — trực cả ngày là chuyện
        // thường, dán nhãn cho mọi cột chỉ làm loãng cái nhãn cần đọc.
        const w = d?.shift_windows ?? [];
        shifts[`${docId}|${selectedDateIso}`] = d?.partial_shift
          ? w.map(([a, b]) => `${minLabel(a)}–${minLabel(b)}`).join(", ")
          : "";
        for (const s of d?.slots ?? []) {
          next[`${docId}|${selectedDateIso}|${s.time}`] = {
            regular: s.regular_cap,
            walkin: s.walkin_cap,
          };
        }
      }
      // Gộp thay vì thay: đổi bộ lọc bác sĩ không nên xoá số chỗ của các cột
      // vừa đọc xong, nếu không lưới nhấp nháy về "chưa biết" mỗi lần lọc.
      setCapByCell((prev) => ({ ...prev, ...next }));
      setOffDuty((prev) => ({ ...prev, ...off }));
      setShiftLabel((prev) => ({ ...prev, ...shifts }));
      setCapLoaded((prev) => ({ ...prev, ...loaded }));
      if (daXep !== undefined) {
        setDaXepCa((prev) => ({ ...prev, [selectedDateIso]: daXep }));
      }
    });
    return () => ctrl.abort();
    // `bookingSeq` đổi sau mỗi lần đặt thành công: số chỗ ĐÃ DÙNG nằm trong
    // chính câu trả lời này, nên không đọc lại thì ô vừa đặt vẫn vẽ là trống.
  }, [selectedDateIso, activeDoctorIds, policy, bookingSeq]);

  // Số lịch còn giữ chỗ, gom theo (bác sĩ, ngày VN, giờ VN).
  //
  // HAI LỖI ĐƯỢC SỬA Ở ĐÂY, VÀ CẢ HAI ĐỀU IM LẶNG.
  //
  // 1. So sánh múi giờ. Bản cũ làm `a.slot_start.slice(11, 16)` — cắt chuỗi ISO
  //    UTC để lấy "HH:mm" rồi đem so với nhãn giờ VN trên lưới. Một lịch 18:00
  //    giờ VN nằm trong database là 11:00Z, nên phép so sánh KHÔNG BAO GIỜ đúng.
  //    Hệ quả: mọi ô luôn hiện "Có thể đặt · 0/N", kể cả khung đã kín, và CSKH
  //    chỉ biết mình đặt trùng khi trigger trả về lỗi 409.
  //
  // 2. Không lọc theo NGÀY. Bản cũ chỉ so giờ, nên nếu phép so sánh có đúng thì
  //    một lịch 18:00 của thứ Ba vẫn được đếm vào ô 18:00 của thứ Năm.
  //
  // Trạng thái chết (CANCELLED/NO_SHOW/DOCTOR_DECLINED) không giữ chỗ — cùng
  // danh sách với lib/slot-capacity.ts và DEAD_STATUSES ở booking_service.py.
  // CHỖ NGƯỜI KHÁC ĐANG GIỮ — khoá "docId|ngày|giờ", giống usageByCell.
  //
  // Trước đây ô bị dán nhãn "Đang giữ" khi có LỊCH HẸN ở trạng thái
  // WAITING/CSKH_CONFIRMED — tức là gọi một ghế ĐÃ BÁN là "đang giữ". Hai thứ
  // đó khác nhau, và gộp lại thì CSKH thứ hai không biết khung nào còn chỗ
  // thật. Giờ nó đọc từ slot_hold: có người đang mở form ở khung này.
  const [heldByOthers, setHeldByOthers] = useState<Map<string, string>>(
    new Map(),
  );

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch(`/api/appointments/slot-hold?date=${selectedDateIso}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d: { items?: SlotHoldLite[] } | null) => {
          if (!alive || !d?.items) return;
          const m = new Map<string, string>();
          for (const h of d.items) {
            const dt = new Date(h.slot_start);
            if (Number.isNaN(dt.getTime())) continue;
            const isoDate = dt.toLocaleDateString("en-CA", { timeZone: VN_TZ });
            m.set(
              `${h.doctor_id ?? ""}|${isoDate}|${fmtTime(dt)}`,
              h.held_by_name ?? "người khác",
            );
          }
          setHeldByOthers(m);
        })
        .catch(() => {
          // Đọc không được thì giữ bản đồ cũ. Xoá sạch nghĩa là mọi ô đột ngột
          // hiện "còn trống" — đúng câu khẳng định gây đặt trùng.
        });
    const t = setTimeout(load, 0);
    // Chỗ giữ sống tối đa 10 phút và người khác bấm liên tục, nên phải làm mới.
    const iv = setInterval(load, 15000);
    return () => {
      alive = false;
      clearTimeout(t);
      clearInterval(iv);
    };
  }, [selectedDateIso]);

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

  const usageByCell = useMemo(() => {
    const m = new Map<string, ApptLite[]>();
    for (const a of apptsForDate ?? []) {
      if (!a.slot_start || isDeadStatus(a.status)) continue;
      const d = new Date(a.slot_start);
      if (Number.isNaN(d.getTime())) continue;
      const isoDate = d.toLocaleDateString("en-CA", { timeZone: VN_TZ });
      const hhmm = fmtTime(d);
      const key = `${a.doctor_id ?? ""}|${isoDate}|${hhmm}`;
      const arr = m.get(key);
      if (arr) arr.push(a);
      else m.set(key, [a]);
    }
    return m;
  }, [apptsForDate]);

  /** Khung `time` của ngày đang xem đã kết thúc chưa.
   *
   * So bằng GIỜ KẾT THÚC, không phải giờ bắt đầu: khung 18:00–18:15 lúc 18:05
   * thì chưa qua, và khách vãng lai bước vào giữa khung phải xếp được vào chính
   * khung đang chạy. Cùng luật với backend.
   */
  function khungDaQua(time: string): boolean {
    // KHÔNG CÓ GIỜ THÌ KHÔNG CÓ MỐC ĐỂ SO — và gọi tiếp là làm vỡ cả màn hình.
    //
    // `vnLocalToUtcISO(ngày, "")` dựng chuỗi "2026-08-29T:00+07:00" → Invalid
    // Date → `.toISOString()` NÉM RangeError. Hàm này chạy TRONG LÚC RENDER
    // (qua selectedCellStatus), nên lỗi ném ra làm React bỏ cả cây và error
    // boundary hiện "Màn hình gặp trục trặc".
    //
    // `selectedSlot.time` rỗng ở hai lúc rất thường: vừa đổi ngày (chonNgay bỏ
    // chọn khung giờ để không đặt nhầm sang ngày mới) và vừa đặt lịch xong
    // (cũng bỏ chọn để không bấm ra lịch thứ hai). Đây không phải trường hợp
    // hiếm — nó là đường đi bình thường của mọi lần đặt lịch.
    if (!time) return false;
    const ketThuc = new Date(vnLocalToUtcISO(selectedDateIso, time));
    ketThuc.setMinutes(ketThuc.getMinutes() + slotMinutes);
    return ketThuc.getTime() <= bayGio;
  }

  function getCellStatus(docId: string, time: string): CellStatus {
    // Chưa chọn khung giờ nào — trả về một trạng thái trung tính thay vì đi
    // tiếp và dựng mốc thời gian từ một chuỗi rỗng.
    if (!time) {
      return {
        tone: "available",
        label: "Chưa chọn khung giờ",
        sub: "—",
        bookedCount: 0,
        maxCap: 0,
      };
    }
    // KHUNG ĐÃ TRÔI QUA — luật cao hơn cả lịch làm việc, vì không ai đặt được
    // vào một thời điểm đã đi qua dù bác sĩ có rảnh hay không.
    //
    // Backend là chốt thật (booking_service._chan_dat_vao_qua_khu). Ở đây chỉ
    // để CSKH không bấm vào một ô rồi mới bị từ chối: trước khi có cả hai lớp,
    // lúc 16:40 vẫn đặt được lịch cho 16:20 và server trả 201.
    if (khungDaQua(time)) {
      return {
        tone: "full",
        label: "Đã qua giờ",
        sub: "—",
        bookedCount: 0,
        maxCap: 0,
      };
    }
    // LỊCH LÀM VIỆC LÀ LUẬT CAO NHẤT — trước cả sức chứa.
    //
    // Một luật "18:00–18:15 tám chỗ" không có nghĩa gì vào ngày bác sĩ không đi
    // làm. Backend đã trả lời câu đó (quote.off_duty, chỉ bật khi ngày ấy ĐÃ
    // xếp ca), nên ở đây chỉ việc nói ra thay vì mời đặt.
    if (offDuty[`${docId}|${selectedDateIso}`]) {
      return {
        tone: "full",
        label: "Không có lịch",
        sub: "—",
        bookedCount: 0,
        maxCap: 0,
      };
    }
    // Luật riêng của ô này nếu đã đọc được; chưa đọc xong thì tạm dùng mặc định
    // phòng khám — cùng con số mà backend sẽ trả về nếu ô không có luật riêng,
    // nên nó không phải một phỏng đoán mới.
    const cell = capByCell[`${docId}|${selectedDateIso}|${time}`];
    // Đã đọc xong mà khung này KHÔNG có trong câu trả lời ⇒ nó nằm ngoài ca
    // trực của bác sĩ (hoặc ngoài giờ mở cửa). Không phải "còn chỗ".
    if (!cell && capLoaded[`${docId}|${selectedDateIso}`]) {
      return {
        tone: "full",
        label: "Ngoài ca trực",
        sub: "—",
        bookedCount: 0,
        maxCap: 0,
      };
    }
    const maxCap = Math.max(
      1,
      cell ? cell.regular + cell.walkin : dynamicCap,
    );
    // Chưa có luật ⇒ chưa biết khung này mấy chỗ. Trả về "full" để mọi ô render
    // ở nhánh disabled sẵn có, thay vì thêm một tone mới chỉ dùng cho lúc hỏng.
    if (gridLocked) {
      return {
        tone: "full",
        label: "Chưa có luật",
        sub: "—",
        bookedCount: 0,
        maxCap,
      };
    }
    // Chưa biết ngày này có gì thì nói là chưa biết. Vẽ "Có thể đặt" trong lúc
    // còn đang tải là câu khẳng định duy nhất ở màn này có thể gây đặt trùng.
    if (dateLoading) {
      // TONE RIÊNG, KHÔNG MƯỢN "holding".
      //
      // Xanh dương ở lưới này có đúng MỘT nghĩa: "một CSKH khác đang chọn ô
      // đó". Cho ô "đang tải" mượn cùng màu là dạy người dùng rằng màu ấy đôi
      // khi chẳng nghĩa gì — và lúc nó thật sự nghĩa gì thì không ai tin nữa.
      return {
        tone: "loading",
        label: "Đang tải…",
        sub: "—",
        bookedCount: 0,
        maxCap,
      };
    }
    const matchingAppts =
      usageByCell.get(`${docId}|${selectedDateIso}|${time}`) ?? [];
    const bookedCount = matchingAppts.length;
    const isSelected =
      selectedSlot.doctorId === docId && selectedSlot.time === time;

    // Ô đang chọn vẫn phải nói SỰ THẬT về sức chứa. Bản cũ trả cứng
    // bookedCount: 1 cho ô được chọn, nên bấm vào một khung đã đầy thì nhãn đổi
    // thành "Còn N chỗ" — giao diện tự trấn an người dùng ngay trước khi server
    // từ chối.
    if (isSelected) {
      return {
        tone: "selected",
        label:
          bookedCount >= maxCap
            ? "Đã đầy — chọn khung khác"
            : `Còn ${maxCap - bookedCount} chỗ`,
        sub: `${bookedCount}/${maxCap}`,
        bookedCount,
        maxCap,
      };
    }

    const holder = heldByOthers.get(`${docId}|${selectedDateIso}|${time}`);
    const isHolding = Boolean(holder);

    if (bookedCount >= maxCap) {
      return {
        tone: "full",
        label: "Đã đầy",
        sub: `${bookedCount}/${maxCap}`,
        bookedCount,
        maxCap,
      };
    }
    if (isHolding) {
      return {
        tone: "holding",
        label: `${holder} đang chọn`,
        sub: `${bookedCount}/${maxCap}`,
        bookedCount,
        maxCap,
      };
    }
    if (bookedCount > 0) {
      return {
        tone: "few",
        label: `Còn ${maxCap - bookedCount} chỗ`,
        sub: `${bookedCount}/${maxCap}`,
        bookedCount,
        maxCap,
      };
    }
    return {
      tone: "available",
      label: "Có thể đặt",
      sub: `0/${maxCap}`,
      bookedCount: 0,
      maxCap,
    };
  }

  // Current slot capacity summary for right panel
  const selectedCellStatus = useMemo(
    () => getCellStatus(selectedSlot.doctorId, selectedSlot.time),
    // CỐ Ý BỎ `getCellStatus` KHỎI DEPS.
    //
    // Nó là một hàm thường, dựng lại ở MỌI lần render, nên đưa vào deps thì
    // useMemo tính lại mỗi lần — tức là không còn là memo nữa. Thứ thật sự
    // quyết định kết quả là năm giá trị dưới đây, và chúng có đủ.
    //
    // capByCell phải nằm trong đó: thiếu nó, thẻ tóm tắt bên phải giữ nguyên số
    // chỗ mặc định sau khi luật riêng của bác sĩ đã về, và hai chỗ trên cùng
    // màn hình nói hai con số khác nhau cho cùng một ô.
    //
    // `selectedDateIso` và `apptsForDate` CŨNG phải nằm trong đó, và thiếu
    // chúng là nửa còn lại của lỗi "đổi ngày mà vẫn ở khung cũ": thẻ "Sức chứa"
    // bên phải giữ nguyên con số của NGÀY TRƯỚC sau khi người dùng đã bấm sang
    // ngày khác. Người đặt đọc đúng dòng đó ngay trước khi bấm.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      selectedSlot,
      selectedDateIso,
      apptsForDate,
      appts,
      capByCell,
      offDuty,
      capLoaded,
    ],
  );

  async function handleConfirmBooking() {
    // Ngày CHƯA XẾP CA thì không có bác sĩ để chọn, và đó là hợp lệ: lịch đi ra
    // với doctor_id = null rồi rơi vào màn "Chờ xếp bác sĩ". Chặn ở đây như cũ
    // nghĩa là nút bấm không làm gì cả trong đúng trường hợp Quang vừa mô tả.
    if (!activePatient) return;
    if (!chuaXepCa && !selectedSlot.doctorId) return;
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
            new Date(`${targetDate}T00:00:00+07:00`).getTime() +
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
          booking_channel: "HOTLINE",
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
        setFetchedByDate((prev) => {
          const next = { ...prev };
          delete next[targetDate];
          return next;
        });
        setBookingSeq((n) => n + 1);
        router.refresh();
      } else {
        const err = await res.json().catch(() => ({}));
        // alert() chặn luồng, không đọc được trên điện thoại và là chỗ duy nhất
        // trong toàn app dùng nó. Lỗi hiện ngay cạnh nút đã bấm.
        setBookingError(
          err.error || err.message || err.detail || "Không thể đặt lịch.",
        );
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
              thuộc luật 2+1 mỗi khung, lịch trực của từng bác sĩ và cấu hình
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
                  title="Sức chứa còn lại phụ thuộc luật 2+1, lịch trực và cấu hình riêng từng bác sĩ — xem trực tiếp trên lưới giờ bên dưới."
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
          <div className="flex items-center justify-center gap-4 rounded-2xl border border-line bg-surface py-2.5 px-4 text-xs font-medium text-ink-muted shadow-card">
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
                ? "xl:grid-cols-[280px_1fr]"
                : "xl:grid-cols-[280px_1fr_320px]"
            }`}
          >
            {/* COLUMN 1 (LEFT - 280px): New Patient Button + Active Patient Card + Search List */}
            <aside className="space-y-3">
              {/* Nút đặt lịch cho khách hàng mới (Đặt lên trên cùng của Cột 1) */}
              <button
                type="button"
                onClick={() => {
                  // BỎ CHỌN KHÁCH CŨ. Bấm "khách mới" mà thẻ "Khách hàng đang
                  // chọn" vẫn là người trước đó thì cả cột trái lẫn panel phải
                  // đang nói về một người KHÔNG liên quan tới biểu mẫu đang mở
                  // — và nút "Đặt lịch hẹn" ở panel ấy vẫn bấm được, ra một
                  // lịch cho đúng người cũ.
                  setMode("new_patient");
                  setSelectedPatientId(null);
                  setJustBooked(null);
                }}
                className="w-full inline-flex items-center justify-center gap-2 rounded-2xl bg-brand-600 py-2.5 px-3.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 transition-all"
              >
                <UserPlus className="size-4" />
                + Đặt lịch hẹn cho khách mới
              </button>

              {/* 1. KHÁCH HÀNG ĐANG CHỌN — hoặc thẻ "khách mới" khi đang nhập.
                     Ô này không bao giờ được để trống trong lúc người dùng
                     đang làm việc: trống nghĩa là "không rõ đang đặt cho ai". */}
              {activePatient && (
                <div className="rounded-2xl border border-brand-300 bg-brand-50/50 p-3.5 shadow-card space-y-3">
                  <div className="flex items-start justify-between">
                    <span className="text-[11px] font-bold text-brand-700 uppercase tracking-wide">
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

              {/* 2. TÌM KIẾM KHÁCH HÀNG CÓ SẴN (Kéo dài tối đa max-h-[380px]) */}
              <div className="rounded-2xl border border-line bg-surface p-3.5 shadow-card space-y-2.5">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
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
                {/* Expanded scroll list */}
                <div className="max-h-[380px] overflow-y-auto divide-y divide-line text-xs pr-0.5">
                  {filteredPatients.map((p) => {
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
                          setSelectedPatientId(p.clinic_patient_id);
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
                        <div className="text-[11px] text-ink-muted">
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
                    role="CSKH"
                    locations={locations}
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

                {/* Doctor dropdown — ẩn hẳn khi ngày chưa xếp ca. Một ô lọc
                    liệt kê tên bác sĩ cho một ngày chưa ai được xếp là mời
                    người dùng chọn một cái tên không có cơ sở. */}
                <div
                  className={`items-center gap-1 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs text-ink font-medium ${
                    chuaXepCa ? "hidden" : "flex"
                  }`}
                >
                  <User size={14} className="text-ink-muted" />
                  <select
                    value={selectedDoctorId}
                    onChange={(e) => handleDoctorFilterChange(e.target.value)}
                    className="bg-transparent text-xs font-semibold text-ink outline-none cursor-pointer"
                  >
                    <option value="all">— Chọn bác sĩ —</option>
                    {doctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                </div>

                <Link
                  href="/schedule"
                  className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-50 ml-auto"
                  title="Xem lịch làm việc ca trực của bác sĩ & phòng khám"
                >
                  📅 Lịch làm việc
                </Link>

              </div>

              {/* Date navigator & legend — CĂN GIỮA cả ba hàng.
                  
                  Trước đây khối này dùng `justify-between`: nút tuần dạt trái,
                  dãy ngày dạt phải, chú thích màu dạt trái — ba hàng ba mép
                  khác nhau trên một tấm thẻ. */}
              <div className="space-y-2.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <div className="relative flex items-center rounded-xl border border-line bg-surface px-2 py-1 text-xs">
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

                {/* Day Tabs */}
                <div className="flex flex-wrap items-center justify-center gap-1 text-xs">
                  {weekDays.map((d) => {
                    const isSelectedDay = d.isoDate === selectedDateIso;
                    return (
                      <button
                        key={d.dayName}
                        type="button"
                        onClick={() => chonNgay(d.isoDate)}
                        className={`rounded-xl border px-3 py-1 font-medium transition-all ${
                          isSelectedDay
                            ? "border-teal-600 bg-teal-50 text-teal-700 font-bold"
                            : "border-line bg-surface text-ink-muted hover:border-line"
                        }`}
                      >
                        {d.dayName} {d.dateStr}
                      </button>
                    );
                  })}
                </div>

                {/* Status Legend Pills */}
                <div className="flex flex-wrap items-center justify-center gap-4 pt-1 text-xs">
                  <span className="flex items-center gap-1.5 text-teal-700 font-medium">
                    <span className="size-3.5 rounded-md border border-teal-300 bg-teal-50" />
                    Có thể đặt
                  </span>
                  <span className="flex items-center gap-1.5 text-amber-700 font-medium">
                    <span className="size-3.5 rounded-md border border-amber-300 bg-amber-50" />
                    Còn ít chỗ
                  </span>
                  <span className="flex items-center gap-1.5 text-sky-700 font-medium">
                    <span className="size-3.5 rounded-md border border-sky-300 bg-sky-50" />
                    Đang giữ
                  </span>
                  <span className="flex items-center gap-1.5 text-rose-700 font-medium">
                    <span className="size-3.5 rounded-md border border-rose-300 bg-rose-50" />
                    Đã đầy
                  </span>
                </div>
              </div>

              {chuaXepCa ? (
                <div
                  role="status"
                  className="rounded-2xl border border-warning/40 bg-warning-bg p-3 text-xs text-warning"
                >
                  <span className="font-semibold">
                    Ngày này chưa xếp lịch làm việc.
                  </span>{" "}
                  Chọn khung giờ khách mong muốn — hệ thống chưa biết ai khám
                  hôm đó nên không đưa tên bác sĩ ra ở đây. Lịch đặt xong sẽ nằm
                  ở màn <b>Chờ xếp bác sĩ</b> để quản lý phân người; khi đã có
                  bác sĩ, khách này hiện lại ở Quản lý khách hàng để CSKH gọi
                  xác nhận lịch và bác sĩ khám.
                </div>
              ) : null}

              {/* Table Grid (FIRST COLUMN = TIME RANGE e.g. 18:00 - 18:15, NO INNER GRID LINES) */}
              {/* CUỘN NGANG khi có nhiều bác sĩ trực hơn bề ngang màn hình.
                  Trước đây lưới cắt cứng còn ba cột nên người thứ tư có ca hôm
                  nay đơn giản là không đặt được. `min-w-max` để các cột giữ bề
                  rộng tối thiểu thay vì bị bóp lại đến mức không đọc nổi. */}
              <div className="overflow-x-auto rounded-2xl border border-line bg-surface shadow-card p-2">
                {/* Doctor Header Row */}
                <div
                  className="grid min-w-max text-xs font-bold text-ink text-center pb-2 border-b border-line"
                  style={{
                    gridTemplateColumns: `110px repeat(${cotLuoi.length}, minmax(170px, 1fr))`,
                  }}
                >
                  <div className="p-2 text-ink-muted font-medium flex items-center justify-center">
                    Giờ
                  </div>
                  {cotLuoi.map((doc) => (
                    <div key={doc.id} className="p-2">
                      <div className="truncate font-bold text-ink">
                        {doc.label}
                      </div>
                      {/* Câu trả lời đặt ngay dưới TÊN BÁC SĨ, không phải ở
                          một góc màn hình: nó nói về đúng người này, và nó là
                          lý do cả cột bên dưới không bấm được. */}
                      {shiftLabel[`${doc.id}|${selectedDateIso}`] ? (
                        <div className="truncate text-[11px] font-medium text-warning">
                          Chỉ trực {shiftLabel[`${doc.id}|${selectedDateIso}`]}
                        </div>
                      ) : chuaXepCa ? (
                        <div className="truncate text-[11px] font-medium text-warning">
                          Chưa xếp ca — quản lý sẽ phân bác sĩ
                        </div>
                      ) : (
                        <div className="text-[11px] font-normal text-ink-muted truncate">
                          Phụ khoa
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {cotLuoi.length === 0 && (
                  <p className="px-3 py-8 text-center text-xs text-warning">
                    Ngày này đã xếp ca nhưng không bác sĩ nào có mặt. Chọn ngày
                    khác, hoặc báo quản lý xếp thêm người.
                  </p>
                )}

                {/* Slot Rows */}
                <div className="max-h-[480px] overflow-y-auto space-y-1 pt-1.5">
                  {timeSlots.map((time) => {
                    // Độ dài khung từ LUẬT, không phải hằng số 15. Phòng khám
                    // đổi sang khung 30 phút thì nhãn "18:00 - 18:15" sẽ nói
                    // sai về đúng cái ô nằm ngay cạnh nó.
                    const timeRangeStr = slotRange(time, slotMinutes);
                    return (
                      <div
                        key={time}
                        className="grid min-w-max text-xs items-center"
                        style={{
                          gridTemplateColumns: `110px repeat(${cotLuoi.length}, minmax(170px, 1fr))`,
                        }}
                      >
                        {/* FIRST COLUMN: TIME RANGE (e.g. 08:00 - 08:15) */}
                        <div className="p-2 text-center font-mono font-medium text-ink-muted text-[11px]">
                          {timeRangeStr}
                        </div>

                        {/* DOCTOR COLUMNS (CELLS - NO TIME TEXT INSIDE!) */}
                        {cotLuoi.map((doc) => {
                          const st = getCellStatus(doc.id, time);

                          if (st.tone === "selected") {
                            return (
                              <button
                                key={doc.id}
                                type="button"
                                className="m-1 flex items-center justify-between rounded-xl bg-teal-600 px-3 py-2 text-xs font-bold text-white shadow-xs transition-all border border-teal-700"
                              >
                                <span>
                                  {st.label} · {st.sub}
                                </span>
                                <span className="grid size-4 place-items-center rounded-full bg-white text-teal-700 text-[10px] font-extrabold">
                                  ✓
                                </span>
                              </button>
                            );
                          }

                          if (st.tone === "few") {
                            return (
                              <button
                                key={doc.id}
                                type="button"
                                onClick={() =>
                                  setSelectedSlot({
                                    doctorId: doc.id,
                                    doctorName: doc.label,
                                    time,
                                  })
                                }
                                className="m-1 flex items-center justify-center rounded-xl border border-amber-200 bg-amber-50/80 py-2 px-3 text-xs font-semibold text-amber-800 transition-all hover:bg-amber-100"
                              >
                                {st.label} · {st.sub}
                              </button>
                            );
                          }

                          if (st.tone === "loading") {
                            return (
                              <button
                                key={doc.id}
                                disabled
                                type="button"
                                className="m-1 flex animate-pulse items-center justify-center rounded-xl border border-line bg-surface-sunken py-2 px-3 text-xs font-medium text-ink-muted"
                              >
                                {st.label}
                              </button>
                            );
                          }

                          if (st.tone === "holding") {
                            return (
                              <button
                                key={doc.id}
                                type="button"
                                onClick={() =>
                                  setSelectedSlot({
                                    doctorId: doc.id,
                                    doctorName: doc.label,
                                    time,
                                  })
                                }
                                className="m-1 flex items-center justify-center rounded-xl border border-sky-200 bg-sky-50/80 py-2 px-3 text-xs font-semibold text-sky-800 transition-all hover:bg-sky-100"
                              >
                                {st.label} · {st.sub}
                              </button>
                            );
                          }

                          if (st.tone === "full") {
                            return (
                              <button
                                key={doc.id}
                                disabled
                                type="button"
                                className="m-1 flex items-center justify-center rounded-xl border border-rose-200 bg-rose-50/70 py-2 px-3 text-xs font-semibold text-rose-700 cursor-not-allowed opacity-75"
                              >
                                {st.label} · {st.sub}
                              </button>
                            );
                          }

                          return (
                            <button
                              key={doc.id}
                              type="button"
                              onClick={() =>
                                setSelectedSlot({
                                  doctorId: doc.id,
                                  doctorName: doc.label,
                                  time,
                                })
                              }
                              className="m-1 flex items-center justify-center rounded-xl border border-teal-200 bg-teal-50/60 py-2 px-3 text-xs font-semibold text-teal-800 transition-all hover:bg-teal-100/80"
                            >
                              {st.label} · {st.sub}
                            </button>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </div>
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
                <span className="rounded-full bg-teal-50 px-2.5 py-0.5 text-[11px] font-bold text-teal-700 border border-teal-200">
                  Đang chọn
                </span>
              </div>

              {/* Patient info box */}
              {activePatient && (
                <div className="rounded-xl border border-line bg-surface-muted/60 p-3 space-y-2 text-xs">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <User size={15} className="text-ink-muted shrink-0" />
                      <div>
                        <div className="font-bold text-ink">
                          {activePatient.full_name}
                        </div>
                        <div className="text-[11px] text-ink-muted font-mono">
                          {activePatient.patient_code}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-ink-muted font-mono">
                      <Phone size={12} />
                      <span>{activePatient.phone_primary ?? "—"}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setMode("grid")}
                    className="text-[11px] font-semibold text-brand-700 hover:underline pt-0.5 block"
                  >
                    Đổi khách hàng
                  </button>
                </div>
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
                    {selectedSlot.doctorId
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
                    {selectedSlot.time
                      ? slotRange(selectedSlot.time, slotMinutes)
                      : "Chưa chọn khung giờ"}
                  </div>
                  <div className="text-[11px] text-teal-700 font-medium">
                    {dayLabel(selectedDateIso)},{" "}
                    {selectedDateIso.split("-").reverse().join("/")}
                  </div>
                </div>
              </div>

              {/* Capacity Status */}
              <div className="flex items-center justify-between text-xs rounded-xl bg-surface-muted p-2.5 border border-line">
                <span className="text-ink-muted font-medium flex items-center gap-1.5">
                  <Users size={13} className="text-brand-600" />
                  Sức chứa:
                </span>
                <span className="font-bold text-ink">
                  {selectedCellStatus.bookedCount}/{selectedCellStatus.maxCap} đã đặt
                  ·{" "}
                  <span className="text-teal-700 font-bold">
                    còn {selectedCellStatus.maxCap - selectedCellStatus.bookedCount} chỗ
                  </span>
                </span>
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

              {/* Confirmation Checklist */}
              <div className="space-y-1.5 border-t border-line pt-2 text-xs">
                <span className="font-semibold text-ink block">
                  Thông tin xác nhận
                </span>
                <label className="flex items-center gap-2 cursor-pointer text-ink-soft">
                  <input
                    type="checkbox"
                    checked={chkCustomer}
                    onChange={(e) => setChkCustomer(e.target.checked)}
                    className="rounded border-line text-brand-600 focus:ring-brand-500"
                  />
                  Đúng khách hàng
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-ink-soft">
                  <input
                    type="checkbox"
                    checked={chkService}
                    onChange={(e) => setChkService(e.target.checked)}
                    className="rounded border-line text-brand-600 focus:ring-brand-500"
                  />
                  Đúng dịch vụ
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-ink-soft">
                  <input
                    type="checkbox"
                    checked={chkDocSlot}
                    onChange={(e) => setChkDocSlot(e.target.checked)}
                    className="rounded border-line text-brand-600 focus:ring-brand-500"
                  />
                  Đúng bác sĩ và khung giờ
                </label>
              </div>

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
                  <p className="mt-1.5 text-[11px] text-ink-muted">
                    Lịch đã có hiệu lực, không cần bấm lại. Muốn đổi hoặc huỷ
                    thì vào Quản lý khách hàng → Lịch hẹn sắp tới.
                  </p>
                  <div className="mt-2.5 flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setJustBooked(null);
                        setSelectedPatientId(null);
                        setConfirmedMsg(null);
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
                  onClick={() => setSelectedPatientId(null)}
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
                    offDuty[`${selectedSlot.doctorId}|${selectedDateIso}`] === true
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
