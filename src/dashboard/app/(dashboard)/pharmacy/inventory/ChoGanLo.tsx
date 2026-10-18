"use client";

// Thuốc đã giao: bổ sung lô thật từ kho hoặc quầy sau, không bắt chuyển trước.
// Tồn khả dụng đã tính nghĩa vụ giao; ledger lô ghi khi xác nhận. Máy chủ quyết lô gán được
// (`GET /api/v1/pharmacy/cho-gan-lo`: cùng thuốc, cùng đơn vị, còn hạn, đủ
// tồn) và kiểm lại khi gán (`POST /api/v1/pharmacy/gan-lo`).

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import { guiKho, soKho } from "./gui-kho";

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
    noi_chua?: string;
    ton: number;
  }[];
  /** Lô của thuốc ở kho/quầy nhưng tính theo đơn vị KHÁC dòng này — để giải thích vì
   *  sao không có lô gán được (máy chủ trả, không đổi luật gán). */
  lo_khac_don_vi?: { drug_batch_id: string; batch_code: string; unit: string | null; ton: number }[];
}

/** "6 hộp · 20 viên" — cộng theo từng đơn vị, không cộng lẫn. */
function tonLoKhacDonVi(lo: NonNullable<DongChoGanLo["lo_khac_don_vi"]>): string {
  const theo = new Map<string, number>();
  for (const b of lo) theo.set(b.unit ?? "", (theo.get(b.unit ?? "") ?? 0) + Number(b.ton));
  return [...theo.entries()].map(([dv, ton]) => `${soKho(ton)} ${dv}`.trim()).join(" · ");
}

const fmtNgay = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "—";

const fmtLuc = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

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
      <td className="px-3 py-2 font-medium text-ink">
        {d.thuoc ?? "—"}
        {/* Điện thoại: tên khách nằm dưới tên thuốc (cột Khách và Giao lúc ẩn) để cột
            Gán lô — nơi nói LÝ DO không gắn được — nằm trong màn hình. */}
        <span className="block text-meta font-normal text-ink-muted sm:hidden">
          {d.khach ?? "—"}
        </span>
      </td>
      <td className="hidden px-3 py-2 text-ink-soft sm:table-cell">
        {d.khach ?? "—"}
        {d.ma_bn ? <span className="text-meta text-ink-muted"> · {d.ma_bn}</span> : null}
      </td>
      <td className="px-3 py-2 text-right">
        {d.so_luong} {d.unit ?? ""}
      </td>
      <td className="hidden px-3 py-2 text-meta text-ink-muted sm:table-cell">
        {fmtLuc(d.giao_luc)}
        {d.nguoi_giao ? ` · ${d.nguoi_giao}` : ""}
      </td>
      <td className="px-3 py-2">
        {d.lo_gan_duoc.length === 0 ? (
          d.lo_khac_don_vi && d.lo_khac_don_vi.length > 0 ? (
            <span role="status" className="text-meta text-warning">
              Kho/quầy có {tonLoKhacDonVi(d.lo_khac_don_vi)} nhưng dòng này giao theo “{d.unit ?? "?"}”
              — khác đơn vị nên không gắn được. Nhập lô theo “{d.unit ?? "?"}” hoặc báo quản lý.
            </span>
          ) : (
            <span className="text-meta text-ink-muted">
              Chưa có lô gán được — nhập lô ở tab Tồn theo lô.
            </span>
          )
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
                  {b.noi_chua === "KHO" ? "Kho" : "Quầy"} · {b.batch_code} · HSD {fmtNgay(b.expiry_date)} · còn {b.ton}
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
        Thuốc đã giao khách, đang chờ xác nhận lô thực tế lấy từ kho hoặc quầy.
        Tồn khả dụng đã trừ phần chờ này; xác nhận lô không trừ tồn khả dụng lần nữa.
      </p>
      <div className={`${TBL_WRAP} overflow-x-auto`}>
        <table className="w-full text-left text-body sm:min-w-2xl">
          <thead className={TBL_HEAD}>
            <tr>
              <th className="px-3 py-2">Thuốc</th>
              <th className="hidden px-3 py-2 sm:table-cell">Khách</th>
              <th className="px-3 py-2 text-right">Số giao</th>
              <th className="hidden px-3 py-2 sm:table-cell">Giao lúc</th>
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
