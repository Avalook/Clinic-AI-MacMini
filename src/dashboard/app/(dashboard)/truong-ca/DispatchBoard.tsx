"use client";

// Bảng điều phối của Trưởng ca — năm màn của prototype, nối vào dữ liệu thật.
//
// Prototype (src/truong-ca-prototype) dựng hình dạng; dữ liệu ở đó là mock cứng.
// Ở đây mọi con số đến từ /api/v1/dispatch/*, tức là từ cùng con trỏ
// `visit.current_room_id` mà mọi bộ phận khác đọc — yêu cầu khách hàng nói rõ
// điều này, và nó là lý do bảng không bao giờ lệch với hàng đợi thật.
//
// BA THỨ PROTOTYPE THIẾU, đã bổ sung theo đúng yêu cầu Notion §4:
//   * cột CHUYÊN KHOA và TỔNG THỜI GIAN trong phòng khám (khác thời gian chờ);
//   * lọc theo BÁC SĨ và theo TRẠNG THÁI;
//   * chỉ báo "dữ liệu cũ X giây" khi không làm mới được.

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Clock,
  History,
  LayoutDashboard,
  Rows3,
  Search,
  Tv,
  Users,
  X,
} from "lucide-react";
import type {
  DispatchAlert,
  DispatchHistoryRow,
  DispatchPatient,
  DispatchRoom,
  RouteTemplate,
} from "./types";
import { humanMinutes, nodeLabel } from "./types";

type TabId = "overview" | "queues" | "alerts" | "history" | "tv";

const TABS: { id: TabId; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "Toàn cảnh điều phối", icon: LayoutDashboard },
  { id: "queues", label: "Hàng đợi theo trạm", icon: Rows3 },
  { id: "alerts", label: "Cảnh báo & ngưỡng", icon: AlertTriangle },
  { id: "history", label: "Lịch sử điều phối", icon: History },
  { id: "tv", label: "TV phòng chờ", icon: Tv },
];

/** Nhịp làm mới. Yêu cầu kỹ thuật: dữ liệu trên bảng phải mới trong 2–3 giây. */
const REFRESH_MS = 3000;

export interface DispatchData {
  patients: DispatchPatient[];
  rooms: DispatchRoom[];
  alerts: DispatchAlert[];
  routes: RouteTemplate[];
  history: DispatchHistoryRow[];
  /** null = không đọc được. Màn phải nói ra, không được vẽ bảng trống. */
  ok: boolean;
}

