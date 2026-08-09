"use client";

// Single-step intake: patient details + (optional) first appointment on ONE
// form. One submit creates the patient (MPI dup-check) then books the
// appointment if a service + date + time were filled, and finally lands on the
// patient's profile. No more two-screen flow.

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { UserRound, CalendarClock } from "lucide-react";
import { type ClinicRole } from "../../../../lib/roles";
import type { Option } from "../AppointmentBooking";
import CinemaSlotPicker from "../CinemaSlotPicker";
import {
  buildSlotUsage,
  usageAt,
  slotBucketMs,
  slotMinuteOptions,
  type SlotApptLite,
} from "../../../../lib/slot-capacity";
import { useBookingPolicy } from "../../BookingPolicyContext";
import { vnLocalToUtcISO, nowMs, slotRange } from "../../../../lib/datetime";
import {
  todayVn,
  clinicHoursForDate,
  clinicHoursError,
} from "../../../../lib/roster";
import {
  digitsOnly,
  normalizePhoneVi,
  toTitleCaseVi,
  phoneError,
  cccdError,
  birthYearError,
  unaccentVi,
} from "../../../../lib/validation";
import DateField from "../../DateField";
import SearchSelect from "../../SearchSelect";
import { LINH_VUC_OPTIONS } from "../../../../lib/linh-vuc";
import {
  INPUT,
  LABEL,
  BTN,
  BTN_GHOST,
  CARD,
  CHANNELS,
} from "../../form-ui";
import Time24Input from "../../Time24Input";

export type { Option };

/** Tỉnh/thành (sau sáp nhập) — server cấp sẵn; phường/xã load runtime. */
export interface ProvinceOpt {
  code: string;
  name: string;
  fullName: string;
}
interface WardOpt {
  code: string;
  name: string;
  full_name: string;
}

interface DupMatch {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  date_of_birth: string | null;
}

// Cảnh báo SỚM (feedback #9): trùng SĐT phát hiện NGAY khi nhập, gọn hơn
// DupMatch (chỉ tên + mã + năm sinh — không CCCD/địa chỉ).
interface PhoneMatch {
  full_name: string;
  patient_code: string;
  birth_year: number | null;
}

interface IntakeAppointment extends SlotApptLite {
  queue_number?: string | null;
}

function Req() {
  return <span className="text-brand-600">*</span>;
}

function findServiceIdByLinhVuc(code: string, services: Option[]): string {
  if (!code) return "";
  const nameMap: Record<string, string[]> = {
    PK: ["Phụ khoa", "PHU_KHOA"],
    SK: ["Sản 1", "Sản khoa", "Sản", "SAN_1"],
    NT: ["Nội tiết - Tình dục", "Nội tiết", "NOI_TIET_TINH_DUC"],
    HMVS: ["Hiếm muộn", "Hiếm muộn - Vô sinh", "HIEM_MUON"],
    NK: ["Nam khoa", "NAM_KHOA"],
  };
  const targets = nameMap[code] ?? [];
  for (const t of targets) {
    const found = services.find((s) => s.label.toLowerCase() === t.toLowerCase());
    if (found) return found.id;
  }
  for (const t of targets) {
    const found = services.find((s) => s.label.toLowerCase().includes(t.toLowerCase()));
    if (found) return found.id;
  }
  return services[0]?.id ?? "";
}

function SectionHeader({
  icon,
  title,
  hint,
}: {
  icon: React.ReactNode;
  title: string;
  hint?: string;
}) {
  return (
    <div className="mb-4 flex items-center gap-2.5 border-b border-surface-sunken pb-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
        {icon}
      </span>
      <div>
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {hint && <p className="text-xs text-ink-muted">{hint}</p>}
      </div>
    </div>
  );
}

