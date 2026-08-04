"use client";

// BỘ PHẬN SIÊU ÂM — bốn màn, theo đúng bản mẫu ở src/truong-ca-prototype.
//
// Giao diện chỉ VẼ. Bốn ô "sẵn sàng", bản nào sửa được, bản nào đã khoá — tất
// cả do backend quyết (ultrasound_board_service.py). Ở đây không có một phép
// tính nghiệp vụ nào, vì màn này nói với kỹ thuật viên rằng bệnh nhân đã đủ
// điều kiện siêu âm hay chưa, và một câu trả lời tính ở trình duyệt là câu
// trả lời không ai kiểm được.
//
// Dùng chung `dispatch.css` với bảng Trưởng ca: hai màn cùng một ngôn ngữ hình
// ảnh, và một bộ thẻ (.card/.badge/.btn) thay vì hai bộ lệch nhau.

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  DoorOpen,
  FileSignature,
  ImageOff,
  Save,
} from "lucide-react";

import { getSupabaseBrowser } from "../../../lib/supabase-browser";
import { roomWithFloor } from "../truong-ca/shared";
import type {
  SonoPatientGroup,
  SonoQueueItem,
  SonoRecord,
  SonoRoom,
} from "./types";

type Tab = "queue" | "dispatch" | "results" | "signed";

const TABS: { key: Tab; label: string; title: string; hint: string }[] = [
  {
    key: "queue",
    label: "Danh sách chờ",
    title: "Danh sách chờ siêu âm",
    hint: "Tiếp nhận yêu cầu, kiểm tra sẵn sàng và theo dõi thời gian chờ.",
  },
  {
    key: "dispatch",
    label: "Điều phối phòng",
    title: "Điều phối phòng siêu âm (SA1–SA3)",
    hint: "Theo dõi SA1–SA3, hàng đợi và tải của từng phòng.",
  },
  {
    key: "results",
    label: "Soạn kết quả",
    title: "Kết quả siêu âm & hoàn thiện báo cáo",
    hint: "Hoàn thiện mô tả và kết luận, rồi chuyển bác sĩ ký.",
  },
  {
    key: "signed",
    label: "Đã ký",
    title: "Báo cáo siêu âm đã ký",
    hint: "Tra cứu theo bệnh nhân. Bản đã ký không sửa được.",
  },
];

