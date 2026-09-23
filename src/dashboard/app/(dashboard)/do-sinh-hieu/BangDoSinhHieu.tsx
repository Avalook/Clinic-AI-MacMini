"use client";

// Danh sách chờ đo + ô điền sinh hiệu. Lưu xong TỰ CHUYỂN sang người kế tiếp:
// người đo làm việc theo hàng, không phải theo từng hồ sơ, và bắt họ bấm lại vào
// danh sách sau mỗi người là thêm một thao tác thừa cho mỗi khách trong ngày.

import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";

import XemLuot from "../_lam-viec/XemLuot";

interface SinhHieu {
  tam_thu: number | null;
  tam_truong: number | null;
  mach: number | null;
  nhiet_do: number | null;
  can_nang: number | null;
  chieu_cao: number | null;
  nhip_tho: number | null;
  spo2: number | null;
  bmi: number | null;
  muc_do_dau: number | null;
  luc: string | null;
  nguoi_do: string | null;
}

interface Luot {
  visit_id: string;
  ma_bn: string;
  ten: string;
  bac_si: string | null;
  check_in_luc: string | null;
  /** `pending` · `in_progress` · `recorded` — trạng thái THẬT, máy chủ giữ. */
  sinh_hieu_trang_thai: string;
  /** Lúc bấm [Bắt đầu] đo. Trống nếu lưu thẳng mà không ai bấm Bắt đầu. */
  bat_dau_do_luc: string | null;
  bat_dau_do_boi: string | null;
  /** Số tiếp đón chung của quầy — số điều dưỡng đọc khi gọi. */
  so_tiep_don: number | null;
  sinh_hieu: SinhHieu | null;
}

/** Ô nhập — khoá gửi backend, nhãn, đơn vị, khoá đọc lại từ `sinh_hieu`. */
const O: readonly {
  gui: string;
  nhan: string;
  don_vi: string;
  doc: keyof SinhHieu;
  batBuoc?: boolean;
}[] = [
  { gui: "systolic", nhan: "Huyết áp tâm thu", don_vi: "mmHg", doc: "tam_thu", batBuoc: true },
  { gui: "diastolic", nhan: "Huyết áp tâm trương", don_vi: "mmHg", doc: "tam_truong", batBuoc: true },
  { gui: "pulse", nhan: "Mạch", don_vi: "lần/phút", doc: "mach" },
  { gui: "temperature", nhan: "Nhiệt độ", don_vi: "°C", doc: "nhiet_do" },
  { gui: "respiratory_rate", nhan: "Nhịp thở", don_vi: "lần/phút", doc: "nhip_tho" },
  { gui: "spo2", nhan: "SpO₂", don_vi: "%", doc: "spo2" },
  { gui: "weight_kg", nhan: "Cân nặng", don_vi: "kg", doc: "can_nang" },
  { gui: "height_cm", nhan: "Chiều cao", don_vi: "cm", doc: "chieu_cao" },
  { gui: "pain_score", nhan: "Mức độ đau", don_vi: "0–10", doc: "muc_do_dau" },
];

/** Khoá gửi lại cho MỘT lần bấm Lưu. Cùng cách LuotKhamBoard làm — không dùng
 *  crypto.randomUUID vì nó chỉ có trong secure context. Đặt NGOÀI component để
 *  không bị coi là tính toán trong lúc vẽ. */
