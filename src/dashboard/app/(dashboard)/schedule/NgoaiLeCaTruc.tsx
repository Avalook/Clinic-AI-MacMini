"use client";

import { useMemo, useState, useTransition } from "react";

import Button from "../../../components/ui/Button";
import { loiDocDuoc } from "../../../lib/loi-doc-duoc";

type NhanSu = { id: string; name: string; vai: string };
export type NgoaiLeCaTrucItem = {
  id: string;
  staff_id: string;
  staff_name: string;
  ngay: string;
  bac_si_id: string | null;
  bac_si_name: string | null;
  ly_do: string;
  mo_boi_name: string;
  mo_luc: string;
  huy_luc: string | null;
};

const INPUT =
  "h-10 w-full rounded-control bg-surface px-3 text-body text-ink ring-1 ring-inset ring-line-strong focus:outline-2 focus:outline-brand-500";

export default function NgoaiLeCaTruc({
  homNay,
  nhanSu,
  banDau,
}: {
  homNay: string;
  nhanSu: NhanSu[];
  banDau: NgoaiLeCaTrucItem[];
}) {
  const [ngay, setNgay] = useState(homNay);
  const [staffId, setStaffId] = useState("");
  const [bacSiId, setBacSiId] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [items, setItems] = useState<NgoaiLeCaTrucItem[]>(banDau);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangGui, startGui] = useTransition();

  const bacSi = useMemo(
    () => nhanSu.filter((n) => n.vai === "DOCTOR" || n.vai === "ULTRASOUND_DOCTOR"),
    [nhanSu],
  );

  const tai = async (ngayXet = ngay) => {
    const res = await fetch(`/api/roster/ngoai-le-ca-truc?ngay=${encodeURIComponent(ngayXet)}`, {
      cache: "no-store",
    });
    const kq = (await res.json().catch(() => ({}))) as { items?: NgoaiLeCaTrucItem[] };
    if (!res.ok) {
      setLoi(loiDocDuoc(kq, "Chưa đọc được danh sách ngoại lệ."));
      return;
    }
    setItems(kq.items ?? []);
    setLoi(null);
  };

  const mo = () => {
    if (!staffId || lyDo.trim().length < 3) {
      setLoi("Chọn người được làm thay và ghi rõ lý do.");
      return;
    }
    startGui(async () => {
      const res = await fetch("/api/roster/ngoai-le-ca-truc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          staff_id: staffId,
          bac_si_id: bacSiId || null,
          ngay,
          ly_do: lyDo.trim(),
        }),
      });
      const kq = (await res.json().catch(() => ({}))) as object;
      if (!res.ok) {
        setLoi(loiDocDuoc(kq, "Chưa mở được ngoại lệ."));
        return;
      }
      setLyDo("");
      await tai();
    });
  };

  const huy = (id: string) => {
    startGui(async () => {
      const res = await fetch(`/api/roster/ngoai-le-ca-truc?id=${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      const kq = (await res.json().catch(() => ({}))) as object;
      if (!res.ok) {
        setLoi(loiDocDuoc(kq, "Chưa huỷ được ngoại lệ."));
        return;
      }
      await tai();
    });
  };

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="space-y-1 text-meta text-ink-muted">
          Ngày áp dụng
          <input
            className={INPUT}
            type="date"
            value={ngay}
            onChange={(e) => {
              const moi = e.target.value;
              setNgay(moi);
              void tai(moi);
            }}
          />
        </label>
        <label className="space-y-1 text-meta text-ink-muted">
          Người được làm thay
          <select className={INPUT} value={staffId} onChange={(e) => setStaffId(e.target.value)}>
            <option value="">Chọn nhân sự</option>
            {nhanSu.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-meta text-ink-muted">
          Làm thay bác sĩ
          <select className={INPUT} value={bacSiId} onChange={(e) => setBacSiId(e.target.value)}>
            <option value="">Mọi bác sĩ</option>
            {bacSi.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-meta text-ink-muted">
          Lý do
          <input className={INPUT} value={lyDo} onChange={(e) => setLyDo(e.target.value)} placeholder="Ví dụ: bổ sung ca đột xuất" maxLength={500} />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="soft" size="lg" disabled={dangGui} onClick={mo}>
          Mở ngoại lệ
        </Button>
        <p className="text-meta text-ink-muted">Ngoại lệ huỷ được và luôn giữ lịch sử người mở, lý do.</p>
      </div>
      {loi && <p className="rounded-control bg-danger-bg px-3 py-2 text-body text-danger">{loi}</p>}
      <ul className="divide-y divide-line rounded-card border border-line">
        {items.length === 0 && <li className="px-3 py-3 text-body text-ink-muted">Ngày này chưa có ngoại lệ.</li>}
        {items.map((n) => (
          <li key={n.id} className="flex flex-wrap items-center justify-between gap-3 px-3 py-3">
            <div className="min-w-0">
              <p className="text-body font-semibold text-ink">{n.staff_name} → {n.bac_si_name ?? "mọi bác sĩ"}</p>
              <p className="text-meta text-ink-muted">{n.ly_do} · {n.mo_boi_name} mở</p>
              {n.huy_luc && <p className="text-meta text-ink-faint">Đã huỷ</p>}
            </div>
            {!n.huy_luc && <Button variant="danger" size="sm" disabled={dangGui} onClick={() => huy(n.id)}>Huỷ ngoại lệ</Button>}
          </li>
        ))}
      </ul>
    </div>
  );
}
