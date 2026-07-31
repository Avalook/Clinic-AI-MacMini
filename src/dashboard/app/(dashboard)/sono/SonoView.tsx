"use client";

// (a) Hàng đợi SA: bắt đầu → hoàn tất → hủy. (b) Hàng đợi XN: 3 ô toggle có/chưa.
// Ghi qua /api/sono (service-role) rồi router.refresh(). In phiếu mở /print/sono/[id].

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2, Printer } from "lucide-react";
import { INPUT, LABEL, BTN } from "../form-ui";
import { fmtTime } from "../../../lib/datetime";

export interface SonoRow {
  id: string;
  kind: "SA" | "XN";
  service_name_raw: string | null;
  status: string | null;
  result_text: string | null;
  started_at: string | null;
  sent_to_lab_at: string | null;
  finished_at: string | null;
  created_at: string;
  patient: { full_name: string | null; patient_code: string | null } | null;
}

// (a) Nhãn + màu trạng thái SA.
const SA_STATUS: Record<string, { label: string; cls: string }> = {
  WAITING: { label: "Chờ khám", cls: "bg-[#dbeafe] text-[#1d4ed8]" },
  IN_PROGRESS: { label: "Đang khám", cls: "bg-warning-bg text-warning" },
  DONE: { label: "Hoàn tất", cls: "bg-success-bg text-success" },
  CANCELLED: { label: "Đã hủy", cls: "bg-danger-bg text-danger" },
};

