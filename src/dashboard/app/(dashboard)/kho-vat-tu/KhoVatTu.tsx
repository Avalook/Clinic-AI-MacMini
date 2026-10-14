"use client";

// KHO VẬT TƯ (G8a, 14/10/2026) — màn RIÊNG, không lẫn Kho thuốc. Cùng kiểu với
// `pharmacy/inventory/KhoThuoc.tsx`: thanh tab, danh sách, nút từ `components/ui`.
// Tab: Danh mục · Tồn theo nơi chứa (· Phiếu · Tiêu hao — các lát sau).
// Máy chủ quyết mọi luật; màn chỉ vẽ và gửi lệnh.

import { useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import DanhMucVatTu from "./DanhMucVatTu";
import TonVatTu, { type DongTon, type NoiChua } from "./TonVatTu";

type Tab = "ton" | "danh_muc";

export default function KhoVatTu({
  ton,
  noiChua,
  vatTu,
  suaGiaDuoc,
}: {
  ton: DongTon[];
  noiChua: NoiChua[];
  vatTu: DongVatTu[];
  /** Có quyền Bảng giá (`price.service.manage`) — chỉ để khoá ô sửa danh mục. */
  suaGiaDuoc: boolean;
}) {
  const [tab, setTab] = useState<Tab>("ton");
  const canChuY = ton.filter((t) => t.canh_bao).length;
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
          { ma: "danh_muc", nhan: `Danh mục (${vatTu.length})` },
        ]}
      />
      {tab === "danh_muc" ? (
        <DanhMucVatTu ds={vatTu} suaDuoc={suaGiaDuoc} />
      ) : (
        <TonVatTu ton={ton} noiChua={noiChua} vatTu={vatTu.map((v) => ({ id: v.id, name: v.name }))} />
      )}
    </main>
  );
}
