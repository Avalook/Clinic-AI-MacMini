"use client";

// Tab DANH MỤC của Kho vật tư (G8a, 14/10/2026). Cùng MỘT nguồn với ngăn "Vật tư
// bán thêm" ở Bảng giá (`cashier/VatTuBangGia.tsx`): tên, loại, kinh doanh / không
// kinh doanh (chỉ PHÂN LOẠI — không chặn bán), giá bán, giá nhập, đơn vị. Ghi qua
// `PATCH /api/service-price` (cùng quyền Bảng giá); sửa ở đâu cũng thấy ở đó ngay.
// Mức tối thiểu là của TỪNG nơi chứa nên nằm ở tab "Tồn theo nơi chứa".
// Đầu tab có khối "Đặt cho cả loại" (`DatCoTheoLoai.tsx`): đặt một cờ cho cả loại VPP / VTYT.

import { useRouter } from "next/navigation";
import { useState } from "react";

import VatTuBangGia, { type DongVatTu } from "../cashier/VatTuBangGia";
import DatCoTheoLoai from "./DatCoTheoLoai";

export default function DanhMucVatTu({ ds, suaDuoc }: { ds: DongVatTu[]; suaDuoc: boolean }) {
  const router = useRouter();
  const [ban, setBan] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  async function sua(id: string, patch: Record<string, unknown>, xong: string): Promise<boolean> {
    setBan(true);
    setLoi(null);
    setBao(null);
    try {
      const r = await fetch("/api/service-price", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, ...patch }),
      });
      if (!r.ok) {
        const kq = (await r.json().catch(() => null)) as { error?: string; detail?: string } | null;
        setLoi(kq?.error ?? kq?.detail ?? "Không lưu được — thử lại.");
        return false;
      }
      setBao(xong);
      router.refresh();
      return true;
    } catch {
      setLoi("Không kết nối được máy chủ — chưa lưu.");
      return false;
    } finally {
      setBan(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {suaDuoc ? null : (
        <p className="text-meta text-ink-muted">
          Bạn xem được danh mục; muốn sửa cần bật khối “Bảng giá dịch vụ” ở màn Phân quyền.
        </p>
      )}
      {suaDuoc ? <DatCoTheoLoai ds={ds} /> : null}
      <VatTuBangGia ds={ds} ban={ban || !suaDuoc} onSua={sua} />
      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      {bao ? (
        <p role="status" className="text-body text-success">
          {bao}
        </p>
      ) : null}
    </div>
  );
}
