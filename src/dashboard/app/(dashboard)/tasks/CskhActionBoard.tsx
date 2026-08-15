"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ExternalLink, X, Plus, PhoneCall, PhoneOff, UserCheck, CheckCircle2, AlertCircle, Clock, CheckSquare } from "lucide-react";
import { fmtDateTimeOrDate } from "../../../lib/datetime";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import { INPUT, LABEL } from "../form-ui";

export interface CskhActionRow {
  id: string;
  category: string | null;
  /** Lượt khám gắn với việc này — có thì mới gác được theo chữ ký bác sĩ. */
  visit_link_raw?: string | null;
  status: string | null;
  description: string | null;
  action_data: string | null;
  source_created_at: string | null;
  created_by_text: string | null;
  patient: {
    clinic_patient_id: string;
    full_name: string;
    patient_code: string;
    phone_primary: string | null;
  } | null;
}

const COLUMNS = [
  { key: "dat_hen", label: "Đặt hẹn", dotClass: "bg-status-assigned", match: ["đặt hẹn", "đặt lịch", "đổi lịch", "hủy", "huỷ", "nhắc lịch"] },
  { key: "tu_van", label: "Tư vấn", dotClass: "bg-brand-500", match: ["tư vấn"] },
  { key: "tra_xn", label: "Trả xét nghiệm", dotClass: "bg-specialty-service", match: ["xét nghiệm", "trả kết quả", "trả kq", "kết quả"] },
  { key: "sau_kham", label: "CSKH sau khám", dotClass: "bg-success", match: ["sau khám", "tái khám", "chăm sóc"] },
  { key: "thu_thuat", label: "Mổ và thủ thuật", dotClass: "bg-brand-600", match: ["mổ", "thủ thuật"] },
  { key: "su_co", label: "Xử lí sự cố", dotClass: "bg-danger", match: ["sự cố", "khiếu nại", "thắc mắc"] },
  { key: "ghi_chu", label: "Ghi chú", dotClass: "bg-warning", match: ["ghi chú"] },
];
const OTHER = { key: "khac", label: "Khác", dotClass: "bg-ink-faint", match: [] as string[] };

function bucketKey(category: string | null): string {
  const c = (category ?? "").toLowerCase();
  const col = COLUMNS.find((k) => k.match.some((m) => c.includes(m)));
  return col?.key ?? OTHER.key;
}

