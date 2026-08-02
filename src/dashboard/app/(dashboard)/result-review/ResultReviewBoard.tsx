"use client";

// ResultReviewBoard — Duyệt kết quả (image_9 + image_3).
// Hàng đợi kết quả XN chờ bác sĩ duyệt. Ký duyệt / trả lại chỉnh sửa.
//
// Hai nút này trước B.4 không gắn với gì cả. Giờ cả hai đi qua FastAPI:
// ký duyệt là chữ ký (is_finalized + reviewed_by_staff_id, một chiều), trả lại
// KHÔNG đụng vào kết quả — nó mở một việc cho phòng xét nghiệm, còn cổng an
// toàn vẫn đóng nguyên. Vì vậy trả lại không bao giờ là đường tắt để kết quả
// chạy tới bệnh nhân.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

interface ReviewPatient {
  full_name: string | null;
  phone_primary: string | null;
}

interface ReviewRow {
  lab_result_id: string;
  clinic_patient_id: string;
  test_code: string;
  test_name: string;
  result_value: string | null;
  result_numeric: number | null;
  result_unit: string | null;
  reference_range_low: number | null;
  reference_range_high: number | null;
  flag: string | null;
  triage_group: string | null;
  requires_doctor_review: boolean;
  is_finalized: boolean;
  result_received_at: string;
  patient: ReviewPatient | null;
}

interface Props {
  results: ReviewRow[];
  /** Kết quả đang có việc "sửa lại" mở — đã trả lại rồi, đừng trả lại lần nữa. */
  sentBackIds: string[];
  canReview: boolean;
}

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

const FLAG_LABEL: Record<string, string> = {
  NORMAL: "Bình thường",
  HIGH: "Cao",
  LOW: "Thấp",
  CRITICAL_HIGH: "Cao nguy kịch",
  CRITICAL_LOW: "Thấp nguy kịch",
  ABNORMAL: "Bất thường",
};

const MIN_REASON = 5;

async function errorOf(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string; detail?: string };
    return body.error ?? body.detail ?? "Không xử lý được kết quả này.";
  } catch {
    return "Không xử lý được kết quả này.";
  }
}

