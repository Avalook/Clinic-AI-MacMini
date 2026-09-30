"use client";

// Single-step intake: patient details + (optional) first appointment on ONE
// form. Ô "Chỉ lưu hồ sơ — chưa đặt lịch" (Tuyền 25/09/2026, P4C) cho lưu khách
// mà không bắt dịch vụ/ngày/giờ — trước đó bản `full` bắt đủ lịch mới lưu được. One submit creates the patient (MPI dup-check) then books the
// appointment if a service + date + time were filled, and finally lands on the
// patient's profile. No more two-screen flow.

import { useState, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { UserRound, CalendarClock } from "lucide-react";
import Button from "@/components/ui/Button";
import { useDoiCa } from "../../dung-doi-ca";
import { nhanLoi } from "@/lib/loi-api";
import {
  docNhap,
  donNhapCu,
  ghiNhap,
  khoaNhap,
  moTaLuc,
  xoaNhap,
} from "../../../../lib/luu-nhap";
import { maTab } from "../../../../lib/ma-tab";
import { type ClinicRole } from "../../../../lib/roles";
import { useCheckInDuoc } from "../../QuyenContext";
import type { Option } from "../AppointmentBooking";
import CinemaSlotPicker from "../CinemaSlotPicker";
import BangBacSiTuan from "../../appointments/BangBacSiTuan";
import { phutVn, thuHaiCua } from "../../appointments/cho-trong";
import { hangCua, khungDay, phutCua } from "../../../../lib/suc-chua-luoi";
import { useBookingPolicy } from "../../BookingPolicyContext";
import { vnLocalToUtcISO, nowMs, slotRange } from "../../../../lib/datetime";
import {
  todayVn,
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
  HANG,
  HANG_LABEL,
  HANG_LABEL_HEP,
  BTN,
  BTN_GHOST,
  CARD,
  CHANNELS_CHON,
  KENH_GIOI_THIEU,
} from "../../form-ui";
import { useSucChuaNgay } from "../dung-suc-chua-ngay";

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
  /** Khoá hồ sơ — nút "thêm số cho khách này" gắn số vào đúng người này. */
  clinic_patient_id?: string;
  full_name: string;
  patient_code: string;
  birth_year: number | null;
}

/** Lịch hôm nay — chỉ còn đọc số khám để gợi ý số kế tiếp cho khách vãng lai.
 *  Số GHẾ không đếm từ danh sách này nữa (29/09/2026): máy chủ trả sẵn. */
interface IntakeAppointment {
  queue_number?: string | null;
}

/** Nút "thêm số cho khách này" trong ô cảnh báo trùng — lối đi thứ ba.
 *
 *  Hai lối cũ của ô cảnh báo là "vẫn tạo hồ sơ mới" (tách đôi bệnh án) và
 *  "bỏ dở". Tuyền 15/08/2026: khách cũ gọi từ số mới là chuyện hằng ngày —
 *  phải gắn được số mới vào hồ sơ CŨ ngay tại đây, không bắt mở màn khác.
 *
 *  Ở CẤP MODULE (không lồng trong form): component lồng bị React dựng lại
 *  mỗi lượt vẽ, mất chữ đang gõ. Mỗi hồ sơ khớp một bản — bấm ra một ô nhập
 *  NGAY BÊN PHẢI nút, Lưu là POST /api/patients/sdt-them; từ đó tra số nào
 *  cũng ra khách ấy. */
/** HAI LỐI RA KHI SỐ ĐIỆN THOẠI TRÙNG ĐÚNG MỘT HỒ SƠ (Tuyền 16/09/2026).
 *
 *  *"người này đã có trong cơ sở dữ liệu, đặt lịch khám mới? / Người khác (kèm
 *  ghi chú vào vì có thể người nhà bệnh nhân đến lấy kết quả mà dùng tên của
 *  bệnh nhân luôn)"*.
 *
 *  Trước đó cảnh báo chỉ LIỆT KÊ hồ sơ trùng rồi để người trực tự xoay: muốn
 *  đặt cho người cũ thì phải nhớ mã, thoát biểu mẫu, sang màn đặt lịch, tìm
 *  lại. Nay:
 *    · "Đặt lịch khám mới" → sang thẳng màn đặt lịch với ĐÚNG hồ sơ ấy được
 *      chọn sẵn. Không cần điền lại gì: mọi thông tin hành chính đã có trong
 *      hồ sơ, chỉ "vấn đề đi khám" là mỗi lần một khác nên để trống.
 *    · "Người khác" → mở ô ghi chú và ghi vào SỔ CHĂM SÓC CỦA HỒ SƠ CŨ. Ghi
 *      vào hồ sơ mới thì lần sau ai mở hồ sơ cũ vẫn không hiểu vì sao số ấy
 *      xuất hiện ở hai nơi — mà bản chất nó là chuyện của MỘT hồ sơ. */
