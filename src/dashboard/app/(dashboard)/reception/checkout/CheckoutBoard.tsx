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
import { getSupabaseBrowser } from "../../../../lib/supabase-browser";
import ChiTietLuot from "./ChiTietLuot";

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
  const [dangChon, setDangChon] = useState<string | null>(null);
  const [tab, setTab] = useState<"tat_ca" | "san_sang" | "bi_chan">("tat_ca");
  const [timKiem, setTimKiem] = useState("");
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

  // ĐỔI Ở ĐÂU THÌ HIỆN NGAY Ở ĐÂY — nghe realtime, không đếm giây.
  //
  // Bản trước poll mỗi 5 giây. Hai cái sai:
  //
  //   1. Lễ tân thấy chậm tới 5 giây sau khi bác sĩ khám xong hay thu ngân thu
  //      tiền. Khi bệnh nhân đang đứng ở quầy thì 5 giây là lâu, và lễ tân sẽ
  //      bấm F5 — tức là poll rồi vẫn phải làm tay.
  //
  //   2. Nó gõ vào server 12 lần mỗi phút cho MỖI tab đang mở, kể cả lúc phòng
  //      khám không có ai. Nhân với số máy ở quầy.
  //
  // Realtime của Supabase đã publish sẵn đúng ba bảng quyết định danh sách này
  // (20260803000004): `visit` (đóng lượt), `work_item` (bước còn dở),
  // `payment` (đã thu chưa). Đăng ký thẳng và tải lại khi có thay đổi thật.
  //
  // KHÔNG dựa vào RealtimeRefresher ở layout: nó gọi router.refresh(), tức là
  // vẽ lại server component — mà `rows` ở đây là state của client, khởi tạo
  // MỘT LẦN từ prop `initial`. Server có dữ liệu mới cũng không chảy vào được.
  useEffect(() => {
    const supabase = getSupabaseBrowser();
    let timer: ReturnType<typeof setTimeout> | null = null;
    // Gộp một chuỗi thay đổi của cùng một thao tác (đóng lượt đụng vài bảng)
    // thành một lần tải lại. Cùng nhịp với RealtimeRefresher.
    const bump = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => void reload(), 250);
    };

    let channel = supabase.channel("reception-checkout");
    for (const table of ["visit", "work_item", "payment"]) {
      channel = channel.on(
        "postgres_changes",
        { event: "*", schema: "public", table },
        bump,
      );
    }
    channel.subscribe();

    // Lưới an toàn cho lúc websocket rớt — không phải đường đồng bộ chính, nên
    // thưa. 60 giây, cùng nhịp với RealtimeRefresher.
    const safety = setInterval(reload, 60_000);

    return () => {
      if (timer) clearTimeout(timer);
      clearInterval(safety);
      void supabase.removeChannel(channel);
    };
  }, [reload]);

  function flash(m: string) {
    setToast(m);
    setTimeout(() => setToast(null), 3500);
  }

  async function close(row: CheckoutRow, khamDo = false) {
    const needReason = khamDo || row.blockers.length > 0;
    if (needReason && !reason.trim()) return;
    setBusy(true);
    const res = await fetch("/api/reception/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visit_id: row.visit_id,
        override_reason: khamDo ? null : needReason ? reason.trim() : null,
        incomplete: khamDo,
        incomplete_reason: khamDo ? reason.trim() : null,
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
        : khamDo
          ? "✓ Đã đóng — đánh dấu khám dở, CSKH sẽ gọi lại"
          : needReason
            ? "✓ Đã đóng lượt (ngoại lệ, đã ghi lý do)"
            : "✓ Đã đóng lượt khám",
    );
    setDangChon(null);
    setReason("");
    await reload();
    router.refresh();
  }

  const pending = rows.filter((r) => !r.already_closed);
  const done = rows.filter((r) => r.already_closed);

  const needle = timKiem.trim().toLocaleLowerCase("vi-VN");
  const hienThi = pending
    .filter((r) => {
      if (tab === "san_sang" && !r.can_close) return false;
      if (tab === "bi_chan" && r.can_close) return false;
      if (!needle) return true;
      return [r.patient_name, r.patient_code]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("vi-VN")
        .includes(needle);
    })
    .sort((a, b) => (a.checked_in_at ?? "").localeCompare(b.checked_in_at ?? ""));

  const chon =
    hienThi.find((r) => r.visit_id === dangChon) ?? hienThi[0] ?? null;

  const TABS = [
    { key: "tat_ca" as const, nhan: `Tất cả (${pending.length})` },
    {
      key: "san_sang" as const,
      nhan: `Đủ điều kiện (${pending.filter((r) => r.can_close).length})`,
    },
    {
      key: "bi_chan" as const,
      nhan: `Bị chặn (${pending.filter((r) => !r.can_close).length})`,
    },
  ];

  return (
    <div className="space-y-3">
      {!live && (
        <div
          role="alert"
          className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger"
        >
          Không đọc được danh sách check-out. Danh sách bên dưới có thể đã cũ —
          tải lại trang.
        </div>
      )}

      {toast && (
        <div className="rounded-card border border-line bg-surface px-4 py-2.5 text-sm text-ink shadow-card">
          {toast}
        </div>
      )}

      {pending.length === 0 ? (
        <div className="rounded-card border border-line bg-surface px-4 py-10 text-center">
          <p className="font-medium text-ink">Không còn lượt nào cần đóng</p>
          <p className="mt-1 text-sm text-ink-muted">
            {done.length > 0
              ? `Đã đóng ${done.length} lượt hôm nay.`
              : "Hôm nay chưa có lượt khám nào."}
          </p>
        </div>
      ) : (
        <div className="grid min-w-0 items-start gap-3 xl:grid-cols-[minmax(260px,0.85fr)_minmax(0,2.5fr)]">
          {/* ── Cột trái: danh sách ────────────────────────────────────── */}
          <section
            aria-label="Danh sách lượt khám"
            className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
          >
            <div className="border-b border-line p-3">
              <h2 className="text-sm font-semibold text-ink">
                Danh sách lượt khám
              </h2>
              <div className="mt-3 flex border-b border-line text-xs">
                {TABS.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setTab(t.key)}
                    aria-pressed={tab === t.key}
                    className={`shrink-0 border-b-2 px-2.5 py-2 font-medium transition-colors ${
                      tab === t.key
                        ? "border-brand-600 text-brand-700"
                        : "border-transparent text-ink-muted hover:text-ink"
                    }`}
                  >
                    {t.nhan}
                  </button>
                ))}
              </div>
              <input
                type="search"
                value={timKiem}
                onChange={(e) => setTimKiem(e.target.value)}
                placeholder="Tìm tên hoặc mã BN"
                className="mt-3 h-9 w-full rounded-control border border-line bg-surface px-3 text-xs text-ink outline-none focus:border-brand-500"
              />
            </div>

            <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto">
              {hienThi.length === 0 ? (
                <li className="px-4 py-8 text-center text-sm text-ink-muted">
                  Không có lượt nào trong nhóm này.
                </li>
              ) : (
                hienThi.map((r) => {
                  const active = chon?.visit_id === r.visit_id;
                  return (
                    <li key={r.visit_id}>
                      <button
                        type="button"
                        onClick={() => setDangChon(r.visit_id)}
                        aria-pressed={active}
                        className={`w-full px-3 py-3 text-left transition-colors ${
                          active
                            ? "border-l-3 border-brand-600 bg-surface-selected pl-[9px]"
                            : "hover:bg-surface-sunken"
                        }`}
                      >
                        <span className="flex items-start justify-between gap-2">
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-semibold text-ink">
                              {r.patient_name ?? "Chưa rõ tên"}
                            </span>
                            <span className="block truncate text-label text-ink-muted">
                              {r.patient_code ?? "—"}
                            </span>
                          </span>
                          <span className="shrink-0 text-label tabular-nums text-ink-muted">
                            {r.checked_in_at
                              ? new Date(r.checked_in_at).toLocaleTimeString(
                                  "vi-VN",
                                  { hour: "2-digit", minute: "2-digit" },
                                )
                              : "—"}
                          </span>
                        </span>
                        <span
                          className={`mt-1.5 inline-flex rounded-chip px-2 py-0.5 text-label font-semibold ${
                            r.can_close
                              ? "bg-success-bg text-success"
                              : "bg-warning-bg text-warning"
                          }`}
                        >
                          {r.can_close
                            ? "Đủ điều kiện đóng"
                            : `Còn ${r.blockers.length} việc`}
                        </span>
                      </button>
                    </li>
                  );
                })
              )}
            </ul>
          </section>

          {/* ── Cột giữa + phải ─────────────────────────────────────────── */}
          {chon ? (
            <div className="min-w-0 space-y-3">
              <ChiTietLuot key={chon.visit_id} visitId={chon.visit_id} />

              <div className="rounded-card border border-line bg-surface p-4 shadow-card">
                {chon.blockers.length > 0 && (
                  <label className="block text-xs text-ink-muted">
                    Lý do đóng khi còn việc chưa xong (bắt buộc)
                    <textarea
                      rows={2}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Vd: khách xin về, đã hẹn quay lại lấy kết quả"
                      className="mt-1 w-full resize-none rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand-500"
                    />
                  </label>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={
                      busy || (chon.blockers.length > 0 && !reason.trim())
                    }
                    onClick={() => void close(chon)}
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-control bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
                  >
                    {busy ? "Đang lưu…" : "Xác nhận đóng lượt khám"}
                  </button>
                  <button
                    type="button"
                    disabled={busy || !reason.trim()}
                    onClick={() => void close(chon, true)}
                    title="Khách về giữa chừng — vẫn đóng, nhưng đánh dấu là khám dở để CSKH gọi lại"
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-control border border-warning px-4 py-2 text-sm font-semibold text-warning hover:bg-warning-bg disabled:cursor-not-allowed disabled:border-line disabled:text-ink-faint"
                  >
                    Đóng — khách về giữa chừng
                  </button>
                </div>
                {chon.blockers.length === 0 && (
                  <p className="mt-2 text-xs text-ink-muted">
                    Nút &ldquo;khách về giữa chừng&rdquo; cần một lý do — đó là
                    thứ CSKH đọc để biết phải gọi lại nói gì.
                  </p>
                )}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
