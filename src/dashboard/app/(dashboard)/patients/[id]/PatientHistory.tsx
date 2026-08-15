// Doctor-facing clinical history for one patient: visits (+ SOAP clinical
// record), lab results, and pregnancy. Read-only, RLS via the shared session.
// Data is real (visit ~5.6k, lab_result ~4.7k); pregnancy is usually empty.

import StatusBadge from "../../StatusBadge";
import LabReviewActions from "./LabReviewActions";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { fmtDate } from "../../../../lib/datetime";

interface ClinicalRecord {
  chief_complaint_at_visit: string | null;
  soap_subjective: unknown;
  soap_objective: unknown;
  soap_assessment: unknown;
  soap_plan: unknown;
}

interface VisitRow {
  visit_id: string;
  status: string;
  created_at: string;
  doctor: { full_name: string } | null;
  service: { name: string } | null;
  clinical_record: ClinicalRecord | ClinicalRecord[] | null;
}

interface LabRow {
  lab_result_id: string;
  test_name: string;
  result_value: string | null;
  result_numeric: number | null;
  result_unit: string | null;
  flag: string | null;
  triage_group: string;
  is_finalized: boolean | null;
  result_received_at: string;
}

interface PregnancyRow {
  id: string;
  lmp_date: string | null;
  edd_date: string | null;
  gestational_age_at_registration: number | null;
  outcome: string;
  is_high_risk: boolean;
  high_risk_reason: string | null;
}

const VISIT_COLUMNS = `
  visit_id, status, created_at,
  doctor:staff!attending_doctor_id ( full_name ),
  service:service_type!service_type_id ( name ),
  clinical_record (
    chief_complaint_at_visit,
    soap_subjective, soap_objective, soap_assessment, soap_plan
  )
`;

// SOAP là JSONB — chuỗi HOẶC object LỒNG (vd objective = {vitals:{...},
// kham_thai:{...}}). Flatten ĐỆ QUY thành "Nhãn: giá trị · …" (KHÔNG để lòi JSON
// thô như trước — đó chính là lỗi hiển thị "thông số" ở Lịch sử khám).
const KV_LABEL: Record<string, string> = {
  mach: "Mạch", nhiet_do: "Nhiệt độ", huyet_ap: "Huyết áp", nhip_tho: "Nhịp thở",
  spo2: "SpO2", can_nang: "Cân nặng", chieu_cao: "Chiều cao", bmi: "BMI",
  tuoi_thai: "Tuổi thai", du_kien_sinh: "Dự kiến sinh", chieu_cao_tc: "Cao TC/VB",
  nhip_tim_thai: "Tim thai", benh_su: "Bệnh sử", chan_doan: "Chuẩn đoán",
  loi_dan: "Lời dặn",
};
function kvPairs(v: unknown): string[] {
  if (v == null) return [];
  if (typeof v !== "object") {
    const s = String(v).trim();
    return s ? [s] : [];
  }
  if (Array.isArray(v)) return v.flatMap(kvPairs);
  const out: string[] = [];
  for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
    if (val == null) continue;
    if (typeof val === "object") {
      out.push(...kvPairs(val)); // nhóm lồng (vitals/kham_thai) → trải nội dung
    } else {
      const s = String(val).trim();
      if (s) out.push(`${KV_LABEL[k] ?? k}: ${s}`);
    }
  }
  return out;
}
function asText(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v.trim();
  return kvPairs(v).join(" · ");
}

function firstRecord(
  cr: ClinicalRecord | ClinicalRecord[] | null,
): ClinicalRecord | null {
  if (!cr) return null;
  return Array.isArray(cr) ? (cr[0] ?? null) : cr;
}

// Tên xét nghiệm nguồn đôi khi kèm link Notion dài "(https://…)" → cắt bỏ cho gọn.
function cleanTestName(s: string): string {
  const out = (s ?? "").replace(/\s*\(https?:\/\/[^)]*\)?/gi, "").trim();
  return out || (s ?? "");
}

const SECTION = "text-base font-semibold text-ink";
const TH = "px-4 py-2.5 font-medium";
const TD = "px-4 py-2.5";
const CARD =
  "rounded-card border border-line bg-surface shadow-card";