function LoiRaKhiTrungSo({ khach }: { khach: PhoneMatch }) {
  const [mo, setMo] = useState(false);
  const [ghi, setGhi] = useState("");
  const [dang, setDang] = useState(false);
  const [ket, setKet] = useState<{ ok: boolean; cau: string } | null>(null);

  async function luu() {
    setDang(true);
    setKet(null);
    // TRY/CATCH, KHÔNG PHẢI `await` TRẦN. Bản đầu để `fetch` trần: mạng chớp
    // một cái là lời hứa bị từ chối, `setDang(false)` không bao giờ chạy và nút
    // đứng nguyên ở "Đang ghi…" — người trực ngồi chờ một việc đã chết. Bắt được
    // trên local: một lần bấm treo vĩnh viễn trong khi cùng lời gọi ấy chạy tay
    // vẫn trả 201.
    try {
      const res = await fetch("/api/cskh-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: "Ghi chú tiếp nhận",
          description: `Người khác dùng thông tin của hồ sơ này tại quầy${
            ghi.trim() ? ` — ${ghi.trim()}` : ""
          }`,
          patient_code: khach.patient_code,
        }),
      });
      setKet(
        res.ok
          ? { ok: true, cau: "Đã ghi vào hồ sơ này." }
          : { ok: false, cau: "Không ghi được — thử lại." },
      );
      if (res.ok) setGhi("");
    } catch {
      setKet({ ok: false, cau: "Mất mạng — chưa ghi được, thử lại." });
    } finally {
      setDang(false);
    }
  }

  return (
    <span className="ml-1 inline-flex flex-wrap items-center gap-1">
      <a
        href={`/appointments?bn=${encodeURIComponent(khach.patient_code)}`}
        className="rounded-chip border border-warning/40 px-1.5 py-0.5 text-meta font-semibold text-warning hover:bg-warning/10"
      >
        Đặt lịch khám mới
      </a>
      <button
        type="button"
        onClick={() => setMo((v) => !v)}
        className="rounded-chip border border-warning/40 px-1.5 py-0.5 text-meta font-semibold text-warning hover:bg-warning/10"
      >
        Người khác
      </button>
      {mo && (
        <span className="inline-flex flex-wrap items-center gap-1">
          <input
            value={ghi}
            onChange={(e) => setGhi(e.target.value)}
            placeholder="VD: người nhà tới lấy kết quả hộ"
            className="min-w-48 rounded-control border border-line bg-surface px-2 py-1 text-meta text-ink outline-none focus:border-brand-600"
          />
          <button
            type="button"
            disabled={dang}
            onClick={() => void luu()}
            className="rounded-control bg-brand-600 px-2 py-1 text-meta font-semibold text-white disabled:opacity-50"
          >
            {dang ? "Đang ghi…" : "Ghi vào hồ sơ này"}
          </button>
          {ket && (
            <span className={ket.ok ? "text-meta text-success" : "text-meta text-danger"}>
              {ket.cau}
            </span>
          )}
        </span>
      )}
    </span>
  );
}

function ThemSdtChoKhach({
  khach,
  goiY,
}: {
  khach: PhoneMatch;
  /** Số điền sẵn — chính là số đang gõ trên form khi cảnh báo là TRÙNG TÊN
   *  (số ấy chưa thuộc về ai). Ô trùng SỐ thì không gợi ý: số đang gõ đã là
   *  của hồ sơ này rồi, thứ cần nhập là một số KHÁC. */
  goiY?: string;
}) {
  const [mo, setMo] = useState(false);
  const [so, setSo] = useState("");
  const [loai, setLoai] = useState<"CHINH" | "NGUOI_NHA">("CHINH");
  const [dang, setDang] = useState(false);
  const [ket, setKet] = useState<{ ok: boolean; cau: string } | null>(null);

  if (!khach.clinic_patient_id) return null;

  async function luu() {
    setDang(true);
    setKet(null);
    const res = await fetch("/api/patients/sdt-them", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: khach.clinic_patient_id,
        so_dien_thoai: so,
        loai,
      }),
    });
    setDang(false);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setKet({ ok: false, cau: nhanLoi(d, `Chưa ghi được (lỗi ${res.status}).`) });
      return;
    }
    setKet({
      ok: true,
      cau: `Đã thêm ${so} cho ${khach.full_name} — tra số nào cũng ra khách này. Nếu chỉ cần cập nhật số thì KHÔNG cần tạo hồ sơ mới nữa.`,
    });
    setMo(false);
  }

  if (ket?.ok) {
    return <p className="mt-1 font-medium text-success">✓ {ket.cau}</p>;
  }
  if (!mo) {
    return (
      <button
        type="button"
        onClick={() => {
          setMo(true);
          if (goiY && /^0\d{9}$/.test(goiY)) setSo(goiY);
        }}
        className="mt-1 inline-flex h-7 items-center gap-1 rounded-control bg-surface px-2.5 text-label font-semibold text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50"
      >
        ＋ Thêm số điện thoại cho khách này
      </button>
    );
  }
  return (
    <span className="mt-1 flex flex-wrap items-center gap-1.5">
      <input
        value={so}
        onChange={(e) => setSo(e.target.value.replace(/\D/g, "").slice(0, 10))}
        placeholder="Số muốn thêm — 10 chữ số"
        inputMode="numeric"
        autoFocus
        className="h-7 w-44 rounded-control bg-surface px-2 text-body text-ink ring-1 ring-inset ring-line focus:ring-brand-500 outline-none"
      />
      {/* Số này là CỦA KHÁCH hay của NGƯỜI NHÀ — vẽ dưới đúng dòng cùng loại
          trên hồ sơ, nên phải hỏi ngay lúc ghi, không đoán. */}
      {(["CHINH", "NGUOI_NHA"] as const).map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={loai === l}
          onClick={() => setLoai(l)}
          className={
            loai === l
              ? "h-7 rounded-control bg-brand-600 px-2 text-label font-semibold text-white"
              : "h-7 rounded-control bg-surface px-2 text-label font-medium text-ink-soft ring-1 ring-inset ring-line hover:bg-surface-muted"
          }
        >
          {l === "CHINH" ? "Số của khách" : "Số người nhà"}
        </button>
      ))}
      <Button
        variant="primary"
        size="sm"
        disabled={so.length !== 10 || dang}
        onClick={() => void luu()}
      >
        {dang ? "Đang ghi…" : "Lưu số"}
      </Button>
      <button
        type="button"
        onClick={() => setMo(false)}
        className="text-label text-ink-faint hover:text-ink-muted"
      >
        Thôi
      </button>
      {ket && !ket.ok && (
        <span className="basis-full text-label text-danger">{ket.cau}</span>
      )}
    </span>
  );
}

