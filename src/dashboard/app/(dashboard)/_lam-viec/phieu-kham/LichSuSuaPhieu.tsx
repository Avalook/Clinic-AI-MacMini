"use client";

// LỊCH SỬ SỬA PHIẾU (Tuyền 25/09/2026 — P4A): Hoàn tất khám không khoá phiếu,
// nên phải xem được AI sửa, LÚC NÀO, ô nào, TRƯỚC → SAU.
//
// Máy chủ ghi bằng trigger (cùng người trong 10 phút gộp một dòng); màn này chỉ
// đọc và đổi khoá ô → nhãn theo khung đang ghim. Dòng sửa SAU khi bác sĩ đã
// Hoàn tất khám có nhãn riêng.

import { useMemo, useState } from "react";

import { buttonClass } from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { giaTriDoc, type DinhNghiaPhieu, type GiaTriO, type OPhieu } from "@/lib/phieu-kham";

interface DongLichSu {
  id: string;
  sua_boi: string | null;
  bat_dau: string;
  sua_luc: string;
  tao_moi: boolean;
  sau_hoan_tat: boolean;
  thay_doi: { ma: string; truoc: GiaTriO | null; sau: GiaTriO | null }[];
}

function luc(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function LichSuSuaPhieu({
  visitId,
  dinhNghia,
}: {
  visitId: string;
  dinhNghia: DinhNghiaPhieu;
}) {
  const [mo, setMo] = useState(false);
  const [dong, setDong] = useState<DongLichSu[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  const oTheoMa = useMemo(() => {
    const m = new Map<string, OPhieu>();
    for (const muc of dinhNghia.khung) for (const o of muc.block) m.set(o.ma, o);
    return m;
  }, [dinhNghia]);

  const doc = async () => {
    setLoi(null);
    const r = await fetch(
      `/api/phieu-kham?visit_id=${visitId}&xem=lich-su&chon=${dinhNghia.form_id}`,
      { cache: "no-store" },
    );
    if (!r.ok) {
      setLoi("Không đọc được lịch sử sửa.");
      return;
    }
    setDong(((await r.json()) as { lich_su: DongLichSu[] }).lich_su);
  };

  const giaTri = (ma: string, v: GiaTriO | null) => {
    const o = oTheoMa.get(ma);
    if (v === null) return "—";
    return o ? giaTriDoc(o, { gia_tri: v, nguon: "" }) : Array.isArray(v) ? v.join(", ") : v || "—";
  };

  return (
    <>
      <button
        type="button"
        className={buttonClass("ghost", "sm")}
        aria-expanded={mo}
        onClick={() => {
          const moi = !mo;
          setMo(moi);
          if (moi) void doc();
        }}
      >
        {mo ? "Ẩn lịch sử sửa" : "Lịch sử sửa"}
      </button>
      {mo ? (
        <div className="basis-full rounded-control border border-line bg-surface-sunken p-3">
          {loi ? <p className="text-body text-danger">{loi}</p> : null}
          {!loi && dong === null ? <p className="text-meta text-ink-muted">Đang đọc…</p> : null}
          {dong && dong.length === 0 ? (
            <p className="text-meta text-ink-muted">Chưa có lần sửa nào.</p>
          ) : null}
          <ol className="space-y-3">
            {(dong ?? []).map((d) => (
              <li key={d.id} className="space-y-1">
                <p className="flex flex-wrap items-center gap-2 text-meta text-ink">
                  <span className="font-semibold">{d.sua_boi ?? "Không rõ người sửa"}</span>
                  <span className="tabular-nums text-ink-muted">
                    {luc(d.bat_dau) === luc(d.sua_luc) ? luc(d.sua_luc) : `${luc(d.bat_dau)} → ${luc(d.sua_luc)}`}
                  </span>
                  {d.tao_moi ? <Chip tone="neutral">Ghi lần đầu</Chip> : null}
                  {d.sau_hoan_tat ? <Chip tone="warning">Sửa sau Hoàn tất</Chip> : null}
                </p>
                <ul className="space-y-0.5 pl-3 text-meta text-ink-muted">
                  {d.thay_doi.map((t) => (
                    <li key={t.ma}>
                      <span className="text-ink">{oTheoMa.get(t.ma)?.ten ?? t.ma}:</span>{" "}
                      {d.tao_moi ? null : (
                        <>
                          <span className="line-through">{giaTri(t.ma, t.truoc)}</span>
                          {" → "}
                        </>
                      )}
                      <span className="text-ink">{giaTri(t.ma, t.sau)}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </>
  );
}
