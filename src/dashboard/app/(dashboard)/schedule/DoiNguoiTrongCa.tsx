"use client";

// ĐỔI NGƯỜI TRONG CA (Tuyền 29/09/2026).
//
// Hà đứng Siêu âm 1, giữa ca phải về → trưởng ca bấm "Thay người" ở dòng của
// Hà, chọn B. Máy chủ đổi người trên chính dòng lịch ấy trong một giao dịch:
// B có ngay trọn quyền của vị trí/phòng, Hà mất ngay, sổ giữ vết "Hà → B lúc
// HH:MM", nhật ký ghi ai đổi. Ai được đổi / ca nào đổi được là việc của máy chủ
// (quyền `roster.shift.swap` — lego Điều phối khách); khối này chỉ hiện khi máy
// chủ báo `doi_nguoi`.

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Button from "../../../components/ui/Button";
import { SHIFT_LABEL, dayShort, fmtDayMonth, type Shift } from "../../../lib/roster";
import { loiDocDuoc } from "../../../lib/loi-doc-duoc";

export interface DongDoiNguoi {
  id: string;
  work_date: string;
  station: string;
  shift: string;
  staff_id: string | null;
  staff_name: string | null;
}

export interface VetThayNguoi {
  roster_id: string | null;
  nguoi_cu_ten: string;
  nguoi_moi_ten: string;
  gio: string;
  boi_ten: string | null;
}

export interface NguoiChon {
  id: string;
  name: string;
}

export default function DoiNguoiTrongCa({
  homNay,
  dong,
  vet,
  nhanViTri,
  nhanSu,
}: {
  homNay: string;
  dong: DongDoiNguoi[];
  vet: VetThayNguoi[];
  nhanViTri: Record<string, string>;
  nhanSu: NguoiChon[];
}) {
  const router = useRouter();
  const [dangMo, setDangMo] = useState<string | null>(null);
  const [nguoiMoi, setNguoiMoi] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [loi, setLoi] = useState<string | null>(null);
  const [baoXong, setBaoXong] = useState<string | null>(null);
  const [dangGui, startGui] = useTransition();

  // Chỉ ca hôm nay và các ngày tới — ca đã qua không đổi được (máy chủ chặn).
  const ngay = useMemo(
    () => [...new Set(dong.map((d) => d.work_date).filter((d) => d >= homNay))].sort(),
    [dong, homNay],
  );
  const [ngayChon, setNgayChon] = useState<string>(ngay[0] ?? homNay);

  const vetTheoDong = useMemo(() => {
    const m = new Map<string, VetThayNguoi[]>();
    for (const v of vet) {
      if (!v.roster_id) continue;
      m.set(v.roster_id, [...(m.get(v.roster_id) ?? []), v]);
    }
    return m;
  }, [vet]);

  const dongNgay = dong
    .filter((d) => d.work_date === ngayChon)
    .sort(
      (a, b) =>
        (nhanViTri[a.station] ?? a.station).localeCompare(nhanViTri[b.station] ?? b.station, "vi") ||
        a.shift.localeCompare(b.shift),
    );

  const mo = (id: string) => {
    setDangMo(id);
    setNguoiMoi("");
    setLyDo("");
    setLoi(null);
    setBaoXong(null);
  };

  const doi = (d: DongDoiNguoi) => {
    if (!nguoiMoi) {
      setLoi("Chọn người vào thay.");
      return;
    }
    setLoi(null);
    startGui(async () => {
      const res = await fetch("/api/roster/thay-nguoi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: d.id, staff_id: nguoiMoi, ly_do: lyDo.trim() || null }),
      });
      const kq = (await res.json().catch(() => ({}))) as {
        nguoi_moi_ten?: string;
        so_lich_cho_xep?: number;
      };
      if (!res.ok) {
        setLoi(loiDocDuoc(kq, "Chưa đổi được người — thử lại."));
        return;
      }
      const choXep = kq.so_lich_cho_xep ?? 0;
      setBaoXong(
        `${d.staff_name || "Người cũ"} → ${kq.nguoi_moi_ten ?? "người mới"}: đã đổi, quyền áp dụng ngay.` +
          (choXep > 0 ? ` ${choXep} lịch hẹn của người cũ chuyển sang "Lịch chờ xếp bác sĩ".` : ""),
      );
      setDangMo(null);
      router.refresh();
    });
  };

  if (ngay.length === 0) {
    return <p className="text-body text-ink-muted">Tuần này không còn ca nào từ hôm nay trở đi.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {ngay.map((n) => (
          <Button
            key={n}
            size="sm"
            variant={n === ngayChon ? "soft" : "secondary"}
            onClick={() => {
              setNgayChon(n);
              setDangMo(null);
            }}
          >
            {n === homNay ? "Hôm nay" : `${dayShort(n)} ${fmtDayMonth(n)}`}
          </Button>
        ))}
      </div>

      {baoXong && (
        <p className="rounded-control bg-status-in-progress-bg px-3 py-2 text-body text-status-in-progress">
          {baoXong}
        </p>
      )}

      <ul className="divide-y divide-line rounded-card border border-line">
        {dongNgay.map((d) => {
          const vetDong = vetTheoDong.get(d.id) ?? [];
          return (
            <li key={d.id} className="space-y-2 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-body font-medium text-ink">
                    {nhanViTri[d.station] ?? d.station}
                    <span className="ml-2 text-meta text-ink-muted">{SHIFT_LABEL[d.shift as Shift] ?? d.shift}</span>
                  </p>
                  <p className="text-body text-ink-soft">{d.staff_name || "—"}</p>
                  {vetDong.map((v, i) => (
                    <p key={i} className="text-meta text-ink-muted">
                      {v.nguoi_cu_ten} đứng tới {v.gio} → {v.nguoi_moi_ten} từ {v.gio}
                      {v.boi_ten ? ` · ${v.boi_ten} đổi` : ""}
                    </p>
                  ))}
                </div>
                {dangMo !== d.id && (
                  <Button size="sm" onClick={() => mo(d.id)}>
                    Thay người
                  </Button>
                )}
              </div>

              {dangMo === d.id && (
                <div className="space-y-2 rounded-control bg-surface-sunken p-2">
                  <label className="block text-meta text-ink-muted">
                    Người vào thay
                    <select
                      value={nguoiMoi}
                      onChange={(e) => setNguoiMoi(e.target.value)}
                      className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-body focus:border-brand-600 focus:outline-none"
                    >
                      <option value="">— Chọn người —</option>
                      {nhanSu
                        .filter((n) => n.id !== d.staff_id)
                        .map((n) => (
                          <option key={n.id} value={n.id}>
                            {n.name}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="block text-meta text-ink-muted">
                    Lý do (không bắt buộc)
                    <input
                      value={lyDo}
                      onChange={(e) => setLyDo(e.target.value)}
                      maxLength={500}
                      placeholder="VD: có việc đột xuất phải về"
                      className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-body focus:border-brand-600 focus:outline-none"
                    />
                  </label>
                  {loi && <p className="text-meta text-danger">{loi}</p>}
                  <div className="flex gap-2">
                    <Button variant="primary" size="sm" disabled={dangGui} onClick={() => doi(d)}>
                      {dangGui ? "Đang đổi…" : "Đổi người"}
                    </Button>
                    <Button variant="ghost" size="sm" disabled={dangGui} onClick={() => setDangMo(null)}>
                      Thôi
                    </Button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
