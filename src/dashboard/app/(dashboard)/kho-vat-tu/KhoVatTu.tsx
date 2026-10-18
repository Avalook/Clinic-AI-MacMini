"use client";

// Điều hướng gọn: tồn kho để thao tác, lịch sử để đối chiếu, danh mục để quản lý.

import { useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";
import XuatBangTrongVung from "@/components/ui/XuatBangTrongVung";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import ChoDuyetVatTu, { type GoiChoDuyet } from "./ChoDuyetVatTu";
import DanhMucVatTu from "./DanhMucVatTu";
import DanhSachPhieuVatTu, { type PhieuVatTu } from "./DanhSachPhieuVatTu";
import TieuHaoVatTu from "./TieuHaoVatTu";
import TonVatTu, { type DongTon, type NoiChua } from "./TonVatTu";

type Tab = "ton" | "bao_cao" | "cho_duyet" | "danh_muc";

export default function KhoVatTu({
  ton,
  noiChua,
  vatTu,
  phieu,
  choDuyet,
  suaGiaDuoc,
}: {
  ton: DongTon[];
  noiChua: NoiChua[];
  vatTu: DongVatTu[];
  phieu: PhieuVatTu[];
  /** Yêu cầu nhập chờ duyệt; null = máy chủ không trả lời (tab tự báo). */
  choDuyet: GoiChoDuyet | null;
  /** Có quyền Bảng giá (`price.service.manage`) — chỉ để khoá ô sửa danh mục. */
  suaGiaDuoc: boolean;
}) {
  const [tab, setTab] = useState<Tab>("ton");
  const [mucBaoCao, setMucBaoCao] = useState<"lich_su" | "tieu_hao">("lich_su");
  const dangCho = choDuyet?.items.filter((y) => y.trang_thai === "CHO_DUYET").length ?? 0;

  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <ThanhTab
        nhan="Kho vật tư"
        chon={tab}
        onChon={setTab}
        muc={[
          { ma: "ton", nhan: "Tồn kho" },
          { ma: "bao_cao", nhan: "Lịch sử & báo cáo" },
          { ma: "cho_duyet", nhan: "Chờ duyệt", dem: dangCho > 0 ? dangCho : undefined },
          { ma: "danh_muc", nhan: "Danh mục" },
        ]}
      />
      <XuatBangTrongVung tenTep={`kho-vat-tu-${tab}`}>
        {tab === "ton" ? (
          <TonVatTu ton={ton} noiChua={noiChua} vatTu={vatTu} />
        ) : tab === "bao_cao" ? (
          <section className="space-y-3">
            <ThanhTab
              nhan="Lịch sử và báo cáo kho vật tư"
              chon={mucBaoCao}
              onChon={setMucBaoCao}
              muc={[
                { ma: "lich_su", nhan: "Lịch sử thao tác" },
                { ma: "tieu_hao", nhan: "Mức dùng theo phòng" },
              ]}
            />
            {mucBaoCao === "lich_su" ? <DanhSachPhieuVatTu ds={phieu} /> : <TieuHaoVatTu />}
          </section>
        ) : tab === "cho_duyet" ? (
          <ChoDuyetVatTu goi={choDuyet} noiChua={noiChua} />
        ) : (
          <DanhMucVatTu ds={vatTu} suaDuoc={suaGiaDuoc} />
        )}
      </XuatBangTrongVung>
    </main>
  );
}