// Note lâm sàng ("Lý do khám") nguồn viết liền — tách thành mục dễ đọc:
// chèn xuống dòng trước ➤<nhãn>:, mục đánh số (1. Hành chính…), và mốc ngày
// lịch sử khám; in đậm nhãn. Giữ xuống dòng sẵn có (whitespace-pre-line).
function ClinicalNote({ text }: { text: string }) {
  const normalized = text
    .replace(/\s*➤/g, "\n➤")
    .replace(/\s+(\d+\.\s*(?:Hành chính|Ghi chú|Lịch sử|Tư vấn|Khám))/g, "\n$1")
    .replace(/\s+(\d{1,2}\/\d{1,2}\/\d{4}\b)/g, "\n$1")
    .replace(/\s*(📌{1,})/g, "\n$1");
  const lines = normalized
    .split(/\n+/)
    .map((l) => l.trim())
    .filter(Boolean);

  return (
    <div className="space-y-1 text-sm leading-relaxed text-ink">
      {lines.map((line, i) => {
        const arrow = line.match(/^➤\s*([^:]+):\s*([\s\S]*)$/);
        if (arrow) {
          return (
            <p key={i} className="whitespace-pre-line">
              <span className="font-semibold text-brand-700">
                {arrow[1].trim()}:{" "}
              </span>
              {arrow[2].trim()}
            </p>
          );
        }
        const num = line.match(/^(\d+)\.\s*([\s\S]*)$/);
        if (num) {
          return (
            <p key={i} className="whitespace-pre-line pt-1">
              <span className="font-semibold text-ink-soft">{num[1]}. </span>
              {num[2].trim()}
            </p>
          );
        }
        const date = line.match(/^(\d{1,2}\/\d{1,2}\/\d{4})\b([\s\S]*)$/);
        if (date) {
          return (
            <p key={i} className="whitespace-pre-line pt-1">
              <span className="font-medium text-ink">{date[1]}</span>
              <span className="text-ink-soft">{date[2]}</span>
            </p>
          );
        }
        return (
          <p key={i} className="whitespace-pre-line">
            {line}
          </p>
        );
      })}
    </div>
  );
}

