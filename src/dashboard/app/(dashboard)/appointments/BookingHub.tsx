"use client";

// BookingHub — Hub Đặt lịch hẹn CSKH 3 cột hoàn chỉnh.
// Cột 1 (Trái - 280px): Khách hàng đang chọn (xếp trên) + Tìm kiếm khách hàng có sẵn (dài hơn) + Thông tin y tế & Lịch sử đặt hẹn.
// Cột 2 (Giữa - 1fr): Bảng lưới giờ chuẩn mockup (Cột đầu = Giờ, các ô KHÔNG ghi lại giờ, màu & trạng thái Có thể đặt / Còn 1 chỗ / Đã đầy / Đang giữ / Đang chọn ✓).
// Cột 3 (Phải - 320px): Panel Xác nhận thông tin đặt lịch (Sức chứa 1/3 đã đặt, Checklist, Đặt lịch hẹn).

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Calendar as CalendarIcon,
  Clock,
  User,
  Users,
  CheckCircle2,
  X,
  Search,
  Phone,
  Filter,
  ChevronLeft,
  ChevronRight,
  Info,
  UserPlus,
  UserCheck,
  Mail,
  MapPin,
  Pencil,
  ChevronDown,
  History,
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

type SlotTone = "available" | "few" | "holding" | "full" | "selected";

/** Trả lời của GET /api/appointments/quote — sức chứa hiệu lực từng khung. */
interface QuoteResponse {
  closed?: boolean;
  /** Ngày đó đã xếp ca và bác sĩ này KHÔNG có tên trong lịch. */
  off_duty?: boolean;
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

  const [selectedServiceId, setSelectedServiceId] = useState<string>(
    cleanServices[0]?.id ?? "",
  );
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(
    patients[0]?.clinic_patient_id ?? null,
  );

  const activePatient = useMemo(
    () =>
      patients.find((p) => p.clinic_patient_id === selectedPatientId) ??
      patients[0] ??
      null,
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

  const [note, setNote] = useState("");
  const [chkCustomer, setChkCustomer] = useState(true);
  const [chkService, setChkService] = useState(true);
  const [chkDocSlot, setChkDocSlot] = useState(true);
  const [confirmedMsg, setConfirmedMsg] = useState<string | null>(null);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingLoading, setBookingLoading] = useState(false);

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
  const activeDoctors = useMemo(() => {
    if (selectedDoctorId === "all") return doctors.slice(0, 3);
    const doc = doctors.find((d) => d.id === selectedDoctorId);
    return doc ? [doc] : doctors.slice(0, 3);
  }, [doctors, selectedDoctorId]);

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
  const activeDoctorIds = activeDoctors.map((d) => d.id).join(",");