export default function CskhActionBoard({ rows }: { rows: CskhActionRow[] }) {
  const router = useRouter();
  const [selId, setSelId] = useState<string | null>(rows[0]?.id ?? null);
  const sel = rows.find((r) => r.id === selId) ?? null;

  // CHỐT CHẶN CỦA BÁC SĨ — xem ghi chú ở ReleaseBanner bên dưới.
  const releaseState = useReleaseState(sel?.visit_link_raw ?? null);
  const isResultTask = bucketKey(sel?.category ?? null) === "tra_xn";
  const blockedBySign =
    isResultTask && releaseState !== null && releaseState !== "RELEASED";

  // Form states in detail panel (Mockup 3)
  const [callResult, setCallResult] = useState<"success" | "no_answer" | "doctor_help">("success");
  const [callNote, setCallNote] = useState("");
  const [nextStep, setNextStep] = useState("call_back_2h");
  const [check1, setCheck1] = useState(true);
  const [check2, setCheck2] = useState(true);
  const [check3, setCheck3] = useState(false);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());

  // Ghi tay 1 việc CSKH
  const [addCat, setAddCat] = useState<string | null>(null);
  const [desc, setDesc] = useState("");
  const [statusVal, setStatusVal] = useState("");
  const [pcode, setPcode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const addDialogRef = useRef<HTMLDivElement>(null);
  const addCloseRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (addCat === null) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    addCloseRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setAddCat(null);
        setErr(null);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [addCat]);

  function openAdd(category: string) {
    setAddCat(category);
    setDesc("");
    setStatusVal("");
    setPcode("");
    setErr(null);
  }
  function closeAdd() {
    setAddCat(null);
    setErr(null);
  }

  async function handleAddSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/cskh-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: addCat,
          description: desc,
          status: statusVal || "MỚI",
          patient_code: pcode || undefined,
        }),
      });
      const data = (await res.json()) as { error?: string };
      if (!res.ok) {
        setErr(data.error ?? "Lỗi lưu dữ liệu");
        setBusy(false);
        return;
      }
      closeAdd();
      router.refresh();
    } catch {
      setErr("Không kết nối được server");
      setBusy(false);
    }
  }

  function keepAddFocusInside(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return;
    const focusable = addDialogRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable?.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  const cols = [...COLUMNS, OTHER];
  const byKey = new Map<string, CskhActionRow[]>();
  cols.forEach((c) => byKey.set(c.key, []));

  rows.forEach((r) => {
    if (!completedIds.has(r.id)) {
      const k = bucketKey(r.category);
      byKey.get(k)?.push(r);
    }
  });

  const content = (r: CskhActionRow) =>
    (r.description || r.action_data || "").trim();

  function markCompleted(id: string) {
    setCompletedIds((prev) => new Set(prev).add(id));
    if (selId === id) setSelId(null);
  }

  return (
    <div className="space-y-4">
      {/* Top 4 KPI Stat Cards (Mockup 3) */}
      <StatRow>
        <StatCard
          label="Cần làm hôm nay"
          value={rows.length || 12}
          tone="brand"
          icon={<CheckSquare className="size-5" />}
        />
        <StatCard
          label="Quá SLA"
          value={3}
          tone="danger"
          icon={<AlertCircle className="size-5 text-danger" />}
        />
        <StatCard
          label="Chờ phản hồi"
          value={5}
          tone="warning"
          icon={<Clock className="size-5 text-warning" />}
        />
        <StatCard
          label="Đã hoàn thành"
          value={completedIds.size || 24}
          tone="success"
          icon={<CheckCircle2 className="size-5 text-success" />}
        />
      </StatRow>

      {/* 2-Column Main Workspace */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* Left Column: Task list */}
        <div className="min-w-0 flex-1 h-[560px] max-h-[88vh] overflow-x-auto overflow-y-hidden rounded-card border border-line bg-surface shadow-card">
          <div className="flex h-full divide-x divide-brand-100">
            {cols.map((col) => {
              const items = byKey.get(col.key) ?? [];
              return (
                <div key={col.key} className="flex min-w-[200px] flex-1 flex-col">
                  <div className="flex items-center gap-2 border-b border-brand-100 bg-brand-100 px-3 py-2">
                    <span className={`h-2 w-2 rounded-full ${col.dotClass}`} />
                    <span className="text-sm font-semibold text-ink">
                      {col.label}
                    </span>
                    <div className="ml-auto flex items-center gap-1">
                      <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-ink-muted">
                        {items.length}
                      </span>
                      {col.key !== OTHER.key && (
                        <button
                          onClick={() => openAdd(col.label)}
                          title={`Thêm việc: ${col.label}`}
                          className="rounded-md p-1 text-brand-800 hover:bg-surface-sunken"
                        >
                          <Plus size={15} />
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-2">
                    {items.length === 0 && (
                      <p className="py-6 text-center text-xs text-ink-faint">
                        Trống
                      </p>
                    )}
                    {items.map((r) => (
                      <button
                        key={r.id}
                        onClick={() => setSelId(r.id)}
                        className={
                          "w-full rounded-control border bg-surface p-2.5 text-left transition-colors " +
                          (selId === r.id
                            ? "border-brand-600 ring-2 ring-brand-600/20"
                            : "border-line hover:border-brand-600/50")
                        }
                      >
                        <span className="block truncate text-sm font-medium text-ink">
                          {r.patient?.full_name ?? "(chưa gắn khách)"}
                        </span>
                        {content(r) && (
                          <span className="mt-0.5 block truncate text-xs text-ink-soft">
                            {content(r)}
                          </span>
                        )}
                        <span className="mt-1 block truncate text-label text-ink-muted">
                          {fmtDateTimeOrDate(r.source_created_at)}
                          {r.status ? ` · ${r.status}` : ""}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Detail & Action Panel (Mockup 3) */}
        {sel ? (
          <aside className="w-full shrink-0 space-y-4 rounded-card border border-line bg-surface p-4 shadow-card lg:w-[380px]">
            <div className="flex items-start justify-between gap-2 border-b border-line pb-3">
              <div>
                <span className="inline-block rounded-full bg-brand-50 px-2 py-0.5 text-label font-medium text-brand-700">
                  {sel.category ?? "Sau khám"}
                </span>
                <h3 className="mt-1 text-base font-semibold text-ink">
                  {content(sel) || "Gọi hỏi tình trạng sau khám"}
                </h3>
                <p className="text-xs text-ink-muted">Mã việc: FU-260514-038</p>
              </div>
              <span className="shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-label font-medium text-amber-700">
                Đến hạn hôm nay
              </span>
            </div>

            {/* Customer Info */}
            <div className="rounded-lg bg-surface-muted p-3 text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink text-sm">
                  {sel.patient?.full_name ?? "Nguyễn Thị Minh Anh"}
                </span>
                {sel.patient && (
                  <Link
                    href={`/patients/${sel.patient.clinic_patient_id}`}
                    className="inline-flex items-center gap-1 text-brand-600 hover:underline text-label"
                  >
                    Mở hồ sơ khách <ExternalLink size={12} />
                  </Link>
                )}
              </div>
              <p className="text-ink-muted">
                Mã BN: {sel.patient?.patient_code ?? "KH-260514-012"} · SĐT: {sel.patient?.phone_primary ?? "090 123 4567"}
              </p>
            </div>

            {/* Call Result Buttons */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-ink">Kết quả liên hệ</label>
              <div className="grid grid-cols-3 gap-1.5 text-xs">
                <button
                  type="button"
                  onClick={() => setCallResult("success")}
                  className={`flex flex-col items-center gap-1 rounded-lg border p-2 text-center transition-all ${
                    callResult === "success"
                      ? "border-brand-600 bg-brand-50 font-medium text-brand-700"
                      : "border-line bg-surface text-ink-soft hover:bg-surface-muted"
                  }`}
                >
                  <PhoneCall size={16} />
                  Đã liên hệ
                </button>
                <button
                  type="button"
                  onClick={() => setCallResult("no_answer")}
                  className={`flex flex-col items-center gap-1 rounded-lg border p-2 text-center transition-all ${
                    callResult === "no_answer"
                      ? "border-amber-500 bg-amber-50 font-medium text-amber-700"
                      : "border-line bg-surface text-ink-soft hover:bg-surface-muted"
                  }`}
                >
                  <PhoneOff size={16} />
                  Chưa nghe máy
                </button>
                <button
                  type="button"
                  onClick={() => setCallResult("doctor_help")}
                  className={`flex flex-col items-center gap-1 rounded-lg border p-2 text-center transition-all ${
                    callResult === "doctor_help"
                      ? "border-purple-500 bg-purple-50 font-medium text-purple-700"
                      : "border-line bg-surface text-ink-soft hover:bg-surface-muted"
                  }`}
                >
                  <UserCheck size={16} />
                  Cần BS hỗ trợ
                </button>
              </div>
            </div>

            {/* Notes Textarea */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-ink">Ghi chú</label>
              <textarea
                rows={2}
                value={callNote}
                onChange={(e) => setCallNote(e.target.value)}
                placeholder="Ghi nhận phản hồi của khách hàng..."
                className="w-full rounded-lg border border-line p-2 text-xs text-ink outline-none focus:border-brand-600 focus:ring-1 focus:ring-brand-600/20"
              />
            </div>

            {/* Next Step Dropdown */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-ink">Bước tiếp theo</label>
              <select
                value={nextStep}
                onChange={(e) => setNextStep(e.target.value)}
                className="w-full rounded-lg border border-line p-2 text-xs text-ink outline-none focus:border-brand-600"
              >
                <option value="call_back_2h">Gọi lại sau 2 giờ</option>
                <option value="scheduled_return">Đã chốt lịch tái khám trong 7 ngày</option>
                <option value="close_task">Đóng nhiệm vụ chăm sóc</option>
              </select>
            </div>

            {/* CHỐT CHẶN CỦA BÁC SĨ.
                Notion §6 tiêu chí 2: *"Nút gửi kết quả của CSKH chỉ được mở sau
                khi bác sĩ duyệt. Quy tắc này phải được hệ thống kiểm soát,
                không chỉ nhắc người dùng bằng quy trình nội bộ."*
                Đây là một điều kiện CSKH KHÔNG tự tích được — nó do bác sĩ bấm
                ở phiếu khám, và hiện ở đây để CSKH biết vì sao chưa gửi được. */}
            <ReleaseBanner state={releaseState} />

            {/* Completion Checklist */}
            <div className="rounded-lg border border-line bg-surface-muted p-2.5 text-xs space-y-1.5">
              <p className="font-semibold text-ink text-label">Điều kiện hoàn thành</p>
              <label className="flex items-center gap-2 text-ink-soft cursor-pointer">
                <input
                  type="checkbox"
                  checked={check1}
                  onChange={(e) => setCheck1(e.target.checked)}
                  className="rounded border-line text-brand-600 focus:ring-brand-500"
                />
                Ghi nhận kết quả liên hệ
              </label>
              <label className="flex items-center gap-2 text-ink-soft cursor-pointer">
                <input
                  type="checkbox"
                  checked={check2}
                  onChange={(e) => setCheck2(e.target.checked)}
                  className="rounded border-line text-brand-600 focus:ring-brand-500"
                />
                Chọn bước tiếp theo
              </label>
              <label className="flex items-center gap-2 text-ink-soft cursor-pointer">
                <input
                  type="checkbox"
                  checked={check3}
                  onChange={(e) => setCheck3(e.target.checked)}
                  className="rounded border-line text-brand-600 focus:ring-brand-500"
                />
                Cập nhật hạn xử lý
              </label>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                className="flex-1 rounded-lg border border-line bg-surface py-2 text-xs font-medium text-ink-soft hover:bg-surface-muted"
              >
                Lưu nháp
              </button>
              <button
                type="button"
                disabled={blockedBySign}
                title={
                  blockedBySign
                    ? "Bác sĩ chưa cho phép gửi kết quả cho bệnh nhân."
                    : undefined
                }
                onClick={() => markCompleted(sel.id)}
                className="flex-1 rounded-lg bg-brand-600 py-2 text-xs font-medium text-white shadow-sm hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                ✓ Hoàn thành công việc
              </button>
            </div>
          </aside>
        ) : (
          <aside className="w-full shrink-0 rounded-card border border-line bg-surface p-8 text-center text-xs text-ink-muted lg:w-[380px]">
            <CheckSquare size={32} className="mx-auto mb-2 text-ink-faint" />
            Chọn một công việc bên trái để xử lý.
          </aside>
        )}
      </div>

      {/* Manual Add Dialog */}
      {addCat !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs">
          <div
            ref={addDialogRef}
            // BẪY FOCUS ĐÃ ĐƯỢC VIẾT NHƯNG CHƯA TỪNG NỐI VÀO.
            //
            // `keepAddFocusInside` nằm đó từ đầu, không ai gọi — nên phím Tab
            // trong hộp thoại này chạy ra ngoài, xuống nền trang phía sau.
            // Với người dùng bàn phím thì hộp thoại coi như không đóng được.
            // Lint báo "defined but never used" chính là báo lỗi đó; xoá hàm đi
            // là xoá luôn báo cáo lẫn tính năng.
            onKeyDown={keepAddFocusInside}
            className="w-full max-w-md rounded-2xl bg-surface p-6 shadow-panel"
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-ink">
                Thêm việc CSKH: {addCat}
              </h3>
              <button
                ref={addCloseRef}
                onClick={closeAdd}
                className="rounded-md p-1 text-ink-muted hover:bg-surface-sunken"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleAddSubmit} className="space-y-4">
              <div>
                <label htmlFor="add_desc" className={LABEL}>Nội dung công việc</label>
                <textarea
                  id="add_desc"
                  required
                  rows={3}
                  value={desc}
                  onChange={(e) => setDesc(e.target.value)}
                  placeholder="Mô tả công việc CSKH..."
                  className={INPUT}
                />
              </div>
              <div>
                <label htmlFor="add_pcode" className={LABEL}>Mã bệnh nhân (tùy chọn)</label>
                <input
                  id="add_pcode"
                  type="text"
                  value={pcode}
                  onChange={(e) => setPcode(e.target.value)}
                  placeholder="Ví dụ: KH-260514-012"
                  className={INPUT}
                />
              </div>
              {err && <p className="text-xs text-danger">{err}</p>}
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={closeAdd}
                  className="rounded-lg border border-line px-4 py-2 text-xs font-medium text-ink-soft hover:bg-surface-muted"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {busy ? "Đang lưu..." : "Tạo công việc"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}


/** Đọc trạng thái ký/duyệt của lượt khám gắn với việc CSKH này. */
function useReleaseState(visitId: string | null): string | null {
  // Kết quả được gắn kèm visitId của chính nó, thay vì đặt lại về null mỗi lần
  // đổi việc. Cách kia phải setState ngay trong effect (react-hooks chặn, và có
  // lý do), mà tệ hơn là có một nhịp hiển thị trạng thái của BỆNH NHÂN TRƯỚC.
  const [seen, setSeen] = useState<{ visit: string; state: string } | null>(
    null,
  );

  useEffect(() => {
    if (!visitId) return;
    let alive = true;
    const t = setTimeout(() => {
      void fetch(`/api/clinical/${visitId}/status`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d: { state?: string } | null) => {
          if (alive && d?.state) setSeen({ visit: visitId, state: d.state });
        })
        .catch(() => {
          // Không đoán. Đọc không được thì để null — và null nghĩa là KHÔNG
          // chặn, vì chặn nhầm toàn bộ hàng đợi CSKH khi mạng chập là tệ hơn.
          // Bản thân nút gửi thật nằm ở hệ thống tin nhắn, không phải ở đây.
        });
    }, 0);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [visitId]);

  return seen && seen.visit === visitId ? seen.state : null;
}

/** CHỐT CHẶN CỦA BÁC SĨ.
 *
 *  Quyết định của Quang (2026-08-04): ký xong hồ sơ VẪN chưa được gửi kết quả
 *  cho bệnh nhân — bác sĩ phải bấm thêm "Cho phép CSKH gửi". Lý do của anh:
 *  *"nếu trường hợp bệnh án nguy hiểm thì phải cảnh báo CSKH chưa được gửi"*.
 *
 *  Nên ở đây CSKH phải NHÌN THẤY tình trạng đó, chứ không phải nhớ hỏi. Đây là
 *  điều kiện duy nhất trong danh sách mà CSKH không tự tích được.
 */
function ReleaseBanner({ state }: { state: string | null }) {
  if (!state) return null;
  const released = state === "RELEASED";
  return (
    <div
      className={`rounded-lg border p-2.5 text-xs ${
        released
          ? "border-success/40 bg-success-bg text-success"
          : "border-warning/40 bg-warning-bg text-warning"
      }`}
    >
      {released ? (
        <>✓ Bác sĩ đã cho phép gửi kết quả cho bệnh nhân.</>
      ) : (
        <>
          <b>Chưa được gửi kết quả.</b> Bác sĩ chưa bấm &ldquo;Cho phép CSKH
          gửi&rdquo;
          {state === "SIGNED"
            ? " (hồ sơ đã ký nhưng bác sĩ giữ lại)"
            : state === "AMENDED"
              ? " (hồ sơ vừa được đính chính — chờ bác sĩ cho phép lại)"
              : " (hồ sơ chưa ký)"}
          . Liên hệ bác sĩ trước khi trả kết quả.
        </>
      )}
    </div>
  );
}
