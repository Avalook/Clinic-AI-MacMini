"use client";

// Nút mở màn XEM LẠI một lượt khám (chỉ đọc, máy chủ cắt nội dung theo vai).
// Tách riêng để màn nào cũng gắn được một dòng, không phải tự giữ state.

import { useState } from "react";

import Button from "@/components/ui/Button";

import XemLuot from "./XemLuot";

export default function NutXemLuot({
  visitId,
  nhan = "Xem hành trình",
}: {
  visitId: string;
  nhan?: string;
}) {
  const [mo, setMo] = useState(false);
  return (
    <>
      <Button size="sm" variant="ghost" className="-ml-3" onClick={() => setMo(true)}>
        {nhan}
      </Button>
      {mo ? <XemLuot visitId={visitId} onDong={() => setMo(false)} /> : null}
    </>
  );
}
