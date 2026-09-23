"use client";

// Mục C (cận lâm sàng) và mục F (thủ thuật) của phiếu v5 — DANH MỤC CÓ GIÁ.
//
// Thiết kế v5: "Mở đúng hạng mục cần dùng. Danh mục đóng mặc định để bác sĩ
// không phải nhìn toàn bộ cùng lúc." Mỗi nhóm là một ngăn gập; tick nhiều mục
// rồi bấm MỘT lần → thành chỉ định thật (lệnh PlaceServiceOrders, như ô chỉ
// định cũ ở Bàn khám). Mục đã chỉ định trong lượt hiện "Đã chỉ định".
//
// Mã dịch vụ và giá do MÁY CHỦ gắn (bảng ghép viết tay `anh_xa_danh_muc.py`) —
// màn này không so tên. Mục chưa có mã (phòng khám chưa có dịch vụ ấy) khoá lại.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { tienVn, type NhomCls } from "@/lib/phieu-kham";

export default function DanhMucChiDinh({
  nhom,
  daDat,
  onDat,
  chiDoc,
  nhanNut = "Chỉ định",
}: {
  nhom: NhomCls[];
  /** service_code đã có chỉ định (chưa huỷ) trong lượt. */
  daDat: ReadonlySet<string>;
  onDat: (codes: string[]) => Promise<{ ok: true } | { ok: false; loi: string }>;
  chiDoc: boolean;
  nhanNut?: string;
}) {
  const [chon, setChon] = useState<string[]>([]);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  const giaCua = new Map(
    nhom.flatMap((n) => n.muc).flatMap((m) => (m.service_code ? [[m.service_code, m.gia]] : [])),
  );
  const tong = chon.reduce((t, c) => t + (giaCua.get(c) ?? 0), 0);

  const bat = (ma: string, co: boolean) =>
    setChon((cu) => (co ? [...cu, ma] : cu.filter((x) => x !== ma)));

  const dat = async () => {
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await onDat(chon);
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setBao(`Đã chỉ định ${chon.length} mục — khách vào hàng chờ phòng sau khi thu tiền.`);
    setChon([]);
  };

  return (
    <div className="space-y-2">
      {nhom.map((n) => {
        const coChon = n.muc.filter((m) => m.service_code && chon.includes(m.service_code)).length;
        const coDat = n.muc.filter((m) => m.service_code && daDat.has(m.service_code)).length;
        return (
          <details key={n.nhom} className="rounded-control border border-hairline bg-surface">
            <summary className="flex min-h-10 cursor-pointer items-center gap-2 px-3 text-body font-medium text-ink">
              <span className="min-w-0 flex-1">{n.nhom}</span>
              {coDat > 0 ? <Chip tone="success">{coDat} đã chỉ định</Chip> : null}
              {coChon > 0 ? <Chip tone="brand">{coChon} đang chọn</Chip> : null}
              <span className="text-meta text-ink-faint">{n.muc.length}</span>
            </summary>
            <ul className="divide-y divide-hairline border-t border-hairline">
              {n.muc.map((m) => {
                const ma = m.service_code;
                const da = ma ? daDat.has(ma) : false;
                const khoa = chiDoc || !ma || da;
                return (
                  <li key={m.nhan}>
                    <label className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5">
                      <input
                        type="checkbox"
                        className="size-4 accent-brand-600"
                        disabled={khoa}
                        checked={da || (ma ? chon.includes(ma) : false)}
                        onChange={(e) => ma && bat(ma, e.target.checked)}
                      />
                      <span className="min-w-0 flex-1 text-body text-ink">{m.nhan}</span>
                      <span className="text-meta text-ink-muted">{m.cach_tra_ket_qua}</span>
                      <span className="text-meta tabular-nums text-ink">
                        {ma ? tienVn(m.gia) : ""}
                      </span>
                      {da ? <Chip tone="success">Đã chỉ định</Chip> : null}
                      {!ma ? <Chip tone="warning">Chưa có trong danh mục</Chip> : null}
                    </label>
                  </li>
                );
              })}
            </ul>
          </details>
        );
      })}
      {!chiDoc ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="primary"
            disabled={dang || chon.length === 0}
            onClick={() => void dat()}
          >
            {dang
              ? "Đang ghi…"
              : chon.length > 0
                ? `${nhanNut} ${chon.length} mục · ${tienVn(tong)}`
                : `Tick mục cần ${nhanNut.toLowerCase()}`}
          </Button>
          {loi ? (
            <p role="alert" className="text-meta text-danger">
              {loi}
            </p>
          ) : null}
          {bao ? <p className="text-meta text-success">{bao}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
