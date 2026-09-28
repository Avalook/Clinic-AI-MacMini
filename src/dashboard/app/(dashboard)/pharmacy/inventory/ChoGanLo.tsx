"use client";

// Thuốc ĐÃ GIAO mà chưa gán lô (Tuyền 28/09/2026: "chưa cần quan tâm lô nào …
// lô nhập và gán sau"). Nhà thuốc giao không lô ở /pharmacy; ở đây gán từng lần
// giao vào một lô thật — lúc ấy kho mới trừ. Máy chủ quyết lô nào gán được
// (`GET /api/v1/pharmacy/cho-gan-lo`: cùng thuốc, cùng đơn vị, còn hạn, đủ
// tồn) và kiểm lại khi gán (`POST /api/v1/pharmacy/gan-lo`).

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import { guiKho } from "./gui-kho";

export interface DongChoGanLo {
  id: string;
  so_luong: number;
  giao_luc: string;
  thuoc: string | null;
  unit: string | null;
  nguoi_giao: string | null;
  khach: string | null;
  ma_bn: string | null;
  lo_gan_duoc: {
    drug_batch_id: string;
    batch_code: string;
    expiry_date: string | null;
    ton: number;
  }[];
}

const fmtNgay = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "—";

function Dong({ d }: { d: DongChoGanLo }) {
  const router = useRouter();
  const [lo, setLo] = useState(d.lo_gan_duoc[0]?.drug_batch_id ?? "");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function gan() {
    setDangGui(true);
    setLoi(null);
    const kq = await guiKho("gan-lo", { dong_id: d.id, drug_batch_id: lo });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    router.refresh();
  }

  return (
    <tr>
      <td className="px-3 py-2 font-medium text-ink">{d.thuoc ?? "—"}</td>
      <td className="px-3 py-2 text-ink-soft">
        {d.khach ?? "—"}
        {d.ma_bn ? <span className="text-meta text-ink-muted"> · {d.ma_bn}</span> : null}
      </td>
      <td className="px-3 py-2 text-right">
        {d.so_luong} {d.unit ?? ""}
      </td>
      <td className="px-3 py-2 text-meta text-ink-muted">
        {fmtNgay(d.giao_luc)}
        {d.nguoi_giao ? ` · ${d.nguoi_giao}` : ""}
      </td>
      <td className="px-3 py-2">
        {d.lo_gan_duoc.length === 0 ? (
          <span className="text-meta text-ink-muted">
            Chưa có lô gán được — nhập lô ở tab Tồn theo lô.
          </span>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={lo}
              onChange={(e) => setLo(e.target.value)}
              className={INPUT}
              aria-label={`Chọn lô cho ${d.thuoc ?? "thuốc"}`}
            >
              {d.lo_gan_duoc.map((b) => (
                <option key={b.drug_batch_id} value={b.drug_batch_id}>
                  {b.batch_code} · HSD {fmtNgay(b.expiry_date)} · còn {b.ton}
                </option>
              ))}
            </select>
            <Button type="button" variant="primary" disabled={dangGui || !lo} onClick={gan}>
              {dangGui ? "Đang gán…" : "Gán lô"}
            </Button>
          </div>
        )}
        {loi ? <p className="mt-1 text-meta text-danger">{loi}</p> : null}
      </td>
    </tr>
  );
}

export default function ChoGanLo({ dong }: { dong: DongChoGanLo[] }) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-meta text-ink-muted">
        Thuốc đã giao khách mà chưa gán lô. Tồn kho đang báo cao hơn thực tế đúng bằng
        các dòng này — gán lô xong thì kho trừ.
      </p>
      <div className={`${TBL_WRAP} overflow-x-auto`}>
        <table className="w-full min-w-2xl text-left text-body">
          <thead className={TBL_HEAD}>
            <tr>
              <th className="px-3 py-2">Thuốc</th>
              <th className="px-3 py-2">Khách</th>
              <th className="px-3 py-2 text-right">Số giao</th>
              <th className="px-3 py-2">Giao lúc</th>
              <th className="px-3 py-2">Gán lô</th>
            </tr>
          </thead>
          <tbody className={TBL_DIV}>
            {dong.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-ink-muted">
                  Không còn lần giao nào chờ gán lô.
                </td>
              </tr>
            ) : (
              dong.map((d) => <Dong key={d.id} d={d} />)
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