function khoaGuiLai(): string {
  return `sh-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function gio(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

async function docBang(): Promise<{ luot: Luot[] } | { loi: string }> {
  try {
    const r = await fetch("/api/luot-kham", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as { luot?: Luot[]; message?: string } | null;
    if (!r.ok) return { loi: d?.message ?? "Không đọc được danh sách khách." };
    return { luot: d?.luot ?? [] };
  } catch {
    return { loi: "Mất kết nối tới máy chủ." };
  }
}

export default function BangDoSinhHieu() {
  const [luot, setLuot] = useState<Luot[] | null>(null);
  const [chon, setChon] = useState<string | null>(null);
  const [xemLuot, setXemLuot] = useState<string | null>(null);
  const [gia, setGia] = useState<Record<string, string>>({});
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dangLuu, setDangLuu] = useState(false);
  const [dangBatDau, setDangBatDau] = useState(false);

  const nhan = useCallback((kq: { luot: Luot[] } | { loi: string }) => {
    if ("loi" in kq) {
      setLoi(kq.loi);
      return;
    }
    setLoi(null);
    setLuot(kq.luot);
  }, []);

  useEffect(() => {
    let huy = false;
    void docBang().then((kq) => {
      if (!huy) nhan(kq);
    });
    // Làm mới mỗi 20 giây: khách check-in liên tục ở quầy, người đo không nên
    // phải tải lại trang mới thấy người vừa đến.
    const t = setInterval(() => {
      void docBang().then((kq) => {
        if (!huy) nhan(kq);
      });
    }, 20000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [nhan]);

  // THỨ TỰ = GIỜ CHECK-IN, người đến trước lên trước (Tuyền 15/09: "hàng chờ =
  // giờ check-in"). Chưa đo đứng trên, đã đo xuống dưới.
  const { choDo, dangDo, daDo } = useMemo(() => {
    const ds = [...(luot ?? [])].sort((a, b) =>
      (a.check_in_luc ?? "").localeCompare(b.check_in_luc ?? ""),
    );
    // "ĐANG ĐO" ĐỌC TỪ TRẠNG THÁI THẬT (23/09/2026), không suy từ giờ gọi.
    // Bản trước lấy `goi_do_luc` làm "đang đo" — tức "đã gọi" bị đọc thành
    // "đã bắt đầu đo", hai chuyện khác nhau. Giờ máy chủ giữ `in_progress`.
    const dangDoThat = (l: Luot) =>
      !l.sinh_hieu && l.sinh_hieu_trang_thai === "in_progress";
    return {
      choDo: ds.filter((l) => !l.sinh_hieu && !dangDoThat(l)),
      dangDo: ds.filter(dangDoThat),
      daDo: ds.filter((l) => l.sinh_hieu),
    };
  }, [luot]);

  const dangChon = (luot ?? []).find((l) => l.visit_id === chon) ?? null;

  const moKhach = (l: Luot) => {
    setChon(l.visit_id);
    // Màn hẹp: khung nhập nằm DƯỚI danh sách chờ (có thể vài chục khách) —
    // chọn xong phải cuộn tay rất xa mới tới ô nhập (smoke 18/09, 375/768).
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      requestAnimationFrame(() =>
        document.getElementById("khung-do-sinh-hieu")?.scrollIntoView({ block: "start" }),
      );
    }
    setXong(null);
    setLoi(null);
    const cu: Record<string, string> = {};
    for (const o of O) {
      const v = l.sinh_hieu?.[o.doc];
      cu[o.gui] = v === null || v === undefined ? "" : String(v);
    }
    setGia(cu);
  };

  // [BẮT ĐẦU] ĐO — thay cho [Gọi vào đo] (Tuyền chốt 23/09/2026: `Gọi vào →
  // Bắt đầu` là hai bước cho một việc). Máy chủ chuyển `pending → in_progress`
  // và ghi ai bắt đầu, lúc nào. Bấm lại chính mình thì không sao; người khác đã
  // bắt đầu thì máy chủ từ chối kèm tên — câu ấy hiện nguyên văn ở đây.
  //
  // Đây là mốc đo THỜI GIAN CHỜ, không phải cửa khoá: ô nhập và nút [Lưu] vẫn
  // dùng được khi chưa ai bấm [Bắt đầu].
  const batDau = async () => {
    if (!dangChon) return;
    setDangBatDau(true);
    setLoi(null);
    setXong(null);
    try {
      const r = await fetch("/api/luot-kham", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": khoaGuiLai() },
        body: JSON.stringify({ thao_tac: "bat-dau-do", id: dangChon.visit_id, du_lieu: {} }),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) {
        setLoi(d?.message ?? d?.error ?? "Không bắt đầu đo được.");
        return;
      }
      setXong(`Bắt đầu đo cho ${dangChon.ten}.`);
      nhan(await docBang());
    } catch {
      setLoi("Mất kết nối — CHƯA bắt đầu đo.");
    } finally {
      setDangBatDau(false);
    }
  };

  const luu = async () => {
    if (!dangChon) return;
    setDangLuu(true);
    setLoi(null);
    try {
      const du_lieu: Record<string, string> = {};
      for (const o of O) if (gia[o.gui]?.trim()) du_lieu[o.gui] = gia[o.gui].trim();
      const r = await fetch("/api/luot-kham", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": khoaGuiLai(),
        },
        body: JSON.stringify({ thao_tac: "sinh-hieu", id: dangChon.visit_id, du_lieu }),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) {
        setLoi(d?.message ?? d?.error ?? "Không lưu được sinh hiệu.");
        return;
      }
      const ten = dangChon.ten;
      const kq = await docBang();
      nhan(kq);
      setXong(`Đã lưu sinh hiệu cho ${ten}.`);
      // Sang NGƯỜI KẾ TIẾP còn chờ đo.
      if ("luot" in kq) {
        const ke = [...kq.luot]
          .sort((a, b) => (a.check_in_luc ?? "").localeCompare(b.check_in_luc ?? ""))
          .find((l) => !l.sinh_hieu);
        if (ke) moKhach(ke);
        else setChon(null);
      }
    } catch {
      setLoi("Mất kết nối — sinh hiệu CHƯA được lưu.");
    } finally {
      setDangLuu(false);
    }
  };

  if (luot === null) {
    return loi ? (
      <p role="alert" className="text-body text-danger">{loi}</p>
    ) : (
      <p className="text-body text-ink-muted">Đang tải…</p>
    );
  }

  const MotDong = ({ l, stt }: { l: Luot; stt: number }) => (
    <li>
      <button
        type="button"
        onClick={() => moKhach(l)}
        className={`flex w-full items-center gap-3 border-b border-line px-3 py-2.5 text-left hover:bg-brand-50 ${
          chon === l.visit_id ? "bg-brand-50" : ""
        }`}
      >
        <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-muted text-sm font-semibold tabular-nums text-ink">
          {l.so_tiep_don ?? stt}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold text-ink">{l.ten}</span>
          <span className="block text-meta text-ink-muted">
            {l.ma_bn} · check-in {gio(l.check_in_luc)}
            {l.bac_si ? ` · ${l.bac_si}` : ""}
          </span>
        </span>
        {l.sinh_hieu ? (
          <span className="shrink-0 rounded-chip bg-success-bg px-2 py-0.5 text-meta text-success">
            Đã đo
          </span>
        ) : l.sinh_hieu_trang_thai === "in_progress" ? (
          <span className="shrink-0 rounded-chip bg-brand-50 px-2 py-0.5 text-meta text-brand-700">
            Đang đo {gio(l.bat_dau_do_luc)}
          </span>
        ) : (
          <span className="shrink-0 rounded-chip bg-warning-bg px-2 py-0.5 text-meta text-warning">
            Chờ đo
          </span>
        )}
      </button>
    </li>
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
        {dangDo.length > 0 ? (
          <>
            <p className="border-b border-line bg-surface-muted px-3 py-2 text-sm font-semibold text-ink">
              Đang đo ({dangDo.length})
            </p>
            <ul>
              {dangDo.map((l, i) => (
                <MotDong key={l.visit_id} l={l} stt={i + 1} />
              ))}
            </ul>
          </>
        ) : null}
        <p className="border-y border-line bg-surface-muted px-3 py-2 text-sm font-semibold text-ink">
          Chờ đo ({choDo.length})
        </p>
        <ul>
          {choDo.length === 0 ? (
            <li className="px-3 py-4 text-meta text-ink-muted">Không còn ai chờ đo.</li>
          ) : (
            choDo.map((l, i) => <MotDong key={l.visit_id} l={l} stt={i + 1} />)
          )}
        </ul>
        {daDo.length > 0 ? (
          <>
            <p className="border-y border-line bg-surface-muted px-3 py-2 text-sm font-semibold text-ink">
              Đã đo hôm nay ({daDo.length})
            </p>
            <ul>
              {daDo.map((l, i) => (
                <MotDong key={l.visit_id} l={l} stt={i + 1} />
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <section
        id="khung-do-sinh-hieu"
        className="rounded-card border border-line bg-surface p-4 shadow-card"
      >
        {!dangChon ? (
          <p className="py-10 text-center text-body text-ink-muted">
            Chọn một khách bên trái để điền sinh hiệu.
          </p>
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
              <p className="text-lg font-semibold text-ink">
                {dangChon.so_tiep_don != null ? `Số ${dangChon.so_tiep_don} · ` : ""}
                {dangChon.ten}
              </p>
              <p className="text-meta text-ink-muted">
                {dangChon.ma_bn} · check-in {gio(dangChon.check_in_luc)}
                {dangChon.sinh_hieu?.nguoi_do
                  ? ` · lần đo trước: ${dangChon.sinh_hieu.nguoi_do} lúc ${gio(dangChon.sinh_hieu.luc)}`
                  : ""}
                {dangChon.bat_dau_do_luc && !dangChon.sinh_hieu
                  ? ` · bắt đầu đo lúc ${gio(dangChon.bat_dau_do_luc)}${dangChon.bat_dau_do_boi ? ` (${dangChon.bat_dau_do_boi})` : ""}`
                  : ""}
              </p>
              {/* Đã đo: xem lại mọi lần đo (người đo, giờ) và lượt trước. */}
              {dangChon.sinh_hieu ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="mt-1 -ml-3"
                  onClick={() => setXemLuot(dangChon.visit_id)}
                >
                  Xem các lần đo &amp; lượt trước
                </Button>
              ) : null}
              {xemLuot ? <XemLuot visitId={xemLuot} onDong={() => setXemLuot(null)} /> : null}
              </div>
              {/* Chỉ hiện khi CHƯA ai bắt đầu. Đang đo rồi thì không bày nút —
                  bấm lại cũng chỉ nhận "đã bắt đầu", không có việc gì mới. */}
              {!dangChon.sinh_hieu && dangChon.sinh_hieu_trang_thai === "pending" ? (
                <Button
                  size="md"
                  variant="primary"
                  onClick={() => void batDau()}
                  disabled={dangBatDau}
                >
                  {dangBatDau ? "Đang bắt đầu…" : "Bắt đầu"}
                </Button>
              ) : null}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {O.map((o) => (
                <label key={o.gui} className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">
                    {o.nhan}
                    {o.batBuoc ? <span className="text-danger"> *</span> : null}
                    {o.don_vi ? <span className="ml-1 text-meta text-ink-muted">({o.don_vi})</span> : null}
                  </span>
                  <input
                    inputMode="decimal"
                    value={gia[o.gui] ?? ""}
                    onChange={(e) => setGia((g) => ({ ...g, [o.gui]: e.target.value }))}
                    className="min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
                  />
                </label>
              ))}
              {/* BMI KHÔNG có ô nhập (S0-3, 18/09/2026): máy chủ tự tính từ cân
                  nặng và chiều cao khi lưu, số gõ tay trước đây từng thắng số
                  tính. Ở đây chỉ hiện lại con số đã lưu. */}
              <div className="block">
                <span className="mb-1 block text-sm font-medium text-ink">
                  BMI <span className="ml-1 text-meta text-ink-muted">(tự tính từ cân nặng, chiều cao khi lưu)</span>
                </span>
                <p className="flex min-h-10 items-center rounded-control border border-line bg-surface-sunken px-3 text-body text-ink-soft">
                  {dangChon.sinh_hieu?.bmi ?? "—"}
                </p>
              </div>
            </div>
            {/* Thông báo nằm DƯỚI ô nhập, cạnh nút Lưu (17/09/2026): đặt trên đầu
                thì bấm [Bắt đầu] xong cả khối ô nhập tụt xuống, bấm lệch ô. */}
            <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
              {loi ? (
                <p role="alert" className="mr-auto rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
                  {loi}
                </p>
              ) : xong ? (
                <p role="status" className="mr-auto rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">
                  {xong}
                </p>
              ) : null}
              <button
                type="button"
                onClick={luu}
                disabled={dangLuu}
                className="inline-flex min-h-10 items-center rounded-control bg-brand-600 px-5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {dangLuu ? "Đang lưu…" : "Lưu sinh hiệu"}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