  useEffect(() => {
    if (!policy || !activeDoctorIds) return;
    const ctrl = new AbortController();
    const ids = activeDoctorIds.split(",");
    Promise.all(
      ids.map((docId) =>
        fetch(
          `/api/appointments/quote?date=${selectedDateIso}&doctor_id=${docId}`,
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
      for (const [docId, d] of pairs) {
        off[`${docId}|${selectedDateIso}`] = d?.off_duty === true;
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

  function getCellStatus(docId: string, time: string): CellStatus {
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
      return {
        tone: "holding",
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

    const isHolding = matchingAppts.some(
      (a) => a.status === "WAITING" || a.status === "CSKH_CONFIRMED",
    );

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
        label: "Đang giữ",
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
    // capByCell nằm trong deps: nếu không, thẻ tóm tắt bên phải giữ nguyên số
    // chỗ mặc định sau khi luật riêng của bác sĩ đã về, và hai chỗ trên cùng
    // màn hình nói hai con số khác nhau cho cùng một ô.
    [selectedSlot, appts, capByCell, offDuty],
  );

  async function handleConfirmBooking() {
    if (!activePatient || !selectedSlot.doctorId) return;
    // Không có luật thì không có lưới, và không có lưới thì không đặt được: gửi
    // đi lúc này chỉ tạo một lịch dài sai giờ. Nút đã bị vô hiệu hoá ở phần
    // render; đây là chốt chặn thứ hai.
    if (!policy) {
      setBookingError("Chưa đọc được luật đặt lịch của phòng khám — thử tải lại trang.");
      return;
    }
    const serviceId = selectedServiceId || cleanServices[0]?.id;
    if (!serviceId) {
      setBookingError("Chưa chọn dịch vụ.");
      return;
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: activePatient.clinic_patient_id,
          doctor_id: selectedSlot.doctorId,
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
          `Đã đặt lịch hẹn thành công cho ${activePatient.full_name} vào khung giờ ${timeDisplay} với ${selectedSlot.doctorName}!` +
            (warn ? ` ⚠️ ${warn}` : ""),
        );
        setNote("");
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
    } catch {
      setBookingError("Mất kết nối tới máy chủ — lịch chưa được lưu.");
    } finally {
      setBookingLoading(false);
    }
  }

  const selectedServiceName =
    cleanServices.find((s) => s.id === selectedServiceId)?.label ??
    "Khám Phụ khoa";

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

      {/* Mode 1: New Patient Intake Form */}
      {mode === "new_patient" ? (
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
          <div className="mb-4 border-b border-line pb-3">
            <h2 className="text-base font-bold text-ink flex items-center gap-2">
              <UserPlus className="size-4 text-brand-600" />
              Nhập thông tin hành chính &amp; Đặt lịch hẹn cho khách hàng mới
            </h2>
            <p className="text-xs text-ink-muted mt-0.5">
              Điền đầy đủ thông tin hành chính của khách hàng lần đầu đến phòng khám
            </p>
          </div>
          <NewPatientForm
            role="CSKH"
            locations={locations}
            services={cleanServices}
            doctors={doctors}
            provinces={provinces}
            variant="full"
          />
        </div>
      ) : (
        /* Mode 2: 3-Column Standard Layout (Left: Patient Cards, Middle: Slot Grid, Right: Confirm Panel) */
        <div className="space-y-4">
          {/* Top 4 Summary Stat Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-700">
                <CalendarIcon className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Lịch hôm nay</p>
                <p className="text-xl font-bold text-ink">42</p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-emerald-50 text-emerald-600">
                <User className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Còn chỗ</p>
                <p className="text-xl font-bold text-ink">18</p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-sky-50 text-sky-600">
                <Clock className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Đang giữ</p>
                <p className="text-xl font-bold text-ink">4</p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-teal-50 text-teal-600">
                <CheckCircle2 className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Đã xác nhận</p>
                <p className="text-xl font-bold text-ink">20</p>
              </div>
            </div>
          </div>

          {/* Stepper (1 Khách hàng -> 2 Khung giờ -> 3 Xác nhận) */}
          <div className="flex items-center justify-center gap-4 rounded-2xl border border-line bg-surface py-2.5 px-4 text-xs font-medium text-ink-muted shadow-card">
            <div className="flex items-center gap-2">
              <span className="grid size-5 place-items-center rounded-full bg-emerald-600 text-[11px] font-bold text-white">
                ✓
              </span>
              <span className="font-semibold text-ink">1 Khách hàng</span>
            </div>
            <div className="h-px w-16 bg-line" />
            <div className="flex items-center gap-2">
              <span className="grid size-5 place-items-center rounded-full bg-brand-600 text-[11px] font-bold text-white">
                2
              </span>
              <span className="font-bold text-brand-700">Khung giờ</span>
            </div>
            <div className="h-px w-16 bg-line" />
            <div className="flex items-center gap-2">
              <span className="grid size-5 place-items-center rounded-full bg-surface-sunken text-[11px] font-bold text-ink-muted">
                3
              </span>
              <span>Xác nhận</span>
            </div>
          </div>

          {/* 3-Column Layout: Left (Patient Cards) + Middle (Grid) + Right (Panel) */}
          <div className="grid items-start gap-4 xl:grid-cols-[280px_1fr_320px]">
            {/* COLUMN 1 (LEFT - 280px): New Patient Button + Active Patient Card + Search List */}
            <aside className="space-y-3">
              {/* Nút đặt lịch cho khách hàng mới (Đặt lên trên cùng của Cột 1) */}
              <button
                type="button"
                onClick={() => setMode("new_patient")}
                className="w-full inline-flex items-center justify-center gap-2 rounded-2xl bg-brand-600 py-2.5 px-3.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 transition-all"
              >
                <UserPlus className="size-4" />
                + Đặt lịch hẹn cho khách mới
              </button>

              {/* 1. KHÁCH HÀNG ĐANG CHỌN */}
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
                        onClick={() => setSelectedPatientId(p.clinic_patient_id)}
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

            {/* COLUMN 2 (MIDDLE - 1fr): Slot Table Grid */}
            <div className="space-y-3 min-w-0">
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
                    {cleanServices.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Doctor dropdown */}
                <div className="flex items-center gap-1 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs text-ink font-medium">
                  <User size={14} className="text-ink-muted" />
                  <select
                    value={selectedDoctorId}
                    onChange={(e) => handleDoctorFilterChange(e.target.value)}
                    className="bg-transparent text-xs font-semibold text-ink outline-none cursor-pointer"
                  >
                    <option value="all">Tất cả bác sĩ</option>
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
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-soft hover:bg-surface-muted"
                >
                  <Filter size={13} /> Bộ lọc
                </button>
              </div>

              {/* Date navigator & legend */}
              <div className="space-y-2.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  {/* Ba nút này TRƯỚC ĐÂY KHÔNG CÓ onClick: mũi tên trái/phải và
                      "Hôm nay" vẽ ra rồi không làm gì, còn nhãn tuần là chuỗi
                      viết cứng "11–16/05/2026". Bấm vào không có phản hồi nào,
                      nên không phân biệt được với một trang đang treo. */}
                  <div className="flex items-center gap-2">
                    <div className="flex items-center rounded-xl border border-line bg-surface px-2 py-1 text-xs">
                      <button
                        type="button"
                        aria-label="Tuần trước"
                        onClick={() => setWeekOffset((w) => w - 1)}
                        className="p-1 hover:text-brand-600"
                      >
                        <ChevronLeft size={14} />
                      </button>
                      <span className="px-2 font-bold text-ink tabular-nums">
                        {weekDays[0]?.dateStr}–{weekDays[6]?.dateStr}/
                        {weekDays[0]?.isoDate.slice(0, 4)}
                      </span>
                      <button
                        type="button"
                        aria-label="Tuần sau"
                        onClick={() => setWeekOffset((w) => w + 1)}
                        className="p-1 hover:text-brand-600"
                      >
                        <ChevronRight size={14} />
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setWeekOffset(0);
                        setSelectedDateIso(vnToday());
                      }}
                      className="rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-muted"
                    >
                      Hôm nay
                    </button>
                  </div>

                  {/* Day Tabs */}
                  <div className="flex items-center gap-1 overflow-x-auto text-xs">
                    {weekDays.map((d) => {
                      const isSelectedDay = d.isoDate === selectedDateIso;
                      return (
                        <button
                          key={d.dayName}
                          type="button"
                          onClick={() => setSelectedDateIso(d.isoDate)}
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
                </div>

                {/* Status Legend Pills (Exact colors from mockup) */}
                <div className="flex flex-wrap items-center gap-4 pt-1 text-xs">
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

              {/* Table Grid (FIRST COLUMN = TIME RANGE e.g. 18:00 - 18:15, NO INNER GRID LINES) */}
              <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card p-2">
                {/* Doctor Header Row */}
                <div
                  className={`grid text-xs font-bold text-ink text-center pb-2 border-b border-line ${
                    activeDoctors.length === 1
                      ? "grid-cols-[110px_1fr]"
                      : activeDoctors.length === 2
                        ? "grid-cols-[110px_1fr_1fr]"
                        : "grid-cols-[110px_1fr_1fr_1fr]"
                  }`}
                >
                  <div className="p-2 text-ink-muted font-medium flex items-center justify-center">
                    Giờ
                  </div>
                  {activeDoctors.map((doc) => (
                    <div key={doc.id} className="p-2">
                      <div className="truncate font-bold text-ink">
                        {doc.label}
                      </div>
                      {/* Câu trả lời đặt ngay dưới TÊN BÁC SĨ, không phải ở
                          một góc màn hình: nó nói về đúng người này, và nó là
                          lý do cả cột bên dưới không bấm được. */}
                      {offDuty[`${doc.id}|${selectedDateIso}`] ? (
                        <div className="truncate text-[11px] font-medium text-warning">
                          Không có lịch làm việc ngày này
                        </div>
                      ) : (
                        <div className="text-[11px] font-normal text-ink-muted truncate">
                          Phụ khoa
                        </div>
                      )}
                    </div>
                  ))}
                </div>

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
                        className={`grid text-xs items-center ${
                          activeDoctors.length === 1
                            ? "grid-cols-[110px_1fr]"
                            : activeDoctors.length === 2
                              ? "grid-cols-[110px_1fr_1fr]"
                              : "grid-cols-[110px_1fr_1fr_1fr]"
                        }`}
                      >
                        {/* FIRST COLUMN: TIME RANGE (e.g. 08:00 - 08:15) */}
                        <div className="p-2 text-center font-mono font-medium text-ink-muted text-[11px]">
                          {timeRangeStr}
                        </div>

                        {/* DOCTOR COLUMNS (CELLS - NO TIME TEXT INSIDE!) */}
                        {activeDoctors.map((doc) => {
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
            </div>

            {/* COLUMN 3 (RIGHT - 320px): Thông tin đặt lịch (Matching Image 3 Mockup) */}
            <aside className="space-y-3.5 rounded-2xl border border-line bg-surface p-4 shadow-card">
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
                  <span className="font-bold text-ink">{selectedServiceName}</span>
                </div>
                <div className="flex justify-between border-b border-line/60 pb-1.5">
                  <span className="text-ink-muted">Bác sĩ:</span>
                  <span className="font-bold text-ink">
                    {selectedSlot.doctorName}
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
                    {slotRange(selectedSlot.time, slotMinutes)}
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

              {/* Notice */}
              <div className="rounded-xl bg-sky-50 p-2.5 text-[11px] text-sky-800 flex items-start gap-2 border border-sky-200/60">
                <Info size={14} className="shrink-0 mt-0.5 text-sky-600" />
                <span>Lịch hẹn sẽ được tạo ngay khi bạn đặt. 10 phút ưu tiên chỉ áp dụng lúc bệnh nhân check-in (theo giờ hẹn).</span>
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

              {/* Action Buttons */}
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
                    offDuty[`${selectedSlot.doctorId}|${selectedDateIso}`] === true
                  }
                  className="flex-[1.5] rounded-xl bg-brand-600 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 disabled:opacity-50"
                >
                  {bookingLoading ? "Đang xử lý..." : "Đặt lịch hẹn"}
                </button>
              </div>
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
