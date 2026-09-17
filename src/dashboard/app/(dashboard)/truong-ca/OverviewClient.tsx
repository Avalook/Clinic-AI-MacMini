"use client";

// Màn TOÀN CẢNH — mỗi bệnh nhân một dòng, kèm panel chi tiết bên phải.

import { useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import type { DispatchAlert, DispatchPatient, DispatchRoom } from "./types";
import { humanMinutes, nodeLabel } from "./types";
import {
  type ActFn,
  type LiveData,
  LiveBadge,
  ReadFailed,
  roomWithFloor,
  Toast,
  useDispatchAction,
  useDispatchLive,
} from "./shared";
import { BonOSo, DieuPhoiNhanh, SoDoPhong } from "./SoDoTang";
import ChiDinhCuaBacSi from "./ChiDinhCuaBacSi";

export default function OverviewClient({
  initial,
}: {
  initial: {
    patients: DispatchPatient[];
    rooms: DispatchRoom[];
    alerts: DispatchAlert[];
    ok: boolean;
  };
}) {
  // CẢNH BÁO ĐÃ TẢI THÌ PHẢI ĐƯỢC DÙNG. Màn này vẫn gọi `/dispatch/alerts` 30
  // giây một lần (cả lúc dựng ở server) nhưng vứt đi bằng `alerts: []`, trong
  // khi mỗi lời gọi ấy chạy lại TOÀN BỘ truy vấn điều phối ở backend. Khối
  // "Điều phối nhanh" nay vẽ đúng dữ liệu ấy.
  const live = useDispatchLive(initial);
  const { act, toast } = useDispatchAction();
  const [selected, setSelected] = useState<DispatchPatient | null>(null);

  return (
    <div className="dispatch-scope">
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <LiveBadge seconds={live.staleSeconds} ok={live.ok} />
      </div>
      <ReadFailed ok={live.ok} />
      <div className="mb-4">
        <BonOSo patients={live.patients} rooms={live.rooms} />
      </div>
      <Board live={live} selected={selected} onSelect={setSelected} onAct={act} />
      <Toast text={toast} />
    </div>
  );
}

function Board({
  live,
  selected,
  onSelect,
  onAct,
}: {
  live: LiveData;
  selected: DispatchPatient | null;
  onSelect: (p: DispatchPatient | null) => void;
  onAct: ActFn;
}) {
  const [q, setQ] = useState("");
  const [room, setRoom] = useState("all");
  const [doctor, setDoctor] = useState("all");

  const doctors = useMemo(
    () =>
      [...new Set(live.patients.map((p) => p.doctor_name).filter(Boolean))].sort(),
    [live.patients],
  );

  const rows = useMemo(() => {
    let out = live.patients;
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
  }, [live.patients, q, room, doctor]);

  return (
    <div style={{ display: "flex", gap: 16 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
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
            {live.rooms.map((r) => (
              <option key={r.code} value={r.code}>
                {roomWithFloor(r.name, r.floor)}
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
                        {(p.so_tiep_don ?? p.queue_number) ? ` · số ${p.so_tiep_don ?? p.queue_number}` : ""}
                      </div>
                    </td>
                    <td>{p.specialty ?? "—"}</td>
                    <td>
                      {p.room_name
                        ? roomWithFloor(p.room_name, p.room_floor)
                        : nodeLabel(p.current_node_code)}
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
                      {/* Tuyến điều phối đã bỏ (16/09): bước kế tiếp đọc từ chỉ
                          định còn mở; không còn gì thì là "—", không báo lỗi. */}
                      {p.next_step ? nodeLabel(p.next_step) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selected ? (
        <DetailPanel
          patient={
            live.patients.find((p) => p.visit_id === selected.visit_id) ?? selected
          }
          rooms={live.rooms}
          onClose={() => onSelect(null)}
          onAct={onAct}
        />
      ) : (
        /* CHƯA CHỌN AI thì cột phải là bàn điều phối: việc cần xử lý ngay, và
           phòng nào đang kẹt. Chọn một người thì chỗ ấy thành panel thao tác —
           một cột, hai nhiệm vụ, không phải hai cột tranh chỗ. */
        <div className="w-80 shrink-0 space-y-3">
          <DieuPhoiNhanh alerts={live.alerts} />
          <SoDoPhong rooms={live.rooms} />
        </div>
      )}
    </div>
  );
}

function DetailPanel({
  patient,
  rooms,
  onClose,
  onAct,
}: {
  patient: DispatchPatient;
  rooms: DispatchRoom[];
  onClose: () => void;
  onAct: ActFn;
}) {
  const [reason, setReason] = useState("");
  const [targetRoom, setTargetRoom] = useState("");
  const [busy, setBusy] = useState(false);

  // Chỉ những phòng phục vụ ĐÚNG bước hiện tại mới chuyển sang được — backend
  // cũng từ chối, nhưng hiện sẵn danh sách đúng thì không ai phải thử rồi lỗi.
  //
  // Đọc `serves_nodes`, KHÔNG đọc `node_code`. Một phòng khám phục vụ cả năm
  // chuyên khoa; lọc theo bước chính (đang là KHAM-PHUKHOA cho cả bốn phòng)
  // thì một ca Nam khoa sẽ thấy danh sách rỗng và Trưởng ca không chuyển được
  // đi đâu cả.
  const sameStepRooms = rooms.filter(
    (r) =>
      r.serves_nodes.includes(patient.current_node_code ?? "") &&
      r.id !== patient.room_id,
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
      // Câu này Trưởng ca đọc lên cho bệnh nhân. "Đã chuyển phòng" không chỉ
      // được đường; "lên tầng 4, phòng SA3" thì chỉ được.
      `✓ Đã chuyển: ${roomWithFloor(
        rooms.find((r) => r.id === targetRoom)?.name ?? null,
        rooms.find((r) => r.id === targetRoom)?.floor ?? null,
      )}`,
    );
    setBusy(false);
    if (ok) {
      setReason("");
      setTargetRoom("");
    }
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
          {patient.room_name
            ? ` · ${roomWithFloor(patient.room_name, patient.room_floor)}`
            : ""}{" "}
          — đang chờ{" "}
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
                  {roomWithFloor(r.name, r.floor)} (chờ {r.waiting})
                  {r.floor && patient.room_floor && r.floor !== patient.room_floor
                    ? " ↕"
                    : ""}
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

      {/* KHỐI "TUYẾN ĐIỀU PHỐI" ĐÃ BỎ (Tuyền 16/09/2026) — xem
          ChiDinhCuaBacSi.tsx. Nó áp một quy trình MẪU lên cả lượt khám, buộc
          trưởng ca nghĩ thay bác sĩ; việc thật đã nằm trong chỉ định. Dịch vụ
          `apply_route` ở backend giữ nguyên, chỉ không còn nút gọi. */}
      <ChiDinhCuaBacSi key={patient.visit_id} visitId={patient.visit_id} />

      <DoiBacSi visitId={patient.visit_id} reason={reason} onAct={onAct} />
    </aside>
  );
}

/** Bác sĩ chính nghỉ giữa chừng → chuyển lượt cho bác sĩ khác (Tuyền chốt
 *  15/09/2026). Dùng chung ô "Lý do điều phối" phía trên — backend bắt buộc. */
function DoiBacSi({
  visitId,
  reason,
  onAct,
}: {
  visitId: string;
  reason: string;
  onAct: ActFn;
}) {
  const [bacSi, setBacSi] = useState<{ id: string; full_name: string }[] | null>(
    null,
  );
  const [chon, setChon] = useState("");
  const [busy, setBusy] = useState(false);

  async function moDanhSach() {
    if (bacSi !== null) return;
    const res = await fetch("/api/dispatch-read?what=bac-si", { cache: "no-store" });
    const json = (await res.json().catch(() => ({}))) as {
      items?: { id: string; full_name: string }[];
    };
    setBacSi(json.items ?? []);
  }

  return (
    <>
      <div style={{ margin: "12px 0 6px", fontSize: 12, fontWeight: 700 }}>
        Chuyển bác sĩ (bác sĩ chính nghỉ giữa chừng)
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <select
          value={chon}
          onFocus={() => void moDanhSach()}
          onChange={(e) => setChon(e.target.value)}
          style={{ flex: 1 }}
        >
          <option value="">-- Chọn bác sĩ nhận --</option>
          {(bacSi ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.full_name}
            </option>
          ))}
        </select>
        <button
          className="btn btn-primary"
          disabled={busy || !chon || !reason.trim()}
          onClick={async () => {
            setBusy(true);
            const ok = await onAct(
              "doi-bac-si",
              { visit_id: visitId, bac_si_moi_id: chon, ly_do: reason.trim() },
              "✓ Đã chuyển bác sĩ — bác sĩ mới mở bệnh án đang dở để khám tiếp",
            );
            setBusy(false);
            if (ok) setChon("");
          }}
        >
          Chuyển
        </button>
      </div>
    </>
  );
}

