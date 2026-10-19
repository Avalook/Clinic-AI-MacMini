"use client";

import { useState } from "react";

import Button from "@/components/ui/Button";

import type { ConfigFloor, NodeDef } from "./types";

const O_NHAP =
  "h-8 rounded-control border border-line bg-surface px-2 text-meta text-ink";

export function FormCoSo({
  ten = "",
  diaChi = "",
  dangHoatDong,
  dangLam,
  onLuu,
  onThoi,
}: {
  ten?: string;
  diaChi?: string;
  dangHoatDong?: boolean;
  dangLam: boolean;
  onLuu: (ten: string, diaChi: string, bat: boolean) => void;
  onThoi: () => void;
}) {
  const [tenMoi, setTenMoi] = useState(ten);
  const [diaChiMoi, setDiaChiMoi] = useState(diaChi);
  const [bat, setBat] = useState(dangHoatDong ?? true);
  return (
    <div className="flex flex-wrap items-end gap-2 rounded-card border border-line bg-surface p-3">
      <label className="flex min-w-48 flex-1 flex-col gap-0.5 text-label text-ink-muted">
        Tên cơ sở
        <input
          value={tenMoi}
          onChange={(event) => setTenMoi(event.target.value)}
          placeholder="VD: Kim Ngưu"
          className={O_NHAP}
        />
      </label>
      <label className="flex min-w-60 flex-[2] flex-col gap-0.5 text-label text-ink-muted">
        Địa chỉ
        <input
          value={diaChiMoi}
          onChange={(event) => setDiaChiMoi(event.target.value)}
          className={O_NHAP}
        />
      </label>
      {dangHoatDong !== undefined ? (
        <label className="flex h-8 items-center gap-1.5 text-meta text-ink">
          <input
            type="checkbox"
            checked={bat}
            onChange={(event) => setBat(event.target.checked)}
            className="size-4 accent-brand-600"
          />
          Đang hoạt động
        </label>
      ) : null}
      <Button
        size="sm"
        variant="primary"
        disabled={dangLam || !tenMoi.trim()}
        onClick={() => onLuu(tenMoi.trim(), diaChiMoi.trim(), bat)}
      >
        {dangHoatDong === undefined ? "Thêm cơ sở" : "Lưu"}
      </Button>
      <Button size="sm" variant="ghost" onClick={onThoi}>
        Thôi
      </Button>
    </div>
  );
}

export function FormThemPhong({
  nodes,
  floors,
  dangLam,
  onThem,
  onThoi,
}: {
  nodes: NodeDef[];
  floors: ConfigFloor[];
  dangLam: boolean;
  onThem: (ten: string, buoc: string, floorId: string) => void;
  onThoi: () => void;
}) {
  const [ten, setTen] = useState("");
  const [buoc, setBuoc] = useState("");
  const [floorId, setFloorId] = useState(
    floors.find((floor) => floor.floor_id && floor.is_active)?.floor_id ?? "",
  );
  return (
    <div className="flex flex-wrap items-end gap-2 border-b border-line bg-surface-muted/40 px-4 py-3">
      <label className="flex min-w-48 flex-1 flex-col gap-0.5 text-label text-ink-muted">
        Tên phòng mới
        <input
          value={ten}
          onChange={(event) => setTen(event.target.value)}
          placeholder="VD: Siêu âm 4"
          className={O_NHAP}
        />
      </label>
      <label className="flex min-w-48 flex-1 flex-col gap-0.5 text-label text-ink-muted">
        Việc chính
        <select value={buoc} onChange={(event) => setBuoc(event.target.value)} className={O_NHAP}>
          <option value="">— chọn —</option>
          {nodes.map((node) => (
            <option key={node.code} value={node.code}>
              {node.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex min-w-36 flex-col gap-0.5 text-label text-ink-muted">
        Tầng
        <select
          value={floorId}
          onChange={(event) => setFloorId(event.target.value)}
          className={O_NHAP}
        >
          <option value="">— chưa xếp tầng —</option>
          {floors
            .filter((floor) => floor.floor_id && floor.is_active)
            .map((floor) => (
              <option key={floor.floor_id} value={floor.floor_id ?? ""}>
                {floor.floor}
              </option>
            ))}
        </select>
      </label>
      <Button
        size="sm"
        variant="primary"
        disabled={dangLam || !ten.trim() || !buoc}
        onClick={() => onThem(ten.trim(), buoc, floorId)}
      >
        Thêm phòng
      </Button>
      <Button size="sm" variant="ghost" onClick={onThoi}>
        Thôi
      </Button>
    </div>
  );
}
