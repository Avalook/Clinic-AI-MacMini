"use client";

// KHO VẬT TƯ (G8a, 14/10/2026) — màn RIÊNG, không lẫn Kho thuốc. Cùng kiểu với
// `pharmacy/inventory/KhoThuoc.tsx`: thanh tab, danh sách, nút từ `components/ui`.
// Tab: Tồn theo nơi chứa · Phiếu · Chờ duyệt (G8b) · Tiêu hao · Danh mục.
// Máy chủ quyết mọi luật; màn chỉ vẽ và gửi lệnh.

import { useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import ChoDuyetVatTu, { type GoiChoDuyet } from "./ChoDuyetVatTu";
import DanhMucVatTu from "./DanhMucVatTu";
import DanhSachPhieuVatTu, { type PhieuVatTu } from "./DanhSachPhieuVatTu";
import LapPhieuVatTu from "./LapPhieuVatTu";
import TieuHaoVatTu from "./TieuHaoVatTu";
import TonVatTu, { type DongTon, type NoiChua } from "./TonVatTu";

type Tab = "ton" | "phieu" | "cho_duyet" | "tieu_hao" | "danh_muc";

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
  const canChuY = ton.filter((t) => t.canh_bao).length;
  const dangCho = choDuyet?.items.filter((y) => y.trang_thai === "CHO_DUYET").length ?? 0;
  const chon = vatTu.map((v) => ({ id: v.id, name: v.name, don_vi: v.don_vi }));
  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <header>
        <h1 className="text-title font-semibold text-ink">Kho vật tư</h1>
        <p className="text-body text-ink-muted">
          Vật tư văn phòng phẩm và y tế, tách khỏi kho thuốc. Tồn theo kho cơ sở và từng phòng; hết
          trên sổ vẫn xuất được, kiểm đếm sau.
        </p>
      </header>
      <ThanhTab
        nhan="Kho vật tư"
        chon={tab}
        onChon={setTab}
        muc={[
          { ma: "ton", nhan: "Tồn theo nơi chứa", dem: canChuY > 0 ? canChuY : undefined },
          { ma: "phieu", nhan: "Phiếu" },
          { ma: "cho_duyet", nhan: "Chờ duyệt", dem: dangCho > 0 ? dangCho : undefined },
          { ma: "tieu_hao", nhan: "Tiêu hao" },
          { ma: "danh_muc", nhan: `Danh mục (${vatTu.length})` },
        ]}
      />
      {tab === "danh_muc" ? (
        <DanhMucVatTu ds={vatTu} suaDuoc={suaGiaDuoc} />
      ) : tab === "tieu_hao" ? (
        <TieuHaoVatTu />
      ) : tab === "cho_duyet" ? (
        <ChoDuyetVatTu goi={choDuyet} noiChua={noiChua} />
      ) : tab === "phieu" ? (
        <div className="flex flex-col gap-4">
          <LapPhieuVatTu noiChua={noiChua} vatTu={chon} xemChoDuyet={() => setTab("cho_duyet")} />
          <DanhSachPhieuVatTu ds={phieu} />
        </div>
      ) : (
        <TonVatTu ton={ton} noiChua={noiChua} vatTu={chon} />
      )}
    </main>
  );
}