export default function NewPatientForm({
  role,
  locations,
  services,
  doctors,
  provinces,
  variant = "full",
  initialAppt,
  nhung = false,
  onHuy,
}: {
  role?: ClinicRole | null;
  locations: Option[];
  services: Option[];
  doctors: Option[];
  provinces: ProvinceOpt[];
  /** "walkin" = điều dưỡng ghi khách vãng lai: bỏ lịch hẹn, gộp dịch vụ/bác sĩ
   *  vào ô thông tin, lưu xong tạo luôn lượt khám HÔM NAY (giờ hiện tại). */
  variant?: "full" | "walkin";
  /** Nhúng vào một màn đã có tiêu đề và thanh bước riêng (vd màn Đặt lịch).
   *
   * Chỉ ẩn phần đầu — toàn bộ biểu mẫu và luật kiểm tra giữ nguyên. Cắt hẳn
   * khối đó khỏi component sẽ làm trang `/patients/new` đứng một mình mất tiêu
   * đề, vì hai nơi dùng CÙNG một component. */
  nhung?: boolean;
  /** Khi biểu mẫu được NHÚNG trong một màn khác: "Huỷ" phải trả người dùng về
   *  đúng chỗ họ đang đứng, không đá sang /patient-list. Không truyền thì giữ
   *  hành vi cũ (trang /patients/new độc lập). */
  onHuy?: () => void;
  /** Điền sẵn ngày/giờ/bác sĩ — ô xanh "đặt vào đây" ở bảng Lịch hẹn khám
   *  (trang chủ) dẫn sang đây kèm query để Lễ tân xếp khách đúng khung. */
  initialAppt?: { date?: string; time?: string; doctorId?: string };
}) {
  const walkin = variant === "walkin";
  // Địa chỉ (Tỉnh/TP + Phường/Xã) BẮT BUỘC cho CSKH (full), Lễ tân (RECEPTION) và
  // Trưởng ca/Quản lý (làm thay Lễ tân). Điều dưỡng walk-in (nurse) giữ TUỲ CHỌN.
  const requireAddress =
    !walkin ||
    role === "RECEPTION" ||
    role === "TRUONG_CA" ||
    role === "MANAGEMENT";
  const router = useRouter();
  // Logic thời gian thực: năm sinh ≤ hôm nay; ngày khám ≥ hôm nay (giờ VN).
  const TODAY = todayVn();
  const CUR_YEAR = Number(TODAY.slice(0, 4));

  // Patient
  const [fullName, setFullName] = useState("");
  // Ngày sinh = 1 ô DD/MM/YYYY (DateField) → ISO "yyyy-mm-dd" (đúng kiểu DB);
  // DateField đã chặn ngày lịch sai (30/2; 29/2 chỉ năm nhuận). Đây chỉ chặn
  // thêm "tương lai".
  const [dobIso, setDobIso] = useState("");
  // Năm sinh-only (feedback B5#4): BN chỉ nhớ năm → bật toggle, nhập năm.
  const [dobYearOnly, setDobYearOnly] = useState(false);
  const [birthYear, setBirthYear] = useState("");
  const dobErr =
    !dobYearOnly && dobIso && dobIso > TODAY
      ? "Ngày sinh không thể ở tương lai."
      : null;
  // "Chỉ biết năm": cũng validate (1900..năm hiện tại, không tương lai) + báo inline.
  const birthYearErr = dobYearOnly ? birthYearError(birthYear, CUR_YEAR) : null;
  const [phone, setPhone] = useState("");
  const [phone2, setPhone2] = useState("");
  const [cccd, setCccd] = useState("");
  const [locationId, setLocationId] = useState(locations[0]?.id ?? "");
  // Hành chính (mục I form khám) — đồng bộ sang hồ sơ lâm sàng.
  const [gender, setGender] = useState("");
  const [ethnicity, setEthnicity] = useState("Kinh");
  const [nationality, setNationality] = useState("Việt Nam");
  const [occupation, setOccupation] = useState("");
  const [objection, setObjection] = useState("");
  // Địa chỉ SAU sáp nhập: chọn Tỉnh → Phường/xã (load runtime) + ô chi tiết (số
  // nhà/đường). BN cũ free-text giữ ở cột address (xem hồ sơ); form mới dựng dropdown.
  const [provinceCode, setProvinceCode] = useState("");
  const [wardCode, setWardCode] = useState("");
  const [wards, setWards] = useState<WardOpt[]>([]);
  const [wardsLoading, setWardsLoading] = useState(false);
  const [addressDetail, setAddressDetail] = useState("");
  // CSKH khai thác lúc đặt lịch: vấn đề khiến đi khám + lĩnh vực (chuyên khoa).
  const [vanDe, setVanDe] = useState("");
  const [linhVuc, setLinhVuc] = useState("");

  // Chọn tỉnh → reset + load phường/xã của tỉnh đó (trong handler, KHÔNG dùng
  // effect → tránh set-state-in-effect + extra render).
  async function onProvinceChange(code: string) {
    setProvinceCode(code);
    setWardCode("");
    setWards([]);
    if (!code) return;
    setWardsLoading(true);
    try {
      const d = await fetch(
        `/api/wards?province=${encodeURIComponent(code)}`,
      ).then((r) => r.json());
      setWards((d.wards as WardOpt[]) ?? []);
    } catch {
      setWards([]);
    } finally {
      setWardsLoading(false);
    }
  }

  // Options cho combobox gõ-để-tìm (memo hoá để SearchSelect không lọc lại thừa).
  const provinceOpts = useMemo(
    () => provinces.map((p) => ({ value: p.code, label: p.fullName })),
    [provinces],
  );
  const wardOpts = useMemo(
    () => wards.map((w) => ({ value: w.code, label: w.full_name })),
    [wards],
  );

  // Appointment (optional)
  const [serviceId, setServiceId] = useState("");
  const [doctorId, setDoctorId] = useState(initialAppt?.doctorId ?? "");
  const [doctorQ, setDoctorQ] = useState(
    initialAppt?.doctorId
      ? (doctors.find((d) => d.id === initialAppt.doctorId)?.label ?? "")
      : "",
  ); // text hiện trong ô
  const [doctorOpen, setDoctorOpen] = useState(false);
  const [apptDate, setApptDate] = useState(initialAppt?.date ?? "");
  const [apptTime, setApptTime] = useState(initialAppt?.time ?? "");
  // Loại ghế đang chọn ở sơ đồ (luồng full): "regular" = BN1/BN2 (kênh thường);
  // "walkin" = chỗ ĐẾN TRỰC TIẾP — đặt như WALK_IN để vào đúng ghế, không
  // cần Kênh đặt. onPick của sơ đồ luôn set lại theo ô bấm.
  // GHẾ VÃNG LAI CHỈ CÒN Ở BẢN WALK-IN của điều dưỡng.
  //
  // Ô chọn kiểu ghế nằm trong sơ đồ chỗ, mà sơ đồ ấy đã bỏ khỏi biểu mẫu CSKH
  // (xem ghi chú ở phần Lịch hẹn khám). Giữ một `useState` mà không nơi nào
  // gọi setter là để lại một biến trông như còn đổi được — người đọc sau sẽ đi
  // tìm chỗ đổi nó. Bản walk-in đi qua nhánh `walkin` riêng, nơi `gheTrucTiep`
  // vốn đã luôn false theo đúng định nghĩa dưới đây.
  const gheTrucTiep = false;
  // Luật đặt lịch của phòng khám (C.3). `null` = chưa đọc được → không đoán.
  const policy = useBookingPolicy();
  // Lịch dài đúng một khung của PHÒNG KHÁM NÀY, không phải 15' cố định.
  const duration = policy?.slotMinutes ?? 0;
  const [existingAppts, setExistingAppts] = useState<IntakeAppointment[]>([]);
  // Bác sĩ TRỰC CA (work_roster LICH_KHAM) của ngày đang đặt — sơ đồ chỉ hiện
  // các bác sĩ này. null = chưa nạp; [] = ngày chưa phân trực (fallback tất cả).
  const [dutyDoctorIds, setDutyDoctorIds] = useState<string[] | null>(null);
  const dutyDate = walkin ? TODAY : apptDate;
  useEffect(() => {
    if (!dutyDate) return;
    const ctrl = new AbortController();
    fetch(`/api/roster?date=${encodeURIComponent(dutyDate)}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) =>
        setDutyDoctorIds(
          j ? (j.doctors as { id: string }[]).map((d) => d.id) : null,
        ),
      )
      .catch(() => {});
    return () => ctrl.abort();
  }, [dutyDate]);
  // Ô "Bác sĩ" CHỈ MỜI NGƯỜI CÓ TRỰC NGÀY ĐÓ.
  //
  // Quang 09/08/2026: *"rõ là hôm nay có lịch mà sao lúc đặt lịch lại không
  // thấy lịch bác sĩ nào hiện ra?"*.
  //
  // `dutyDoctorIds` được nạp từ trước — nhưng chỉ đưa xuống sơ đồ khung giờ,
  // còn ô tìm bác sĩ ngay trên nó thì lọc trên TOÀN BỘ danh sách. Nên biểu mẫu
  // mời cả mười lăm bác sĩ cho một ngày chỉ có hai người trực, và không nói một
  // chữ nào về việc ai đang trực. Dữ liệu đúng, nạp đúng, rồi không ai dùng.
  //
  // `null` = chưa hỏi xong; `[]` = ngày chưa xếp trực → mời tất cả (cùng đường
  // lùi với sơ đồ khung giờ, và nay nói ra thành lời ở ngay dưới ô).
  const bacSiTrucCa = useMemo(
    () =>
      dutyDoctorIds === null || dutyDoctorIds.length === 0
        ? doctors
        : doctors.filter((d) => dutyDoctorIds.includes(d.id)),
    [doctors, dutyDoctorIds],
  );

  // Ô tìm bác sĩ CỦA MÀN VÃNG LAI vẫn còn (điều dưỡng ghi khách đến thẳng, không
  // qua sơ đồ khung giờ), nhưng nay cũng chỉ mời người CÓ TRỰC hôm đó.
  const filteredDoctors = useMemo(() => {
    const t = unaccentVi(doctorQ.trim());
    if (!t) return bacSiTrucCa;
    return bacSiTrucCa.filter((d) => unaccentVi(d.label).includes(t));
  }, [doctorQ, bacSiTrucCa]);

  // CAP-01: phân loại tải để engine ngân sách (newCap + Thành-min) chặn đúng.
  // Khách MỚI luôn là ca KHÁM MỚI (EPI-01 DEC-E5) → cố định NEW, không còn nút đổi
  // (BN cũ/tái khám đổi loại ở AppointmentBooking trên trang chi tiết BN).
  const [patientKind] = useState<"NEW" | "RETURN">("NEW");
  const [needSono, setNeedSono] = useState(false);
  // Kênh đặt = NHẬP TỰ DO (feedback: "cho điền thôi, sau tự tính"). Để trống được.
  const [channel, setChannel] = useState("");
  // Số khám (queue_number) — feedback B5#8.
  const [queueNumber, setQueueNumber] = useState("");

  // Fetch appointments for selected date to check availability / walk-in queues
  useEffect(() => {
    if (walkin) {
      let active = true;
      fetch(`/api/appointments?date=${encodeURIComponent(TODAY)}`)
        .then((r) => (r.ok ? r.json() : { appointments: [] }))
        .then((data) => {
          if (!active) return;
          const appts = data.appointments ?? [];
          setExistingAppts(appts);
          let maxNum = 0;
          for (const appt of appts) {
            const q = (appt.queue_number ?? "").trim();
            const num = parseInt(q, 10);
            if (Number.isFinite(num) && num > maxNum) {
              maxNum = num;
            }
          }
          setQueueNumber(String(maxNum + 1));
        })
        .catch(() => {});
      return () => {
        active = false;
      };
    } else {
      if (!apptDate) return;
      let active = true;
      // Lấy lịch MỌI bác sĩ trong ngày (KHÔNG lọc doctor_id) để sơ đồ "rạp chiếu
      // phim" vẽ từng hàng bác sĩ; isSlotBooked vẫn lọc theo doctorId ở client.
      fetch(`/api/appointments?date=${encodeURIComponent(apptDate)}`)
        .then((r) => (r.ok ? r.json() : { appointments: [] }))
        .then((data) => {
          if (active) {
            setExistingAppts(data.appointments ?? []);
          }
        })
        .catch(() => {
          if (active) setExistingAppts([]);
        });
      return () => {
        active = false;
      };
    }
  }, [apptDate, walkin, TODAY]);

  const visibleExistingAppts = useMemo(
    () => (walkin || apptDate ? existingAppts : []),
    [walkin, apptDate, existingAppts],
  );

  // Khung đang chọn còn chỗ ĐÚNG LOẠI không? Số chỗ mỗi loại là cấu hình của
  // phòng khám (clinic.settings.booking), không phải hằng số 2+1.
  const isSlotBooked = useMemo(() => {
    const day = walkin ? TODAY : apptDate;
    if (!day || !apptTime || !policy) return false;
    try {
      const bucketMs = slotBucketMs(vnLocalToUtcISO(day, apptTime), policy);
      const u = usageAt(
        buildSlotUsage(visibleExistingAppts, policy),
        doctorId || null,
        bucketMs,
      );
      // Chỗ đến trực tiếp (walk-in flow HOẶC full flow chọn ô xanh).
      return walkin || gheTrucTiep
        ? u.walkin >= policy.walkinCap
        : u.regular >= policy.regularCap;
    } catch {
      return false;
    }
  }, [
    walkin,
    gheTrucTiep,
    TODAY,
    apptDate,
    apptTime,
    doctorId,
    visibleExistingAppts,
    policy,
  ]);

  // CSKH: số khám ĐỂ TRỐNG — hệ thống cấp SỐ CHUNG THEO THỜI GIAN lúc check-in.
  // KHÔNG tự dập "ƯT" theo phút (sai nghĩa): ƯT chỉ dành cho NGƯỜI QUEN nhà bác sĩ,
  // do người nhập gõ tay khi cần. Đổi ngày/giờ → xoá số đang điền cho gọn.
  useEffect(() => {
    if (walkin) return;
    const timer = window.setTimeout(() => setQueueNumber(""), 0);
    return () => window.clearTimeout(timer);
  }, [apptTime, isSlotBooked, walkin]);

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dupes, setDupes] = useState<DupMatch[] | null>(null);

  // Cảnh báo SỚM trùng SĐT (feedback #9): nhập đủ 10 số → hỏi backend xem đã có
  // ai dùng chưa. CHỈ cảnh báo, KHÔNG chặn lưu — backend lo chuẩn hoá +84/0.
  const [phoneDupes, setPhoneDupes] = useState<PhoneMatch[]>([]);
  useEffect(() => {
    let alive = true;
    // Debounce 450ms — toàn bộ (cả việc xoá cảnh báo cũ) chạy trong timeout để
    // KHÔNG setState đồng bộ trong thân effect (react-hooks/set-state-in-effect).
    const t = setTimeout(() => {
      // HỎI KHI CÓ ĐỦ MỘT TRONG HAI, không chỉ khi đủ số điện thoại.
      //
      // Bản cũ chỉ hỏi khi gõ xong 10 chữ số, nên người khai SĐT mới — hoặc
      // không khai SĐT — không bao giờ được cảnh báo, dù hồ sơ cũ nằm ngay đó
      // với đúng tên và đúng năm sinh. Notion đòi kiểm "SĐT đã chuẩn hoá, KẾT
      // HỢP họ tên và năm sinh".
      const digits = phone.replace(/\D/g, "");
      const nam = dobYearOnly
        ? Number(birthYear)
        : Number(dobIso.slice(0, 4));
      const coTen = fullName.trim().length >= 3 && nam >= 1900 && nam <= CUR_YEAR;
      if (digits.length !== 10 && !coTen) {
        if (alive) setPhoneDupes([]);
        return;
      }
      void (async () => {
        try {
          // MỘT LUẬT DUY NHẤT: endpoint này gọi đúng hàm mà đường LƯU gọi
          // (MPIService.find_candidates). Bản cũ dùng /check-phone với một
          // truy vấn riêng chỉ so SĐT — nên màn hình nói "không trùng", Lễ tân
          // bấm lưu, rồi hồ sơ rơi vào hàng chờ gộp.
          const qs = new URLSearchParams();
          if (digits.length === 10) qs.set("phone", phone);
          if (coTen) {
            qs.set("full_name", fullName.trim());
            qs.set("birth_year", String(nam));
          }
          const res = await fetch(`/api/patients/check-duplicate?${qs}`);
          if (!res.ok) return;
          const json = (await res.json()) as {
            exists?: boolean;
            matches?: PhoneMatch[];
          };
          if (alive) setPhoneDupes(json.exists ? (json.matches ?? []) : []);
        } catch {
          /* cảnh báo là phụ: lỗi mạng thì im lặng, submit vẫn có guard riêng */
        }
      })();
    }, 450);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [phone, fullName, dobIso, dobYearOnly, birthYear, CUR_YEAR]);

  // Walk-in: chỉ cần chọn dịch vụ là tạo lượt khám (giờ = bây giờ). Full: cần đủ
  // dịch vụ + ngày + giờ.
  const wantsAppointment = walkin
    ? !!serviceId
    : !!(serviceId && apptDate && apptTime);
  // Bắt buộc trước khi lưu: Họ tên + SĐT + Giới tính + Cơ sở (Ngày sinh kiểm
  // trong save() vì có toggle "Chỉ biết năm"). Nút khoá tới khi đủ.
  // Khách thường (không vãng lai) phải đủ: Tỉnh/TP + Phường/Xã + Dịch vụ + Bác sĩ
  // + Ngày + Giờ khám + Kênh đặt (mới đủ điều kiện tạo lượt khám). Walk-in giữ nguyên.
  // Giờ mở cửa PK theo ngày khám đã chọn (T2–T6 17–23h; T7+CN cả ngày).
  const apptCh =
    apptDate && policy ? clinicHoursForDate(apptDate, policy.hours) : null;
  const apptMinHour = apptCh ? Number(apptCh.open.slice(0, 2)) : 0;
  const apptMaxHour = apptCh ? Number(apptCh.close.slice(0, 2)) - 1 : 23;
  // Lỗi nhỏ ngay cạnh ô SĐT/CCCD (live) — rõ ô NÀO sai (chính/người nhà/CCCD),
  // không chờ submit + không còn 1 câu lỗi chung gây khó hiểu.
  const phoneErr = phoneError(phone);
  const phone2Err = phoneError(phone2);
  const cccdErr = cccdError(cccd);

  async function bookFor(clinicPatientId: string): Promise<boolean> {
    // Cùng lớp đỡ như save(): state có thể còn rỗng nếu danh sách cơ sở tới
    // sau, và gửi location_id rỗng thì backend từ chối bằng một câu khó hiểu.
    const effLocationId = locationId || locations[0]?.id || "";
    if (!wantsAppointment) return true;
    if (!policy) {
      setError(
        "Chưa đọc được luật đặt lịch của phòng khám — hồ sơ đã lưu, nhưng chưa đặt được lịch. Tải lại trang rồi đặt lại.",
      );
      return false;
    }
    // Walk-in: Lễ tân đã bấm ô xanh trên sơ đồ → dùng đúng khung đó; chưa bấm
    // (khám ngay) → giờ hiện tại. Server vẫn chặn nếu khung đã có khách vãng lai.
    const start = walkin
      ? apptTime
        ? new Date(vnLocalToUtcISO(TODAY, apptTime))
        : new Date()
      : new Date(vnLocalToUtcISO(apptDate, apptTime));
    const end = new Date(start.getTime() + duration * 60_000);
    const res = await fetch("/api/appointments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        doctor_id: doctorId,
        service_type_id: serviceId,
        location_id: effLocationId,
        slot_start: start.toISOString(),
        slot_end: end.toISOString(),
        // Ghế đến trực tiếp (ô xanh) → phải là WALK_IN để server xếp đúng
        // ghế (nếu không sẽ đội lên BN1/BN2 và bị chặn cứng cap 2).
        booking_channel: walkin || gheTrucTiep ? "WALK_IN" : channel,
        queue_number: queueNumber,
        patient_kind: patientKind,
        need_sono: needSono,
      }),
    });
    if (!res.ok) {
      const json = await res.json();
      setError(
        `Đã tạo hồ sơ nhưng đặt lịch lỗi: ${json.error ?? "không rõ"}. Mở hồ sơ để đặt lại.`,
      );
      return false;
    }
    return true;
  }

  // Land on the patient profile (the "nice profile" the user sees right after).
  // Kèm mã BN để banner hiện "Mã BN: …" ngay sau khi tạo (feedback B5#2).
  function goToProfile(id: string, code?: string) {
    // LỄ TÂN: tạo BN xong → về BẢNG bệnh nhân (Danh sách bệnh nhân), không đứng
    // lại ở hồ sơ (Quang 2026-07-02). Khách vãng lai vừa nhận auto CHECKED_IN
    // hôm nay nên hiện ngay trên bảng đó.
    if (role === "RECEPTION") {
      router.push("/patient-list");
      return;
    }
    // Khách thường (CSKH/QL): nhảy sang "Thông tin khách hàng" với khách vừa nhập
    // được CHỌN sẵn + bôi hồng (đúng yêu cầu "thông tin sau nhập trả về"). Khách
    // vãng lai (điều dưỡng): về hồ sơ để thấy luôn lượt khám hôm nay.
    if (walkin) {
      const qs = code ? `?new=1&code=${encodeURIComponent(code)}` : "?new=1";
      router.push(`/patients/${id}${qs}`);
    } else {
      router.push(`/customers?selected=${encodeURIComponent(id)}`);
    }
  }

  async function proceed(clinicPatientId: string, code?: string) {
    const booked = await bookFor(clinicPatientId);
    if (!booked) {
      // Patient exists; let the operator open the profile to retry booking.
      setSubmitting(false);
      setDupes(null);
      return;
    }
    goToProfile(clinicPatientId, code);
  }

  // Cơ sở mặc định TÍNH RA, không phải đặt bằng effect.
  //
  // Bản cũ dùng useEffect để nhét locations[0] vào state khi state còn rỗng —
  // `react-hooks/set-state-in-effect` chặn đúng, vì nó gây một lượt render
  // thừa và có một nhịp mà form đang ở trạng thái "chưa chọn cơ sở" dù danh
  // sách đã có. Bấm Lưu trúng nhịp đó thì rơi vào nhánh "Chưa chọn cơ sở khám".
  //
  // Không cần thay bằng gì cả: state đã khởi tạo `locations[0]?.id` ngay ở
  // useState, và `save()` vẫn còn lớp đỡ `locationId || locations[0]?.id`.

  async function save(force: boolean) {
    setError(null);
    const effLocationId = locationId || locations[0]?.id || "";
    if (!effLocationId) {
      setError("Chưa chọn cơ sở khám.");
      return;
    }
    // BẮT BUỘC điền (mục có dấu *): Họ tên + SĐT + Giới tính.
    if (!fullName.trim()) {
      setError("Vui lòng nhập Họ và tên bệnh nhân (ở mục Thông tin hành chính phía trên).");
      return;
    }
    if (!phone.trim()) {
      setError("Vui lòng nhập Số điện thoại chính (10 chữ số).");
      return;
    }
    if (!gender) {
      setError("Vui lòng chọn Giới tính (Nam / Nữ).");
      return;
    }
    // Quy tắc nhập liệu CỨNG: SĐT 10 số / CCCD 12 số (chặn ngay trước khi gửi).
    const ve = phoneError(phone) || phoneError(phone2) || cccdError(cccd);
    if (ve) {
      setError(ve);
      return;
    }
    // Ngày sinh (yêu cầu 04/06): tick "Chỉ biết năm" → CHỈ cần NĂM (1900–2100);
    // KHÔNG tick → phải điền ĐỦ ngày/tháng/năm.
    if (dobYearOnly) {
      if (!birthYear.trim()) {
        setError(`Nhập năm sinh (1900–${CUR_YEAR}), hoặc bỏ tick “Chỉ biết năm”.`);
        return;
      }
      if (birthYearErr) {
        setError(birthYearErr);
        return;
      }
    } else if (!dobIso) {
      setError(
        "Phải điền đầy đủ ngày/tháng/năm sinh hợp lệ. Nếu chỉ biết năm, hãy tick “Chỉ biết năm”.",
      );
      return;
    } else if (dobErr) {
      setError(dobErr);
      return;
    }
    // BẮT BUỘC địa chỉ: CSKH (full) + Lễ tân (RECEPTION) phải có Tỉnh/TP + Phường/Xã.
    if (requireAddress) {
      if (!provinceCode) {
        setError("Vui lòng chọn Tỉnh / Thành phố.");
        return;
      }
      if (!wardCode) {
        setError("Vui lòng chọn Phường / Xã.");
        return;
      }
    }
    // BẮT BUỘC (khách thường, không vãng lai): Dịch vụ + Bác sĩ + Ngày + Giờ khám
    // + Kênh đặt — đủ thì mới tạo được lượt khám.
    if (!walkin) {
      if (!serviceId) {
        setError("Vui lòng chọn dịch vụ khám.");
        return;
      }
      // BÁC SĨ KHÔNG BẮT BUỘC.
      //
      // Khách gọi đặt trước 2–3 tuần hoặc cả tháng — lúc ấy lịch trực chưa công
      // bố, và khách cũng không biết phòng khám có những bác sĩ nào. Bắt chọn
      // bác sĩ ở đây nghĩa là lễ tân phải bịa một cái tên để lưu được hồ sơ, và
      // cái tên bịa ấy trông y hệt một quyết định thật ở mọi màn sau.
      //
      // Bỏ trống → lịch vào hàng chờ, quản lý xếp sau (assign_doctor).
      // Database vốn đã cho phép: appointment.doctor_id là NULLABLE.
      if (!apptDate) {
        setError("Vui lòng chọn ngày khám.");
        return;
      }
      if (!apptTime) {
        setError("Vui lòng chọn giờ khám.");
        return;
      }
      if (!gheTrucTiep && !channel) {
        setError("Vui lòng chọn kênh đặt.");
        return;
      }
    }
    // Lịch khám (không phải vãng lai): KHÔNG cho đặt vào quá khứ — thời gian thực.
    if (!walkin && wantsAppointment) {
      const startTs = new Date(vnLocalToUtcISO(apptDate, apptTime)).getTime();
      if (startTs < nowMs()) {
        setError("Không thể đặt lịch khám trong quá khứ. Chọn ngày/giờ từ hiện tại trở đi.");
        return;
      }
      const chErr = policy
        ? clinicHoursError(apptDate, apptTime, policy.hours)
        : "Chưa đọc được giờ mở cửa của phòng khám.";
      if (chErr) {
        setError(chErr);
        return;
      }
    }
    setSubmitting(true);
    // Gộp địa chỉ đầy đủ (chi tiết + phường full + tỉnh full) cho cột address
    // free-text (back-compat hiển thị) + gửi kèm mã/tên có cấu trúc.
    const provSel = provinces.find((p) => p.code === provinceCode);
    const wardSel = wards.find((w) => w.code === wardCode);
    const composedAddress = [addressDetail.trim(), wardSel?.full_name, provSel?.fullName]
      .filter(Boolean)
      .join(", ");
    const res = await fetch("/api/patients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: fullName,
        date_of_birth: dobYearOnly ? "" : dobIso,
        birth_year: dobYearOnly ? birthYear : undefined,
        phone_primary: phone,
        phone_secondary: phone2,
        national_id_number: cccd,
        location_id: effLocationId,
        gender,
        ethnicity,
        nationality,
        occupation,
        patient_objection: objection,
        address: composedAddress,
        province_code: provinceCode || undefined,
        province_name: provSel?.name || undefined,
        ward_code: wardCode || undefined,
        ward_name: wardSel?.name || undefined,
        address_detail: addressDetail.trim() || undefined,
        van_de_di_kham: vanDe.trim() || undefined,
        linh_vuc: linhVuc || undefined,
        force,
      }),
    });
    const json = await res.json();
    if (!res.ok) {
      setSubmitting(false);
      setError(json.error ?? "Có lỗi xảy ra.");
      return;
    }
    if (json.duplicate) {
      setSubmitting(false);
      setDupes(json.matches as DupMatch[]);
      return;
    }
    await proceed(
      json.patient.clinic_patient_id as string,
      json.patient.patient_code as string,
    );
  }

  return (
    <div aria-label="Luồng tạo hồ sơ và đặt lịch" className="space-y-4">
      {nhung ? null : (
        <header className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          <div className="border-b border-line px-4 py-3 sm:px-5">
            <p className="text-sm font-semibold text-ink">
              {walkin ? "Luồng tiếp nhận khách vãng lai" : "Luồng tạo hồ sơ và đặt lịch"}
            </p>
            <p className="mt-1 text-xs text-ink-muted">
              {walkin
                ? "Xác minh thông tin, chọn dịch vụ và tạo lượt khám khi đủ điều kiện."
                : "Hồ sơ và lịch hẹn được tạo qua hai bước, dùng cùng một nguồn dữ liệu."}
            </p>
          </div>
          <ol className="grid grid-cols-2 divide-x divide-line text-xs sm:grid-cols-3" aria-label="Các bước tiếp nhận">
            <li className="flex items-center gap-2 px-4 py-3 text-brand-800">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-[11px] font-bold text-white">1</span>
              <span className="font-semibold">Thông tin hồ sơ</span>
            </li>
            <li className="flex items-center gap-2 px-4 py-3 text-ink-muted">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-surface-sunken text-[11px] font-bold text-ink-soft">2</span>
              <span>{walkin ? "Dịch vụ & lượt khám" : "Lịch hẹn khám"}</span>
            </li>
            {!walkin && (
              <li className="hidden items-center gap-2 px-4 py-3 text-ink-muted sm:flex">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-surface-sunken text-[11px] font-bold text-ink-soft">3</span>
                <span>Xác nhận & lưu</span>
              </li>
            )}
          </ol>
        </header>
      )}

      <section aria-label="Thông tin hồ sơ" className={CARD}>
        <SectionHeader
          icon={<UserRound size={16} />}
          title="Thông tin hồ sơ"
          hint="Mục có dấu * là bắt buộc (Họ tên, Ngày sinh, SĐT, Giới tính, Cơ sở)."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className={LABEL}>
              Họ tên <Req />
            </label>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              onBlur={() => setFullName((v) => toTitleCaseVi(v))}
              className={INPUT}
              placeholder="Nguyễn Thị A"
            />
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <label className={LABEL + " mb-0"}>
                {dobYearOnly ? "Năm sinh" : "Ngày sinh"} <Req />
              </label>
              <label className="flex cursor-pointer items-center gap-1 text-[12px] text-ink-muted">
                <input
                  type="checkbox"
                  checked={dobYearOnly}
                  onChange={(e) => setDobYearOnly(e.target.checked)}
                  className="accent-brand-600"
                />
                Chỉ biết năm
              </label>
            </div>
            {dobYearOnly ? (
              <div>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={4}
                  value={birthYear}
                  onChange={(e) => {
                    // Năm sinh: tối đa 4 chữ số, KẸP > năm nay về năm nay (không
                    // để nhập 3245). < 1900 vẫn báo lỗi inline bên dưới.
                    let v = e.target.value.replace(/\D/g, "").slice(0, 4);
                    if (v.length === 4 && Number(v) > CUR_YEAR) v = String(CUR_YEAR);
                    setBirthYear(v);
                  }}
                  className={INPUT + (birthYearErr ? " border-danger" : "")}
                  placeholder="VD: 1990"
                />
                {birthYearErr && (
                  <p className="mt-1 text-[12px] text-danger">{birthYearErr}</p>
                )}
              </div>
            ) : (
              <div>
                <DateField
                  value={dobIso}
                  onChange={setDobIso}
                  max={TODAY}
                  ariaLabel="Ngày sinh"
                  invalid={!!dobErr}
                />
                {dobErr && (
                  <p className="mt-1 text-[12px] text-danger">{dobErr}</p>
                )}
              </div>
            )}
          </div>
          <div>
            <label className={LABEL}>
              SĐT chính <Req />
            </label>
            <input
              value={phone}
              onChange={(e) => setPhone(normalizePhoneVi(e.target.value))}
              className={INPUT + (phoneErr ? " border-danger" : "")}
              placeholder="10 chữ số, bắt đầu bằng 0 — vd 0901234567"
              inputMode="numeric"
              maxLength={10}
            />
            {phoneErr && (
              <p className="mt-1 text-[12px] text-danger">{phoneErr}</p>
            )}
            {/* Cảnh báo MỀM trùng SĐT (feedback #9) — KHÔNG chặn lưu. */}
            {phoneDupes.length > 0 && (
              <div className="mt-1.5 rounded-lg border border-warning/30 bg-warning-bg px-3 py-2 text-[12px] text-warning">
                <p className="font-medium">⚠ Số này đã có trong hệ thống:</p>
                <ul className="mt-1 space-y-0.5">
                  {phoneDupes.map((m) => (
                    <li key={m.patient_code}>
                      {m.full_name}{" "}
                      <span className="font-mono text-ink-muted">
                        {m.patient_code}
                      </span>
                      {m.birth_year && (
                        <span className="text-ink-muted"> · {m.birth_year}</span>
                      )}
                    </li>
                  ))}
                </ul>
                <p className="mt-1">
                  Kiểm tra xem có phải người nhà dùng chung số không. Vẫn tạo
                  mới được.
                </p>
              </div>
            )}
          </div>
          <div>
            <label className={LABEL}>SĐT người nhà (nếu có)</label>
            <input
              value={phone2}
              onChange={(e) => setPhone2(normalizePhoneVi(e.target.value))}
              className={INPUT + (phone2Err ? " border-danger" : "")}
              placeholder="10 chữ số, bắt đầu bằng 0"
              inputMode="numeric"
              maxLength={10}
            />
            {phone2Err && (
              <p className="mt-1 text-[12px] text-danger">{phone2Err}</p>
            )}
          </div>
          <div>
            <label className={LABEL}>CCCD (nếu cung cấp)</label>
            <input
              value={cccd}
              onChange={(e) => setCccd(digitsOnly(e.target.value).slice(0, 12))}
              className={INPUT + (cccdErr ? " border-danger" : "")}
              placeholder="12 chữ số"
              inputMode="numeric"
              maxLength={12}
            />
            {cccdErr && (
              <p className="mt-1 text-[12px] text-danger">{cccdErr}</p>
            )}
          </div>
          <div>
            <label className={LABEL}>
              Cơ sở đăng ký khám <Req />
            </label>
            <select
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              className={INPUT}
            >
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL}>
              Giới tính <Req />
            </label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className={INPUT}
            >
              <option value="" disabled hidden>— Chọn —</option>
              <option value="Nữ">Nữ</option>
              <option value="Nam">Nam</option>
              <option value="Khác">Khác</option>
            </select>
          </div>
          <div>
            <label className={LABEL}>Dân tộc</label>
            <input
              value={ethnicity}
              onChange={(e) => setEthnicity(e.target.value)}
              className={INPUT}
            />
          </div>
          <div>
            <label className={LABEL}>Quốc tịch</label>
            <input
              value={nationality}
              onChange={(e) => setNationality(e.target.value)}
              className={INPUT}
            />
          </div>
          <div>
            <label className={LABEL}>Nghề nghiệp</label>
            <input
              value={occupation}
              onChange={(e) => setOccupation(e.target.value)}
              className={INPUT}
            />
          </div>
          <div>
            <label className={LABEL}>Đối tượng</label>
            <input
              value={objection}
              onChange={(e) => setObjection(e.target.value)}
              className={INPUT}
              placeholder="DV / BHYT / ..."
            />
          </div>
          <div>
            <label className={LABEL}>
              Tỉnh / Thành phố {requireAddress && <Req />}
            </label>
            <SearchSelect
              options={provinceOpts}
              value={provinceCode}
              onChange={onProvinceChange}
              placeholder="Gõ để tìm tỉnh/thành…"
              ariaLabel="Tỉnh / Thành phố"
            />
          </div>
          <div>
            <label className={LABEL}>
              Phường / Xã {requireAddress && <Req />}
            </label>
            <SearchSelect
              options={wardOpts}
              value={wardCode}
              onChange={setWardCode}
              disabled={!provinceCode || wardsLoading}
              placeholder={
                !provinceCode
                  ? "— Chọn tỉnh trước —"
                  : wardsLoading
                    ? "Đang tải…"
                    : "Gõ để tìm phường/xã…"
              }
              ariaLabel="Phường / Xã"
            />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL}>Địa chỉ chi tiết (số nhà, đường)</label>
            <input
              value={addressDetail}
              onChange={(e) => setAddressDetail(e.target.value)}
              className={INPUT}
              placeholder="VD: 123 Lê Lợi"
            />
          </div>

          <div className="sm:col-span-2">
            <label className={LABEL}>Vấn đề khiến bệnh nhân đi khám</label>
            <input
              value={vanDe}
              onChange={(e) => setVanDe(e.target.value)}
              className={INPUT}
              placeholder="CSKH ghi theo lời bệnh nhân (khác Lý do khám của bác sĩ)"
            />
          </div>

          {/* Walk-in: Dịch vụ + Bác sĩ nằm CÙNG ô thông tin (không có lịch hẹn). */}
          {walkin && (
            <>
              <div>
                <label className={LABEL}>Dịch vụ khám</label>
                <select
                  value={linhVuc}
                  onChange={(e) => {
                    const code = e.target.value;
                    setLinhVuc(code);
                    const svcId = findServiceIdByLinhVuc(code, services);
                    setServiceId(svcId);
                  }}
                  className={INPUT}
                >
                  <option value="" disabled hidden>— Chọn dịch vụ —</option>
                  {LINH_VUC_OPTIONS.map((o) => (
                    <option key={o.code} value={o.code}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={LABEL}>Bác sĩ</label>
                <div className="relative">
                  <input
                    value={doctorQ}
                    onChange={(e) => {
                      setDoctorQ(e.target.value);
                      setDoctorId(""); // xóa chọn cũ khi gõ đè
                      setDoctorOpen(true);
                    }}
                    onFocus={() => setDoctorOpen(true)}
                    onBlur={() => setTimeout(() => setDoctorOpen(false), 150)}
                    placeholder="Tìm bác sĩ…"
                    className={INPUT}
                    autoComplete="off"
                  />
                  {doctorOpen && (
                    <ul className="absolute z-30 mt-1 max-h-52 w-full overflow-auto rounded-lg border border-line bg-white shadow-lg">
                      <li
                        onMouseDown={() => {
                          setDoctorId("");
                          setDoctorQ("");
                          setDoctorOpen(false);
                        }}
                        className="cursor-pointer px-3 py-2 text-sm text-ink-muted hover:bg-brand-50"
                      >
                        — Chưa phân bác sĩ —
                      </li>
                      {filteredDoctors.length === 0 ? (
                        <li className="px-3 py-2 text-sm text-ink-faint">
                          Không tìm thấy bác sĩ
                        </li>
                      ) : (
                        filteredDoctors.map((d) => (
                          <li
                            key={d.id}
                            onMouseDown={() => {
                              setDoctorId(d.id);
                              setDoctorQ(d.label);
                              setDoctorOpen(false);
                            }}
                            className={
                              "cursor-pointer px-3 py-2 text-sm hover:bg-brand-50 " +
                              (d.id === doctorId
                                ? "bg-brand-100 font-medium text-brand-800"
                                : "text-ink")
                            }
                          >
                            {d.label}
                          </li>
                        ))
                      )}
                    </ul>
                  )}
                </div>
              </div>
              <div>
                {/* Khách MỚI ⇒ luôn Khám mới (EPI-01 DEC-E5): bỏ nút Loại khám, giữ NEW. */}
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginTop: 6,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={needSono}
                    onChange={(e) => setNeedSono(e.target.checked)}
                  />
                  Có siêu âm
                </label>
              </div>
              {/* Số khám: KHÔNG nhập tay — hệ tự cấp khi check-in / walk-in auto-checkin. */}
              {/* Sơ đồ chỗ HÔM NAY: Lễ tân xếp khách vãng lai vào Ô XANH (chỗ thứ 3)
                  của khung còn trống; khung đã có khách vãng lai → ô kín, chọn khung
                  kế tiếp. BN1/BN2 hiện để đối chiếu, không bấm được ở chế độ này. */}
              <div className="sm:col-span-2">
                <label className={LABEL}>
                  Xếp chỗ vãng lai (ô xanh &quot;đặt vào đây&quot;) — bỏ trống nếu khám ngay
                </label>
                <CinemaSlotPicker
                  date={TODAY}
                  doctors={doctors}
                  dutyDoctorIds={dutyDoctorIds}
                  existingAppts={visibleExistingAppts}
                  selectedDoctorId={doctorId}
                  selectedTime={apptTime}
                  mode="walkin"
                  onPick={(docId, t) => {
                    setApptTime(t);
                    setDoctorId(docId);
                    setDoctorQ(
                      docId
                        ? (doctors.find((d) => d.id === docId)?.label ?? "")
                        : "",
                    );
                  }}
                />
                {apptTime && policy && (
                  <p
                    className={`mt-1 text-[11px] font-medium ${
                      isSlotBooked ? "text-danger" : "text-success"
                    }`}
                  >
                    {isSlotBooked
                      ? "Khung đang chọn đã có khách vãng lai — chuyển sang khung kế tiếp."
                      : `Xếp khách vào chỗ vãng lai khung ${slotRange(apptTime, policy.slotMinutes)}.`}
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </section>

      {!walkin && (
      <section aria-label="Lịch hẹn khám" className={CARD}>
        <SectionHeader
          icon={<CalendarClock size={16} />}
          title="Lịch hẹn khám"
          hint="Mục có dấu * là bắt buộc (Dịch vụ, Bác sĩ, Ngày, Giờ, Kênh đặt)."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className={LABEL}>
              Dịch vụ khám <Req />
            </label>
            <select
              value={linhVuc}
              onChange={(e) => {
                const code = e.target.value;
                setLinhVuc(code);
                const svcId = findServiceIdByLinhVuc(code, services);
                setServiceId(svcId);
              }}
              className={INPUT}
            >
              <option value="" disabled hidden>— Chọn dịch vụ —</option>
              {LINH_VUC_OPTIONS.map((o) => (
                <option key={o.code} value={o.code}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          {/* Ô "Tìm bác sĩ" ĐÃ BỎ.
              Quang 09/08/2026: *"chỉ xoá cả bảng chọn… nó dùng cho cả màn khách
              mới và khách cũ"*. Bác sĩ được chọn bằng cách bấm vào một ô trong
              sơ đồ khung giờ bên dưới — `onPick` set thẳng `doctorId`. Giữ thêm
              một ô gõ tay ở trên là hỏi cùng một câu hai lần bằng hai cách,
              trong đó cách gõ tay không biết gì về ca trực lẫn sức chứa. */}
          <div>
            <label className={LABEL}>
              Ngày khám <Req />
            </label>
            <DateField
              value={apptDate}
              onChange={setApptDate}
              min={TODAY}
              ariaLabel="Ngày khám"
            />
          </div>
          <div>
            <label className={LABEL}>
              Giờ <Req />
            </label>
            <Time24Input
              value={apptTime}
              onChange={setApptTime}
              minHour={apptMinHour}
              maxHour={apptMaxHour}
              minutesOptions={policy ? slotMinuteOptions(policy) : []}
            />
            {/* BỎ DÒNG "đến muộn 15 phút mất chỗ" (Quang chốt 09/08/2026).
                Nó là một lời hứa về luật vận hành mà hệ thống KHÔNG thi hành:
                không có chỗ nào hạ ưu tiên người đến muộn, và thứ tự gọi do
                services/queue_order.py quyết theo giờ check-in thật. Một câu
                doạ không có hiệu lực thì chỉ dạy người đọc bỏ qua chữ đỏ. */}
            {apptCh && (
              <p className="mt-1 text-[11px] text-ink-faint">
                Giờ mở cửa: {apptCh.open}–{apptCh.close}
              </p>
            )}
          </div>
          <div>
            {/* Khách MỚI ⇒ luôn Khám mới (EPI-01 DEC-E5): bỏ nút Loại khám, giữ NEW. */}
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginTop: 6,
              }}
            >
              <input
                type="checkbox"
                checked={needSono}
                onChange={(e) => setNeedSono(e.target.checked)}
              />
              Có siêu âm
            </label>
          </div>
          {/* SƠ ĐỒ CHỖ ĐÃ BỎ KHỎI BIỂU MẪU KHÁCH MỚI (Quang chốt 09/08/2026).

              Nó vẽ MỘT HÀNG CHO MỖI BÁC SĨ nhân với mọi khung giờ trong ngày —
              mười lăm bác sĩ thành mười lăm khối, kéo dài gấp ba phần biểu mẫu
              phía trên và đẩy nút "Nhập thông tin khách hàng" xuống tận đáy.
              Với một khách MỚI thì chọn ghế của bác sĩ nào cũng vô nghĩa: ngày
              đó có thể chưa xếp ca, và người khám sẽ do quản lý gán sau.

              Hai ô Ngày khám / Giờ ở trên vẫn đủ để đặt: thiếu bác sĩ thì lịch
              đi ra với doctor_id rỗng và rơi vào hàng đợi "Chờ xếp bác sĩ". */}
          {/* Số khám: KHÔNG nhập tay — hệ tự cấp khi check-in. */}
          <div>
            <label className={LABEL}>
              Kênh đặt {!gheTrucTiep && <Req />}
            </label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className={INPUT}
            >
              <option value="" disabled hidden>— Chọn kênh —</option>
              {CHANNELS.filter((c) => c.id !== "WALK_IN").map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>
      )}

      {/* Duplicate-phone warning */}
      {dupes && dupes.length > 0 && (
        <div className="space-y-2 rounded-xl border border-warning/30 bg-warning-bg px-4 py-3 text-sm text-warning">
          <p className="font-medium">
            ⚠️ Đã có bệnh nhân dùng SĐT này. Chọn đúng người để đặt lịch, hoặc
            vẫn tạo mới:
          </p>
          <ul className="space-y-1.5">
            {dupes.map((m) => (
              <li
                key={m.clinic_patient_id}
                className="flex flex-col gap-2 rounded-lg bg-white px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
              >
                <span className="text-ink">
                  {m.full_name}{" "}
                  <span className="font-mono text-xs text-ink-muted">
                    {m.patient_code}
                  </span>
                  {m.date_of_birth && (
                    <span className="ml-2 text-xs text-ink-muted">
                      {m.date_of_birth}
                    </span>
                  )}
                </span>
                <button
                  onClick={() => proceed(m.clinic_patient_id)}
                  disabled={submitting}
                  className="min-h-10 shrink-0 rounded-lg bg-brand-600 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-700 active:bg-brand-700 disabled:opacity-50 sm:min-h-0 sm:py-1.5"
                >
                  Dùng bệnh nhân này
                </button>
              </li>
            ))}
          </ul>
          <button
            onClick={() => save(true)}
            disabled={submitting}
            className="text-xs font-medium text-danger underline disabled:opacity-50"
          >
            Vẫn tạo bệnh nhân mới
          </button>
        </div>
      )}

      {error && (
        <div className="space-y-2 rounded-lg bg-danger-bg px-4 py-3 text-sm text-danger">
          <p>{error}</p>
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <button type="button" onClick={() => save(false)} disabled={submitting} className={BTN}>
          {submitting
            ? "Đang lưu..."
            : walkin
              ? wantsAppointment
                ? "Tạo bệnh nhân & lượt khám"
                : "Tạo bệnh nhân"
              : wantsAppointment
                ? role === "CSKH" || role === "TRUONG_CA" || role === "MANAGEMENT"
                  ? "Nhập thông tin khách hàng & đặt lịch"
                  : "Tạo bệnh nhân & đặt lịch"
                : role === "CSKH" || role === "TRUONG_CA" || role === "MANAGEMENT"
                  ? "Nhập thông tin khách hàng"
                  : "Tạo bệnh nhân"}
        </button>
        {onHuy ? (
          <button type="button" onClick={onHuy} className={BTN_GHOST}>
            Huỷ
          </button>
        ) : (
          <Link href="/patient-list" className={BTN_GHOST + " text-center"}>
            Huỷ
          </Link>
        )}
      </div>
    </div>
  );
}
