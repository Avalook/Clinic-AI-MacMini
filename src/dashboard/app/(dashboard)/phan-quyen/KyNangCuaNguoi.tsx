"use client";

// KỸ NĂNG CỦA MỘT NGƯỜI (Tuyền chốt 28/09/2026, bản "D"): toàn bộ kỹ năng xếp
// dọc theo nhóm, mỗi dòng một ô tick + ngay cạnh là màn / phòng kỹ năng ấy mở.
// Tick = máy chủ bật đúng các lego của kỹ năng (ky_nang_service) — màn này
// không tự suy lego nào. Dưới cùng: lịch hôm nay (đứng đâu thì dùng được gì).

import Link from "next/link";
import { useEffect, useState } from "react";

export interface KyNang {
  ma: string;
  ten: string;
  nhom: string;
  man: string[];
  phong: string[];
  moi_phong: boolean;
  so_nguoi: number;
}

interface CuaNguoi {
  ky_nang: string[];
  hom_nay: { shift: string | null; vi_tri: string | null; phong: string | null }[];
}

const CA: Record<string, string> = { SANG: "Sáng", CHIEU: "Chiều", TOI: "Tối", CA_NGAY: "Cả ngày" };

export default function KyNangCuaNguoi({
  staffId,
  danhMuc,
  nhanSu,
  onDoi,
  onLoi,
}: {
  staffId: string;
  danhMuc: KyNang[];
  /** Để chép kỹ năng từ người khác. */
  nhanSu: { id: string; ten: string }[];
  /** Gọi sau mỗi lần tick — để cột trái và khung ngoại lệ đọc lại. */
  onDoi: () => void;
  onLoi: (loi: string | null) => void;
}) {
  const [cua, setCua] = useState<CuaNguoi | null>(null);
  const [dang, setDang] = useState<string | null>(null);
  const [lan, setLan] = useState(0);
  const [chepTu, setChepTu] = useState("");

  useEffect(() => {
    let huy = false;
    void fetch(`/api/phan-quyen?ky-nang-cua=${staffId}`, { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<CuaNguoi>) : null))
      .then((d) => {
        if (huy) return;
        if (d) setCua(d);
        else onLoi("Không đọc được kỹ năng của người này.");
      });
    return () => {
      huy = true;
    };
  }, [staffId, lan, onLoi]);

  async function gui(thaoTac: string, duLieu: Record<string, unknown>, khoa: string) {
    setDang(khoa);
    onLoi(null);
    const r = await fetch("/api/phan-quyen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thao_tac: thaoTac, staff_id: staffId, du_lieu: duLieu }),
    });
    setDang(null);
    if (!r.ok) {
      const d = (await r.json().catch(() => null)) as { message?: string } | null;
      onLoi(d?.message ?? "Không lưu được.");
    }
    setLan((n) => n + 1);
    onDoi();
  }

  if (!cua) return <p className="mt-3 text-body text-ink-muted">Đang tải kỹ năng…</p>;
  if (danhMuc.length === 0) {
    return (
      <p className="mt-3 rounded-control bg-warning-bg px-3 py-2 text-body text-warning">
        Phòng khám chưa khai kỹ năng nào — dùng mục Ngoại lệ bên dưới để bật từng màn.
      </p>
    );
  }
  const co = new Set(cua.ky_nang);
  const nhom = [...new Set(danhMuc.map((k) => k.nhom))];

  return (
    <div className="mt-3 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="chep-tu">
          Chép kỹ năng từ người khác
        </label>
        <select
          id="chep-tu"
          value={chepTu}
          onChange={(e) => setChepTu(e.target.value)}
          className="min-h-9 min-w-0 flex-1 rounded-control border border-line bg-surface px-2 text-meta text-ink sm:max-w-72"
        >
          <option value="">Chép kỹ năng từ người khác…</option>
          {nhanSu
            .filter((n) => n.id !== staffId)
            .map((n) => (
              <option key={n.id} value={n.id}>
                {n.ten}
              </option>
            ))}
        </select>
        <button
          type="button"
          disabled={!chepTu || dang !== null}
          onClick={() => void gui("chep-ky-nang", { tu_staff_id: chepTu }, "chep").then(() => setChepTu(""))}
          className="min-h-9 rounded-control bg-surface-sunken px-3 text-meta font-medium text-ink-soft hover:bg-surface-selected disabled:opacity-50"
        >
          {dang === "chep" ? "Đang chép…" : "Chép"}
        </button>
      </div>

      {nhom.map((t) => (
        <section key={t} aria-label={t}>
          <h3 className="mb-1 px-2 text-label font-semibold uppercase tracking-wide text-ink-muted">{t}</h3>
          <ul className="overflow-hidden rounded-card border border-line bg-surface">
            {danhMuc
              .filter((k) => k.nhom === t)
              .map((k) => {
                const on = co.has(k.ma);
                return (
                  <li key={k.ma} className="border-b border-hairline last:border-b-0">
                    <label
                      className={`grid cursor-pointer grid-cols-[1.25rem_minmax(0,1fr)] items-start gap-x-3 px-3 py-2.5 sm:grid-cols-[1.25rem_10rem_minmax(0,1fr)] ${
                        on ? "bg-brand-50" : "hover:bg-surface-sunken"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={dang !== null}
                        onChange={(e) => void gui("doi-ky-nang", { ma: k.ma, bat: e.target.checked }, k.ma)}
                        className="mt-0.5 size-4 accent-brand-600"
                      />
                      <span className="text-body font-semibold text-ink">
                        {k.ten}
                        <span className="ml-1 font-normal text-ink-faint">· {k.so_nguoi}</span>
                      </span>
                      <span className="col-start-2 text-meta text-ink-muted sm:col-start-3">
                        {dang === k.ma ? "Đang lưu…" : k.man.join(" · ")}
                        {k.phong.length > 0 ? ` — ${k.phong.join(", ")}` : k.moi_phong ? " — mọi phòng" : ""}
                      </span>
                    </label>
                  </li>
                );
              })}
          </ul>
        </section>
      ))}

      <section aria-label="Hôm nay theo lịch" className="rounded-card border border-line bg-surface px-3 py-2.5">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-label font-semibold uppercase tracking-wide text-ink-muted">Hôm nay theo lịch</h3>
          <Link href="/settings/clinic-config" className="text-meta text-brand-700 hover:underline">
            Sửa lịch ở Cấu trúc phòng
          </Link>
        </div>
        {cua.hom_nay.length === 0 ? (
          <p className="mt-1 text-body text-ink-muted">Hôm nay chưa được xếp lịch.</p>
        ) : (
          <ul className="mt-1 space-y-0.5 text-body text-ink">
            {cua.hom_nay.map((h, i) => (
              <li key={i}>
                <span className="text-ink-muted">{CA[h.shift ?? ""] ?? h.shift ?? ""}</span> · {h.vi_tri ?? "—"}
                {h.phong ? <span className="text-ink-muted"> — {h.phong}</span> : null}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-1 text-label text-ink-faint">
          Khi bật “quyền theo lịch”, người này chỉ làm việc được ở phòng đang được xếp hôm nay.
        </p>
      </section>
    </div>
  );
}
