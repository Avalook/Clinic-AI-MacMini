"use client";

// Kho thuốc — hai tab (Tuyền 25/09/2026): DANH MỤC (tên, giá, hướng dẫn — nạp
// sẵn theo KiotViet) và TỒN THEO LÔ (nhà thuốc tự nhập lô, điều chỉnh, huỷ).
// 29/09/2026 (kho kiểu KiotViet): thêm PHIẾU NHẬP, KIỂM KHO, THẺ KHO, XUẤT
// NHẬP TỒN. `ghiDuoc` = có quyền `pharmacy.dispense` — chỉ để ẨN nút ghi;
// máy chủ vẫn tự kiểm quyền ở mọi lệnh.

import { useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";
import KhachMuaThuoc from "../KhachMuaThuoc";
import ChoGanLo, { type DongChoGanLo } from "./ChoGanLo";
import DanhMucKho, { type ThuocKho } from "./DanhMucKho";
import InventoryBoard, { type InvBatch } from "./InventoryBoard";
import KiemKho from "./KiemKho";
import PhieuNhap from "./PhieuNhap";
import TheKho from "./TheKho";
import XuatNhapTon from "./XuatNhapTon";

type Tab = "danh_muc" | "ton" | "cho_gan_lo" | "phieu_nhap" | "kiem_kho" | "the_kho" | "xnt";

export default function KhoThuoc({
  batches,
  thuoc,
  choGanLo = [],
  ghiDuoc = false,
  moBanLe = false,
}: {
  batches: InvBatch[];
  thuoc: ThuocKho[];
  /** Thuốc đã giao chưa gán lô (giao không lô, 28/09/2026). */
  choGanLo?: DongChoGanLo[];
  /** Có quyền ghi kho (`pharmacy.dispense`) — chỉ ẩn/hiện nút. */
  ghiDuoc?: boolean;
  /** V8: được mở lượt "Khách mua thuốc" — máy chủ quyết (lego nhà thuốc / thu tiền). */
  moBanLe?: boolean;
}) {
  const [tab, setTab] = useState<Tab>("danh_muc");
  const [theKhoId, setTheKhoId] = useState<string | null>(null);
  const xemThe = (id: string) => {
    setTheKhoId(id);
    setTab("the_kho");
  };
  const canSoat = thuoc.some((t) => t.dang_dung && (t.can_soat || !t.cach_dung));
  const sapHet = thuoc.filter((t) => t.sap_het_hang).length;
  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Khách chỉ đến mua thuốc (V8): mở lượt bán lẻ rồi sang Nhà thuốc kê + thu. */}
      {moBanLe ? (
        <div className="flex flex-wrap items-start gap-2">
          <KhachMuaThuoc sangNhaThuoc />
        </div>
      ) : null}
      <ThanhTab
        nhan="Kho thuốc"
        chon={tab}
        onChon={setTab}
        muc={[
          {
            ma: "danh_muc",
            nhan: `Danh mục thuốc (${thuoc.filter((t) => t.dang_dung).length})`,
            nhac: canSoat || sapHet > 0,
          },
          { ma: "ton", nhan: `Tồn theo lô (${batches.length})` },
          {
            ma: "cho_gan_lo",
            nhan: `Chờ gán lô (${choGanLo.length})`,
            nhac: choGanLo.length > 0,
          },
          { ma: "phieu_nhap", nhan: "Phiếu nhập" },
          { ma: "kiem_kho", nhan: "Kiểm kho" },
          { ma: "the_kho", nhan: "Thẻ kho" },
          { ma: "xnt", nhan: "Xuất nhập tồn" },
        ]}
      />
      {tab === "danh_muc" ? (
        <DanhMucKho thuoc={thuoc} ghiDuoc={ghiDuoc} onXemThe={xemThe} />
      ) : tab === "cho_gan_lo" ? (
        <ChoGanLo dong={choGanLo} />
      ) : tab === "phieu_nhap" ? (
        <PhieuNhap thuoc={thuoc} ghiDuoc={ghiDuoc} />
      ) : tab === "kiem_kho" ? (
        <KiemKho batches={batches} ghiDuoc={ghiDuoc} />
      ) : tab === "the_kho" ? (
        <TheKho thuoc={thuoc} chonId={theKhoId} onChon={setTheKhoId} />
      ) : tab === "xnt" ? (
        <XuatNhapTon onXemThe={xemThe} />
      ) : (
        <InventoryBoard batches={batches} thuoc={thuoc} ghiDuoc={ghiDuoc} onXemThe={xemThe} />
      )}
    </div>
  );
}