// Ô "Dịch vụ khám" khi đặt lịch = 5 lĩnh vực + hai loại khám ĐI THẲNG PHÒNG
// (28/09/2026 — Tuyền: "node đặt lịch hẹn chưa có thủ thuật và sàn chậu chuyên
// sâu"). Hai loại sau KHÔNG có mã lĩnh vực trên hồ sơ (CHECK `patient_linh_vuc`
// chỉ nhận 5 mã) — chỉ chọn loại khám; `linh_vuc` gửi rỗng.
const LOAI_KHAM_DAT_LICH: { code: string; label: string }[] = [
  ...LINH_VUC_OPTIONS,
  { code: "TT", label: "Thủ thuật" },
  { code: "SC", label: "Sàn chậu chuyên sâu" },
];
const MA_LINH_VUC = new Set(LINH_VUC_OPTIONS.map((o) => o.code));

function findServiceIdByLinhVuc(code: string, services: Option[]): string {
  if (!code) return "";
  const nameMap: Record<string, string[]> = {
    PK: ["Phụ khoa", "PHU_KHOA"],
    SK: ["Sản 1", "Sản khoa", "Sản", "SAN_1"],
    NT: ["Nội tiết - Tình dục", "Nội tiết", "NOI_TIET_TINH_DUC"],
    HMVS: ["Hiếm muộn", "Hiếm muộn - Vô sinh", "HIEM_MUON"],
    NK: ["Nam khoa", "NAM_KHOA"],
    TT: ["Thủ thuật", "THU_THUAT"],
    SC: ["Sàn chậu chuyên sâu", "Sàn chậu", "SAN_CHAU"],
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
  // Không đoán loại khám khác (bản trước trả loại khám ĐẦU danh sách — chọn
  // "Thủ thuật" mà không khớp tên là đặt nhầm thành Phụ khoa).
  return "";
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
  staffId = null,
  coSoMacDinhId = null,
  role,
  locations,
  services,
  doctors,
  provinces,
  variant = "full",
  initialAppt,
  nhung = false,
  onHuy,
  veTiepDon = false,
}: {
  /** Khoá bản nhập dở theo NGƯỜI đang đăng nhập — quầy dùng chung máy,
   *  nháp của người trước không được hiện cho người sau (luu-nhap.ts). */
  staffId?: string | null;
  role?: ClinicRole | null;
  locations: Option[];
  /** Cơ sở của người đang đặt (staff.primary_location_id qua /api/v1/me).
   *  Mặc định ô "Cơ sở đăng ký khám" — KHÔNG phải cơ sở đầu danh sách. */
  coSoMacDinhId?: string | null;
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
  /** Lưu xong thì về màn TIẾP ĐÓN KHÁCH (`/reception/queue`) để làm tiếp
   *  (Tuyền 29/09/2026). Trang gọi hỏi `moDuocMan("/reception/queue")` — cùng
   *  luật cửa của trang đích (lego, không theo vai). false → hành vi cũ. */
  veTiepDon?: boolean;
}) {
  const walkin = variant === "walkin";
  // Kênh "Trực tiếp" kéo theo tự check-in → theo LEGO Tiếp đón (30/09/2026).
  const checkInDuoc = useCheckInDuoc(role);
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
  // Cơ sở CỦA NGƯỜI ĐẶT trước, rồi mới tới đầu danh sách (16/09/2026): danh
  // sách xếp theo tên nên `locations[0]` là "Kim Ngưu" với mọi người — hồ sơ
  // khách mới của CSKH ở cơ sở khác rơi sai cơ sở mà không ai để ý.
  const coSoDau =
    locations.find((l) => l.id === coSoMacDinhId)?.id ?? locations[0]?.id ?? "";
  const [locationId, setLocationId] = useState(coSoDau);
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
  // P4C (25/09/2026): lưu hồ sơ khách, CHƯA đặt lịch. Mặc định KHÔNG tick —
  // luồng đặt lịch như cũ; tick thì bỏ khối lịch và bỏ kiểm dịch vụ/ngày/giờ.
  const [chuaDatLich, setChuaDatLich] = useState(false);

  // ── BẢN NHẬP DỞ (Tuyền 17/08: "mất mạng hay refresh thì có lưu lại
  // không?"). Cùng cơ chế đã chạy ở màn bệnh án (lib/luu-nhap): localStorage
  // khoá theo người đăng nhập, hạn 24h, ghi sau mỗi nhịp gõ ngừng 1 giây.
  // CHỈ giữ phần HÀNH CHÍNH — ngày/giờ/bác sĩ của lịch hẹn KHÔNG khôi phục:
  // chúng thường tới từ URL ("đặt vào đây") và một khung giờ cũ khôi phục lại
  // có thể đã bị người khác giữ mất — bịa lại lựa chọn thời gian là sai hơn
  // bắt chọn lại. ──
  // KHOÁ THEO TAB, không phải chữ "form" cố định. Hai tab cùng nhập khách mới
  // thì tab gõ sau từng ghi đè bản nháp của tab gõ trước — người kia F5 là nhận
  // về thông tin của khách khác. Xem lib/ma-tab.ts.
  const khoaNhapKhach = khoaNhap(staffId, "khach-moi", maTab() || "form");
  const [nhapDo, setNhapDo] = useState<{
    moTa: string;
    giaTri: Record<string, string | boolean>;
  } | null>(() => {
    if (typeof window === "undefined" || !khoaNhapKhach) return null;
    donNhapCu(window.localStorage, Date.now());
    const b = docNhap<Record<string, string | boolean>>(
      window.localStorage,
      khoaNhapKhach,
      Date.now(),
    );
    return b ? { moTa: moTaLuc(b.luc, Date.now()), giaTri: b.giaTri } : null;
  });
  const mocNhapRef = useRef<string>("");

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
  // BẢNG BÁC SĨ × TUẦN cho khách mới (16/09/2026) — cùng nguồn "còn chỗ" với
  // màn Đặt lịch. `oLich` = ô (bác sĩ × ngày) đang mở lưới khung giờ.
  const [tuanLech, setTuanLech] = useState(0);
  const [oLich, setOLich] = useState<{
    doctorId: string | null;
    doctorName: string;
    date: string;
  } | null>(null);
  const [phutHienTai] = useState(() => phutVn(nowMs()));
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
  // Bác sĩ TRỰC CA (work_roster LICH_KHAM) của ngày đang đặt — sơ đồ chỉ hiện
  // các bác sĩ này. null = chưa nạp; [] = ngày chưa phân trực (fallback tất cả).
  const [dutyDoctorIds, setDutyDoctorIds] = useState<string[] | null>(null);
  /** Tuần chứa ngày đã chọn chưa được bấm "Áp dụng tuần" — xem /api/roster. */
  const [dutyDuKien, setDutyDuKien] = useState(false);
  const dutyDate = walkin ? TODAY : apptDate;
  // Ca trực đổi giữa chừng (quản lý thêm/xoá ca) → nạp lại danh sách bác sĩ
  // trực của ngày — lưới đặt chỗ vẽ theo danh sách này. Xem dung-doi-ca.ts.
  const doiCa = useDoiCa();
  useEffect(() => {
    if (!dutyDate) return;
    const ctrl = new AbortController();
    fetch(`/api/roster?date=${encodeURIComponent(dutyDate)}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        setDutyDoctorIds(
          j ? (j.doctors as { id: string }[]).map((d) => d.id) : null,
        );
        setDutyDuKien(Boolean(j?.du_kien));
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [dutyDate, doiCa]);

  // SỐ GHẾ + KHOẢNG CA của lưới vãng lai hôm nay — MỘT lượt hỏi máy chủ, xem
  // `dung-suc-chua-ngay.ts`. Chỉ màn vãng lai có lưới, nên chỉ hỏi khi walkin.
  const sucChua = useSucChuaNgay(walkin ? dutyDate : null, [
    ...(dutyDoctorIds ?? []),
    doctorId,
  ]);
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
  const [gioiThieu, setGioiThieu] = useState("");
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
          const appts: IntakeAppointment[] = data.appointments ?? [];
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
    }
    // Biểu mẫu đặt lịch đầy đủ không có lưới ghế ở đây — không cần danh sách
    // lịch của ngày (bản trước nạp nó chỉ để tự đếm ghế, 29/09/2026 đã bỏ).
  }, [walkin, TODAY]);

  // Khung đang chọn còn ghế ĐÚNG LOẠI không — THEO MÁY CHỦ (trần theo bác sĩ ×
  // khung, cờ chặn của trigger), không tự đếm lịch và không lấy trần chung.
  const isSlotBooked =
    walkin && apptTime
      ? khungDay(
          hangCua(sucChua.data, doctorId || null),
          phutCua(apptTime),
          "walkin",
        ) === true
      : false;

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
  // TRÙNG TÊN ĐƠN THUẦN — tín hiệu YẾU, tách khỏi `phoneDupes`.
  //
  // `phoneDupes` là những hồ sơ mà ĐƯỜNG LƯU cũng coi là trùng (số điện thoại,
  // CCCD, hoặc tên + năm sinh). Danh sách này thì chỉ trùng tên — thường gặp ở
  // Việt Nam nên không được trộn vào đó, nếu không người trực sẽ học cách bỏ
  // qua cả hai.
  const [trungTen, setTrungTen] = useState<PhoneMatch[]>([]);
  /** Năm sinh đang gõ — dùng để đoán nhánh nào đã khớp (xem chỗ vẽ cảnh báo). */
  const namSinhDangGo = dobYearOnly
    ? Number(birthYear) || null
    : Number(dobIso.slice(0, 4)) || null;
  const [dupes, setDupes] = useState<DupMatch[] | null>(null);
  // CCCD trùng hồ sơ khác: cảnh báo + bắt ghi lý do (Tuyền chốt 15/09/2026 —
  // trước đó chặn cứng). Backend quyết; ô này chỉ gom lý do để gửi lại.
  const [cccdTrung, setCccdTrung] = useState(false);
  const [lyDoTrungCccd, setLyDoTrungCccd] = useState("");

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
      // TÊN 3 KÝ TỰ LÀ ĐỦ HỎI (Tuyền 15/08/2026): khách cũ đọc số mới,
      // người trực gõ tên trước khi kịp hỏi năm sinh — trước đây nhánh này
      // đòi cả năm nên đúng ca hay gặp nhất không bao giờ được cảnh báo.
      // Năm sinh (khi có) vẫn được gửi kèm để bật nhánh khớp MẠNH.
      const coTen = fullName.trim().length >= 3;
      const coNam = nam >= 1900 && nam <= CUR_YEAR;
      if (digits.length !== 10 && !coTen) {
        if (alive) {
          setPhoneDupes([]);
          setTrungTen([]);
        }
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
            if (coNam) qs.set("birth_year", String(nam));
          }
          const res = await fetch(`/api/patients/check-duplicate?${qs}`);
          if (!res.ok) return;
          const json = (await res.json()) as {
            exists?: boolean;
            matches?: PhoneMatch[];
            trung_ten?: PhoneMatch[];
          };
          if (alive) {
            setPhoneDupes(json.exists ? (json.matches ?? []) : []);
            setTrungTen(json.trung_ten ?? []);
          }
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
    : !chuaDatLich && !!(serviceId && apptDate && apptTime);
  // Hồ sơ chỉ bắt buộc Họ tên (30/09/2026). Muốn ĐẶT LỊCH thì vẫn cần Dịch vụ +
  // Ngày + Giờ + Kênh; để trống cả khối lịch (hoặc tick "Chỉ lưu hồ sơ") = chỉ lưu hồ sơ.
  // Lỗi nhỏ ngay cạnh ô SĐT/CCCD (live) — rõ ô NÀO sai (chính/người nhà/CCCD),
  // không chờ submit + không còn 1 câu lỗi chung gây khó hiểu.
  const phoneErr = phoneError(phone);
  const phone2Err = phoneError(phone2);
  const cccdErr = cccdError(cccd);

  async function bookFor(clinicPatientId: string): Promise<boolean> {
    // Cùng lớp đỡ như save(): state có thể còn rỗng nếu danh sách cơ sở tới
    // sau, và gửi location_id rỗng thì backend từ chối bằng một câu khó hiểu.
    const effLocationId = locationId || coSoDau;
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
        nguoi_gioi_thieu:
          channel === KENH_GIOI_THIEU ? gioiThieu.trim() || undefined : undefined,
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
  // Ghi nháp sau mỗi nhịp gõ ngừng 1 giây — chỉ khi đã có gì đáng cứu.
  useEffect(() => {
    if (!khoaNhapKhach || typeof window === "undefined") return;
    const giaTri: Record<string, string | boolean> = {
      fullName, dobIso, dobYearOnly, birthYear, phone, phone2, cccd,
      gender, ethnicity, nationality, occupation, objection,
      provinceCode, wardCode, addressDetail, vanDe, linhVuc,
    };
    const hienTai = JSON.stringify(giaTri);
    if (mocNhapRef.current === "") {
      mocNhapRef.current = hienTai; // lần đầu: form trống/prefill — chưa ai gõ
      return;
    }
    if (hienTai === mocNhapRef.current) return;
    const coGiCuu = fullName.trim() || phone || cccd || vanDe;
    if (!coGiCuu) return;
    const t = setTimeout(() => {
      ghiNhap(window.localStorage, khoaNhapKhach, giaTri, Date.now());
      mocNhapRef.current = hienTai;
    }, 1000);
    return () => clearTimeout(t);
  }, [
    khoaNhapKhach, fullName, dobIso, dobYearOnly, birthYear, phone, phone2,
    cccd, gender, ethnicity, nationality, occupation, objection,
    provinceCode, wardCode, addressDetail, vanDe, linhVuc,
  ]);

  function khoiPhucNhap() {
    if (!nhapDo) return;
    const g = nhapDo.giaTri;
    const chu = (k: string) => (typeof g[k] === "string" ? (g[k] as string) : "");
    setFullName(chu("fullName"));
    setDobIso(chu("dobIso"));
    setDobYearOnly(Boolean(g["dobYearOnly"]));
    setBirthYear(chu("birthYear"));
    setPhone(chu("phone"));
    setPhone2(chu("phone2"));
    setCccd(chu("cccd"));
    setGender(chu("gender"));
    setEthnicity(chu("ethnicity") || "Kinh");
    setNationality(chu("nationality") || "Việt Nam");
    setOccupation(chu("occupation"));
    setObjection(chu("objection"));
    setProvinceCode(chu("provinceCode"));
    setWardCode(chu("wardCode"));
    setAddressDetail(chu("addressDetail"));
    setVanDe(chu("vanDe"));
    setLinhVuc(chu("linhVuc"));
    setNhapDo(null);
  }

  function boNhap() {
    if (khoaNhapKhach && typeof window !== "undefined") {
      xoaNhap(window.localStorage, khoaNhapKhach);
    }
    setNhapDo(null);
  }

  function goToProfile(id: string, code?: string) {
    // TẠO XONG LÀ NHÁP HẾT VIỆC — để lại thì lần mở sau mời khôi phục một
    // khách đã nằm trong hệ thống, và người trực tạo trùng.
    if (khoaNhapKhach && typeof window !== "undefined") {
      xoaNhap(window.localStorage, khoaNhapKhach);
    }
    // TẠO XONG → VỀ MÀN TIẾP ĐÓN (Tuyền 29/09/2026: "lễ tân thêm khách mới
    // xong thì nhảy về màn Tiếp đón khách để làm việc tiếp"). Áp cho mọi đường
    // lưu thành công: chỉ lưu hồ sơ, lưu + đặt lịch (khách Trực tiếp hôm nay đã
    // tự check-in nên hiện ngay trong danh sách), và "Dùng bệnh nhân này". Ai
    // được vào màn ấy do trang quyết theo lego (`veTiepDon`), không theo vai.
    if (veTiepDon) {
      router.push("/reception/queue");
      return;
    }
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

  async function save(force: boolean, lyDoCccd?: string) {
    setError(null);
    const effLocationId = locationId || coSoDau;
    if (!effLocationId) {
      setError("Chưa chọn cơ sở khám.");
      return;
    }
    // CHỈ BẮT BUỘC HỌ TÊN (Tuyền chốt 30/09/2026). Quầy đông, khách đứng chờ —
    // SĐT, giới tính, ngày sinh, địa chỉ để trống được, sửa sau ở hồ sơ
    // (PatientAdminEditor). Backend và database vốn đã cho các cột này NULL.
    if (!fullName.trim()) {
      setError("Vui lòng nhập Họ và tên bệnh nhân (ở mục Thông tin hồ sơ phía trên).");
      return;
    }
    // Bỏ trống thì cho qua; ĐÃ ĐIỀN thì phải đúng định dạng — số sai lưu xuống
    // còn tệ hơn không có số (SĐT 10 số / CCCD 12 số / năm sinh 1900–nay).
    const ve =
      phoneError(phone) ||
      phoneError(phone2) ||
      cccdError(cccd) ||
      (dobYearOnly ? birthYearErr : dobErr);
    if (ve) {
      setError(ve);
      return;
    }
    // ĐẶT LỊCH (khách thường, không vãng lai) cần Dịch vụ + Ngày + Giờ + Kênh.
    // Tick "Chỉ lưu hồ sơ" — HOẶC để trống cả dịch vụ, ngày, giờ — thì chỉ lưu
    // hồ sơ (30/09/2026: quầy đông chỉ kịp gõ tên, đừng bắt nhớ tick). Nút lúc
    // ấy đã đổi nhãn thành "Tạo bệnh nhân", không còn "& đặt lịch". Đã chọn
    // DỞ một phần lịch thì vẫn đòi đủ — người ta đang định đặt.
    const lichTrong = !serviceId && !apptDate && !apptTime;
    if (!walkin && !chuaDatLich && !lichTrong) {
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
        linh_vuc: MA_LINH_VUC.has(linhVuc) ? linhVuc : undefined,
        force,
        ly_do_trung_cccd: lyDoCccd?.trim() || undefined,
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
      setCccdTrung(Boolean(json.cccd_trung));
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
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-label font-bold text-white">1</span>
              <span className="font-semibold">Thông tin hồ sơ</span>
            </li>
            <li className="flex items-center gap-2 px-4 py-3 text-ink-muted">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-surface-sunken text-label font-bold text-ink-soft">2</span>
              <span>{walkin ? "Dịch vụ & lượt khám" : "Lịch hẹn khám"}</span>
            </li>
            {!walkin && (
              <li className="hidden items-center gap-2 px-4 py-3 text-ink-muted sm:flex">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-surface-sunken text-label font-bold text-ink-soft">3</span>
                <span>Xác nhận & lưu</span>
              </li>
            )}
          </ol>
        </header>
      )}

      {/* BẢN NHẬP DỞ — mất mạng/F5 giữa chừng thì gõ lại từ đầu là hình phạt
          sai người (tình huống phát sinh mục 4). Chỉ NHẮC, không tự đổ vào
          form: người trực có thể đang cố tình nhập một khách KHÁC. */}
      {nhapDo && (
        <div className="flex flex-wrap items-center gap-2 rounded-control bg-warning-bg px-3 py-2 text-meta text-warning">
          <span className="font-medium">
            🕘 Có bản nhập dở lưu {nhapDo.moTa} — khôi phục?
          </span>
          <button
            type="button"
            onClick={khoiPhucNhap}
            className="h-7 rounded-control bg-surface px-2.5 text-label font-semibold text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50"
          >
            Khôi phục
          </button>
          <button
            type="button"
            onClick={boNhap}
            className="text-label text-ink-faint hover:text-ink-muted"
          >
            Bỏ nháp
          </button>
        </div>
      )}

      <section aria-label="Thông tin hồ sơ" className={CARD}>
        <SectionHeader
          icon={<UserRound size={16} />}
          title="Thông tin hồ sơ"
          hint="Chỉ cần Họ tên — các ô khác để trống được, sửa sau ở hồ sơ."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className={LABEL}>
              Họ tên
            </label>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              onBlur={() => setFullName((v) => toTitleCaseVi(v))}
              className={INPUT}
              placeholder="Nguyễn Thị A"
            />
          </div>
          <div className={HANG}>
            <label className={HANG_LABEL_HEP}>
              {dobYearOnly ? "Năm sinh" : "Ngày sinh"}
            </label>
            {dobYearOnly ? (
              <div className="min-w-0 flex-1">
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
                  <p className="mt-1 text-meta text-danger">{birthYearErr}</p>
                )}
              </div>
            ) : (
              <div className="min-w-0 flex-1">
                <DateField
                  value={dobIso}
                  onChange={setDobIso}
                  max={TODAY}
                  ariaLabel="Ngày sinh"
                  invalid={!!dobErr}
                />
                {dobErr && (
                  <p className="mt-1 text-meta text-danger">{dobErr}</p>
                )}
              </div>
            )}
            {/* Ô tích đi CÙNG DÒNG với ô ngày (16/09/2026) — nó đổi chính ô
                bên cạnh, để tách ra một dòng riêng thì phải dò xem nó đổi cái
                gì. */}
            <label className="flex cursor-pointer items-center gap-1 whitespace-nowrap text-meta text-ink-muted">
              <input
                type="checkbox"
                checked={dobYearOnly}
                onChange={(e) => setDobYearOnly(e.target.checked)}
                className="accent-brand-600"
              />
              Chỉ biết năm
            </label>
          </div>
          <div>
            <label className={LABEL}>
              SĐT chính
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
              <p className="mt-1 text-meta text-danger">{phoneErr}</p>
            )}
            {/* Cảnh báo MỀM trùng SĐT (feedback #9) — KHÔNG chặn lưu. */}
            {phoneDupes.length > 0 && (
              <div className="mt-1.5 rounded-lg border border-warning/30 bg-warning-bg px-3 py-2 text-meta text-warning">
                {/* NÓI ĐÚNG THỨ ĐÃ KHỚP.
                    Bản trước luôn mở đầu bằng "Số này đã có trong hệ thống",
                    kể cả khi thứ khớp là TÊN + NĂM SINH chứ không phải số điện
                    thoại — nên người trực đọc xong vẫn tưởng nó nói về số, và
                    một cảnh báo trùng tên trôi qua như không có.
                    Suy được vì luật khớp mạnh chỉ có ba nhánh, mà biểu mẫu này
                    không gửi CCCD: khớp cả tên lẫn năm sinh ⇒ nhánh tên; còn
                    lại ⇒ nhánh số điện thoại. */}
                <p className="font-medium">
                  ⚠{" "}
                  {phoneDupes.every(
                    (m) =>
                      m.birth_year === namSinhDangGo &&
                      unaccentVi(m.full_name) === unaccentVi(fullName.trim()),
                  )
                    ? "Trùng cả họ tên và năm sinh với hồ sơ đã có:"
                    : "Số này đã có trong hệ thống:"}
                </p>
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
                      {/* Khách dùng thêm số khác? Gắn ngay vào hồ sơ này —
                          KHÔNG gợi ý số đang gõ: nó đã là của hồ sơ này. */}
                      <ThemSdtChoKhach khach={m} />
                      <LoiRaKhiTrungSo khach={m} />
                    </li>
                  ))}
                </ul>
                <p className="mt-1">
                  Kiểm tra xem có phải người nhà dùng chung số không. Vẫn tạo
                  mới được.
                </p>
              </div>
            )}
            {/* TRÙNG TÊN — VÀNG NHẠT (Tuyền 16/09/2026 muốn nó cũng là cảnh
                báo vàng). Nhưng vẫn PHẢI nhẹ hơn khối trên và không có nút
                hành động: trùng tên ở Việt Nam là chuyện thường, để hai khối
                y hệt nhau là dạy người trực bỏ qua cả hai. Nhạt + không nút =
                vẫn vàng mà vẫn phân biệt được nặng nhẹ. */}
            {trungTen.length > 0 && (
              <div className="mt-1.5 rounded-lg border border-warning/25 bg-warning-bg/50 px-3 py-2 text-meta text-ink-soft">
                <p className="font-medium text-warning">
                  ⚠ Đã có {trungTen.length} hồ sơ trùng họ tên:
                </p>
                <ul className="mt-1 space-y-0.5">
                  {trungTen.map((m) => (
                    <li key={m.patient_code}>
                      {m.full_name}{" "}
                      <span className="font-mono text-ink-muted">
                        {m.patient_code}
                      </span>
                      {m.birth_year && (
                        <span className="text-ink-muted"> · {m.birth_year}</span>
                      )}
                      {/* Trùng tên + khách đọc một số MỚI = đúng ca "khách
                          cũ, số mới": gợi ý luôn số đang gõ trên form. */}
                      <ThemSdtChoKhach khach={m} goiY={phone} />
                    </li>
                  ))}
                </ul>
                <p className="mt-1">
                  Trùng tên là chuyện thường — chỉ nhắc để kiểm lại năm sinh có
                  gõ nhầm không.
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
              <p className="mt-1 text-meta text-danger">{phone2Err}</p>
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
              <p className="mt-1 text-meta text-danger">{cccdErr}</p>
            )}
          </div>
          <div>
            <label className={LABEL}>
              Cơ sở đăng ký khám
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
              Giới tính
            </label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className={INPUT}
            >
              <option value="">— Chưa rõ —</option>
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
          <div className={HANG}>
            <label className={HANG_LABEL}>Quốc tịch</label>
            <input
              value={nationality}
              onChange={(e) => setNationality(e.target.value)}
              className={INPUT}
            />
          </div>
          <div className={HANG}>
            <label className={HANG_LABEL}>Nghề nghiệp</label>
            <input
              value={occupation}
              onChange={(e) => setOccupation(e.target.value)}
              className={INPUT}
            />
          </div>
          <div className={HANG}>
            <label className={HANG_LABEL}>Đối tượng</label>
            <input
              value={objection}
              onChange={(e) => setObjection(e.target.value)}
              className={INPUT}
              placeholder="DV / BHYT / ..."
            />
          </div>
          <div>
            <label className={LABEL}>
              Tỉnh / Thành phố
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
              Phường / Xã
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
          <div className={`sm:col-span-2 ${HANG}`}>
            <label className={HANG_LABEL}>Địa chỉ chi tiết</label>
            <input
              value={addressDetail}
              onChange={(e) => setAddressDetail(e.target.value)}
              className={INPUT}
              placeholder="VD: 123 Lê Lợi"
            />
          </div>

          <div className={`sm:col-span-2 ${HANG}`}>
            <label className={HANG_LABEL}>Vấn đề đi khám</label>
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
                  {LOAI_KHAM_DAT_LICH.map((o) => (
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
                  dutyDuKien={dutyDuKien}
                  sucChua={sucChua}
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
                    className={`mt-1 text-label font-medium ${
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
          hint="Bắt buộc: Dịch vụ, Bác sĩ, Ngày, Giờ, Kênh đặt."
        />
        <label className="mb-3 flex min-h-10 items-center gap-2 text-body text-ink">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={chuaDatLich}
            onChange={(e) => setChuaDatLich(e.target.checked)}
          />
          Chỉ lưu hồ sơ — chưa đặt lịch
        </label>
        {chuaDatLich ? (
          <p className="text-meta text-ink-muted">
            Lưu khách vào hệ thống, không tạo lịch hẹn. Đặt lịch sau ở màn Đặt lịch.
          </p>
        ) : null}
        <div className={chuaDatLich ? "hidden" : "grid grid-cols-1 gap-4 sm:grid-cols-2"}>
          <div className={`sm:col-span-2 ${HANG}`}>
            <label className={HANG_LABEL}>
              Dịch vụ khám
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
              {LOAI_KHAM_DAT_LICH.map((o) => (
                <option key={o.code} value={o.code}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          {/* KÊNH ĐẶT ngay dưới Dịch vụ khám (Tuyền 16/09/2026): hai ô này là
              "khám gì" và "khách tới từ đâu" — trả lời một lượt rồi mới tới
              chuyện xếp giờ. Ô "Có siêu âm" đã bỏ khỏi biểu mẫu khách mới: siêu
              âm là một DỊCH VỤ trong ô ngay trên, nên hỏi lại bằng ô tích là
              mời người nhập tự mâu thuẫn với chính mình. Cột `need_sono` vẫn
              còn và luồng VÃNG LAI của lễ tân vẫn tích được. */}
          <div className={`sm:col-span-2 ${HANG}`}>
            <label className={HANG_LABEL}>
              Kênh đặt
            </label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className={INPUT}
            >
              <option value="" disabled hidden>— Chọn kênh —</option>
              {/* "Trực tiếp" chỉ hiện với người có lego Tiếp đón (check-in):
                  kênh ấy kéo theo tự check-in, và backend từ chối thẳng nếu
                  người đặt không được check-in (luật Tuyền 15/09/2026). */}
              {CHANNELS_CHON.filter(
                (c) => c.id !== "WALK_IN" || checkInDuoc,
              ).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            {channel === KENH_GIOI_THIEU ? (
              <input
                value={gioiThieu}
                onChange={(e) => setGioiThieu(e.target.value)}
                maxLength={200}
                placeholder="Ai giới thiệu? (lưu vào hồ sơ khám)"
                aria-label="Người giới thiệu"
                className={`${INPUT} mt-2`}
              />
            ) : null}
          </div>
          {/* Ô "Tìm bác sĩ" ĐÃ BỎ — bác sĩ chọn bằng cách bấm một ô trong SƠ ĐỒ
              KHUNG GIỜ ngay dưới đây (`onPick` set thẳng `doctorId`).

              VÀ SƠ ĐỒ ẤY PHẢI CÓ MẶT Ở ĐÂY. Trước đó nó chỉ được dựng trong
              nhánh VÃNG LAI; luồng CSKH tạo khách mới chưa bao giờ có sơ đồ —
              chỉ có hai ô Giờ/Phút và một ô gõ tên bác sĩ. Bỏ ô gõ tên mà không
              đưa sơ đồ sang là cắt mất đường phân bác sĩ duy nhất của luồng
              này: Quang thử trên staging và thấy biểu mẫu không còn chỗ nào
              chọn bác sĩ. Lỗi của tôi, sinh ra ở đúng lượt sửa trước. */}
          {/* BÁC SĨ + NGÀY + KHUNG GIỜ — bảng Bác sĩ × tuần + lưới khung giờ
              (Tuyền duyệt 16/09/2026). Thay sơ đồ "rạp chiếu phim" + hai ô
              Giờ/Phút: sơ đồ cũ tự đếm chỗ trong trình duyệt theo con số chung
              của phòng khám (lệch trigger) và ô giờ mời chọn cả 00–06h. Nay số
              chỗ và khung giờ đều do backend nói. */}
          <div className="sm:col-span-2 space-y-2">
            <label className={LABEL}>
              Chọn giờ khám
            </label>
            <div className="rounded-card border border-hairline p-2">
              <BangBacSiTuan
                weekStart={thuHaiCua(TODAY, tuanLech)}
                lamMoi={doiCa}
                homNay={TODAY}
                bayGioPhut={phutHienTai}
                chon={
                  oLich
                    ? { doctorId: oLich.doctorId, date: oLich.date, time: apptTime }
                    : null
                }
                onChonKhung={(v) => {
                  setOLich({ doctorId: v.doctorId, doctorName: v.doctorName, date: v.date });
                  setApptDate(v.date);
                  setApptTime(v.time);
                  setDoctorId(v.doctorId ?? "");
                }}
                doiTuan={{
                  truoc: () => setTuanLech((n) => n - 1),
                  sau: () => setTuanLech((n) => n + 1),
                  homNay: () => setTuanLech(0),
                }}
              />
            </div>
            {/* Ô "3. Khung giờ khả dụng" đã bỏ (Tuyền 16/09/2026) — nó gọi
                cùng endpoint và in cùng nhãn với popup của bảng. Còn lại một
                dòng NHẮC LẠI thứ vừa chọn: biểu mẫu dài, và khung giờ là thứ
                người nhập phải đọc lại trước khi bấm lưu. */}
            {oLich ? (
              <p className="rounded-card border border-hairline bg-surface-muted px-3 py-2 text-label text-ink">
                <span className="font-semibold">{oLich.doctorName}</span> ·{" "}
                {oLich.date.split("-").reverse().join("/")}
                {apptTime ? ` · ${apptTime}` : ""}
              </p>
            ) : (
              <p className="rounded-card border border-dashed border-line px-3 py-3 text-center text-label text-ink-muted">
                Bấm một ô trong bảng để chọn bác sĩ, ngày và khung giờ.
              </p>
            )}
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
        </div>
      </section>
      )}

      {/* Duplicate-phone warning */}
      {dupes && dupes.length > 0 && (
        <div className="space-y-2 rounded-xl border border-warning/30 bg-warning-bg px-4 py-3 text-sm text-warning">
          <p className="font-medium">
            {cccdTrung
              ? "⚠️ CCCD này đã có hồ sơ. Chọn đúng người để đặt lịch, hoặc ghi lý do rồi vẫn tạo mới:"
              : "⚠️ Đã có bệnh nhân dùng SĐT này. Chọn đúng người để đặt lịch, hoặc vẫn tạo mới:"}
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
                  type="button"
                  onClick={() => proceed(m.clinic_patient_id)}
                  disabled={submitting}
                  className="min-h-10 shrink-0 rounded-lg bg-brand-600 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-700 active:bg-brand-700 disabled:opacity-50 sm:min-h-0 sm:py-1.5"
                >
                  Dùng bệnh nhân này
                </button>
              </li>
            ))}
          </ul>
          {cccdTrung && (
            <textarea
              value={lyDoTrungCccd}
              onChange={(e) => setLyDoTrungCccd(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="Lý do trùng CCCD (bắt buộc), ví dụ: hồ sơ cũ nhập nhầm số"
              className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink"
            />
          )}
          <button
            onClick={() => save(true, cccdTrung ? lyDoTrungCccd : undefined)}
            disabled={submitting || (cccdTrung && !lyDoTrungCccd.trim())}
            className="text-xs font-medium text-danger underline disabled:opacity-50"
          >
            {cccdTrung ? "Vẫn tạo hồ sơ mới (đã ghi lý do)" : "Vẫn tạo bệnh nhân mới"}
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