export default function DispatchBoard({ initial }: { initial: DispatchData }) {
  const router = useRouter();
  const [tab, setTab] = useState<TabId>("overview");
  const [data, setData] = useState(initial);
  const [selected, setSelected] = useState<DispatchPatient | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  // Mốc dữ liệu, để nói "cũ X giây" khi mạng hỏng.
  const [fetchedAt, setFetchedAt] = useState(() => Date.now());
  const [staleSeconds, setStaleSeconds] = useState(0);

  // Làm mới định kỳ. Yêu cầu kỹ thuật nói rõ: *"Nếu kết nối trực tiếp bị mất,
  // hệ thống tự tải lại định kỳ và báo rõ dữ liệu đã cũ bao nhiêu giây."*
  // Không đặt lại `fetchedAt` khi hỏng — đó chính là cách đồng hồ cũ chạy lên.
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const [ov, al] = await Promise.all([
          fetch("/api/dispatch-read?what=overview").then((r) => r.json()),
          fetch("/api/dispatch-read?what=alerts").then((r) => r.json()),
        ]);
        if (!ov.ok) return;
        setData((d) => ({
          ...d,
          patients: ov.patients ?? [],
          rooms: ov.rooms ?? [],
          alerts: al.items ?? [],
        }));
        setFetchedAt(Date.now());
      } catch {
        // Im lặng: đồng hồ "cũ X giây" bên dưới đã nói hộ.
      }
    }, REFRESH_MS);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(
      () => setStaleSeconds(Math.round((Date.now() - fetchedAt) / 1000)),
      1000,
    );
    return () => clearInterval(t);
  }, [fetchedAt]);

  function flash(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  }

  async function act(action: string, body: unknown, okMsg: string) {
    const res = await fetch(`/api/dispatch/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const out = (await res.json().catch(() => ({}))) as {
      ok?: boolean;
      error?: string;
    };
    if (!res.ok || !out.ok) {
      flash(`✗ ${out.error ?? `Lỗi máy chủ (${res.status})`}`);
      return false;
    }
    flash(okMsg);
    router.refresh();
    return true;
  }

  const alertCount = data.alerts.filter((a) => a.severity === "critical").length;

  return (
    <div className="dispatch-scope" style={{ display: "flex", gap: 16 }}>
      {/* Cột trái: chuyển màn. Dashboard đã có sidebar riêng nên đây chỉ là
          các tab của chính màn điều phối, không phải một sidebar thứ hai. */}
      <nav style={{ flex: "0 0 210px" }}>
        <div style={{ position: "sticky", top: 12, display: "grid", gap: 4 }}>
          {TABS.map((t) => {
            const Icon = t.icon;
            const on = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={on ? "btn btn-primary" : "btn btn-ghost"}
                style={{ justifyContent: "flex-start", gap: 8, width: "100%" }}
              >
                <Icon size={15} />
                <span style={{ flex: 1, textAlign: "left" }}>{t.label}</span>
                {t.id === "alerts" && alertCount > 0 && (
                  <span className="badge badge-danger">{alertCount}</span>
                )}
              </button>
            );
          })}
          <StaleIndicator seconds={staleSeconds} ok={data.ok} />
        </div>
      </nav>

      <div style={{ flex: 1, minWidth: 0 }}>
        {!data.ok && (
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
            Không đọc được dữ liệu điều phối. Các con số bên dưới có thể đã cũ —
            tải lại trang.
          </div>
        )}

        {tab === "overview" && (
          <Overview
            data={data}
            selected={selected}
            onSelect={setSelected}
            onAct={act}
          />
        )}
        {tab === "queues" && <Queues rooms={data.rooms} patients={data.patients} />}
        {tab === "alerts" && <Alerts alerts={data.alerts} rooms={data.rooms} onAct={act} />}
        {tab === "history" && <HistoryTable rows={data.history} />}
        {tab === "tv" && <TvBoard rooms={data.rooms} patients={data.patients} />}
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

/** "Cập nhật trực tiếp" hay "dữ liệu cũ X giây" — không bao giờ im lặng. */
function StaleIndicator({ seconds, ok }: { seconds: number; ok: boolean }) {
  const stale = !ok || seconds > 10;
  return (
    <div
      style={{
        marginTop: 8,
        padding: "8px 10px",
        borderRadius: "var(--radius-chip)",
        background: stale ? "var(--warning-bg)" : "var(--surface-muted)",
        color: stale ? "var(--warning)" : "var(--ink-muted)",
        fontSize: 11,
        display: "flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: stale ? "var(--warning)" : "var(--success)",
        }}
        className={stale ? undefined : "pulse-dot"}
      />
      {stale ? `Dữ liệu cũ ${seconds} giây` : "Cập nhật trực tiếp"}
    </div>
  );
}

// ── Toàn cảnh ───────────────────────────────────────────────────────────────

type ActFn = (a: string, b: unknown, m: string) => Promise<boolean>;

function Overview({
  data,
  selected,
  onSelect,
  onAct,
}: {
  data: DispatchData;
  selected: DispatchPatient | null;
  onSelect: (p: DispatchPatient | null) => void;
  onAct: ActFn;
}) {
  const [q, setQ] = useState("");
  const [room, setRoom] = useState("all");
  const [doctor, setDoctor] = useState("all");

  const doctors = useMemo(
    () =>
      [...new Set(data.patients.map((p) => p.doctor_name).filter(Boolean))].sort(),
    [data.patients],
  );

  const rows = useMemo(() => {
    let out = data.patients;
    const s = q.trim().toLowerCase();
    if (s)
      out = out.filter(
        (p) =>
          (p.patient_name ?? "").toLowerCase().includes(s) ||
          (p.patient_code ?? "").toLowerCase().includes(s),
      );
    if (room !== "all") out = out.filter((p) => p.room_code === room);
    if (doctor !== "all") out = out.filter((p) => p.doctor_name === doctor);
    // Chờ lâu nhất lên đầu — đó là thứ Trưởng ca cần xử lý trước.
    return [...out].sort((a, b) => b.wait_minutes - a.wait_minutes);
  }, [data.patients, q, room, doctor]);

  return (
    <div style={{ display: "flex", gap: 16 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <StationCards rooms={data.rooms} />

        <div
          style={{
            display: "flex",
            gap: 8,
            margin: "16px 0 12px",
            flexWrap: "wrap",
          }}
        >
          <div style={{ position: "relative", flex: "0 0 240px" }}>
            <Search
              size={14}
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--ink-muted)",
              }}
            />
            <input
              type="search"
              placeholder="Tìm tên hoặc mã bệnh nhân…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              style={{ width: "100%", paddingLeft: 30 }}
            />
          </div>
          <select value={room} onChange={(e) => setRoom(e.target.value)}>
            <option value="all">Mọi phòng</option>
            {data.rooms.map((r) => (
              <option key={r.code} value={r.code}>
                {r.name}
              </option>
            ))}
          </select>
          {/* Lọc theo bác sĩ — prototype thiếu, mà đây là bộ lọc Notion nêu đầu tiên. */}
          <select value={doctor} onChange={(e) => setDoctor(e.target.value)}>
            <option value="all">Mọi bác sĩ</option>
            {doctors.map((d) => (
              <option key={d} value={d ?? ""}>
                {d}
              </option>
            ))}
          </select>
          <span
            style={{
              alignSelf: "center",
              fontSize: 12,
              color: "var(--ink-muted)",
            }}
          >
            {rows.length} bệnh nhân
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Bệnh nhân</th>
                <th>Chuyên khoa</th>
                <th>Đang ở</th>
                <th>Chờ</th>
                <th>Tổng</th>
                <th>Đã xong</th>
                <th>Kế tiếp</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ color: "var(--ink-muted)" }}>
                    Không có bệnh nhân nào đang trong phòng khám.
                  </td>
                </tr>
              )}
              {rows.map((p) => {
                const over = p.wait_minutes > p.threshold_minutes;
                return (
                  <tr
                    key={p.visit_id}
                    onClick={() => onSelect(p)}
                    className={selected?.visit_id === p.visit_id ? "selected" : ""}
                    style={{ cursor: "pointer" }}
                  >
                    <td>
                      <div style={{ fontWeight: 600 }}>{p.patient_name ?? "—"}</div>
                      <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                        {p.patient_code ?? ""}
                        {p.queue_number ? ` · số ${p.queue_number}` : ""}
                      </div>
                    </td>
                    <td>{p.specialty ?? "—"}</td>
                    <td>
                      {p.room_name ?? nodeLabel(p.current_node_code)}
                      {p.doctor_name && (
                        <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                          {p.doctor_name}
                        </div>
                      )}
                    </td>
                    <td>
                      <span
                        className={over ? "badge badge-danger" : "badge badge-neutral"}
                      >
                        {p.wait_minutes}′
                      </span>
                    </td>
                    {/* Tổng thời gian trong phòng khám — prototype không có cột này. */}
                    <td style={{ color: "var(--ink-muted)" }}>
                      {humanMinutes(p.total_minutes)}
                    </td>
                    <td style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                      {p.done_steps.length
                        ? p.done_steps.map(nodeLabel).join(" · ")
                        : "—"}
                    </td>
                    <td>
                      {p.next_step ? (
                        nodeLabel(p.next_step)
                      ) : (
                        <span className="badge badge-warning">Chưa có tuyến</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <DetailPanel
          patient={
            data.patients.find((p) => p.visit_id === selected.visit_id) ?? selected
          }
          rooms={data.rooms}
          routes={data.routes}
          onClose={() => onSelect(null)}
          onAct={onAct}
        />
      )}
    </div>
  );
}

function StationCards({ rooms }: { rooms: DispatchRoom[] }) {
  const tone = {
    ok: { bg: "var(--success-bg)", fg: "var(--success)", label: "Trong mức" },
    warning: { bg: "var(--warning-bg)", fg: "var(--warning)", label: "Cần chú ý" },
    critical: { bg: "var(--danger-bg)", fg: "var(--danger)", label: "Quá tải" },
  };
  return (
    <div
      className="fade-in"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
        gap: 10,
      }}
    >
      {rooms.map((r) => {
        const t = tone[r.state];
        return (
          <div key={r.id} className="card" style={{ padding: 12 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <span style={{ fontWeight: 700, fontSize: 13 }}>{r.name}</span>
              <span
                className="badge"
                style={{ background: t.bg, color: t.fg }}
              >
                {t.label}
              </span>
            </div>
            <div style={{ display: "flex", gap: 14, fontSize: 12 }}>
              <span>
                <Users size={12} /> đang khám <b>{r.serving}</b>
              </span>
              <span>
                <Clock size={12} /> chờ <b>{r.waiting}</b>
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 6 }}>
              lâu nhất {r.max_wait}′ · TB {r.avg_wait}′ · ngưỡng{" "}
              {r.threshold_minutes}′/{r.threshold_waiting} người
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Panel chi tiết: timeline + chuyển phòng + chọn tuyến ────────────────────

function DetailPanel({
  patient,
  rooms,
  routes,
  onClose,
  onAct,
}: {
  patient: DispatchPatient;
  rooms: DispatchRoom[];
  routes: RouteTemplate[];
  onClose: () => void;
  onAct: ActFn;
}) {
  const [reason, setReason] = useState("");
  const [targetRoom, setTargetRoom] = useState("");
  const [routeCode, setRouteCode] = useState("");
  const [isException, setIsException] = useState(false);
  const [busy, setBusy] = useState(false);

  // Chỉ những phòng phục vụ ĐÚNG bước hiện tại mới chuyển sang được — backend
  // cũng từ chối, nhưng hiện sẵn danh sách đúng thì không ai phải thử rồi lỗi.
  const sameStepRooms = rooms.filter(
    (r) => r.node_code === patient.current_node_code && r.id !== patient.room_id,
  );

  async function transfer() {
    if (!targetRoom || !reason.trim()) return;
    setBusy(true);
    const ok = await onAct(
      "transfer-room",
      {
        visit_id: patient.visit_id,
        node_code: patient.current_node_code,
        room_id: targetRoom,
        reason: reason.trim(),
      },
      "✓ Đã chuyển phòng",
    );
    setBusy(false);
    if (ok) {
      setReason("");
      setTargetRoom("");
    }
  }

  async function applyRoute() {
    if (!routeCode) return;
    if (isException && !reason.trim()) return;
    setBusy(true);
    const ok = await onAct(
      "route",
      {
        visit_id: patient.visit_id,
        template_code: routeCode,
        is_exception: isException,
        reason: reason.trim() || null,
      },
      "✓ Đã áp dụng tuyến điều phối",
    );
    setBusy(false);
    if (ok) setReason("");
  }

  return (
    <aside
      className="card slide-in-right"
      style={{ flex: "0 0 320px", padding: 16, alignSelf: "flex-start" }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <div style={{ fontWeight: 700 }}>{patient.patient_name}</div>
          <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
            {patient.patient_code} · trong phòng khám{" "}
            {humanMinutes(patient.total_minutes)}
          </div>
        </div>
        <button onClick={onClose} className="btn btn-ghost" style={{ padding: 4 }}>
          <X size={16} />
        </button>
      </div>

      <div style={{ margin: "14px 0 6px", fontSize: 12, fontWeight: 700 }}>
        Hành trình
      </div>
      <ol style={{ margin: 0, paddingLeft: 16, fontSize: 12, lineHeight: 1.9 }}>
        {patient.done_steps.map((s) => (
          <li key={s} style={{ color: "var(--ink-muted)" }}>
            {nodeLabel(s)} <span style={{ color: "var(--success)" }}>✓</span>
          </li>
        ))}
        <li style={{ fontWeight: 700 }}>
          {nodeLabel(patient.current_node_code)}
          {patient.room_name ? ` · ${patient.room_name}` : ""} — đang chờ{" "}
          {patient.wait_minutes}′
        </li>
        {patient.next_step && (
          <li style={{ color: "var(--ink-faint)" }}>{nodeLabel(patient.next_step)}</li>
        )}
      </ol>

      <div style={{ margin: "14px 0 6px", fontSize: 12, fontWeight: 700 }}>
        Lý do điều phối <span style={{ color: "var(--danger)" }}>*</span>
      </div>
      <input
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="VD: SA1 quá tải, chuyển sang SA2"
        style={{ width: "100%" }}
      />

      {sameStepRooms.length > 0 && (
        <>
          <div style={{ margin: "12px 0 6px", fontSize: 12, fontWeight: 700 }}>
            Chuyển phòng
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <select
              value={targetRoom}
              onChange={(e) => setTargetRoom(e.target.value)}
              style={{ flex: 1 }}
            >
              <option value="">-- Chọn phòng --</option>
              {sameStepRooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} (chờ {r.waiting})
                </option>
              ))}
            </select>
            <button
              className="btn btn-primary"
              disabled={busy || !targetRoom || !reason.trim()}
              onClick={transfer}
            >
              Chuyển
            </button>
          </div>
        </>
      )}

      <div style={{ margin: "12px 0 6px", fontSize: 12, fontWeight: 700 }}>
        Tuyến điều phối
      </div>
      <select
        value={routeCode}
        onChange={(e) => setRouteCode(e.target.value)}
        style={{ width: "100%" }}
      >
        <option value="">-- Chọn tuyến --</option>
        {routes.map((r) => (
          <option key={r.code} value={r.code}>
            {r.name}
          </option>
        ))}
      </select>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
          margin: "8px 0",
        }}
      >
        <input
          type="checkbox"
          checked={isException}
          onChange={() => setIsException(!isException)}
        />
        Đổi tuyến giữa chừng (bắt buộc ghi lý do)
      </label>
      {/* Bước đã hoàn tất không bị đụng tới — backend giữ chúng trong
          `kept_steps`. Nói ra để người bấm biết mình không làm mất gì. */}
      {patient.done_steps.length > 0 && (
        <div style={{ fontSize: 11, color: "var(--ink-muted)", marginBottom: 8 }}>
          Giữ nguyên bước đã xong: {patient.done_steps.map(nodeLabel).join(", ")}
        </div>
      )}
      <button
        className="btn btn-primary"
        style={{ width: "100%" }}
        disabled={busy || !routeCode || (isException && !reason.trim())}
        onClick={applyRoute}
      >
        Áp dụng tuyến
      </button>
    </aside>
  );
}

// ── Hàng đợi theo trạm ──────────────────────────────────────────────────────

function Queues({
  rooms,
  patients,
}: {
  rooms: DispatchRoom[];
  patients: DispatchPatient[];
}) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        gap: 12,
      }}
    >
      {rooms.map((r) => {
        const here = patients
          .filter((p) => p.room_code === r.code)
          .sort((a, b) => b.wait_minutes - a.wait_minutes);
        return (
          <div key={r.id} className="card" style={{ padding: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>
              {r.name}{" "}
              <span style={{ fontWeight: 400, color: "var(--ink-muted)" }}>
                · {here.length} người
              </span>
            </div>
            {here.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--ink-faint)" }}>
                Không có ai đang chờ
              </div>
            ) : (
              here.map((p) => (
                <div
                  key={p.visit_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: 12,
                    padding: "5px 0",
                    borderBottom: "1px solid var(--line)",
                  }}
                >
                  <span>
                    {p.queue_number ? `${p.queue_number} · ` : ""}
                    {p.patient_name}
                  </span>
                  <span
                    style={{
                      color:
                        p.wait_minutes > p.threshold_minutes
                          ? "var(--danger)"
                          : "var(--ink-muted)",
                    }}
                  >
                    {p.wait_minutes}′
                  </span>
                </div>
              ))
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Cảnh báo + ngưỡng ───────────────────────────────────────────────────────

function Alerts({
  alerts,
  rooms,
  onAct,
}: {
  alerts: DispatchAlert[];
  rooms: DispatchRoom[];
  onAct: ActFn;
}) {
  const [edit, setEdit] = useState<Record<string, { w: number; n: number }>>({});
  return (
    <div>
      {alerts.length === 0 ? (
        <div className="card" style={{ padding: 20, textAlign: "center" }}>
          <div style={{ fontWeight: 700 }}>Không có cảnh báo</div>
          <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
            Mọi trạm đang trong ngưỡng.
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {alerts.map((a, i) => (
            <div
              key={i}
              className="card"
              style={{
                padding: 12,
                borderLeft: `3px solid ${
                  a.severity === "critical" ? "var(--danger)" : "var(--warning)"
                }`,
              }}
            >
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <AlertTriangle
                  size={14}
                  color={
                    a.severity === "critical" ? "var(--danger)" : "var(--warning)"
                  }
                />
                <span style={{ fontWeight: 600, fontSize: 13 }}>{a.message}</span>
              </div>
              {/* "chỉ rõ phòng VÀ danh sách bệnh nhân bị ảnh hưởng" */}
              {a.patients.length > 0 && (
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--ink-muted)",
                    marginTop: 4,
                    marginLeft: 22,
                  }}
                >
                  {a.patients.map((p) => p.name).join(" · ")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <h3 style={{ fontSize: 14, fontWeight: 700, margin: "20px 0 10px" }}>
        Ngưỡng cảnh báo theo phòng
      </h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Phòng</th>
              <th>Chờ quá (phút)</th>
              <th>Số người tối đa</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rooms.map((r) => {
              const e = edit[r.id] ?? {
                w: r.threshold_minutes,
                n: r.threshold_waiting,
              };
              return (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>
                    <input
                      type="text"
                      value={e.w}
                      onChange={(ev) =>
                        setEdit({
                          ...edit,
                          [r.id]: { ...e, w: Number(ev.target.value) || 0 },
                        })
                      }
                      style={{ width: 70 }}
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={e.n}
                      onChange={(ev) =>
                        setEdit({
                          ...edit,
                          [r.id]: { ...e, n: Number(ev.target.value) || 0 },
                        })
                      }
                      style={{ width: 70 }}
                    />
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      onClick={() =>
                        onAct(
                          "threshold",
                          {
                            room_id: r.id,
                            wait_minutes: e.w,
                            max_waiting: e.n,
                          },
                          `✓ Đã lưu ngưỡng cho ${r.name}`,
                        )
                      }
                    >
                      Lưu
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Lịch sử ─────────────────────────────────────────────────────────────────

const EVENT_LABEL: Record<string, string> = {
  "dispatch.moved": "Chuyển bước",
  "dispatch.transfer_room": "Chuyển phòng",
  "dispatch.route_applied": "Áp dụng tuyến",
  "dispatch.checkin": "Tiếp nhận",
};

function HistoryTable({ rows }: { rows: DispatchHistoryRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Thời gian</th>
            <th>Thao tác</th>
            <th>Bệnh nhân</th>
            <th>Từ</th>
            <th>Đến</th>
            <th>Lý do</th>
            <th>Người thực hiện</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={7} style={{ color: "var(--ink-muted)" }}>
                Chưa có thao tác điều phối nào.
              </td>
            </tr>
          )}
          {rows.map((h, i) => (
            <tr key={i}>
              <td style={{ whiteSpace: "nowrap" }}>
                {new Date(h.at).toLocaleString("vi-VN", {
                  timeZone: "Asia/Ho_Chi_Minh",
                  day: "2-digit",
                  month: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </td>
              <td>{EVENT_LABEL[h.event_type] ?? h.event_type}</td>
              <td>
                {h.patient_name ?? "—"}
                <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                  {h.patient_code ?? ""}
                </div>
              </td>
              <td>{h.from_room ?? nodeLabel(h.from_node)}</td>
              <td>
                <ArrowRight size={11} /> {h.to_room ?? nodeLabel(h.to_node)}
              </td>
              <td style={{ color: "var(--ink-muted)" }}>{h.reason ?? ""}</td>
              <td>{h.actor_name ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── TV phòng chờ ────────────────────────────────────────────────────────────

function TvBoard({
  rooms,
  patients,
}: {
  rooms: DispatchRoom[];
  patients: DispatchPatient[];
}) {
  const shown = rooms.filter((r) => r.show_on_tv);
  return (
    <div>
      <div
        style={{ fontSize: 12, color: "var(--ink-muted)", marginBottom: 10 }}
      >
        Màn hình công cộng: chỉ hiện <b>số thứ tự</b>, không hiện tên bệnh nhân
        hay dịch vụ.
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
        }}
      >
        {shown.map((r) => {
          const queue = patients
            .filter((p) => p.room_code === r.code && p.queue_number)
            .sort((a, b) => b.wait_minutes - a.wait_minutes)
            .map((p) => p.queue_number);
          return (
            <div key={r.id} className="card" style={{ padding: 14 }}>
              <div
                style={{
                  fontWeight: 800,
                  fontSize: 13,
                  letterSpacing: 0.4,
                  textTransform: "uppercase",
                  marginBottom: 10,
                }}
              >
                {r.name}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                Đang phục vụ
              </div>
              <div style={{ fontSize: 34, fontWeight: 800, lineHeight: 1.1 }}>
                {queue[0] ?? "—"}
              </div>
              <div
                style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 8 }}
              >
                Tiếp theo
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {queue.slice(1, 7).map((n) => (
                  <span key={n} className="badge badge-neutral">
                    {n}
                  </span>
                ))}
                {queue.length <= 1 && (
                  <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>—</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