export default function ResultReviewBoard({
  results,
  sentBackIds,
  canReview,
}: Props) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState<"review" | "send-back" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);

  const sentBack = useMemo(() => new Set(sentBackIds), [sentBackIds]);

  const selected = useMemo(
    () => results.find((r) => r.lab_result_id === selectedId) ?? null,
    [results, selectedId],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return results;
    return results.filter(
      (r) =>
        r.patient?.full_name?.toLowerCase().includes(q) ||
        r.test_name.toLowerCase().includes(q) ||
        r.test_code.toLowerCase().includes(q),
    );
  }, [results, search]);

  function pick(id: string) {
    setSelectedId(id);
    setMessage(null);
    setError(null);
    setAsking(false);
    setReason("");
  }

  async function send(path: string, body: Record<string, unknown>) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      setError(await errorOf(response));
      return false;
    }
    return true;
  }

  async function review() {
    if (!selected || busy) return;
    const confirmed = window.confirm(
      "Xác nhận bạn đã đọc kết quả gốc và muốn ký duyệt kết quả này?",
    );
    if (!confirmed) return;

    setBusy("review");
    setError(null);
    const ok = await send(`/api/lab-result/${selected.lab_result_id}/review`, {
      clinic_patient_id: selected.clinic_patient_id,
    });
    setBusy(null);
    if (!ok) return;
    setMessage("Đã ký duyệt. Quy tắc báo bệnh nhân vẫn được kiểm tra riêng.");
    router.refresh();
  }

  async function sendBack() {
    if (!selected || busy) return;
    if (reason.trim().length < MIN_REASON) {
      setError("Ghi rõ cần sửa gì thì phòng xét nghiệm mới sửa được.");
      return;
    }

    setBusy("send-back");
    setError(null);
    const ok = await send(`/api/lab-result/${selected.lab_result_id}/send-back`, {
      clinic_patient_id: selected.clinic_patient_id,
      reason: reason.trim(),
    });
    setBusy(null);
    if (!ok) return;
    setAsking(false);
    setReason("");
    setMessage(
      "Đã trả lại. Kết quả vẫn nằm trong hàng đợi và chưa được báo cho bệnh nhân.",
    );
    router.refresh();
  }

  return (
    <div className="grid h-full grid-cols-[minmax(320px,400px)_1fr] gap-4 p-4">
      {/* Cột trái: hàng đợi */}
      <section className="flex flex-col rounded-control border border-line bg-surface">
        <div className="border-b border-line p-3">
          <h2 className="text-sm font-semibold text-ink">Chờ duyệt</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            {results.length} kết quả · hiển thị {filtered.length}
          </p>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm BN / xét nghiệm…"
            className="mt-2 w-full rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="p-4 text-sm text-ink-muted">Không có kết quả chờ duyệt.</p>
          ) : (
            filtered.map((r) => (
              <button
                key={r.lab_result_id}
                onClick={() => pick(r.lab_result_id)}
                className={`block w-full border-b border-line px-3 py-2.5 text-left transition-colors hover:bg-surface-muted ${
                  selectedId === r.lab_result_id ? "bg-surface-selected" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink">
                    {r.patient?.full_name ?? "Chưa có tên"}
                  </span>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      r.flag === "CRITICAL_HIGH" || r.flag === "CRITICAL_LOW"
                        ? "bg-danger-bg text-danger"
                        : r.flag && r.flag !== "NORMAL"
                          ? "bg-warning-bg text-warning"
                          : "bg-success-bg text-success"
                    }`}
                  >
                    {FLAG_LABEL[r.flag ?? ""] ?? r.flag ?? "—"}
                  </span>
                </div>
                <div className="mt-0.5 truncate text-xs text-ink-muted">
                  {r.test_name} · {r.result_value ?? r.result_numeric ?? "—"}
                  {r.result_unit ? ` ${r.result_unit}` : ""}
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 text-xs text-ink-faint">
                  {fmtDate(r.result_received_at)}
                  {sentBack.has(r.lab_result_id) ? (
                    <span className="rounded-full bg-warning-bg px-1.5 py-0.5 text-[11px] font-medium text-warning">
                      Đã trả lại
                    </span>
                  ) : null}
                </div>
              </button>
            ))
          )}
        </div>
      </section>

      {/* Cột phải: chi tiết + hành động */}
      <section className="overflow-y-auto">
        {selected ? (
          <div className="rounded-control border border-line bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-ink">
                  {selected.patient?.full_name ?? "Chưa có tên"}
                </h3>
                <div className="mt-0.5 text-xs text-ink-muted">
                  {selected.patient?.phone_primary ?? "—"} · {selected.test_code}
                </div>
              </div>
              <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                {selected.triage_group ?? "PENDING"}
              </span>
            </div>

            <div className="mt-4 rounded-control border border-line bg-surface-muted p-3">
              <h4 className="text-xs font-semibold tracking-wide text-ink-soft">
                {selected.test_name}
              </h4>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-semibold text-ink">
                  {selected.result_value ?? selected.result_numeric ?? "—"}
                </span>
                {selected.result_unit ? (
                  <span className="text-sm text-ink-muted">
                    {selected.result_unit}
                  </span>
                ) : null}
              </div>
              {(selected.reference_range_low !== null ||
                selected.reference_range_high !== null) && (
                <div className="mt-1 text-xs text-ink-muted">
                  Khoảng tham chiếu: {selected.reference_range_low ?? "—"} –{" "}
                  {selected.reference_range_high ?? "—"}
                </div>
              )}
              {selected.flag && (
                <div className="mt-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      selected.flag === "CRITICAL_HIGH" ||
                      selected.flag === "CRITICAL_LOW"
                        ? "bg-danger-bg text-danger"
                        : selected.flag !== "NORMAL"
                          ? "bg-warning-bg text-warning"
                          : "bg-success-bg text-success"
                    }`}
                  >
                    {FLAG_LABEL[selected.flag] ?? selected.flag}
                  </span>
                </div>
              )}
            </div>

            {sentBack.has(selected.lab_result_id) ? (
              <p className="mt-3 rounded-control bg-warning-bg px-3 py-2 text-xs text-warning">
                Kết quả này đã được trả lại và đang chờ phòng xét nghiệm sửa.
              </p>
            ) : null}

            {selected.is_finalized ? (
              <p className="mt-4 text-sm font-semibold text-success">
                Đã được bác sĩ ký duyệt.
              </p>
            ) : canReview ? (
              <>
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    onClick={review}
                    disabled={busy !== null}
                    className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
                  >
                    {busy === "review"
                      ? "Đang ký duyệt…"
                      : "Ký duyệt & cho phép trả kết quả"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAsking((v) => !v);
                      setError(null);
                    }}
                    disabled={busy !== null}
                    className="rounded-control border border-line bg-surface px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-surface-muted disabled:cursor-not-allowed disabled:text-ink-faint"
                  >
                    Trả lại chỉnh sửa
                  </button>
                </div>

                {asking ? (
                  <div className="mt-3 flex flex-col gap-2">
                    <label className="flex flex-col gap-1 text-sm">
                      <span className="text-ink-muted">
                        Cần sửa gì (phòng xét nghiệm sẽ đọc dòng này)
                      </span>
                      <input
                        value={reason}
                        onChange={(e) => {
                          setReason(e.target.value);
                          setError(null);
                        }}
                        minLength={MIN_REASON}
                        placeholder="Thiếu trang 2 của phiếu"
                        className="rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-ink outline-none focus:border-brand-500"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={sendBack}
                      disabled={busy !== null}
                      className="self-start rounded-control bg-warning px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
                    >
                      {busy === "send-back" ? "Đang gửi…" : "Gửi trả lại"}
                    </button>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="mt-4 text-xs text-ink-faint">
                Chỉ bác sĩ ký duyệt hoặc trả lại kết quả. Bạn xem để theo dõi
                hàng đợi.
              </p>
            )}

            {error ? (
              <p className="mt-3 rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
                {error}
              </p>
            ) : null}
            {message ? (
              <p
                role="status"
                className="mt-3 rounded-control bg-success-bg px-3 py-2 text-sm text-success"
              >
                {message}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center rounded-control border border-dashed border-line text-sm text-ink-faint">
            Chọn một kết quả để duyệt
          </div>
        )}
      </section>
    </div>
  );
}
