"use client";

// Kho thuốc — hai khu (Tuyền 16/10/2026, sau bản demo bấm thử):
//   KHO   : Thuốc trong kho · Nhập thuốc · Lịch sử kho · Danh mục & giá · Kiểm đếm kho
//           (· Chuyển ra quầy — chỉ khi cơ sở bật tách kho/quầy hoặc người quản lý cần bật)
//   QUẦY  : Kiểm đầu ca · Kiểm cuối ca · Báo cáo cuối ngày · Đã giao, chưa trừ kho
// Đổi TÊN và gom nhóm cho dễ hiểu; mỗi tab vẫn là component cũ (không đổi luật kho / tiền).
// `ghiDuoc` = có quyền `pharmacy.dispense` — chỉ để ẨN nút ghi; máy chủ vẫn tự kiểm quyền ở mọi lệnh.

import Link from "next/link";
import { useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";
import KhachMuaThuoc from "../KhachMuaThuoc";
import ChoGanLo, { type DongChoGanLo } from "./ChoGanLo";
import ChuyenKho from "./ChuyenKho";
import DanhMucKho, { type ThuocKho } from "./DanhMucKho";
import InventoryBoard, { type CauHinhHan, type InvBatch } from "./InventoryBoard";
import KiemKeCa from "./KiemKeCa";
import KiemKho from "./KiemKho";
import PhieuNhap from "./PhieuNhap";
import TheKho from "./TheKho";
import XuatNhapTon from "./XuatNhapTon";

type Khu = "kho" | "quay";
type Tab =
  | "ton" | "nhap" | "lich_su" | "danh_muc" | "kiem_kho" | "chuyen_kho"
  | "kiem_dau" | "kiem_cuoi" | "bao_cao" | "cho_gan_lo";

const TAB_KHO: readonly Tab[] = ["ton", "nhap", "lich_su", "danh_muc", "kiem_kho", "chuyen_kho"];
const TAB_QUAY: readonly Tab[] = ["kiem_dau", "kiem_cuoi", "bao_cao", "cho_gan_lo"];
const TAB_HOP_LE: readonly Tab[] = [...TAB_KHO, ...TAB_QUAY];

/** Tên tab CŨ trong link đã lưu / link từ báo cáo hàng hoá → tab mới tương ứng. */
const TAB_CU: Record<string, Tab> = {
  "kiem_ke_ca": "kiem_cuoi",
  "phieu_nhap": "nhap",
  "the_kho": "lich_su",
  "xnt": "bao_cao",
};

const khuCua = (t: Tab): Khu => (TAB_QUAY.includes(t) ? "quay" : "kho");

/** `?tab=kiem-ke-ca` → "kiem_cuoi"; mã lạ / thiếu → "ton" (không ném). */
function tabTuUrl(tab?: string): Tab {
  const ma = (tab ?? "").replace(/-/g, "_");
  return TAB_CU[ma] ?? TAB_HOP_LE.find((t) => t === ma) ?? "ton";
}

export default function KhoThuoc({
  batches,
  thuoc,
  choGanLo = [],
  ghiDuoc = false,
  moBanLe = false,
  cauHinhHan,
  tachKhoQuay = false,
  suaTachDuoc = false,
  tabDau,
  ngayKiemKe,
  caKiemKe,
}: {
  batches: InvBatch[];
  thuoc: ThuocKho[];
  /** Thuốc đã giao chưa gán lô (giao không lô, 28/09/2026). */
  choGanLo?: DongChoGanLo[];
  /** Có quyền ghi kho (`pharmacy.dispense`) — chỉ ẩn/hiện nút. */
  ghiDuoc?: boolean;
  /** V8: được mở lượt "Khách mua thuốc" — máy chủ quyết (lego nhà thuốc / thu tiền). */
  moBanLe?: boolean;
  cauHinhHan?: CauHinhHan;
  /** G7: cơ sở bật tách kho / quầy (mặc định tắt = một kho như cũ). */
  tachKhoQuay?: boolean;
  /** G7: được bật / tắt tách (`config.clinic.manage`) — chỉ ẩn / hiện nút. */
  suaTachDuoc?: boolean;
  /** `?tab=` của URL — link từ báo cáo hàng hoá mở thẳng tab Kiểm cuối ca. */
  tabDau?: string;
  /** `?ngay=` / `?ca=` đã kiểm dạng ở trang — chỉ để KiemKeCa mở đúng ngày / ca. */
  ngayKiemKe?: string;
  caKiemKe?: "SANG" | "CHIEU" | "TOI";
}) {
  const [tab, setTab] = useState<Tab>(() => tabTuUrl(tabDau));
  const [theKhoId, setTheKhoId] = useState<string | null>(null);
  const xemThe = (id: string) => {
    setTheKhoId(id);
    setTab("lich_su");
  };
  const khu = khuCua(tab);
  const canSoat = thuoc.some((t) => t.dang_dung && (t.can_soat || !t.cach_dung));
  const sapHet = thuoc.filter((t) => t.sap_het_hang).length;
  // Chuyển kho → quầy KHÔNG bắt buộc: chỉ hiện khi cơ sở đã bật tách hoặc người quản lý có
  // quyền bật (nút bật nằm trong chính tab ấy). Còn lại quầy bán thẳng từ kho.
  const hienChuyen = tachKhoQuay || suaTachDuoc;

  const mucKho = [
    { ma: "ton" as const, nhan: `Thuốc trong kho (${batches.length} lô)` },
    { ma: "nhap" as const, nhan: "Nhập thuốc" },
    { ma: "lich_su" as const, nhan: "Lịch sử kho" },
    {
      ma: "danh_muc" as const,
      nhan: `Danh mục & giá (${thuoc.filter((t) => t.dang_dung).length})`,
      nhac: canSoat || sapHet > 0,
    },
    { ma: "kiem_kho" as const, nhan: "Kiểm đếm kho" },
    ...(hienChuyen ? [{ ma: "chuyen_kho" as const, nhan: "Chuyển ra quầy (tuỳ chọn)" }] : []),
  ];
  const mucQuay = [
    { ma: "kiem_dau" as const, nhan: "Kiểm đầu ca" },
    { ma: "kiem_cuoi" as const, nhan: "Kiểm cuối ca" },
    { ma: "bao_cao" as const, nhan: "Báo cáo cuối ngày" },
    {
      ma: "cho_gan_lo" as const,
      nhan: `Đã giao, chưa trừ kho (${choGanLo.length})`,
      nhac: choGanLo.length > 0,
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Khách chỉ đến mua thuốc (V8): mở lượt bán lẻ rồi sang Nhà thuốc kê + thu. */}
      {moBanLe ? (
        <div className="flex flex-wrap items-start gap-2">
          <KhachMuaThuoc sangNhaThuoc />
        </div>
      ) : null}
      <ThanhTab
        nhan="Khu của kho thuốc"
        chon={khu}
        onChon={(k) => setTab(k === "kho" ? "ton" : "kiem_dau")}
        muc={[
          { ma: "kho", nhan: "KHO — nhập và theo dõi thuốc" },
          { ma: "quay", nhan: "QUẦY — kiểm ca, báo cáo", nhac: choGanLo.length > 0 },
        ]}
      />
      {khu === "kho" ? (
        <ThanhTab nhan="Kho thuốc" chon={tab} onChon={setTab} muc={mucKho} />
      ) : (
        <ThanhTab nhan="Quầy thuốc" chon={tab} onChon={setTab} muc={mucQuay} />
      )}

      {tab === "danh_muc" ? (
        <DanhMucKho thuoc={thuoc} ghiDuoc={ghiDuoc} onXemThe={xemThe} />
      ) : tab === "cho_gan_lo" ? (
        <ChoGanLo dong={choGanLo} />
      ) : tab === "nhap" ? (
        <PhieuNhap thuoc={thuoc} ghiDuoc={ghiDuoc} />
      ) : tab === "chuyen_kho" ? (
        <ChuyenKho batches={batches} tachKhoQuay={tachKhoQuay} suaTachDuoc={suaTachDuoc} ghiDuoc={ghiDuoc} />
      ) : tab === "kiem_dau" ? (
        <KiemKeCa batches={batches} ghiDuoc={ghiDuoc} ngayDau={ngayKiemKe} caDau={caKiemKe} loaiCoDinh="DAU" />
      ) : tab === "kiem_cuoi" ? (
        <KiemKeCa batches={batches} ghiDuoc={ghiDuoc} ngayDau={ngayKiemKe} caDau={caKiemKe} loaiCoDinh="CUOI" />
      ) : tab === "kiem_kho" ? (
        <KiemKho batches={batches} ghiDuoc={ghiDuoc} thuoc={thuoc} />
      ) : tab === "lich_su" ? (
        <TheKho thuoc={thuoc} chonId={theKhoId} onChon={setTheKhoId} />
      ) : tab === "bao_cao" ? (
        <div className="flex flex-col gap-3">
          <p className="text-body text-ink-soft">
            Số thuốc vào – ra – còn theo khoảng ngày (tồn đầu, nhập, bán, điều chỉnh, huỷ, khách trả, tồn cuối).
            Báo cáo cả ngày kèm doanh thu từng thuốc ở{" "}
            <Link href="/reports?tab=hang-hoa" className="text-brand-700 underline">
              Báo cáo → Hàng hoá
            </Link>
            .
          </p>
          <XuatNhapTon onXemThe={xemThe} />
        </div>
      ) : (
        <InventoryBoard batches={batches} thuoc={thuoc} ghiDuoc={ghiDuoc} onXemThe={xemThe} cauHinhHan={cauHinhHan} tachKhoQuay={tachKhoQuay} />
      )}
    </div>
  );
}
