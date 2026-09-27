"use client";

// Nút mở màn XEM LẠI một lượt khám (chỉ đọc, máy chủ cắt nội dung theo vai).
// Tách riêng để màn nào cũng gắn được một dòng, không phải tự giữ state.

import { useState } from "react";

import Button, { type ButtonVariant } from "@/components/ui/Button";

import XemLuot from "./XemLuot";

export default function NutXemLuot({
  visitId,
  nhan = "Xem hành trình",
  variant = "ghost",
}: {
  visitId: string;
  nhan?: string;
  /** Mặc định nút chữ (ghost, lề âm để thẳng hàng chữ bên trên). Danh sách
   *  Tiếp đón (27/09 đợt 3) dùng `secondary` — nút viền đứng cạnh Check-out. */
  variant?: ButtonVariant;
}) {
  const [mo, setMo] = useState(false);
  return (
    <>
      <Button
        size="sm"
        variant={variant}
        className={variant === "ghost" ? "-ml-3" : ""}
        onClick={() => setMo(true)}
      >
        {nhan}
      </Button>
      {mo ? <XemLuot visitId={visitId} onDong={() => setMo(false)} /> : null}
    </>
  );
}
