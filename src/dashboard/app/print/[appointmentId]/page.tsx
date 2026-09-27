// Trang IN PHIẾU "Tóm tắt khám bệnh" của 1 lịch hẹn (đã khám xong) — lễ tân mở
// từ trang chủ. Server Component: đọc THẬT dữ liệu BN + hồ sơ khám (qua RLS) →
// map sang form → MedicalSummaryPrint (client) tự lo nút In/Xuất PDF.
// Đặt NGOÀI nhóm (dashboard) nên KHÔNG có sidebar → in sạch khổ A4.

import { notFound, redirect } from "next/navigation";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { requireClinicalRole } from "../../../lib/clinic-session";
import { VN_TZ, isVnMidnight } from "../../../lib/datetime";
import MedicalSummaryPrint, { type FormData } from "./MedicalSummaryPrint";

export const dynamic = "force-dynamic";

// ---- helpers ----
const objOf = (x: unknown): Record<string, unknown> =>
  x && typeof x === "object" && !Array.isArray(x)
    ? (x as Record<string, unknown>)
    : {};
const str = (x: unknown): string => (x == null ? "" : String(x));
const one = <T,>(x: T | T[] | null | undefined): T | null =>
  !x ? null : Array.isArray(x) ? (x[0] ?? null) : x;
const famText = (x: unknown) =>
  !x ? "" : typeof x === "string" ? x : JSON.stringify(x);
// Tên XN đôi khi kèm link Notion dài → cắt cho gọn.
const cleanTestName = (s: string) =>
  (s ?? "").replace(/\s*\(https?:\/\/[^)]*\)?/gi, "").trim() || (s ?? "");

/** yyyy-mm-dd → dd/mm/yyyy (giữ nguyên nếu không khớp). */
function ymdToDmy(s: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : s ?? "";
}
/** timestamptz → "HH:MM dd/mm/yyyy" theo giờ VN. */
function fmtVnDateTime(v: string | null | undefined): string {
  if (!v) return "";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TZ,
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour12: false,
  }).format(d);
}
/** timestamptz → "dd/mm/yyyy" (CHỈ ngày) theo giờ VN — dùng cho lịch chỉ có ngày. */
function fmtVnDate(v: string | null | undefined): string {
  if (!v) return "";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TZ,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(d);
}

interface PatientRow {
  clinic_patient_id: string;
  patient_code: string | null;
  full_name: string | null;
  date_of_birth: string | null;
  gender: string | null;
  ethnicity: string | null;
  nationality: string | null;
  occupation: string | null;
  patient_objection: string | null;
  address: string | null;
  guardian_name: string | null;
  phone_primary: string | null;
}
interface ApptRow {
  id: string;
  slot_start: string;
  status: string;
  patient: PatientRow | PatientRow[] | null;
  doctor: { full_name: string } | { full_name: string }[] | null;
  service: { name: string } | { name: string }[] | null;
  location: { name: string } | { name: string }[] | null;
}
interface ClinRow {
  chief_complaint_at_visit: string | null;
  soap_subjective: unknown;
  soap_objective: unknown;
  soap_assessment: unknown;
  soap_plan: unknown;
}
interface ProfileRow {
  allergies: string[] | null;
  chronic_diseases: string[] | null;
  current_medications: string[] | null;
  surgical_history: string[] | null;
  family_history: unknown;
  notes: string | null;
}
interface LabRow {
  test_name: string;
  result_value: string | null;
  result_numeric: number | null;
  result_unit: string | null;
  flag: string | null;
}

