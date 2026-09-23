"use client";

// "Tự nhắc tôi" — hẹn nhắc CHÍNH MÌNH về một khách (nhóm 5, Tuyền chốt 23/09:
// "hoặc tự tạo việc cho chính mình để tự nhắc"). Tới giờ, chuông réo đúng người
// hẹn. Máy chủ kiểm giờ/nội dung (`nhac_viec_service.py`).

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";

interface Nhac {
  id: string;
  noi_dung: string;
  nhac_luc: string;
  xong: boolean;
}

function gio(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
        timeZone: "Asia/Ho_Chi_Minh",
      });
}

export default function TuNhac({
  clinicPatientId,
  visitId,
}: {
  clinicPatientId: string;
  visitId?: string | null;
}) {
  const [ds, setDs] = useState<Nhac[]>([]);
  const [noiDung, setNoiDung] = useState("");
  const [luc, setLuc] = useState("");
  const [loi, setLoi] = useState<string | null>(null);
  const [dang, setDang] = useState(false);

  const doc = useCallback(async (): Promise<Nhac[] | null> => {
    const r = await fetch(`/api/nhac-viec?khach=${clinicPatientId}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as { items?: Nhac[] } | null;
    return r.ok ? (d?.items ?? []) : null;
  }, [clinicPatientId]);

  useEffect(() => {
    let huy = false;
    void doc().then((x) => {
      if (!huy && x) setDs(x);
    });
    return () => {
      huy = true;
    };
  }, [doc]);

  const gui = async (than: unknown) => {
    setDang(true);
    setLoi(null);
    try {
      const r = await fetch("/api/nhac-viec", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(than),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) setLoi(d?.message ?? d?.error ?? "Không lưu được.");
      const moi = await doc();
      if (moi) setDs(moi);
      return r.ok;
    } catch {
      setLoi("Mất kết nối — CHƯA lưu.");
      return false;
    } finally {
      setDang(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-2">
        <input
          value={noiDung}
          onChange={(e) => setNoiDung(e.target.value)}
          placeholder="Nhắc tôi việc gì (vd: gọi khách hẹn tái khám)"
          aria-label="Nội dung tự nhắc"
          className="min-h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 text-body text-ink"
        />
        <input
          type="datetime-local"
          value={luc}
          onChange={(e) => setLuc(e.target.value)}
          aria-label="Giờ nhắc"
          className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink"
        />
        <Button
          size="lg"
          variant="primary"
          disabled={dang || noiDung.trim() === "" || luc === ""}
          onClick={() =>
            void gui({
              thao_tac: "tao",
              du_lieu: {
                noi_dung: noiDung.trim(),
                // datetime-local không có múi giờ → máy chủ hiểu là giờ Việt Nam.
                nhac_luc: luc,
                clinic_patient_id: clinicPatientId,
                visit_id: visitId ?? null,
              },
            }).then((ok) => {
              if (ok) {
                setNoiDung("");
                setLuc("");
              }
            })
          }
        >
          Nhắc tôi
        </Button>
      </div>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {ds.length > 0 ? (
        <ul className="space-y-1 text-meta text-ink">
          {ds.map((n) => (
            <li key={n.id} className="flex flex-wrap items-center gap-2">
              <span className={n.xong ? "text-ink-faint line-through" : ""}>
                {gio(n.nhac_luc)} · {n.noi_dung}
              </span>
              {!n.xong ? (
                <Button size="sm" variant="ghost" disabled={dang} onClick={() => void gui({ thao_tac: "xong", id: n.id })}>
                  Xong
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