export default async function PatientHistory({
  id,
  canReviewLabs = false,
}: {
  id: string;
  /** Show the doctor's triage/approve controls. The backend enforces the
   *  real gate (DOCTOR_ROLES); this only decides whether to draw them. */
  canReviewLabs?: boolean;
}) {
  const supabase = await getSupabaseServer();
  const [visitRes, labRes, pregRes] = await Promise.all([
    supabase
      .from("visit")
      .select(VISIT_COLUMNS)
      .eq("clinic_patient_id", id)
      .order("created_at", { ascending: false })
      .limit(50),
    supabase
      .from("lab_result")
      .select(
        "lab_result_id, test_name, result_value, result_numeric, result_unit, flag, triage_group, is_finalized, result_received_at",
      )
      .eq("clinic_patient_id", id)
      .order("result_received_at", { ascending: false })
      .limit(50),
    supabase
      .from("pregnancy")
      .select(
        "id, lmp_date, edd_date, gestational_age_at_registration, outcome, is_high_risk, high_risk_reason",
      )
      .eq("clinic_patient_id", id)
      .order("created_at", { ascending: false }),
  ]);

  const visits = (visitRes.data as VisitRow[] | null) ?? [];
  const labs = (labRes.data as LabRow[] | null) ?? [];
  const pregnancies = (pregRes.data as PregnancyRow[] | null) ?? [];

  return (
    <div className="space-y-6">
      {/* ---- Pregnancy (women's clinic — show if any) ---- */}
      {pregnancies.length > 0 && (
        <section className="space-y-3">
          <h3 className={SECTION}>Thai kỳ</h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {pregnancies.map((p) => (
              <div key={p.id} className={`${CARD} p-4`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ink">
                    {p.outcome}
                  </span>
                  {p.is_high_risk && (
                    <span className="rounded-full bg-danger-bg px-2 py-0.5 text-xs font-medium text-danger">
                      Nguy cơ cao
                    </span>
                  )}
                </div>
                <dl className="mt-2 grid grid-cols-3 gap-2 text-xs text-ink-soft">
                  <div>
                    <dt className="text-ink-muted">LMP</dt>
                    <dd>{fmtDate(p.lmp_date)}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-muted">Dự sinh</dt>
                    <dd>{fmtDate(p.edd_date)}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-muted">Tuổi thai (đăng ký)</dt>
                    <dd>{p.gestational_age_at_registration ?? "—"}</dd>
                  </div>
                </dl>
                {p.high_risk_reason && (
                  <p className="mt-2 text-xs text-danger">
                    {p.high_risk_reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ---- Visit / clinical history ---- */}
      <section className="space-y-3">
        <h3 className={SECTION}>Lịch sử khám ({visits.length})</h3>
        {visitRes.error && (
          <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
            {visitRes.error.message}
          </div>
        )}
        {visits.length === 0 ? (
          <div className={`${CARD} px-4 py-6 text-center text-sm text-ink-muted`}>
            Chưa có lần khám nào.
          </div>
        ) : (
          <div className="space-y-3">
            {visits.map((v) => {
              const cr = firstRecord(v.clinical_record);
              const soap = [
                { label: "Lý do khám", value: cr?.chief_complaint_at_visit ?? "" },
                { label: "Chủ quan (S)", value: asText(cr?.soap_subjective) },
                { label: "Khách quan (O)", value: asText(cr?.soap_objective) },
                { label: "Chuẩn đoán (A)", value: asText(cr?.soap_assessment) },
                { label: "Kế hoạch (P)", value: asText(cr?.soap_plan) },
              ].filter((s) => s.value);
              return (
                <div key={v.visit_id} className={`${CARD} p-4`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-medium text-ink">
                      {fmtDate(v.created_at)}
                      <span className="ml-2 text-xs font-normal text-ink-muted">
                        {v.service?.name ?? "—"} ·{" "}
                        {v.doctor?.full_name ?? "—"}
                      </span>
                    </span>
                    <StatusBadge status={v.status} />
                  </div>
                  {soap.length > 0 ? (
                    <dl className="mt-3 space-y-2 sm:space-y-1.5">
                      {soap.map((s) => (
                        <div
                          key={s.label}
                          className="grid grid-cols-1 gap-0.5 sm:grid-cols-[120px_1fr] sm:gap-2"
                        >
                          <dt className="text-xs text-ink-muted">{s.label}</dt>
                          <dd className="text-sm text-ink">
                            {s.label === "Lý do khám" ? (
                              <ClinicalNote text={s.value} />
                            ) : (
                              <span className="whitespace-pre-line">
                                {s.value}
                              </span>
                            )}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <p className="mt-2 text-xs italic text-ink-muted">
                      Không có ghi chú khám.
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* ---- Lab results ---- */}
      <section className="space-y-3">
        <h3 className={SECTION}>Xét nghiệm ({labs.length})</h3>
        {labs.length === 0 ? (
          <div className={`${CARD} px-4 py-6 text-center text-sm text-ink-muted`}>
            Chưa có kết quả xét nghiệm.
          </div>
        ) : (
          <>
            {/* Mobile: card list (<md). */}
            <div className="space-y-2 md:hidden">
              {labs.map((l) => (
                <div key={l.lab_result_id} className={`${CARD} p-3`}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-ink">
                      {cleanTestName(l.test_name)}
                    </span>
                    <span className="shrink-0 font-mono text-xs text-ink-muted">
                      {fmtDate(l.result_received_at)}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-ink-soft">
                    {l.result_value ??
                      (l.result_numeric != null
                        ? String(l.result_numeric)
                        : "—")}
                    {l.result_unit ? ` ${l.result_unit}` : ""}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    Cờ: {l.flag ?? "—"} · Phân nhóm: {l.triage_group}
                  </p>
                  {canReviewLabs && (
                    <LabReviewActions
                      labResultId={l.lab_result_id}
                      clinicPatientId={id}
                      triageGroup={l.triage_group}
                      isFinalized={Boolean(l.is_finalized)}
                      hasResult={
                        Boolean(l.result_value) || l.result_numeric != null
                      }
                    />
                  )}
                </div>
              ))}
            </div>

            {/* Desktop: table (≥md). */}
            <div className={`hidden overflow-auto max-h-[88vh] min-h-[180px] md:block ${CARD}`}>
              <table className="min-w-full divide-y divide-brand-100 text-sm">
              <thead className="sticky top-0 z-10 bg-brand-100 text-left text-label font-semibold uppercase tracking-wide text-brand-800">
                <tr>
                  <th className={TH}>Ngày</th>
                  <th className={TH}>Xét nghiệm</th>
                  <th className={TH}>Kết quả</th>
                  <th className={TH}>Cờ</th>
                  <th className={TH}>Phân nhóm</th>
                  {canReviewLabs && <th className={TH}>Duyệt</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-100">
                {labs.map((l) => (
                  <tr key={l.lab_result_id} className="hover:bg-brand-50">
                    <td className={`${TD} font-mono text-xs text-ink-soft`}>
                      {fmtDate(l.result_received_at)}
                    </td>
                    <td className={`${TD} text-ink`}>{cleanTestName(l.test_name)}</td>
                    <td className={`${TD} text-ink-soft`}>
                      {l.result_value ??
                        (l.result_numeric != null ? String(l.result_numeric) : "—")}
                      {l.result_unit ? ` ${l.result_unit}` : ""}
                    </td>
                    <td className={`${TD} text-ink-soft`}>{l.flag ?? "—"}</td>
                    <td className={`${TD} text-ink-soft`}>{l.triage_group}</td>
                    {canReviewLabs && (
                      <td className={TD}>
                        <LabReviewActions
                          labResultId={l.lab_result_id}
                          clinicPatientId={id}
                          triageGroup={l.triage_group}
                          isFinalized={Boolean(l.is_finalized)}
                          hasResult={
                            Boolean(l.result_value) || l.result_numeric != null
                          }
                        />
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
