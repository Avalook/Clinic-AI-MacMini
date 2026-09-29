"use client";

// Thẻ kho một thuốc (Tuyền 29/09/2026: "ai cho vào có lịch sử ghi hết lại").
// Chỉ đọc: `GET /api/pharmacy/the-kho?id=` → `GET /api/v1/pharmacy/the-kho/{id}`.
// Máy chủ tính tồn trước → sau, tên loại, mã phiếu; ở đây chỉ vẽ.

import { useEffect, useState } from "react";

import { INPUT, LABEL, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import type { ThuocKho } from "./DanhMucKho";
import { soKho, tonTheoDonVi } from "./gui-kho";

interface DongTheKho {
  id: string;
  luc: string;
  loai: string;
  loai_nhan: string;
  ma_phieu: string | null;
  khach: string | null;
  so_lo: string;
  so_luong: number;
  /** Đơn vị của lô — tồn trước → sau tính riêng từng đơn vị. */
  don_vi: string | null;
  ton_truoc: number;
  ton_sau: number;
  nguoi_lam: string | null;
  ly_do: string | null;
}

interface TheKhoData {
  thuoc: {
    ten: string;
    don_vi_ban: string | null;
    /** Tồn tách theo đơn vị lô (29/09): không cộng hộp với viên. */
    ton_theo_don_vi: { don_vi: string | null; ton: number }[];
  };
  dong: DongTheKho[];
}

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export default function TheKho({
  thuoc,
  chonId,
  onChon,
}: {
  thuoc: ThuocKho[];
  chonId: string | null;
  onChon: (id: string | null) => void;
}) {
  // Kết quả gắn với id đã hỏi — đang tải = kết quả chưa phải của `chonId`
  // (không setState đồng bộ trong effect).
  const [kq, setKq] = useState<{ id: string; data: TheKhoData | null; loi: string | null } | null>(
    null,
  );
  const dangTai = chonId != null && kq?.id !== chonId;
  const data = kq?.id === chonId ? kq.data : null;
  const loi = kq?.id === chonId ? kq.loi : null;
  const [go, setGo] = useState(() => thuoc.find((t) => t.id === chonId)?.ten ?? "");

  useEffect(() => {
    if (!chonId) return;
    let bo = false;
    fetch(`/api/pharmacy/the-kho?id=${encodeURIComponent(chonId)}`, { cache: "no-store" })
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as (TheKhoData & { error?: string }) | null;
        if (bo) return;
        if (!r.ok || !d) setKq({ id: chonId, data: null, loi: d?.error ?? "Không đọc được thẻ kho." });
        else setKq({ id: chonId, data: d, loi: null });
      })
      .catch(() => {
        if (!bo) setKq({ id: chonId, data: null, loi: "Mất kết nối — chưa đọc được thẻ kho." });
      });
    return () => {
      bo = true;
    };
  }, [chonId]);

  return (
    <div className="flex flex-col gap-3">
      <label className="block sm:w-96">
        <span className={LABEL}>Thuốc</span>
        <input
          list="the-kho-thuoc"
          value={go}
          placeholder="Gõ tên thuốc…"
          onChange={(e) => {
            setGo(e.target.value);
            const t = thuoc.find((x) => x.ten === e.target.value);
            if (t) onChon(t.id);
          }}
          className={INPUT}
        />
        <datalist id="the-kho-thuoc">
          {thuoc.map((t) => (
            <option key={t.id} value={t.ten} />
          ))}
        </datalist>
      </label>

      {!chonId ? (
        <p className="text-body text-ink-muted">
          Chọn một thuốc (hoặc bấm tên thuốc ở tab Danh mục) để xem mọi lần nhập, bán/giao,
          điều chỉnh, huỷ, kiểm kho — ai làm, lúc nào, tồn trước và sau.
        </p>
      ) : dangTai ? (
        <p className="text-body text-ink-muted">Đang đọc thẻ kho…</p>
      ) : loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : data ? (
        <>
          <p className="text-body text-ink">
            <span className="font-semibold">{data.thuoc.ten}</span> · tồn hiện tại{" "}
            <span className="font-semibold tabular-nums">
              {tonTheoDonVi(data.thuoc.ton_theo_don_vi)}
            </span>{" "}
            · {data.dong.length} biến động
          </p>
          <div className={`${TBL_WRAP} overflow-x-auto`}>
            <table className="w-full min-w-3xl text-left text-body">
              <thead className={TBL_HEAD}>
                <tr>
                  <th className="px-3 py-2">Thời gian</th>
                  <th className="px-3 py-2">Loại</th>
                  <th className="px-3 py-2">Mã phiếu</th>
                  <th className="px-3 py-2">Lô</th>
                  <th className="px-3 py-2 text-right">Số lượng</th>
                  <th className="px-3 py-2 text-right">Tồn trước → sau</th>
                  <th className="px-3 py-2">Người làm</th>
                  <th className="px-3 py-2">Lý do</th>
                </tr>
              </thead>
              <tbody className={TBL_DIV}>
                {data.dong.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-3 py-6 text-center text-ink-muted">
                      Thuốc này chưa có biến động kho nào.
                    </td>
                  </tr>
                ) : (
                  data.dong.map((d) => (
                    <tr key={d.id}>
                      <td className="whitespace-nowrap px-3 py-2 text-ink-muted">{gio(d.luc)}</td>
                      <td className="px-3 py-2 text-ink">{d.loai_nhan}</td>
                      <td className="px-3 py-2 text-ink-muted">
                        {d.ma_phieu ?? "—"}
                        {d.khach ? <span className="block text-meta">{d.khach}</span> : null}
                      </td>
                      <td className="px-3 py-2 text-ink-muted">{d.so_lo}</td>
                      <td
                        className={`px-3 py-2 text-right font-semibold tabular-nums ${
                          Number(d.so_luong) < 0 ? "text-danger" : "text-success"
                        }`}
                      >
                        {Number(d.so_luong) > 0 ? "+" : ""}
                        {soKho(d.so_luong)} {d.don_vi ?? ""}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-ink">
                        {soKho(d.ton_truoc)} → {soKho(d.ton_sau)} {d.don_vi ?? ""}
                      </td>
                      <td className="px-3 py-2 text-ink-muted">{d.nguoi_lam ?? "—"}</td>
                      <td className="max-w-xs px-3 py-2 text-meta text-ink-muted">
                        {d.ly_do ?? ""}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
