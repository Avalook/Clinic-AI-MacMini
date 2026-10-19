"use client";

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

const O_NHAP =
  "h-8 rounded-control border border-line bg-surface px-2 text-meta text-ink";

export function ViTriEditor({
  viTri,
  dangLam,
  onDoi,
}: {
  viTri: { ten: string; is_active: boolean };
  dangLam: boolean;
  onDoi: (duLieu: Record<string, unknown>) => void;
}) {
  const [ten, setTen] = useState(viTri.ten);

  return (
    <div className="space-y-1">
      <div className="flex min-w-0 items-center gap-1">
        <input
          value={ten}
          onChange={(event) => setTen(event.target.value)}
          aria-label={`Tên vị trí ${viTri.ten}`}
          maxLength={120}
          disabled={dangLam}
          className={`${O_NHAP} min-w-0 flex-1`}
        />
        <Button
          size="sm"
          variant="secondary"
          disabled={dangLam || !ten.trim() || ten.trim() === viTri.ten}
          onClick={() => onDoi({ ten: ten.trim() })}
        >
          Lưu tên vị trí
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-1">
        <Chip tone={viTri.is_active ? "success" : "neutral"}>
          {viTri.is_active ? "đang sử dụng" : "ngừng sử dụng"}
        </Chip>
        <Button
          size="sm"
          variant={viTri.is_active ? "danger" : "secondary"}
          disabled={dangLam}
          onClick={() => onDoi({ is_active: !viTri.is_active })}
        >
          {viTri.is_active ? "Ngừng sử dụng vị trí" : "Dùng lại vị trí"}
        </Button>
      </div>
    </div>
  );
}