export default function UltrasoundBoard({
  initialQueue,
  initialRooms,
  ok,
}: {
  initialQueue: SonoQueueItem[];
  initialRooms: SonoRoom[];
  ok: boolean;
}) {
  const [tab, setTab] = useState<Tab>("queue");
  const [queue, setQueue] = useState(initialQueue);
  const [rooms, setRooms] = useState(initialRooms);
  const [drafts, setDrafts] = useState<SonoRecord[] | null>(null);
  const [signed, setSigned] = useState<SonoPatientGroup[] | null>(null);
  const [live, setLive] = useState(ok);
  const [toast, setToast] = useState<string | null>(null);

  const flash = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(null), 3500);
  };

  const reload = useCallback(async () => {
    try {
      const [q, r] = await Promise.all([
        fetch("/api/ultrasound?what=queue").then((x) => x.json()),
        fetch("/api/ultrasound?what=rooms").then((x) => x.json()),
      ]);
      if (q.ok === false || r.ok === false) {
        setLive(false);
        return;
      }
      setQueue(q.items ?? []);
      setRooms(r.items ?? []);
      setLive(true);
    } catch {
      setLive(false);
    }
  }, []);

  // Hai tab kia nạp KHI MỞ, không nạp sẵn. Người làm siêu âm ở tab hàng chờ gần
  // như cả buổi; kéo sẵn danh sách đã ký của cả tuần cho một tab chưa ai mở là
  // trả tiền mạng cho việc không xảy ra.
  const loadRecords = useCallback(async (which: "results" | "signed") => {
    const isSigned = which === "signed";
    const res = await fetch(
      `/api/ultrasound?what=records&signed=${isSigned}&days=${isSigned ? 7 : 1}`,
    ).then((x) => x.json());
    if (res.ok === false) {
      setLive(false);
      return;
    }
    if (isSigned) setSigned(res.patients ?? []);
    else setDrafts(res.items ?? []);
  }, []);

  useEffect(() => {
    // Bọc trong một tick: `loadRecords` gọi setState, và gọi thẳng trong thân
    // effect là đúng thứ `react-hooks/set-state-in-effect` chặn (render lan
    // tầng). Huỷ khi đổi tab để không setState lên một tab đã rời.
    let alive = true;
    const t = setTimeout(() => {
      if (!alive) return;
      if (tab === "results" && drafts === null) void loadRecords("results");
      if (tab === "signed" && signed === null) void loadRecords("signed");
    }, 0);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [tab, drafts, signed, loadRecords]);

  // Hàng chờ và tải phòng đổi khi người khác thao tác (bác sĩ chỉ định thêm,
  // Trưởng ca chuyển phòng). Nghe realtime thay vì đếm giây — cùng cách với
  // màn check-out và bảng điều phối.
  useEffect(() => {
    const supabase = getSupabaseBrowser();
    let timer: ReturnType<typeof setTimeout> | null = null;
    const bump = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => void reload(), 250);
    };
    let channel = supabase.channel("ultrasound-board");
    for (const table of ["work_item", "visit"]) {
      channel = channel.on(
        "postgres_changes",
        { event: "*", schema: "public", table },
        bump,
      );
    }
    channel.subscribe();
    const beat = setInterval(reload, 30_000);
    return () => {
      if (timer) clearTimeout(timer);
      clearInterval(beat);
      void supabase.removeChannel(channel);
    };
  }, [reload]);

  const meta = TABS.find((t) => t.key === tab)!;

  return (
    <div className="dispatch-scope">
      <header style={{ marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>{meta.title}</h1>
        <p style={{ fontSize: 12, color: "var(--ink-muted)", margin: "2px 0 0" }}>
          {meta.hint}
        </p>
      </header>

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
          Không đọc được dữ liệu siêu âm. Danh sách bên dưới có thể đã cũ — tải
          lại trang. ĐỪNG coi danh sách trống là &ldquo;không còn ai cần siêu
          âm&rdquo;.
        </div>
      )}

      <nav
        style={{
          display: "flex",
          gap: 6,
          marginBottom: 14,
          borderBottom: "1px solid var(--line)",
        }}
      >
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            style={{
              padding: "8px 14px",
              border: "none",
              background: "transparent",
              borderBottom:
                tab === t.key
                  ? "2px solid var(--brand-600)"
                  : "2px solid transparent",
              color: tab === t.key ? "var(--brand-700)" : "var(--ink-soft)",
              fontWeight: tab === t.key ? 700 : 500,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            {t.label}
            {t.key === "queue" && queue.length > 0 ? ` (${queue.length})` : ""}
          </button>
        ))}
      </nav>

      {tab === "queue" && <QueueTab items={queue} />}
      {tab === "dispatch" && <RoomsTab rooms={rooms} queue={queue} />}
      {tab === "results" && (
        <ResultsTab
          drafts={drafts}
          onSaved={async (msg) => {
            flash(msg);
            await loadRecords("results");
          }}
        />
      )}
      {tab === "signed" && <SignedTab groups={signed} />}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

// ── Tab 1: hàng chờ ────────────────────────────────────────────────────────

function ReadyDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 11,
        color: ok ? "var(--success)" : "var(--ink-muted)",
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: ok ? "var(--success)" : "var(--line)",
        }}
      />
      {label}
    </span>
  );
}

