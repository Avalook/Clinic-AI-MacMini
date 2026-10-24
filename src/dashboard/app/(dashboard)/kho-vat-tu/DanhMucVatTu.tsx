"use client";

// Tab DANH MỤC của Kho vật tư (G8a, 14/10/2026). Cùng MỘT nguồn với ngăn "Vật tư
// bán thêm" ở Bảng giá (`cashier/VatTuBangGia.tsx`): tên, loại, kinh doanh / không
// kinh doanh (chỉ PHÂN LOẠI — không chặn bán), giá bán, giá nhập, đơn vị. Ghi qua
// `PATCH /api/service-price` (cùng quyền Bảng giá); sửa ở đâu cũng thấy ở đó ngay.
// Mức tối thiểu là của TỪNG nơi chứa nên nằm ở tab "Tồn theo nơi chứa".
// Đầu tab có khối "Đặt cho cả loại" (`DatCoTheoLoai.tsx`): đặt một cờ cho cả loại VPP / VTYT.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import VatTuBangGia, { type DongVatTu } from "../cashier/VatTuBangGia";
import DatCoTheoLoai from "./DatCoTheoLoai";

export default function DanhMucVatTu({
  ds,
  suaDuoc,
  laQuanLy,
}: {
  ds: DongVatTu[];
  suaDuoc: boolean;
  laQuanLy: boolean;
}) {
  const router = useRouter();
  const [ban, setBan] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [moThem, setMoThem] = useState(false);
  const [tenMoi, setTenMoi] = useState("");
  const [loaiMoi, setLoaiMoi] = useState<"VPP" | "VTYT">("VTYT");
  const [donViMoi, setDonViMoi] = useState("");
  const [maVachMoi, setMaVachMoi] = useState("");
  const [giaNhapMoi, setGiaNhapMoi] = useState("");
  const [giaBanMoi, setGiaBanMoi] = useState("");
  const [kinhDoanhMoi, setKinhDoanhMoi] = useState(false);
  const [duyetBanMoi, setDuyetBanMoi] = useState(false);
  const [duyetNhapMoi, setDuyetNhapMoi] = useState(false);

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

  async function themVatTu() {
    setBan(true);
    setLoi(null);
    setBao(null);
    try {
      const r = await fetch("/api/service-price", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
          name: tenMoi.trim(),
          group: "vat_tu",
          don_vi: donViMoi.trim() || null,
          ma_vach: maVachMoi.trim() || null,
          gia_nhap: giaNhapMoi.trim() || null,
          unit_price: giaBanMoi.trim() || null,
          ...(laQuanLy
            ? {
                loai_vat_tu: loaiMoi,
                kinh_doanh: kinhDoanhMoi,
                can_ql_duyet: duyetBanMoi,
                can_duyet_nhap: duyetNhapMoi,
              }
            : {}),
        }),
      });
      if (!r.ok) {
        const kq = (await r.json().catch(() => null)) as { error?: string; detail?: string } | null;
        setLoi(kq?.error ?? kq?.detail ?? "Không thêm được vật tư — thử lại.");
        return;
      }
      setBao(`Đã thêm “${tenMoi.trim()}” vào danh mục. Giờ có thể nhập hàng hoặc bổ sung vào phòng.`);
      setTenMoi("");
      setDonViMoi("");
      setMaVachMoi("");
      setGiaNhapMoi("");
      setGiaBanMoi("");
      setMoThem(false);
      router.refresh();
    } catch {
      setLoi("Không kết nối được máy chủ — vật tư chưa được thêm.");
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
      {suaDuoc && laQuanLy ? <DatCoTheoLoai ds={ds} /> : null}
      {suaDuoc ? (
        <section className="rounded-card border border-line bg-surface p-3 shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-emph font-semibold">Thêm vật tư vào danh mục</h2>
              <p className="text-meta text-ink-muted">Tạo mặt hàng trước, sau đó ghi nhận số lượng ở Tồn kho.</p>
            </div>
            <Button type="button" variant={moThem ? "secondary" : "primary"} onClick={() => setMoThem((m) => !m)}>
              {moThem ? "Đóng" : "+ Thêm vật tư"}
            </Button>
          </div>
          {moThem ? (
            <div className="mt-3 grid grid-cols-1 gap-3 rounded-control bg-surface-muted p-3 sm:grid-cols-2 xl:grid-cols-4">
              <label className="block sm:col-span-2">
                <span className="mb-1 block text-meta text-ink-soft">Tên vật tư</span>
                <ONhap value={tenMoi} maxLength={300} onChange={(e) => setTenMoi(e.target.value)} placeholder="Ví dụ: Găng tay khám size M" className="w-full" />
              </label>
              {laQuanLy ? (
                <label className="block">
                  <span className="mb-1 block text-meta text-ink-soft">Nhóm</span>
                  <OChon value={loaiMoi} onChange={(e) => setLoaiMoi(e.target.value as "VPP" | "VTYT")} className="w-full">
                    <option value="VTYT">Vật tư y tế</option>
                    <option value="VPP">Văn phòng phẩm</option>
                  </OChon>
                </label>
              ) : null}
              <label className="block">
                <span className="mb-1 block text-meta text-ink-soft">Đơn vị tính</span>
                <ONhap value={donViMoi} maxLength={40} onChange={(e) => setDonViMoi(e.target.value)} placeholder="hộp, cái, đôi…" className="w-full" />
              </label>
              <label className="block">
                <span className="mb-1 block text-meta text-ink-soft">Mã vạch</span>
                <ONhap value={maVachMoi} maxLength={120} onChange={(e) => setMaVachMoi(e.target.value)} placeholder="Tuỳ chọn" className="w-full" />
              </label>
              <label className="block">
                <span className="mb-1 block text-meta text-ink-soft">Giá nhập một đơn vị (₫)</span>
                <ONhap inputMode="numeric" value={giaNhapMoi} onChange={(e) => setGiaNhapMoi(e.target.value)} placeholder="Tuỳ chọn" className="w-full" />
              </label>
              <label className="block">
                <span className="mb-1 block text-meta text-ink-soft">Giá bán thêm (₫)</span>
                <ONhap inputMode="numeric" value={giaBanMoi} onChange={(e) => setGiaBanMoi(e.target.value)} placeholder="Để trống nếu không bán" className="w-full" />
              </label>
              {laQuanLy ? (
                <fieldset className="flex flex-wrap gap-x-4 gap-y-2 text-meta text-ink-soft sm:col-span-2 xl:col-span-4">
                  <legend className="mb-1">Phân loại và phê duyệt</legend>
                  <label className="flex items-center gap-2"><input type="checkbox" checked={kinhDoanhMoi} onChange={(e) => setKinhDoanhMoi(e.target.checked)} /> Được phép kinh doanh</label>
                  <label className="flex items-center gap-2"><input type="checkbox" checked={duyetBanMoi} onChange={(e) => setDuyetBanMoi(e.target.checked)} /> Cần quản lý duyệt bán</label>
                  <label className="flex items-center gap-2"><input type="checkbox" checked={duyetNhapMoi} onChange={(e) => setDuyetNhapMoi(e.target.checked)} /> Cần quản lý duyệt nhập</label>
                </fieldset>
              ) : null}
              <div className="flex flex-wrap items-center gap-2 sm:col-span-2 xl:col-span-4">
                <Button type="button" variant="primary" disabled={ban || !tenMoi.trim()} onClick={() => void themVatTu()}>
                  {ban ? "Đang lưu…" : "Thêm vào danh mục"}
                </Button>
                <span className="text-meta text-ink-muted">Mặt hàng đã có phát sinh sẽ được tạm ngưng, không xoá khỏi lịch sử.</span>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
      <VatTuBangGia ds={ds} ban={ban || !suaDuoc} laQuanLy={laQuanLy} onSua={sua} />
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
