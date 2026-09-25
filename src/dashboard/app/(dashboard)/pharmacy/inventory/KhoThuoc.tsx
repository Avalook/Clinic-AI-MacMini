"use client";

// Kho thuốc — hai tab (Tuyền 25/09/2026): DANH MỤC (tên, giá, hướng dẫn — nạp
// sẵn theo KiotViet) và TỒN THEO LÔ (nhà thuốc tự nhập lô, điều chỉnh, huỷ).

import { useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";
import DanhMucKho, { type ThuocKho } from "./DanhMucKho";
import InventoryBoard, { type InvBatch } from "./InventoryBoard";

type Tab = "danh_muc" | "ton";

export default function KhoThuoc({
  batches,
  thuoc,
}: {
  batches: InvBatch[];
  thuoc: ThuocKho[];
}) {
  const [tab, setTab] = useState<Tab>("danh_muc");
  const canSoat = thuoc.some((t) => t.dang_dung && (t.can_soat || !t.cach_dung));
  return (
    <div className="flex flex-col gap-4 p-4">
      <ThanhTab
        nhan="Kho thuốc"
        chon={tab}
        onChon={setTab}
        muc={[
          { ma: "danh_muc", nhan: `Danh mục thuốc (${thuoc.filter((t) => t.dang_dung).length})`, nhac: canSoat },
          { ma: "ton", nhan: `Tồn theo lô (${batches.length})` },
        ]}
      />
      {tab === "danh_muc" ? (
        <DanhMucKho thuoc={thuoc} />
      ) : (
        <InventoryBoard batches={batches} thuoc={thuoc} />
      )}
    </div>
  );
}
