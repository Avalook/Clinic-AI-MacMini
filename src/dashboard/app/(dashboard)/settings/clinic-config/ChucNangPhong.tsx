"use client";

// KHỐI "CHỨC NĂNG CỦA PHÒNG" (Tuyền 04/11/2026) — "đứng đâu làm việc đó".
//
// Ai được xếp lịch đứng phòng này hôm nay thì làm được các việc đã tick, cả
// ngày hôm đó. Danh sách việc tick được (nhóm việc tại chỗ) và nhãn là của máy
// chủ (`phong_chuc_nang_service`); màn chỉ vẽ và gửi tick / bỏ tick. Bỏ tick
// nhầm thì tick lại — không có gì khoá cứng.

import { useEffect, useState } from "react";

import ChipChon from "@/components/ui/ChipChon";

interface ChucNang {
  work_pack: string;
  ten: string;
  mo_ta: string;
  bat: boolean;
  chi_dung_phong: boolean;
}
interface DuLieu {
  chon: ChucNang[];
  khac: { work_pack: string; ten: string }[];
}

export default function ChucNangPhong({ roomId }: { roomId: string }) {
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    void fetch(`/api/chuc-nang-phong?room_id=${roomId}`, { cache: "no-store" })
      .then(async (r) => {
        if (huy) return;
        const body = (await r.json().catch(() => null)) as (DuLieu & { error?: string }) | null;
        if (!r.ok || !body) {
          setLoi(body?.error ?? "Không đọc được chức năng của phòng.");
          return;
        }
        setLoi(null);
        setDl(body);
      })
      .catch(() => !huy && setLoi("Mất kết nối."));
    return () => {
      huy = true;
    };
  }, [roomId]);

  async function doi(c: ChucNang) {
    setDangGui(c.work_pack);
    try {
      const r = await fetch("/api/chuc-nang-phong", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room_id: roomId, work_pack: c.work_pack, bat: !c.bat }),
      });
      const body = (await r.json().catch(() => null)) as (DuLieu & { error?: string }) | null;
      if (!r.ok || !body) {
        setLoi(body?.error ?? "Không lưu được.");
        return;
      }
      setLoi(null);
      setDl(body);
    } catch {
      setLoi("Mất kết nối.");
    } finally {
      setDangGui(null);
    }
  }

  return (
    <section aria-label="Chức năng của phòng" className="space-y-2">
      <div>
        <h4 className="text-body font-medium text-ink">Chức năng của phòng</h4>
        <p className="text-meta text-ink-muted">
          Ai được xếp lịch đứng phòng này hôm nay thì làm được các việc đã tick, cả ngày hôm đó.
        </p>
      </div>
      {loi ? <p className="text-meta text-danger">{loi}</p> : null}
      {dl ? (
        <div className="flex flex-wrap gap-2">
          {dl.chon.map((c) => (
            <ChipChon
              key={c.work_pack}
              chon={c.bat}
              disabled={dangGui !== null}
              onDoi={() => void doi(c)}
            >
              <span title={c.mo_ta}>
                {c.ten}
                {c.chi_dung_phong ? <span className="text-ink-muted"> (chỉ phòng này)</span> : null}
              </span>
            </ChipChon>
          ))}
        </div>
      ) : !loi ? (
        <p className="text-meta text-ink-muted">Đang tải…</p>
      ) : null}
      {dl && dl.khac.length > 0 ? (
        <p className="text-meta text-ink-muted">
          Phòng còn mở thêm: {dl.khac.map((k) => k.ten).join(", ")}.
        </p>
      ) : null}
    </section>
  );
}
