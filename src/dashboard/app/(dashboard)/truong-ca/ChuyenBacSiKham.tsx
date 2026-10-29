"use client";

// CHUYỂN BÁC SĨ KHÁM — trong hộp điều phối một khách (Tuyền 29/10/2026).
//
// Khách ĐANG KHÁM thì bác sĩ khác không tự [Nhận] được (luật "ai nhận trước
// giữ"), nên khám nhầm người / bác sĩ bận giữa chừng phải có người điều phối
// chuyển. Máy chủ: `POST /dispatch/doi-bac-si` (quyền Điều phối khách, lý do
// bắt buộc; đổi người khám của lượt, phiên đang khám giữ nguyên). [Hoàn tác] =
// chuyển ngược về bác sĩ cũ bằng chính lệnh ấy (`bac_si_cu_id` máy chủ trả).
// Danh sách người nhận do máy chủ lọc (Khám bệnh + Hoàn tất khám) và chia nhóm.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";

interface BacSi {
  id: string;
  full_name: string;
  nhom: "TRUC_HOM_NAY" | "BAC_SI_KHAC" | "QUAN_LY";
}

const TEN_NHOM: Record<BacSi["nhom"], string> = {
  TRUC_HOM_NAY: "Đang trực hôm nay",
  BAC_SI_KHAC: "Bác sĩ khác",
  QUAN_LY: "Quản lý",
};

async function guiDoi(
  visitId: string,
  bacSiMoiId: string,
  lyDo: string,
): Promise<{ ok: true; cu: string | null } | { ok: false; loi: string }> {
  try {
    const r = await fetch("/api/dispatch/doi-bac-si", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visit_id: visitId, bac_si_moi_id: bacSiMoiId, ly_do: lyDo }),
    });
    const d = (await r.json().catch(() => null)) as
      | { bac_si_cu_id?: string | null; error?: string; message?: string }
      | null;
    if (!r.ok) return { ok: false, loi: d?.error ?? d?.message ?? "Không chuyển được bác sĩ." };
    return { ok: true, cu: d?.bac_si_cu_id ?? null };
  } catch {
    return { ok: false, loi: "Mất kết nối — CHƯA chuyển được." };
  }
}

export default function ChuyenBacSiKham({
  visitId,
  bacSiHienTai,
  onDoi,
}: {
  visitId: string;
  bacSiHienTai: string | null;
  onDoi?: () => void;
}) {
  const [ds, setDs] = useState<BacSi[] | null>(null);
  const [chon, setChon] = useState("");
  const [xacNhan, setXacNhan] = useState(false);
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [vua, setVua] = useState<{ ten: string; cu: string | null } | null>(null);

  useEffect(() => {
    let song = true;
    void fetch("/api/dispatch-read?what=bac-si", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { items?: BacSi[] } | null) => {
        if (song) setDs(Array.isArray(j?.items) ? j.items : []);
      })
      .catch(() => song && setDs([]));
    return () => {
      song = false;
    };
  }, []);

  const tenCua = (id: string) => ds?.find((b) => b.id === id)?.full_name ?? "bác sĩ mới";

  async function chuyen() {
    setDang(true);
    setLoi(null);
    const kq = await guiDoi(visitId, chon, lyDo.trim());
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setVua({ ten: tenCua(chon), cu: kq.cu });
    setXacNhan(false);
    setLyDo("");
    setChon("");
    onDoi?.();
  }

  async function hoanTac() {
    if (!vua?.cu) return;
    setDang(true);
    setLoi(null);
    const kq = await guiDoi(visitId, vua.cu, "Hoàn tác chuyển bác sĩ");
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setVua(null);
    onDoi?.();
  }

  if (ds === null) return null;
  if (ds.length === 0) return null;
  const nhom = (Object.keys(TEN_NHOM) as BacSi["nhom"][])
    .map((n) => ({ n, bs: ds.filter((b) => b.nhom === n) }))
    .filter((g) => g.bs.length > 0);

  return (
    <div className="grid gap-1.5">
      <p className="text-meta text-ink-muted">
        Đang khám: <b className="text-ink">{bacSiHienTai ?? "chưa có bác sĩ"}</b>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Chuyển sang bác sĩ"
          value={chon}
          disabled={dang}
          onChange={(e) => {
            setChon(e.target.value);
            setXacNhan(false);
          }}
          className="min-h-8 rounded-control border border-line bg-surface px-2 text-xs text-ink"
        >
          <option value="">Chuyển sang bác sĩ…</option>
          {nhom.map((g) => (
            <optgroup key={g.n} label={TEN_NHOM[g.n]}>
              {g.bs.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.full_name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={!chon || dang || xacNhan}
          onClick={() => setXacNhan(true)}
        >
          Chuyển bác sĩ
        </Button>
      </div>
      {xacNhan && chon ? (
        <XacNhanTaiCho
          cau={`Chuyển khách sang ${tenCua(chon)}? Phiếu đang điền giữ nguyên.`}
          nhanDongY="Chuyển bác sĩ"
          onDongY={() => void chuyen()}
          onThoi={() => setXacNhan(false)}
          dangGui={dang}
          choDongY={lyDo.trim().length >= 3}
        >
          <input
            type="text"
            aria-label="Lý do chuyển bác sĩ"
            placeholder="Lý do (bắt buộc) — vd khám nhầm người, bác sĩ bận"
            value={lyDo}
            maxLength={300}
            onChange={(e) => setLyDo(e.target.value)}
            className="min-h-8 w-full rounded-control border border-line bg-surface px-2 text-body text-ink"
          />
        </XacNhanTaiCho>
      ) : null}
      {vua ? (
        <p role="status" className="flex flex-wrap items-center gap-2 text-meta text-success">
          Đã chuyển sang {vua.ten}.
          {vua.cu ? (
            <Button type="button" size="sm" variant="ghost" disabled={dang} onClick={() => void hoanTac()}>
              Hoàn tác
            </Button>
          ) : null}
        </p>
      ) : null}
      {loi ? <p className="text-label text-danger">{loi}</p> : null}
    </div>
  );
}
