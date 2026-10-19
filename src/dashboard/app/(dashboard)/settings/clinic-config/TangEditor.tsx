"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

import type { ConfigFloor } from "./types";

const O_NHAP =
  "h-8 rounded-control border border-line bg-surface px-2 text-meta text-ink";

export function TangEditor({
  floor,
  dangLam,
  lenDuoc,
  xuongDuoc,
  onDoiTen,
  onBatTat,
  onDoiThuTu,
}: {
  floor: ConfigFloor;
  dangLam: boolean;
  lenDuoc: boolean;
  xuongDuoc: boolean;
  onDoiTen: (ten: string) => void;
  onBatTat: () => void;
  onDoiThuTu: (delta: -1 | 1) => void;
}) {
  const [dangSua, setDangSua] = useState(false);
  const [ten, setTen] = useState(floor.floor ?? "");

  if (!floor.floor_id) {
    return (
      <p className="bg-surface-muted px-4 py-1.5 text-label font-semibold text-ink-muted">
        Chưa gắn tầng
      </p>
    );
  }
  const soPhongDangBat = floor.rooms.filter((room) => room.is_active).length;

  if (dangSua) {
    return (
      <div className="flex flex-wrap items-center gap-1.5 bg-surface-muted px-4 py-1.5">
        <label className="sr-only" htmlFor={`floor-${floor.floor_id}`}>
          Tên tầng
        </label>
        <input
          id={`floor-${floor.floor_id}`}
          value={ten}
          onChange={(event) => setTen(event.target.value)}
          maxLength={40}
          className={`${O_NHAP} min-w-36`}
        />
        <Button
          size="sm"
          variant="primary"
          disabled={dangLam || !ten.trim() || ten.trim() === floor.floor}
          onClick={() => {
            onDoiTen(ten.trim());
            setDangSua(false);
          }}
        >
          Lưu tên tầng
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setTen(floor.floor ?? "");
            setDangSua(false);
          }}
        >
          Thôi
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 bg-surface-muted px-4 py-1.5">
      <span
        className={`text-label font-semibold uppercase ${
          floor.is_active ? "text-ink-muted" : "text-ink-faint line-through"
        }`}
      >
        {floor.floor}
      </span>
      {!floor.is_active ? <Chip tone="neutral">ngừng sử dụng</Chip> : null}
      <span className="text-label text-ink-faint">
        · {soPhongDangBat} phòng đang dùng
      </span>
      <div className="ml-auto flex items-center gap-1">
        <Button
          size="sm"
          variant="ghost"
          aria-label="Đưa tầng lên"
          title="Đưa tầng lên"
          disabled={dangLam || !lenDuoc}
          onClick={() => onDoiThuTu(-1)}
        >
          <ArrowUp className="size-4" aria-hidden="true" />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label="Đưa tầng xuống"
          title="Đưa tầng xuống"
          disabled={dangLam || !xuongDuoc}
          onClick={() => onDoiThuTu(1)}
        >
          <ArrowDown className="size-4" aria-hidden="true" />
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setDangSua(true)}>
          Đổi tên tầng
        </Button>
        <Button
          size="sm"
          variant={floor.is_active ? "danger" : "secondary"}
          disabled={dangLam || (floor.is_active && soPhongDangBat > 0)}
          title={
            floor.is_active && soPhongDangBat > 0
              ? "Chuyển hết phòng sang tầng khác trước khi ngừng sử dụng tầng."
              : undefined
          }
          onClick={onBatTat}
        >
          {floor.is_active ? "Ngừng sử dụng tầng" : "Dùng lại tầng"}
        </Button>
      </div>
    </div>
  );
}

export function FormThemTang({
  dangLam,
  onThem,
  onThoi,
}: {
  dangLam: boolean;
  onThem: (ten: string) => void;
  onThoi: () => void;
}) {
  const [ten, setTen] = useState("");
  return (
    <div className="flex flex-wrap items-end gap-2 border-b border-line bg-surface-muted/40 px-4 py-3">
      <label className="flex min-w-48 flex-1 flex-col gap-0.5 text-label text-ink-muted">
        Tên tầng mới
        <input
          value={ten}
          onChange={(event) => setTen(event.target.value)}
          maxLength={40}
          placeholder="VD: Tầng 5"
          className={O_NHAP}
        />
      </label>
      <Button
        size="sm"
        variant="primary"
        disabled={dangLam || !ten.trim()}
        onClick={() => onThem(ten.trim())}
      >
        Thêm tầng
      </Button>
      <Button size="sm" variant="ghost" onClick={onThoi}>
        Thôi
      </Button>
    </div>
  );
}
