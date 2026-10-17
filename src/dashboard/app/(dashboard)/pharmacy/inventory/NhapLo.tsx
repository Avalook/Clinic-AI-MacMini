"use client";

// Nhập lô thuốc vào kho (Tuyền 25/09/2026: "lô thuốc, ngày nhập xuất, kho để
// họ tự fill"). Gọi lệnh có sẵn `receive` → `POST /api/v1/pharmacy/receive`:
// số lô và đơn vị bắt buộc; hạn có thể bổ sung sau. Tồn
// cộng qua sổ kho (trigger), không cộng tay.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { INPUT, LABEL } from "../../form-ui";
import type { ThuocKho } from "./DanhMucKho";
import { guiKho } from "./gui-kho";
import OQuetMa, { type KetQuaQuet } from "./OQuetMa";
import QuyDoiNhap from "./QuyDoiNhap";

const TRONG = { ten: "", so_lo: "", han: "", so_luong: "", don_vi: "", gia_nhap: "", ghi_chu: "" };

export default function NhapLo({
  thuoc,
  onXong,
  ghiDuoc = true,
}: {
  thuoc: ThuocKho[];
  onXong: () => void;
  ghiDuoc?: boolean;
}) {
  const router = useRouter();
  const [f, setF] = useState(TRONG);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // Nhập khác đơn vị bán: 1 <đơn vị nhập> = heSo đơn vị bán (xem QuyDoiNhap).
  const [heSo, setHeSo] = useState("");
  const [xacNhanHeSo, setXacNhanHeSo] = useState(false);

  const dangDung = thuoc.filter((t) => t.dang_dung);
  const chon = dangDung.find((t) => t.ten === f.ten) ?? null;

  const doiTen = (ten: string) => {
    const t = dangDung.find((x) => x.ten === ten);
    // Chọn đúng thuốc → điền sẵn đơn vị lô đang có (29/09), chưa có lô thì đơn vị bán.
    setF((cu) => ({ ...cu, ten, don_vi: t && !cu.don_vi ? (t.don_vi_lo?.[0] ?? t.don_vi_ban ?? "") : cu.don_vi }));
  };

  const [baoQuet, setBaoQuet] = useState<string | null>(null);

  // Quét hộp / tem → điền sẵn thuốc; mã vuông GS1 điền thêm số lô + hạn. Chỉ
  // ĐIỀN SẴN — người bấm "Nhập vào kho" mới ghi.
  const khiQuet = (kq: KetQuaQuet) => {
    setBaoQuet(null);
    if (kq.loai !== "thuoc" && kq.loai !== "tem") return;
    const id = kq.loai === "thuoc" ? kq.thuoc.id : kq.lo.drug_catalog_id;
    const t = dangDung.find((x) => x.id === id);
    if (!t) {
      setBaoQuet("Thuốc này đang tắt trong danh mục — bật lại ở Danh mục thuốc trước khi nhập.");
      return;
    }
    doiTen(t.ten);
    if (kq.loai === "tem") {
      setF((cu) => ({ ...cu, ten: t.ten, so_lo: kq.lo.batch_code, han: kq.lo.expiry_date ?? cu.han, don_vi: kq.lo.unit }));
      setBaoQuet(`Tem lô ${kq.lo.batch_code}: nhập thêm vào đúng lô này.`);
    } else if (kq.gs1) {
      setF((cu) => ({ ...cu, ten: t.ten, so_lo: kq.gs1?.so_lo ?? cu.so_lo, han: kq.gs1?.han ?? cu.han }));
    }
  };

  const luu = async () => {
    if (!chon) {
      setLoi("Chọn thuốc có trong danh mục (gõ rồi chọn trong danh sách).");
      return;
    }
    setDang(true);
    setLoi(null);
    const kq = await guiKho("receive", {
      drug_catalog_id: chon.id,
      batch_code: f.so_lo.trim(),
      expiry_date: f.han || null,
      so_luong: f.so_luong.trim(),
      unit: f.don_vi.trim(),
      cost_price: f.gia_nhap.trim() === "" ? null : f.gia_nhap.trim(),
      ly_do: f.ghi_chu.trim() || null,
      he_so: heSo.trim() || null,
      xac_nhan_he_so: xacNhanHeSo,
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setF(TRONG);
    onXong();
    router.refresh();
  };

  const o = (ma: keyof typeof TRONG, nhan: string, kieu = "text") => (
    <label className="block">
      <span className={LABEL}>{nhan}</span>
      <input
        type={kieu}
        value={f[ma]}
        inputMode={kieu === "text" && ["so_luong", "gia_nhap"].includes(ma) ? "decimal" : undefined}
        onChange={(e) => setF({ ...f, [ma]: e.target.value })}
        className={INPUT}
      />
    </label>
  );

  return (
    <section
      aria-label="Nhập lô thuốc"
      className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card"
    >
      <h3 className="text-title text-ink">Nhập lô thuốc</h3>
      <OQuetMa
        thuoc={dangDung.map((t) => ({ id: t.id, ten: t.ten }))}
        ghiDuoc={ghiDuoc}
        onKetQua={khiQuet}
      />
      {baoQuet ? (
        <p role="status" className="text-meta text-ink-soft">
          {baoQuet}
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block sm:col-span-2">
          <span className={LABEL}>Thuốc</span>
          <input
            list="kho-thuoc-dang-dung"
            value={f.ten}
            onChange={(e) => doiTen(e.target.value)}
            placeholder="Gõ tên thuốc…"
            className={INPUT}
          />
          <datalist id="kho-thuoc-dang-dung">
            {dangDung.map((t) => (
              <option key={t.id} value={t.ten} />
            ))}
          </datalist>
        </label>
        {o("so_lo", "Số lô")}
        {o("han", "Hạn dùng (có thể nhập sau)", "date")}
        {o("so_luong", "Số lượng nhập")}
        {o("don_vi", "Đơn vị")}
        {o("gia_nhap", "Giá nhập (đ / đơn vị)")}
        {o("ghi_chu", "Ghi chú (nhà cung cấp, số hoá đơn…)")}
      </div>
      <QuyDoiNhap
        ma="nhap-lo"
        idThuoc={chon?.id}
        donVi={f.don_vi}
        soLuong={f.so_luong}
        heSo={heSo}
        xacNhan={xacNhanHeSo}
        onHeSo={setHeSo}
        onXacNhan={setXacNhanHeSo}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="primary"
          disabled={dang || !f.ten || !f.so_lo.trim() || !f.so_luong.trim() || !f.don_vi.trim()}
          onClick={() => void luu()}
        >
          {dang ? "Đang nhập…" : "Nhập vào kho"}
        </Button>
        <Button type="button" variant="ghost" onClick={onXong}>
          Thôi
        </Button>
        {loi ? (
          <p role="alert" className="text-meta text-danger">
            {loi}
          </p>
        ) : null}
      </div>
    </section>
  );
}
