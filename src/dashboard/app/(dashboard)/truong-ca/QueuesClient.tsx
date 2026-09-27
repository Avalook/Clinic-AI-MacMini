"use client";

// HÀNG ĐỢI THEO TRẠM — XEM + ĐIỀU PHỐI TRÊN CÙNG MỘT TRANG (Tuyền 27/09/2026:
// "trang điều phối ca đang xấu quá, khó làm… muốn cùng 1 trang để theo dõi
// được tổng thể hơn").
//
// Mỗi phòng một thẻ; khách chờ QUÁ NGƯỠNG của phòng tô đỏ và đứng đầu. Bấm một
// khách → khung bên phải liệt kê từng chỉ định của khách với ô đổi phòng
// (`ChiDinhCuaBacSi` → `DoiPhong`): danh sách phòng làm được đúng dịch vụ ấy và
// số người chờ do MÁY CHỦ trả — màn không tự đoán phòng nào làm được gì.
// Mỗi phòng có nút mở TV riêng (`/display?phong=<mã phòng>` — cùng màn TV đã lọc danh tính).
//
// 28/09/2026 (Tuyền): KÉO khách thả sang phòng cùng chức năng (keo-tha.ts —
// phòng nhận được sáng lên, phòng khác mờ đi) và BẢNG "chờ quá lâu" mở ra khi
// bấm ô "Chờ quá ngưỡng". Bấm khách vẫn mở popup như cũ (điện thoại không kéo
// thả được — popup là lối chính trên màn cảm ứng).