function SaBadge({ status }: { status: string | null }) {
  const s = SA_STATUS[status ?? "WAITING"] ?? SA_STATUS.WAITING;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${s.cls}`}
    >
      {s.label}
    </span>
  );
}

function PrintLink({ id }: { id: string }) {
  return (
    <a
      href={`/print/sono/${id}`}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="In phiếu"
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[#7c3aed] hover:bg-[#f3e8ff]"
    >
      <Printer size={14} /> In
    </a>
  );
}

const TH = "border-b border-surface-sunken px-3 py-2 text-left font-semibold text-[#525252]";
const TD = "border-b border-[#f3f3f3] px-3 py-2 align-middle";

export default function SonoView({ sa, xn }: { sa: SonoRow[]; xn: SonoRow[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(method: string, body: unknown): Promise<boolean> {
    setError(null);
    setBusy(true);
    const res = await fetch("/api/sono", {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setBusy(false);
    if (!res.ok) {
      setError((await res.json().catch(() => ({}))).error ?? "Có lỗi xảy ra.");
      return false;
    }
    router.refresh();
    return true;
  }

  function patientCell(r: SonoRow) {
    return (
      <>
        <span className="font-medium text-ink">
          {r.patient?.full_name ?? r.service_name_raw ?? "—"}
        </span>
        {r.patient?.patient_code && (
          <span className="ml-1.5 text-xs text-ink-muted">
            {r.patient.patient_code}
          </span>
        )}
        {r.patient && r.service_name_raw && (
          <span className="block text-xs text-ink-faint">{r.service_name_raw}</span>
        )}
      </>
    );
  }

  return (
    <div className="space-y-8">
      {error && (
        <p className="rounded bg-danger-bg px-3 py-2 text-sm text-danger">{error}</p>
      )}

      {/* ===================== (a) HÀNG ĐỢI SIÊU ÂM ===================== */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-ink">
          (a) Hàng đợi siêu âm — BN sắp khám
        </h2>
        <AddForm kind="SA" busy={busy} onAdd={(b) => send("POST", b)} />
        <div className="overflow-auto rounded-xl border border-surface-sunken bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <table className="w-full min-w-max border-collapse text-sm">
            <thead className="bg-surface-muted">
              <tr>
                <th className={TH}>Giờ tạo</th>
                <th className={TH}>Bệnh nhân</th>
                <th className={TH}>Trạng thái</th>
                <th className={TH}>Thao tác</th>
                <th className={`${TH} text-right`}>{""}</th>
              </tr>
            </thead>
            <tbody>
              {sa.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-ink-muted" colSpan={5}>
                    Chưa có BN trong hàng đợi siêu âm.
                  </td>
                </tr>
              ) : (
                sa.map((r) => {
                  const st = r.status ?? "WAITING";
                  const done = st === "DONE" || st === "CANCELLED";
                  return (
                    <tr key={r.id} className="hover:bg-surface-muted">
                      <td className={`${TD} whitespace-nowrap tabular-nums text-ink-soft`}>
                        {fmtTime(r.created_at)}
                      </td>
                      <td className={TD}>{patientCell(r)}</td>
                      <td className={`${TD} whitespace-nowrap`}>
                        <SaBadge status={st} />
                      </td>
                      <td className={`${TD} whitespace-nowrap`}>
                        <div className="flex gap-1.5">
                          {st === "WAITING" && (
                            <button
                              onClick={() => send("PATCH", { id: r.id, action: "start" })}
                              disabled={busy}
                              className="rounded-md bg-warning-bg px-2 py-1 text-xs font-medium text-warning hover:brightness-95 disabled:opacity-50"
                            >
                              Bắt đầu
                            </button>
                          )}
                          {st === "IN_PROGRESS" && (
                            <button
                              onClick={() => send("PATCH", { id: r.id, action: "finish" })}
                              disabled={busy}
                              className="rounded-md bg-success-bg px-2 py-1 text-xs font-medium text-success hover:brightness-95 disabled:opacity-50"
                            >
                              Hoàn tất
                            </button>
                          )}
                          {!done && (
                            <button
                              onClick={() => send("PATCH", { id: r.id, action: "cancel" })}
                              disabled={busy}
                              className="rounded-md bg-danger-bg px-2 py-1 text-xs font-medium text-danger hover:brightness-95 disabled:opacity-50"
                            >
                              Hủy
                            </button>
                          )}
                          {done && <span className="text-xs text-ink-faint">—</span>}
                        </div>
                      </td>
                      <td className={`${TD} whitespace-nowrap text-right`}>
                        <div className="flex items-center justify-end gap-1">
                          <PrintLink id={r.id} />
                          <button
                            onClick={() => send("DELETE", { id: r.id })}
                            disabled={busy}
                            aria-label="Xoá"
                            className="rounded-md p-1.5 text-ink-faint hover:bg-danger-bg hover:text-danger disabled:opacity-50"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ===================== (b) HÀNG ĐỢI XÉT NGHIỆM ===================== */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-ink">
          (b) Hàng đợi xét nghiệm — 3 trạng thái
        </h2>
        <AddForm kind="XN" busy={busy} onAdd={(b) => send("POST", b)} />
        <div className="overflow-auto rounded-xl border border-surface-sunken bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <table className="w-full min-w-max border-collapse text-sm">
            <thead className="bg-surface-muted">
              <tr>
                <th className={TH}>Bệnh nhân</th>
                <th className={`${TH} text-center`}>Lấy mẫu</th>
                <th className={`${TH} text-center`}>Gửi lab</th>
                <th className={`${TH} text-center`}>Có KQ</th>
                <th className={`${TH} text-right`}>{""}</th>
              </tr>
            </thead>
            <tbody>
              {xn.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-ink-muted" colSpan={5}>
                    Chưa có mẫu trong hàng đợi xét nghiệm.
                  </td>
                </tr>
              ) : (
                xn.map((r) => (
                  <tr key={r.id} className="hover:bg-surface-muted">
                    <td className={TD}>{patientCell(r)}</td>
                    <MilestoneCell
                      busy={busy}
                      at={r.started_at}
                      onToggle={(v) =>
                        send("PATCH", { id: r.id, milestone: "sample", value: v })
                      }
                    />
                    <MilestoneCell
                      busy={busy}
                      at={r.sent_to_lab_at}
                      onToggle={(v) =>
                        send("PATCH", { id: r.id, milestone: "sendlab", value: v })
                      }
                    />
                    <MilestoneCell
                      busy={busy}
                      at={r.finished_at}
                      onToggle={(v) =>
                        send("PATCH", { id: r.id, milestone: "result", value: v })
                      }
                    />
                    <td className={`${TD} whitespace-nowrap text-right`}>
                      <div className="flex items-center justify-end gap-1">
                        <PrintLink id={r.id} />
                        <button
                          onClick={() => send("DELETE", { id: r.id })}
                          disabled={busy}
                          aria-label="Xoá"
                          className="rounded-md p-1.5 text-ink-faint hover:bg-danger-bg hover:text-danger disabled:opacity-50"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

// 1 ô mốc XN: nút "có / chưa" (toggle). Đã đạt → hiện giờ + cho bỏ; chưa → nút "Đánh dấu".
function MilestoneCell({
  at,
  busy,
  onToggle,
}: {
  at: string | null;
  busy: boolean;
  onToggle: (value: boolean) => void;
}) {
  const has = !!at;
  return (
    <td className="border-b border-[#f3f3f3] px-3 py-2 text-center">
      {has ? (
        <button
          onClick={() => onToggle(false)}
          disabled={busy}
          title="Bấm để bỏ đánh dấu"
          className="inline-flex flex-col items-center rounded-md bg-success-bg px-2 py-1 text-xs font-medium text-success hover:brightness-95 disabled:opacity-50"
        >
          <span>✓ Có</span>
          <span className="tabular-nums text-[10px] text-success/70">
            {fmtTime(at)}
          </span>
        </button>
      ) : (
        <button
          onClick={() => onToggle(true)}
          disabled={busy}
          className="rounded-md border border-line px-2 py-1 text-xs text-ink-muted hover:border-brand-600 hover:text-brand-600 disabled:opacity-50"
        >
          Đánh dấu
        </button>
      )}
    </td>
  );
}

// Form thêm dòng vào hàng đợi (dùng chung cho SA và XN).
function AddForm({
  kind,
  busy,
  onAdd,
}: {
  kind: "SA" | "XN";
  busy: boolean;
  onAdd: (body: unknown) => Promise<boolean>;
}) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  async function submit() {
    const ok = await onAdd({
      kind,
      service_name: name.trim(),
      patient_code: code.trim() || undefined,
    });
    if (ok) {
      setName("");
      setCode("");
    }
  }
  return (
    <div className="rounded-xl border border-line bg-white p-3 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_220px_auto] sm:items-end">
        <div>
          <label className={LABEL}>
            {kind === "SA" ? "Dịch vụ siêu âm" : "Xét nghiệm"}
          </label>
          <input
            className={INPUT}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={kind === "SA" ? "VD: Siêu âm thai" : "VD: Công thức máu"}
          />
        </div>
        <div>
          <label className={LABEL}>Mã BN (tuỳ chọn)</label>
          <input
            className={INPUT}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="VD: BN0001"
          />
        </div>
        <button onClick={submit} disabled={busy} className={BTN}>
          {busy ? "Đang lưu..." : "+ Thêm"}
        </button>
      </div>
    </div>
  );
}
