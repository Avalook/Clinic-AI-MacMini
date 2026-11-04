"use client";

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

const O_NHAP =
  "h-8 rounded-control border border-line bg-surface px-2 text-meta text-ink";

/** Ô bác sĩ cùng phòng mà một ô phụ tá chọn để hỗ trợ. */
export interface OBacSi {
  id: string;
  ten: string;
}

/** Giá trị ô chọn "Ô này là" → dữ liệu gửi máy chủ. Máy chủ + Postgres kiểm
 *  ô hỗ trợ đúng là ô bác sĩ cùng phòng (trigger `vi_tri_kiem_ho_tro`). */
function duLieuLoai(gt: string): Record<string, unknown> {
  if (gt === "bs") return { nhom_nghe: "BAC_SI" };
  if (gt.startsWith("pt:")) return { nhom_nghe: "DIEU_DUONG", ho_tro_id: gt.slice(3) };
  return { nhom_nghe: "DIEU_DUONG", bo_ho_tro: true };
}

export function ViTriEditor({
  viTri,
  oBacSi,
  dangLam,
  onDoi,
}: {
  viTri: { ten: string; is_active: boolean; nhom_nghe: string; ho_tro_id?: string | null };
  /** Các ô bác sĩ khác đang dùng trong cùng phòng. */
  oBacSi: OBacSi[];
  dangLam: boolean;
  onDoi: (duLieu: Record<string, unknown>) => void;
}) {
  const [ten, setTen] = useState(viTri.ten);
  // Ô đối tác / ô chung giữ nhóm cũ — không đổi qua ô chọn này.
  const doiDuoc = viTri.nhom_nghe === "BAC_SI" || viTri.nhom_nghe === "DIEU_DUONG";
  const loai =
    viTri.nhom_nghe === "BAC_SI" ? "bs" : viTri.ho_tro_id ? `pt:${viTri.ho_tro_id}` : "nv";
  const hoTroMat = viTri.ho_tro_id && !oBacSi.some((b) => b.id === viTri.ho_tro_id);

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
      {doiDuoc ? (
        <label className="flex min-w-0 items-center gap-1 text-meta text-ink-muted">
          Ô này là
          <select
            value={hoTroMat ? "nv" : loai}
            disabled={dangLam || !viTri.is_active}
            onChange={(event) => onDoi(duLieuLoai(event.target.value))}
            aria-label={`Vị trí ${viTri.ten} là`}
            className={`${O_NHAP} min-w-0 flex-1`}
          >
            <option value="bs">Ô bác sĩ</option>
            {oBacSi.map((b) => (
              <option key={b.id} value={`pt:${b.id}`}>
                Phụ tá cho {b.ten}
              </option>
            ))}
            <option value="nv">Ô nhân viên (không đi theo bác sĩ)</option>
          </select>
        </label>
      ) : null}
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
