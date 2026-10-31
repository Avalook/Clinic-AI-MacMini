"use client";

// Báo cáo kho có lối vào trong KHO; giữ lối QUẦY và URL cũ để không mất liên kết.
// `ghiDuoc` = có quyền `pharmacy.dispense` — chỉ để ẨN nút ghi; máy chủ vẫn tự kiểm quyền ở mọi lệnh.

import { useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";
import XuatBangTrongVung from "@/components/ui/XuatBangTrongVung";
import ChoGanLo, { type DongChoGanLo } from "./ChoGanLo";
import ChuyenKho from "./ChuyenKho";
import DanhMucKho, { type ThuocKho } from "./DanhMucKho";
import InventoryBoard, { type CauHinhHan, type InvBatch } from "./InventoryBoard";
import KiemKeCa from "./KiemKeCa";
import KiemKho from "./KiemKho";
import PhieuNhap from "./PhieuNhap";
import TheoDoiThuoc, { type ChonThuoc } from "./TheoDoiThuoc";
import ThuocTraChoKiem, { type DongTraChoKiem } from "./ThuocTraChoKiem";
import XuatNhapTon from "./XuatNhapTon";

type Khu = "kho" | "quay";
type Tab =
  | "bao_cao_kho" | "ton" | "nhap" | "chuyen_kho" | "theo_doi" | "danh_muc" | "kiem_kho"
  | "kiem_dau" | "kiem_cuoi" | "cho_gan_lo" | "tra_cho_kiem";

const TAB_KHO: readonly Tab[] = ["ton", "nhap", "chuyen_kho", "bao_cao_kho", "theo_doi", "danh_muc", "kiem_kho"];
const TAB_QUAY: readonly Tab[] = ["kiem_dau", "kiem_cuoi", "cho_gan_lo", "tra_cho_kiem"];
const TAB_HOP_LE: readonly Tab[] = [...TAB_KHO, ...TAB_QUAY];

/** Tên tab CŨ trong link đã lưu / link từ báo cáo hàng hoá → tab mới tương ứng. */
const TAB_CU: Record<string, Tab> = {
  "kiem_ke_ca": "kiem_cuoi",
  "phieu_nhap": "nhap",
  "the_kho": "theo_doi",
  "lich_su": "theo_doi",
  "bao_cao": "bao_cao_kho",
  "xnt": "bao_cao_kho",
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
  thuocTraChoKiem = [],
  ghiDuoc = false,
  suaGiaDuoc = false,
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
  /** Thuốc khách đã trả, chưa quyết nhập lại bán được / huỷ (17/10/2026). */
  thuocTraChoKiem?: DongTraChoKiem[];
  /** Có quyền ghi kho (`pharmacy.dispense`) — chỉ ẩn/hiện nút. */
  ghiDuoc?: boolean;
  /** `price.medicine.manage`: chỉ để khoá ô giá, máy chủ tự kiểm quyền. */
  suaGiaDuoc?: boolean;
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
  // Tab Chuyển kho: cơ sở đã tách, hoặc người được bật tách (công tắc nằm trong tab).
  const coChuyenKho = tachKhoQuay || suaTachDuoc;
  const [chonTab, setTab] = useState<Tab>(() => tabTuUrl(tabDau));
  const tab: Tab = chonTab === "chuyen_kho" && !coChuyenKho ? "ton" : chonTab;
  const [theoDoi, setTheoDoi] = useState<ChonThuoc | null>(null);
  const xemThe = (id: string) => {
    setTheoDoi({ id });
    setTab("theo_doi");
  };
  const khu = khuCua(tab);
  const canSoat = thuoc.some((t) => t.dang_dung && t.can_soat);
  const sapHet = thuoc.filter((t) => t.sap_het_hang).length;

  const mucKho = [
    { ma: "ton" as const, nhan: `Thuốc trong kho (${batches.length} lô)` },
    { ma: "nhap" as const, nhan: "Nhập thuốc" },
    ...(coChuyenKho ? [{ ma: "chuyen_kho" as const, nhan: "Chuyển kho ↔ quầy" }] : []),
    { ma: "bao_cao_kho" as const, nhan: "Báo cáo kho" },
    { ma: "theo_doi" as const, nhan: "Theo dõi thuốc" },
    {
      ma: "danh_muc" as const,
      nhan: `Danh mục & giá (${thuoc.filter((t) => t.dang_dung).length})`,
      nhac: canSoat || sapHet > 0,
    },
    { ma: "kiem_kho" as const, nhan: "Kiểm đếm kho" },
  ];
  const mucQuay = [
    { ma: "kiem_dau" as const, nhan: "Kiểm đầu ca" },
    { ma: "kiem_cuoi" as const, nhan: "Kiểm cuối ca" },
    {
      ma: "cho_gan_lo" as const,
      nhan: `Đã giao, chưa trừ kho (${choGanLo.length})`,
      nhac: choGanLo.length > 0,
    },
    {
      ma: "tra_cho_kiem" as const,
      nhan: `Thuốc trả chờ kiểm (${thuocTraChoKiem.length})`,
      nhac: thuocTraChoKiem.length > 0,
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Hai KHU là hai nút TO, tách hẳn với dãy tab nhỏ bên dưới (Tuyền 16/10). */}
      <div role="tablist" aria-label="Khu của kho thuốc" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {(
          [
            { ma: "kho" as const, nhan: "KHO", mota: "Nhập và theo dõi thuốc", nhac: false },
            { ma: "quay" as const, nhan: "QUẦY", mota: "Kiểm ca, báo cáo cuối ngày", nhac: choGanLo.length > 0 || thuocTraChoKiem.length > 0 },
          ] as const
        ).map((k) => {
          const dang = k.ma === khu;
          return (
            <button
              key={k.ma}
              type="button"
              role="tab"
              aria-selected={dang}
              onClick={() => setTab(k.ma === "kho" ? "ton" : "kiem_dau")}
              className={`flex min-h-16 flex-col items-start justify-center rounded-card px-5 py-3 text-left ring-1 ring-inset ${
                dang
                  ? "bg-brand-600 text-white ring-brand-600"
                  : "bg-surface text-ink ring-line-strong hover:bg-surface-muted"
              }`}
            >
              <span className="flex items-center gap-2 text-title font-semibold">
                {k.nhan}
                {k.nhac ? <span aria-label="có việc cần xem" className="size-2 rounded-full bg-warning" /> : null}
              </span>
              <span className={`text-meta ${dang ? "text-white/90" : "text-ink-muted"}`}>{k.mota}</span>
            </button>
          );
        })}
      </div>
      <XuatBangTrongVung
        tenTep={`kho-thuoc-${tab}`}
        thanhCongCu={khu === "kho"
          ? <ThanhTab nhan="Kho thuốc" chon={tab} onChon={setTab} muc={mucKho} />
          : <ThanhTab nhan="Quầy thuốc" chon={tab} onChon={setTab} muc={mucQuay} />}
      >
      {tab === "danh_muc" ? (
        <DanhMucKho thuoc={thuoc} ghiDuoc={ghiDuoc} suaGiaDuoc={suaGiaDuoc} onXemThe={xemThe} />
      ) : tab === "chuyen_kho" ? (
        <ChuyenKho batches={batches} tachKhoQuay={tachKhoQuay} suaTachDuoc={suaTachDuoc} ghiDuoc={ghiDuoc} />
      ) : tab === "cho_gan_lo" ? (
        <ChoGanLo dong={choGanLo} ghiDuoc={ghiDuoc} />
      ) : tab === "tra_cho_kiem" ? (
        <ThuocTraChoKiem dong={thuocTraChoKiem} ghiDuoc={ghiDuoc} />
      ) : tab === "nhap" ? (
        <PhieuNhap thuoc={thuoc} ghiDuoc={ghiDuoc} />

      ) : tab === "kiem_dau" ? (
        <KiemKeCa key={tab} batches={batches} ghiDuoc={ghiDuoc} ngayDau={ngayKiemKe} caDau={caKiemKe} loaiCoDinh="DAU" />
      ) : tab === "kiem_cuoi" ? (
        <KiemKeCa key={tab} batches={batches} ghiDuoc={ghiDuoc} ngayDau={ngayKiemKe} caDau={caKiemKe} loaiCoDinh="CUOI" />
      ) : tab === "kiem_kho" ? (
        <KiemKho batches={batches} ghiDuoc={ghiDuoc} thuoc={thuoc} tachKhoQuay={tachKhoQuay} />
      ) : tab === "theo_doi" ? (
        <TheoDoiThuoc chon={theoDoi} onChon={setTheoDoi} />
      ) : tab === "bao_cao_kho" ? (
        <XuatNhapTon onXemThe={xemThe} />
      ) : (
        <InventoryBoard batches={batches} thuoc={thuoc} ghiDuoc={ghiDuoc} onXemThe={xemThe} cauHinhHan={cauHinhHan} tachKhoQuay={tachKhoQuay} />
      )}
      </XuatBangTrongVung>
    </div>
  );
}
