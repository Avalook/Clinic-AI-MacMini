"use client";

import { useState } from "react";

import Button from "@/components/ui/Button";

/** Nút "Xoá …" hỏi lại ngay tại chỗ (không hộp thoại trình duyệt). Xoá ở màn cấu
 *  trúc là ẨN khỏi mọi màn — việc đã ghi vẫn giữ cho báo cáo, khôi phục được ở
 *  mục "Đã xoá" (Tuyền 04/11/2026: "xoá hẳn đi cho sạch, dữ liệu đã ghi giữ"). */
export function XacNhanXoa({
  nhan,
  cau,
  dangLam,
  khoa,
  lyDoKhoa,
  onXoa,
}: {
  nhan: string;
  cau: string;
  dangLam: boolean;
  khoa?: boolean;
  lyDoKhoa?: string;
  onXoa: () => void;
}) {
  const [hoi, setHoi] = useState(false);
  if (!hoi) {
    return (
      <Button
        size="sm"
        variant="danger"
        disabled={dangLam || khoa}
        title={khoa ? lyDoKhoa : undefined}
        onClick={() => setHoi(true)}
      >
        {nhan}
      </Button>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-1 rounded-control bg-danger-bg px-2 py-1 text-meta text-ink">
      <span className="min-w-0 flex-1">{cau}</span>
      <Button size="sm" variant="ghost" onClick={() => setHoi(false)}>
        Thôi
      </Button>
      <Button
        size="sm"
        variant="danger"
        disabled={dangLam}
        onClick={() => {
          setHoi(false);
          onXoa();
        }}
      >
        Xoá
      </Button>
    </span>
  );
}
