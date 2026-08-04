"use client";

// Màn CHECK-OUT của Lễ tân — đối soát trước, đóng sau.
//
// Nút "Đóng lượt" chỉ sáng khi lượt khám sạch vướng mắc. Còn vướng thì nó vẫn
// bấm được, nhưng bắt buộc gõ lý do — Notion §2 gọi đó là "ghi nhận ngoại lệ",
// và điều quan trọng là lý do ĐI KÈM ảnh chụp những gì còn dở tại thời điểm
// đóng, để sau này đọc lại được người đóng đã nhìn thấy gì mà vẫn quyết định.
//
// Không có nút thu tiền ở đây. Notion: *"Lễ tân chỉ được xem trạng thái thanh
// toán"* — màn này nói còn thiếu khoản nào, việc thu là của Thu ngân.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, Lock } from "lucide-react";

export interface Blocker {
  type: string;
  message: string;
}

export interface CheckoutRow {
  visit_id: string;
  patient_name: string | null;
  patient_code: string | null;
  room_name: string | null;
  already_closed: boolean;
  checked_in_at: string | null;
  blockers: Blocker[];
  can_close: boolean;
}

export default function CheckoutBoard({
  initial,
  ok,
}: {
  initial: CheckoutRow[];
  ok: boolean;
}) {
  const router = useRouter();
  const [rows, setRows] = useState(initial);
  const [live, setLive] = useState(ok);
  const [open, setOpen] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const r = await fetch("/api/reception/checkout");
      const d = (await r.json()) as { ok?: boolean; items?: CheckoutRow[] };
      if (d.ok === false) {
        setLive(false);
        return;
      }
      setRows(d.items ?? []);
      setLive(true);
    } catch {
      setLive(false);
    }
  }, []);

  // Danh sách này đổi khi bộ phận khác làm xong việc (thu tiền, trả kết quả),
  // nên nó phải tự mới. 5 giây: chậm hơn bảng điều phối vì ở đây không ai đang
  // đứng chờ được gọi tên.
  useEffect(() => {
    const t = setInterval(reload, 5000);
    return () => clearInterval(t);
  }, [reload]);

  function flash(m: string) {
    setToast(m);
    setTimeout(() => setToast(null), 3500);
  }

  async function close(row: CheckoutRow) {
    const needReason = row.blockers.length > 0;
    if (needReason && !reason.trim()) return;
    setBusy(true);
    const res = await fetch("/api/reception/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visit_id: row.visit_id,
        override_reason: needReason ? reason.trim() : null,
      }),
    });
    const out = (await res.json().catch(() => ({}))) as {
      ok?: boolean;
      error?: string;
      already_closed?: boolean;
    };
    setBusy(false);
    if (!res.ok || !out.ok) {
      flash(`✗ ${out.error ?? `Lỗi máy chủ (${res.status})`}`);
      return;
    }
    flash(
      out.already_closed
        ? "Lượt khám này đã được đóng trước đó."
        : needReason
          ? "✓ Đã đóng lượt (ngoại lệ, đã ghi lý do)"
          : "✓ Đã đóng lượt khám",
    );
    setOpen(null);
    setReason("");
    await reload();
    router.refresh();
  }

  const pending = rows.filter((r) => !r.already_closed);
  const done = rows.filter((r) => r.already_closed);

  return (
    <div className="dispatch-scope">
      {!live && (
        <div
          role="alert"
          className="card"
          style={{
            marginBottom: 12,
            borderColor: "var(--danger)",
            background: "var(--danger-bg)",
            color: "var(--danger)",
            fontSize: 13,
          }}
        >
          Không đọc được danh sách check-out. Danh sách bên dưới có thể đã cũ —
          tải lại trang.
        </div>
      )}

      <div style={{ fontSize: 12, color: "var(--ink-muted)", marginBottom: 10 }}>
        {pending.length} lượt chưa đóng · {done.length} đã đóng hôm nay
      </div>

      {pending.length === 0 && (
        <div className="card" style={{ padding: 20, textAlign: "center" }}>
          <div style={{ fontWeight: 700 }}>Không còn lượt nào cần đóng</div>
          <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
            Mọi lượt khám hôm nay đã được đóng.
          </div>
        </div>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {pending.map((r) => {
          const clean = r.blockers.length === 0;
          return (
            <div key={r.visit_id} className="card" style={{ padding: 14 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  alignItems: "flex-start",
                }}
              >
                <div>
                  <div style={{ fontWeight: 700 }}>
                    {r.patient_name ?? "—"}{" "}
                    <span
                      style={{
                        fontWeight: 400,
                        fontSize: 12,
                        color: "var(--ink-muted)",
                      }}
                    >
                      {r.patient_code ?? ""}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                    {r.checked_in_at
                      ? `Đến ${new Date(r.checked_in_at).toLocaleTimeString("vi-VN", {
                          timeZone: "Asia/Ho_Chi_Minh",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}`
                      : "Chưa rõ giờ đến"}
                    {r.room_name ? ` · đang ở ${r.room_name}` : ""}
                  </div>
                </div>

                <span
                  className="badge"
                  style={
                    clean
                      ? { background: "var(--success-bg)", color: "var(--success)" }
                      : { background: "var(--warning-bg)", color: "var(--warning)" }
                  }
                >
                  {clean
                    ? "Đủ điều kiện đóng"
                    : `Còn ${r.blockers.length} việc`}
                </span>
              </div>

              {/* Danh sách việc còn thiếu, không phải một câu chung chung.
                  Nói một vướng mắc rồi im là bắt Lễ tân sửa xong lại bấm, lại
                  bị chặn — Notion đòi "hiển thị danh sách việc còn thiếu". */}
              {!clean && (
                <ul
                  style={{
                    margin: "10px 0 0 18px",
                    padding: 0,
                    fontSize: 12,
                    color: "var(--warning)",
                    lineHeight: 1.9,
                  }}
                >
                  {r.blockers.map((b) => (
                    <li key={b.type}>{b.message}</li>
                  ))}
                </ul>
              )}

              <div
                style={{
                  marginTop: 12,
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                {clean ? (
                  <button
                    className="btn btn-primary"
                    disabled={busy}
                    onClick={() => close(r)}
                  >
                    <CheckCircle2 size={14} /> Đóng lượt khám
                  </button>
                ) : open === r.visit_id ? (
                  <>
                    <input
                      type="text"
                      autoFocus
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Lý do đóng khi còn việc chưa xong…"
                      style={{ flex: "1 1 260px" }}
                    />
                    <button
                      className="btn btn-danger"
                      disabled={busy || !reason.trim()}
                      onClick={() => close(r)}
                    >
                      Xác nhận đóng
                    </button>
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        setOpen(null);
                        setReason("");
                      }}
                    >
                      Huỷ
                    </button>
                  </>
                ) : (
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      setOpen(r.visit_id);
                      setReason("");
                    }}
                  >
                    <AlertTriangle size={14} /> Đóng dù còn việc (ghi lý do)
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {done.length > 0 && (
        <>
          <h3 style={{ fontSize: 14, fontWeight: 700, margin: "22px 0 8px" }}>
            Đã đóng hôm nay
          </h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Bệnh nhân</th>
                  <th>Mã BN</th>
                  <th>Giờ đến</th>
                </tr>
              </thead>
              <tbody>
                {done.map((r) => (
                  <tr key={r.visit_id}>
                    <td>
                      <Lock size={11} /> {r.patient_name ?? "—"}
                    </td>
                    <td>{r.patient_code ?? ""}</td>
                    <td>
                      {r.checked_in_at
                        ? new Date(r.checked_in_at).toLocaleTimeString("vi-VN", {
                            timeZone: "Asia/Ho_Chi_Minh",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