import Link from "next/link";
import { Tv, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import Chip from "@/components/ui/Chip";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import ChiDinhCuaBacSi from "./ChiDinhCuaBacSi";
import type { DispatchPatient, DispatchRoom } from "./types";
import { LiveBadge, ReadFailed, tenPhong, useDispatchLive } from "./shared";
import { timDichDen, type DichDen } from "./keo-tha";

const quaNguong = (p: DispatchPatient) => p.wait_minutes > p.threshold_minutes;

export default function QueuesClient({
  initial,
}: {
  initial: { patients: DispatchPatient[]; rooms: DispatchRoom[]; ok: boolean };
}) {
  const live = useDispatchLive({ ...initial, alerts: [] });
  const [chon, setChon] = useState<string | null>(null);
  const khach = live.patients.find((p) => p.visit_id === chon) ?? null;
  const [moQuaLau, setMoQuaLau] = useState(false);
  // KÉO THẢ: `keo` = khách đang kéo (đích chưa đọc xong = "dang-doc").
  const [keo, setKeo] = useState<{ p: DispatchPatient; dich: DichDen | "dang-doc" } | null>(null);
  const [bao, setBao] = useState<{ ok: boolean; text: string } | null>(null);
  const keoId = useRef<string | null>(null);

  async function batDauKeo(p: DispatchPatient) {
    keoId.current = p.visit_id;
    setBao(null);
    setKeo({ p, dich: "dang-doc" });
    const d = await timDichDen(p);
    if (keoId.current !== p.visit_id) return; // đã thả / huỷ trước khi đọc xong
    if ("loi" in d) {
      setKeo(null);
      setBao({ ok: false, text: d.loi });
      return;
    }
    setKeo({ p, dich: d });
  }
  function huyKeo() {
    keoId.current = null;
    setKeo(null);
  }
  async function tha(roomId: string, tenPhongDen: string) {
    const k = keo;
    huyKeo();
    if (!k || k.dich === "dang-doc" || !k.dich.phong.has(roomId)) return;
    const kq = await k.dich.gui(roomId);
    setBao(
      kq.ok
        ? { ok: true, text: `Đã chuyển ${k.p.patient_name ?? "khách"} (${k.dich.tenDichVu}) sang ${tenPhongDen}.` }
        : { ok: false, text: kq.loi },
    );
    if (kq.ok) void live.lamMoi();
  }

  // Esc đóng hộp điều phối.
  useEffect(() => {
    if (!chon) return;
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setChon(null);
    };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [chon]);

  const soDo = live.patients.filter(quaNguong).length;
  const phongDay = live.rooms.filter((r) => r.state === "critical").length;
  const tongCho = live.rooms.reduce((s, r) => s + r.waiting, 0);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <StatRow>
          <StatCard label="Đang chờ" value={tongCho} tone="brand" />
          <StatCard
            label={moQuaLau ? "Chờ quá ngưỡng · đang mở" : "Chờ quá ngưỡng"}
            value={soDo}
            tone={soDo ? "danger" : "neutral"}
            onSelect={() => setMoQuaLau((m) => !m)}
            active={moQuaLau}
          />
          <StatCard label="Phòng quá tải" value={phongDay} tone={phongDay ? "warning" : "neutral"} />
        </StatRow>
        <LiveBadge seconds={live.staleSeconds} ok={live.ok} />
      </div>
      <ReadFailed ok={live.ok} />
      {bao ? (
        <p
          role={bao.ok ? "status" : "alert"}
          className={`rounded-control px-3 py-2 text-meta ${bao.ok ? "bg-success-bg text-success" : "bg-danger-bg text-danger"}`}
        >
          {bao.text}
        </p>
      ) : null}
      {moQuaLau ? <BangQuaLau ds={live.patients} onChon={setChon} /> : null}
      <p className="hidden text-meta text-ink-muted md:block">
        Kéo một khách thả vào phòng sáng lên để chuyển — hoặc bấm khách để chọn phòng.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {live.rooms.map((r) => (
            <ThePhong
              key={r.id}
              phong={r}
              ds={live.patients}
              chon={chon}
              onChon={setChon}
              keo={keo}
              onKeo={(p) => void batDauKeo(p)}
              onHuyKeo={huyKeo}
              onTha={(id, ten) => void tha(id, ten)}
            />
          ))}
      </div>

      {/* POPUP giữa màn (Tuyền 27/09: "popup thôi, không cần mở hẳn sang bên"):
          lớp phủ mờ, bấm ra ngoài / Esc / ✕ là đóng; lưới phòng giữ nguyên. */}
      {khach ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Điều phối ${khach.patient_name ?? "khách"}`}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <div aria-hidden className="absolute inset-0 bg-ink/40" onClick={() => setChon(null)} />
          <div className="relative max-h-[85dvh] w-full max-w-md overflow-y-auto rounded-2xl border border-line bg-surface p-4 shadow-panel">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-emph font-semibold text-ink">{khach.patient_name ?? "—"}</p>
                <p className="text-meta text-ink-muted">
                  {khach.patient_code ?? ""}
                  {khach.doctor_name ? ` · ${khach.doctor_name}` : ""}
                </p>
              </div>
              <button
                type="button"
                aria-label="Đóng"
                onClick={() => setChon(null)}
                className="rounded-control p-1.5 text-ink-muted hover:bg-surface-sunken"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <p className={`mt-2 text-meta ${quaNguong(khach) ? "font-semibold text-danger" : "text-ink-soft"}`}>
              {khach.current_node_name ?? khach.current_node_code ?? "—"}
              {khach.room_name ? ` · ${tenPhong(khach.room_name)}` : ""} — chờ {khach.wait_minutes}′
              {quaNguong(khach) ? ` (ngưỡng ${khach.threshold_minutes}′)` : ""}
            </p>
            <p className="mt-3 text-label font-semibold uppercase text-ink-muted">
              Chuyển sang phòng làm được việc này
            </p>
            <ChiDinhCuaBacSi key={khach.visit_id} visitId={khach.visit_id} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ThePhong({
  phong: r,
  ds,
  chon,
  onChon,
  keo,
  onKeo,
  onHuyKeo,
  onTha,
}: {
  phong: DispatchRoom;
  ds: DispatchPatient[];
  chon: string | null;
  onChon: (id: string) => void;
  keo: { p: DispatchPatient; dich: DichDen | "dang-doc" } | null;
  onKeo: (p: DispatchPatient) => void;
  onHuyKeo: () => void;
  onTha: (roomId: string, ten: string) => void;
}) {
  const [treo, setTreo] = useState(false);
  const o = useMemo(
    () =>
      ds
        .filter((p) => p.room_code === r.code)
        .sort((a, b) => Number(quaNguong(b)) - Number(quaNguong(a)) || b.wait_minutes - a.wait_minutes),
    [ds, r.code],
  );
  const tone = r.state === "critical" ? "danger" : r.state === "warning" ? "warning" : "success";
  // Khi đang kéo: phòng nhận được sáng viền, phòng khác mờ; phòng gốc giữ nguyên.
  const dich = keo && keo.dich !== "dang-doc" ? keo.dich : null;
  const nhanDuoc = dich?.phong.has(r.id) ?? false;
  const laGoc = keo?.p.room_code === r.code;
  const trangThaiKeo = !keo
    ? ""
    : nhanDuoc
      ? treo
        ? "ring-2 ring-brand-600 bg-brand-50"
        : "ring-2 ring-brand-300"
      : laGoc || keo.dich === "dang-doc"
        ? ""
        : "opacity-40";
  return (
    <section
      onDragOver={(e) => {
        if (!nhanDuoc) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (!treo) setTreo(true);
      }}
      onDragLeave={() => setTreo(false)}
      onDrop={(e) => {
        e.preventDefault();
        setTreo(false);
        onTha(r.id, tenPhong(r.name));
      }}
      className={`rounded-card border bg-surface shadow-card transition ${
        r.state === "critical" ? "border-danger/40" : "border-line"
      } ${trangThaiKeo}`}
    >
      <header className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div className="min-w-0">
          <h2 className="truncate text-body font-semibold text-ink">{tenPhong(r.name)}</h2>
          <p className="text-label text-ink-muted">
            {o.length} khách · {r.serving} đang làm
            {r.accepting ? "" : " · tạm ngưng nhận"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Chip tone={tone}>{r.state === "critical" ? "Quá tải" : r.state === "warning" ? "Đông" : "Ổn"}</Chip>
          <Link
            href={`/display?phong=${encodeURIComponent(r.code)}&ten=${encodeURIComponent(tenPhong(r.name))}`}
            target="_blank"
            title="Mở TV của phòng này"
            aria-label={`Mở TV ${tenPhong(r.name)}`}
            className="rounded-control p-1.5 text-ink-muted hover:bg-surface-sunken hover:text-ink"
          >
            <Tv className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </header>
      {o.length === 0 ? (
        <p className="px-3 py-3 text-meta text-ink-faint">Không có ai đang chờ</p>
      ) : (
        <ul>
          {o.map((p) => {
            const do_ = quaNguong(p);
            const dang = p.visit_id === chon;
            return (
              <li key={p.visit_id} className="border-b border-line last:border-b-0">
                <button
                  type="button"
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.effectAllowed = "move";
                    e.dataTransfer.setData("text/plain", p.visit_id);
                    onKeo(p);
                  }}
                  onDragEnd={onHuyKeo}
                  onClick={() => onChon(p.visit_id)}
                  aria-current={dang ? "true" : undefined}
                  title={do_ ? "Chờ quá ngưỡng — kéo sang phòng khác hoặc bấm để chuyển" : "Kéo sang phòng khác hoặc bấm để chuyển"}
                  className={`flex w-full cursor-grab items-center gap-2 border-l-3 px-3 py-2 text-left text-meta active:cursor-grabbing ${
                    dang
                      ? "border-l-brand-500 bg-surface-selected"
                      : do_
                        ? "border-l-danger bg-danger-bg/50 hover:bg-danger-bg"
                        : "border-l-transparent hover:bg-surface-sunken"
                  }`}
                >
                  <span className="w-8 shrink-0 font-semibold tabular-nums text-ink-soft">
                    {p.so_tiep_don ?? p.queue_number ?? ""}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-ink">{p.patient_name ?? "—"}</span>
                  <span className={`shrink-0 tabular-nums ${do_ ? "font-semibold text-danger" : "text-ink-muted"}`}>
                    {p.wait_minutes}′
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** BẢNG CHỜ QUÁ LÂU (Tuyền 28/09/2026) — mọi khách vượt ngưỡng, lâu nhất trước,
 *  kèm đang ở đâu; bấm một dòng mở cùng popup chuyển phòng. Chỉ đọc lại
 *  `live.patients`, không hỏi thêm máy chủ. */
function BangQuaLau({
  ds,
  onChon,
}: {
  ds: DispatchPatient[];
  onChon: (id: string) => void;
}) {
  const o = ds.filter(quaNguong).sort((a, b) => b.wait_minutes - a.wait_minutes);
  return (
    <section aria-label="Khách chờ quá lâu" className="rounded-card border border-line bg-surface p-3 shadow-card">
      <h2 className="px-1 text-emph font-semibold text-ink">
        Khách chờ quá lâu <span className="font-normal text-ink-muted">· {o.length}</span>
      </h2>
      {o.length === 0 ? (
        <p className="px-1 py-2 text-meta text-ink-muted">Không có khách nào chờ quá ngưỡng.</p>
      ) : (
        <div className="mt-2 max-h-80 overflow-auto">
          <table className="w-full min-w-120 border-collapse text-body">
            <thead className="sticky top-0 bg-surface">
              <tr className="text-left text-meta text-ink-faint">
                <th className="px-2 py-1.5 font-medium">Số</th>
                <th className="px-2 py-1.5 font-medium">Khách</th>
                <th className="px-2 py-1.5 font-medium">Đang ở</th>
                <th className="px-2 py-1.5 text-right font-medium">Chờ</th>
              </tr>
            </thead>
            <tbody>
              {o.map((p) => (
                <tr key={p.visit_id} className="hover:bg-surface-sunken">
                  <td className="px-2 py-1.5 tabular-nums text-ink-soft">{p.so_tiep_don ?? p.queue_number ?? ""}</td>
                  <td className="px-2 py-1.5">
                    <button
                      type="button"
                      onClick={() => onChon(p.visit_id)}
                      className="text-left font-medium text-ink hover:text-brand-700 hover:underline"
                    >
                      {p.patient_name ?? "—"}
                    </button>
                  </td>
                  <td className="px-2 py-1.5 text-ink-muted">
                    {p.current_node_name ?? p.current_node_code ?? "—"}
                    {p.room_name ? ` · ${tenPhong(p.room_name)}` : ""}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <span className="font-semibold text-danger">{p.wait_minutes}′</span>
                    <span className="text-meta text-ink-faint"> / {p.threshold_minutes}′</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