function QueueTab({ items }: { items: SonoQueueItem[] }) {
  if (items.length === 0) {
    return (
      <div className="card" style={{ padding: 20, textAlign: "center" }}>
        <ClipboardList size={22} style={{ color: "var(--ink-faint)" }} />
        <div style={{ fontWeight: 700, marginTop: 6 }}>
          Chưa có ai chờ siêu âm
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
          Danh sách hiện khi bác sĩ chỉ định siêu âm cho một lượt khám.
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {items.map((p) => (
        <div key={p.work_item_id} className="card" style={{ padding: 14 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div>
              <div style={{ fontWeight: 700 }}>
                <span style={{ color: "var(--ink-muted)", fontWeight: 400 }}>
                  {p.queue_number ?? p.stt}.{" "}
                </span>
                {p.patient_name ?? "—"}{" "}
                <span
                  style={{
                    fontWeight: 400,
                    fontSize: 12,
                    color: "var(--ink-muted)",
                  }}
                >
                  {p.patient_code ?? ""}
                  {p.birth_year ? ` · ${p.birth_year}` : ""}
                  {p.gender ? ` · ${p.gender}` : ""}
                </span>
              </div>
              <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
                {p.service_name ?? "Siêu âm"}
                {p.indication_doctor ? ` · chỉ định: ${p.indication_doctor}` : ""}
                {p.room_name ? ` · ${roomWithFloor(p.room_name, p.room_floor)}` : ""}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <span
                className={`badge ${
                  p.status === "IN_PROGRESS" ? "badge-brand" : "badge-neutral"
                }`}
              >
                {p.status === "IN_PROGRESS" ? "Đang làm" : "Đang chờ"}
              </span>
              <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 4 }}>
                chờ {p.wait_minutes} phút
              </div>
            </div>
          </div>

          {/* BỐN Ô SẴN SÀNG. Ô cuối là phép AND của ba ô đầu — backend tính.
              Hiện đủ bốn thay vì chỉ hiện kết luận, vì khi bị chặn thì kỹ thuật
              viên cần biết THIẾU CÁI GÌ để đi xử lý, không phải chỉ biết "chưa
              được". */}
          <div
            style={{
              display: "flex",
              gap: 14,
              marginTop: 10,
              paddingTop: 10,
              borderTop: "1px solid var(--line)",
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <ReadyDot ok={p.readiness.checked_in} label="Đã check-in" />
            <ReadyDot ok={p.readiness.identified} label="Đủ định danh" />
            <ReadyDot ok={p.readiness.indication_valid} label="Chỉ định hiệu lực" />
            <span style={{ flex: 1 }} />
            {p.readiness.may_perform ? (
              <span className="badge badge-success">
                <CheckCircle2 size={12} /> Được phép siêu âm
              </span>
            ) : (
              <span className="badge badge-warning">
                <AlertTriangle size={12} /> Chưa đủ điều kiện
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Tab 2: điều phối phòng ────────────────────────────────────────────────

function RoomsTab({ rooms, queue }: { rooms: SonoRoom[]; queue: SonoQueueItem[] }) {
  return (
    <div
      style={{
        display: "grid",
        gap: 12,
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
      }}
    >
      {rooms.map((r) => {
        const here = queue.filter((p) => p.room_code === r.code);
        return (
          <div key={r.id} className="card" style={{ padding: 14 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ fontWeight: 700 }}>
                <DoorOpen size={14} /> {roomWithFloor(r.name, r.floor)}
              </div>
              <span
                className={`badge ${r.accepting ? "badge-success" : "badge-neutral"}`}
              >
                {r.accepting ? "Đang nhận" : "Tạm ngưng"}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "var(--ink-muted)", marginTop: 4 }}>
              đang làm {r.serving} · đang chờ {r.waiting}
              {!r.floor && (
                <span style={{ color: "var(--warning)" }}> · chưa khai tầng</span>
              )}
            </div>
            <div style={{ marginTop: 10 }}>
              {here.length === 0 ? (
                <div style={{ fontSize: 12, color: "var(--ink-faint)" }}>
                  Không có ai trong phòng
                </div>
              ) : (
                here.map((p) => (
                  <div
                    key={p.work_item_id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 12,
                      padding: "5px 0",
                      borderBottom: "1px solid var(--line)",
                    }}
                  >
                    <span>{p.patient_name ?? "—"}</span>
                    <span style={{ color: "var(--ink-muted)" }}>
                      {p.wait_minutes}′
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Tab 3: soạn kết quả ───────────────────────────────────────────────────

function ResultsTab({
  drafts,
  onSaved,
}: {
  drafts: SonoRecord[] | null;
  onSaved: (msg: string) => Promise<void>;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [mota, setMota] = useState("");
  const [ketLuan, setKetLuan] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (drafts === null) {
    return <div style={{ fontSize: 13, color: "var(--ink-muted)" }}>Đang tải…</div>;
  }
  if (drafts.length === 0) {
    return (
      <div className="card" style={{ padding: 20, textAlign: "center" }}>
        <div style={{ fontWeight: 700 }}>Không có bản nháp nào</div>
        <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
          Bản nháp xuất hiện sau khi siêu âm xong và bắt đầu nhập kết quả.
        </div>
      </div>
    );
  }

  async function save(rec: SonoRecord) {
    if (!rec.visit_id || !rec.ultrasound_type) return;
    setBusy(true);
    setErr(null);
    const res = await fetch("/api/ultrasound", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visit_id: rec.visit_id,
        ultrasound_type: rec.ultrasound_type,
        // `findings` là jsonb có cấu trúc. Ô nhập một dòng mô tả nên nó vào
        // khoá `mo_ta`; khi có mẫu theo từng loại siêu âm thì thêm khoá, không
        // phải đổi kiểu.
        findings: mota.trim() ? { mo_ta: mota.trim() } : null,
        impression: ketLuan.trim() || null,
      }),
    });
    const out = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok || out.ok === false) {
      setErr(out.error ?? `Lỗi máy chủ (${res.status})`);
      return;
    }
    setOpenId(null);
    await onSaved("✓ Đã lưu kết quả siêu âm");
  }

  return (
    <div style={{ display: "grid", gap: 10 }}>
      {drafts.map((d) => {
        const open = openId === d.ultrasound_id;
        return (
          <div key={d.ultrasound_id} className="card" style={{ padding: 14 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                flexWrap: "wrap",
              }}
            >
              <div>
                <div style={{ fontWeight: 700 }}>
                  {d.patient_name ?? "—"}{" "}
                  <span
                    style={{
                      fontWeight: 400,
                      fontSize: 12,
                      color: "var(--ink-muted)",
                    }}
                  >
                    {d.patient_code ?? ""}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
                  {d.ultrasound_type ?? "Siêu âm"}
                  {d.performed_by_name ? ` · ${d.performed_by_name}` : ""}
                  {d.room_name
                    ? ` · ${roomWithFloor(d.room_name, d.room_floor)}`
                    : ""}
                </div>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setOpenId(open ? null : d.ultrasound_id);
                  setErr(null);
                  const f = d.findings as { mo_ta?: string } | null;
                  setMota(f?.mo_ta ?? "");
                  setKetLuan(d.impression ?? "");
                }}
              >
                {open ? "Đóng" : "Nhập kết quả"}
              </button>
            </div>

            {/* ẢNH SIÊU ÂM CHƯA CÓ CHỖ LƯU. Nói thẳng thay vì để một ô ảnh
                trống — ô trống đọc thành "chưa chụp", còn sự thật là hệ thống
                chưa có kho tệp nào. */}
            <div
              style={{
                marginTop: 8,
                fontSize: 11,
                color: "var(--ink-muted)",
                display: "flex",
                alignItems: "center",
                gap: 5,
              }}
            >
              <ImageOff size={12} />
              Ảnh siêu âm: chưa có chỗ lưu trên hệ thống (đang lưu ngoài máy).
            </div>

            {open && (
              <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
                <textarea
                  value={mota}
                  onChange={(e) => setMota(e.target.value)}
                  rows={3}
                  placeholder="Mô tả hình ảnh…"
                />
                <textarea
                  value={ketLuan}
                  onChange={(e) => setKetLuan(e.target.value)}
                  rows={2}
                  placeholder="Kết luận…"
                />
                {err && (
                  <p role="alert" style={{ fontSize: 12, color: "var(--danger)" }}>
                    {err}
                  </p>
                )}
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="btn btn-primary"
                    disabled={busy}
                    onClick={() => void save(d)}
                  >
                    <Save size={14} /> Lưu kết quả
                  </button>
                  <span
                    style={{
                      fontSize: 11,
                      color: "var(--ink-muted)",
                      alignSelf: "center",
                    }}
                  >
                    Lưu xong vẫn sửa được. Bác sĩ ký ở phiếu khám — ký rồi thì
                    khoá.
                  </span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Tab 4: đã ký ──────────────────────────────────────────────────────────

function SignedTab({ groups }: { groups: SonoPatientGroup[] | null }) {
  if (groups === null) {
    return <div style={{ fontSize: 13, color: "var(--ink-muted)" }}>Đang tải…</div>;
  }
  if (groups.length === 0) {
    return (
      <div className="card" style={{ padding: 20, textAlign: "center" }}>
        <div style={{ fontWeight: 700 }}>Chưa có báo cáo nào được ký</div>
        <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>
          Bảy ngày gần nhất.
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {groups.map((g) => (
        <div
          key={g.clinic_patient_id ?? g.reports[0]?.ultrasound_id}
          className="card"
          style={{ padding: 14 }}
        >
          <div style={{ fontWeight: 700 }}>
            {g.patient_name ?? "—"}{" "}
            <span
              style={{ fontWeight: 400, fontSize: 12, color: "var(--ink-muted)" }}
            >
              {g.patient_code ?? ""}
              {g.birth_year ? ` · ${g.birth_year}` : ""} · {g.report_count} phiếu
            </span>
          </div>
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table>
              <thead>
                <tr>
                  <th>Loại</th>
                  <th>Kết luận</th>
                  <th>Bác sĩ ký</th>
                  <th>Lúc</th>
                </tr>
              </thead>
              <tbody>
                {g.reports.map((r) => (
                  <tr key={r.ultrasound_id}>
                    <td>{r.ultrasound_type ?? "—"}</td>
                    <td>{r.impression ?? "—"}</td>
                    <td>
                      <FileSignature size={11} /> {r.signed_by_name ?? "—"}
                    </td>
                    <td>
                      {r.signed_at
                        ? new Date(r.signed_at).toLocaleString("vi-VN", {
                            timeZone: "Asia/Ho_Chi_Minh",
                            day: "2-digit",
                            month: "2-digit",
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
        </div>
      ))}
    </div>
  );
}
