"use client";

// Ba nút của dược sĩ: CẤP THUỐC, KHÁCH KHÔNG LẤY, CHỐT KHÔNG CẤP THÊM.
//
// Trước component này màn nhà thuốc chỉ đọc — không có nút nào, và cũng không
// có gì để nút gọi. Ba nút ở đây phủ đúng ba tình huống Quang mô tả: mua,
// không mua, mua một phần. "Mua một phần" không phải một nút riêng: cấp 4 rồi
// bấm Chốt.
//
// Mọi thao tác đi qua /api/pharmacy/* → FastAPI → service_role. Trình duyệt
// không ghi thẳng vào kho được (RLS chỉ cấp SELECT), và đó là chủ ý.

import { useState } from "react";
import { useRouter } from "next/navigation";

export interface LoThuoc {
  id: string;
  batch_code: string;
  expiry_date: string;
  quantity_on_hand: number;
  unit: string;
  ten: string;
}

interface Props {
  prescriptionId: string;
  drugName: string | null;
  /** Số bác sĩ kê. `null` khi câu bác sĩ gõ không đọc ra số. */
  quantityNum: number | null;
  quantityText: string | null;
  dispensedQty: number;
  dispenseStatus: string | null;
  closed: boolean;
  /** Các lô còn hàng, đã lọc theo tên thuốc ở phía gọi. */
  batches: LoThuoc[];
}

const NHAN_TRANG_THAI: Record<string, string> = {
  CHUA_CAP: "Chưa cấp",
  CAP_MOT_PHAN: "Đã cấp một phần",
  CAP_DU: "Đã cấp đủ",
  TU_CHOI: "Khách không lấy",
};

export default function ThaoTacCapPhat({
  prescriptionId,
  drugName,
  quantityNum,
  quantityText,
  dispensedQty,
  dispenseStatus,
  closed,
  batches,
}: Props) {
  const router = useRouter();
  const [loId, setLoId] = useState<string>(batches[0]?.id ?? "");
  const [soLuong, setSoLuong] = useState<string>("");
  const [lyDo, setLyDo] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const conLai =
    quantityNum === null ? null : Math.max(0, quantityNum - dispensedQty);

  async function goi(action: string, body: Record<string, unknown>) {
    setDangGui(true);
    setLoi(null);
    try {
      const res = await fetch(`/api/pharmacy/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        // Câu từ chối của backend đã viết bằng tiếng Việt và có số liệu
        // ("đơn kê 10, đã cấp 4 — chỉ còn 6"). Hiện nguyên văn, đừng thay
        // bằng một câu chung chung.
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(d?.message ?? d?.error ?? "Không lưu được. Thử lại giúp em.");
        return;
      }
      setSoLuong("");
      setLyDo("");
      router.refresh();
    } finally {
      setDangGui(false);
    }
  }

  if (closed) {
    return (
      <div className="rounded-control border border-line bg-surface-muted p-3 text-sm text-ink-soft">
        Dòng thuốc này đã chốt —{" "}
        <span className="font-medium text-ink">
          {NHAN_TRANG_THAI[dispenseStatus ?? ""] ?? dispenseStatus}
        </span>
        {dispensedQty > 0 && <> · đã cấp {dispensedQty}</>}.
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-control border border-line bg-surface p-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
        <span className="font-semibold text-ink">Cấp thuốc</span>
        <span className="text-ink-muted">
          Kê {quantityText ?? "—"}
          {quantityNum === null && (
            <span className="text-warning">
              {" "}
              (không đọc được số — nhập tay)
            </span>
          )}
          {dispensedQty > 0 && <> · đã cấp {dispensedQty}</>}
          {conLai !== null && <> · còn {conLai}</>}
        </span>
      </div>

      {batches.length === 0 ? (
        <p className="rounded-control bg-warning-bg px-3 py-2 text-xs text-warning">
          Kho chưa có lô nào còn hàng cho “{drugName ?? "thuốc này"}”. Vào Kho
          &amp; tồn kho để nhập lô trước.
        </p>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex-1 min-w-[200px] text-xs text-ink-muted">
            Lô thuốc
            <select
              value={loId}
              onChange={(e) => setLoId(e.target.value)}
              className="mt-1 w-full rounded-control border border-line bg-surface px-2 py-1.5 text-sm text-ink"
            >
              {batches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_code} · HSD{" "}
                  {new Date(b.expiry_date).toLocaleDateString("vi-VN")} · còn{" "}
                  {b.quantity_on_hand} {b.unit}
                </option>
              ))}
            </select>
          </label>
          <label className="w-28 text-xs text-ink-muted">
            Số lượng
            <input
              type="number"
              min="0"
              step="any"
              value={soLuong}
              onChange={(e) => setSoLuong(e.target.value)}
              className="mt-1 w-full rounded-control border border-line bg-surface px-2 py-1.5 text-sm text-ink"
            />
          </label>
          <button
            type="button"
            disabled={dangGui || !loId || !soLuong}
            onClick={() =>
              goi("dispense", {
                prescription_id: prescriptionId,
                drug_batch_id: loId,
                so_luong: Number(soLuong),
              })
            }
            className="rounded-control bg-brand-600 px-3 py-2 text-sm font-medium text-surface hover:bg-brand-700 disabled:opacity-50"
          >
            {dangGui ? "Đang lưu…" : "Cấp thuốc"}
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2 border-t border-line pt-3">
        <label className="flex-1 min-w-[220px] text-xs text-ink-muted">
          Lý do (bắt buộc khi khách không lấy)
          <input
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            placeholder="Khách đã có thuốc ở nhà…"
            className="mt-1 w-full rounded-control border border-line bg-surface px-2 py-1.5 text-sm text-ink"
          />
        </label>
        <button
          type="button"
          disabled={dangGui || !lyDo.trim()}
          onClick={() =>
            goi("refuse", { prescription_id: prescriptionId, ly_do: lyDo })
          }
          className="rounded-control border border-danger px-3 py-2 text-sm font-medium text-danger hover:bg-danger-bg disabled:opacity-50"
        >
          Khách không lấy
        </button>
        <button
          type="button"
          disabled={dangGui}
          onClick={() =>
            goi("close-line", {
              prescription_id: prescriptionId,
              ly_do: lyDo.trim() || null,
            })
          }
          className="rounded-control border border-line px-3 py-2 text-sm font-medium text-ink-soft hover:bg-surface-muted disabled:opacity-50"
          title="Dùng khi khách lấy một phần rồi thôi, hoặc đã cấp đủ"
        >
          Chốt — không cấp thêm
        </button>
      </div>

      {loi && (
        <p className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-xs text-danger">
          {loi}
        </p>
      )}
    </div>
  );
}
