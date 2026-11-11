// (Client — chỉ `KetQuaKhach.tsx` dùng; không "use client" để nhận hàm `onGan`.) Gmail G10: thư email chờ mà máy không gợi ý
// được khách ⇒ người tìm khách (tên không dấu / SĐT / mã BN) rồi gán. Câu tìm ở máy
// chủ (`ban_le_service.tim_khach_conn`, dùng chung); tờ vào đâu (chỉ định đúng loại hay
// hồ sơ theo lượt khám) máy chủ quyết — màn chỉ vẽ và gửi id khách đã chọn.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import OTimKhach from "@/components/ui/OTimKhach";

interface KhachTim {
  clinic_patient_id: string;
  full_name: string;
  patient_code: string | null;
  phone_primary: string | null;
  birth_year: number | null;
}

const moTa = (k: KhachTim) =>
  [k.full_name, k.phone_primary, k.patient_code, k.birth_year ? `sinh ${k.birth_year}` : null]
    .filter(Boolean)
    .join(" · ");

export default function GanKhachEmail({
  dang,
  onGan,
}: {
  dang: boolean;
  onGan: (clinicPatientId: string, ten: string) => void;
}) {
  const [go, setGo] = useState("");
  const [ds, setDs] = useState<KhachTim[] | null>(null);
  const [chon, setChon] = useState<KhachTim | null>(null);

  useEffect(() => {
    const q = go.trim();
    if (q.length < 2) return;
    let huy = false;
    const h = setTimeout(async () => {
      try {
        const r = await fetch(`/api/xet-nghiem/ban/tim-khach?${new URLSearchParams({ q })}`, { cache: "no-store" });
        const d = r.ok ? ((await r.json()) as { items: KhachTim[] }).items : [];
        if (!huy) setDs(d);
      } catch {
        if (!huy) setDs([]);
      }
    }, 350);
    return () => {
      huy = true;
      clearTimeout(h);
    };
  }, [go]);

  if (chon) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-meta">
        <span className="min-w-0 break-words text-ink-soft">
          Đã chọn: <span className="font-semibold text-ink">{moTa(chon)}</span>
        </span>
        <Button type="button" size="sm" variant="primary" disabled={dang} onClick={() => onGan(chon.clinic_patient_id, chon.full_name)}>
          Gán cho khách đã chọn
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setChon(null)}>
          Chọn khách khác
        </Button>
      </div>
    );
  }
  const q = go.trim();
  return (
    <div className="flex w-full flex-col gap-1 sm:max-w-md">
      <OTimKhach value={go} onChange={setGo} nhan="Tìm khách để gán thư này" />
      {q.length >= 2 && ds ? (
        <ul className="flex flex-col overflow-hidden rounded-control border border-line bg-surface">
          {ds.map((k) => (
            <li key={k.clinic_patient_id}>
              <button
                type="button"
                onClick={() => {
                  setChon(k);
                  setGo("");
                  setDs(null);
                }}
                className="w-full border-b border-line px-3 py-2 text-left text-meta text-ink last:border-b-0 hover:bg-surface-sunken"
              >
                {moTa(k)}
              </button>
            </li>
          ))}
          {!ds.length ? <li className="px-3 py-2 text-meta text-ink-muted">Không thấy khách nào.</li> : null}
        </ul>
      ) : null}
    </div>
  );
}