export default async function PrintMedicalSummaryPage({
  params,
}: {
  params: Promise<{ appointmentId: string }>;
}) {
  await requireClinicalRole(); // phiếu chứa hồ sơ khám: ai có khối khám / kết quả
  const { appointmentId } = await params;
  // 24/09/2026: đọc qua backend `GET /api/v1/clinical-records/in-theo-lich/{id}`
  // (vai lâm sàng, lọc phòng khám) thay vì đọc thẳng 4 bảng bằng Supabase.
  const doc = await fetchFromBackend<{
    appointment: PatientRow & {
      id: string;
      slot_start: string;
      status: string;
      doctor_name: string | null;
      service_name: string | null;
      location_name: string | null;
    };
    visit: (ClinRow & { visit_id: string; status: string; created_at: string }) | null;
    profile: ProfileRow | null;
    labs: LabRow[];
  }>(`/api/v1/clinical-records/in-theo-lich/${encodeURIComponent(appointmentId)}`);
  if (!doc) notFound();
  // MỘT BẢN IN CHO MỌI KHÂU (Tuyền 27/09/2026): lượt đã mở phiếu khám mới thì
  // nút In ở Trang chủ ra ĐÚNG bản in hai trang (thông tin + ảnh) như Bàn khám
  // và Xem lượt. Chỉ lượt cũ (trước phiếu v5) mới còn in "Tóm tắt khám bệnh".
  if (doc.visit?.visit_id) {
    const v5 = await fetchFromBackend<{ form_id: string | null }>(
      `/api/v1/phieu-kham/luot/${encodeURIComponent(doc.visit.visit_id)}/phieu`,
    );
    if (v5?.form_id) redirect(`/print/phieu-kham/${doc.visit.visit_id}`);
  }
  const a = doc.appointment;
  const p: PatientRow = a;
  const appt: ApptRow = {
    id: a.id,
    slot_start: a.slot_start,
    status: a.status,
    patient: p,
    doctor: a.doctor_name ? { full_name: a.doctor_name } : null,
    service: a.service_name ? { name: a.service_name } : null,
    location: a.location_name ? { name: a.location_name } : null,
  };
  const cr = doc.visit;
  const profile = doc.profile;
  const labs = doc.labs;

  const subj = objOf(cr?.soap_subjective);
  const obj = objOf(cr?.soap_objective);
  const vitals = objOf(obj.vitals);
  const khamThai = objOf(obj.kham_thai);
  const assess = objOf(cr?.soap_assessment);
  const plan = objOf(cr?.soap_plan);

  const tienSuParts: string[] = [];
  if (profile?.chronic_diseases?.length)
    tienSuParts.push("Bệnh mạn tính: " + profile.chronic_diseases.join(", "));
  if (profile?.surgical_history?.length)
    tienSuParts.push("Tiền sử phẫu thuật: " + profile.surgical_history.join(", "));
  if (profile?.current_medications?.length)
    tienSuParts.push("Thuốc đang dùng: " + profile.current_medications.join(", "));
  const fam = famText(profile?.family_history);
  if (fam) tienSuParts.push("Gia đình: " + fam);
  if (profile?.notes) tienSuParts.push(profile.notes);

  const labsText = labs
    .map((l) => {
      const val =
        l.result_value ??
        (l.result_numeric != null ? String(l.result_numeric) : "");
      const flag = l.flag && l.flag !== "NORMAL" ? ` [${l.flag}]` : "";
      const unit = l.result_unit ? ` ${l.result_unit}` : "";
      return `${cleanTestName(l.test_name)}: ${val || "—"}${unit}${flag}`;
    })
    .join("\n");

  // Mục X — Theo dõi & Tái khám (soap_plan.tai_kham, hợp đồng với màn CSKH):
  //   { ngay: "YYYY-MM-DD", xn: ["HM",…], ghi_chu?: "…" }
  // → nối thành 1 dòng dưới "Hướng xử lý" (FormData của phiếu in cố định, không
  // thêm trường mới được). Chỉ hiện khi hồ sơ có tai_kham.
  const TK_XN_LABEL: Record<string, string> = {
    HM: "Hormone",
    SH: "Sinh hóa",
    SA: "Siêu âm",
    DXA: "Đo loãng xương",
    PS: "Pap smear",
  };
  const taiKham = objOf(plan.tai_kham);
  const tkParts: string[] = [];
  if (str(taiKham.ngay)) {
    tkParts.push(`Hẹn tái khám: ${ymdToDmy(str(taiKham.ngay))}`);
  }
  const tkXn = Array.isArray(taiKham.xn)
    ? taiKham.xn.map((c) => TK_XN_LABEL[String(c)] ?? String(c))
    : [];
  if (tkXn.length) tkParts.push(`Kiểm tra lại: ${tkXn.join(", ")}`);
  if (str(taiKham.ghi_chu)) tkParts.push(str(taiKham.ghi_chu));
  const taiKhamLine = tkParts.join(" — ");

  const doctorName = one(appt.doctor)?.full_name ?? "";
  const code = p.patient_code ?? "";

  const initial: FormData = {
    maHoSo: code,
    maNB: code,
    maHS: code,
    phongKham: one(appt.location)?.name ?? one(appt.service)?.name ?? "",
    hoTen: p.full_name ?? "",
    ngaySinh: ymdToDmy(p.date_of_birth),
    gioiTinh: p.gender ?? "",
    danToc: p.ethnicity ?? "",
    quocTich: p.nationality ?? "",
    ngheNghiep: p.occupation ?? "",
    doiTuong: p.patient_objection ?? "",
    diaChi: p.address ?? "",
    nguoiBaoLanh: p.guardian_name ?? "",
    soDienThoai: p.phone_primary ?? "",
    denKhamLuc: isVnMidnight(appt.slot_start)
      ? fmtVnDate(appt.slot_start)
      : fmtVnDateTime(appt.slot_start),
    lyDoVaoKham: cr?.chief_complaint_at_visit ?? "",
    tienSuDiUng: profile?.allergies?.length ? profile.allergies.join(", ") : "",
    para: "",
    tienSu: tienSuParts.join("\n"),
    benhSu: str(subj.benh_su),
    tuoiThai: str(khamThai.tuoi_thai),
    duKienSinh: ymdToDmy(str(khamThai.du_kien_sinh)),
    chieuCaoTuCung: str(khamThai.chieu_cao_tc),
    conCoTuCung: "",
    nhipTimThai: str(khamThai.nhip_tim_thai),
    mach: str(vitals.mach),
    nhietDo: str(vitals.nhiet_do),
    huyetAp: str(vitals.huyet_ap),
    nhipTho: str(vitals.nhip_tho),
    spo2: str(vitals.spo2),
    canNang: str(vitals.can_nang),
    chieuCao: str(vitals.chieu_cao),
    bmi: str(vitals.bmi),
    congThucMau: labsText,
    sinhHoaMau: "",
    cdha: "",
    chanDoan: str(assess.chan_doan),
    huongXuLy: [str(plan.loi_dan), taiKhamLine].filter(Boolean).join("\n"),
    thanhPho: "",
    nguoiKy: doctorName,
    ngayKyDuyet: fmtVnDateTime(cr?.created_at ?? appt.slot_start),
  };

  return <MedicalSummaryPrint initial={initial} />;
}
