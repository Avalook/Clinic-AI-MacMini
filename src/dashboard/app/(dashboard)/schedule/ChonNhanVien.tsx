"use client";

// Ô chọn nhân viên trong popup xếp ca (thay `<select>` cũ, 09/10/2026): ô tìm ở
// trên + danh sách chia nhóm theo vai, bấm tên nhóm để xổ ra / thu vào; đang gõ
// tìm thì mọi nhóm có kết quả tự mở. CHỈ VẼ: lọc/chia nhóm ở
// `lib/chon-nhan-vien.ts`; ai được xếp vào ô do nơi gọi lọc theo ma trận vai và
// máy chủ kiểm lại khi lưu.
//
// Bàn phím: Tab vào ô tìm → Tab tới từng nút nhóm (Enter/Space xổ ra) → các
// người là radio cùng tên, mũi tên lên/xuống đi giữa người, Space chọn.

import { useId, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import ONhap from "../../../components/ui/ONhap";
import { dangTim, nhomNhanVien, type NguoiChonDuoc } from "../../../lib/chon-nhan-vien";

export default function ChonNhanVien<T extends NguoiChonDuoc>({
  nhanVien,
  daChon,
  onChon,
  nhan = "Nhân viên",
}: {
  nhanVien: readonly T[];
  daChon: string;
  onChon: (id: string) => void;
  nhan?: string;
}) {
  const id = useId();
  const [kim, setKim] = useState("");
  const [moTay, setMoTay] = useState<ReadonlySet<string>>(() => new Set());
  const nhom = nhomNhanVien(nhanVien, kim);
  const tim = dangTim(kim);
  // Chỉ một nhóm thì mở luôn — bắt bấm thêm một lần là thừa.
  const moHet = tim || nhom.length === 1;
  const nguoiDaChon = nhanVien.find((n) => n.id === daChon);

  const daoNhom = (ma: string) =>
    setMoTay((cu) => {
      const moi = new Set(cu);
      if (moi.has(ma)) moi.delete(ma);
      else moi.add(ma);
      return moi;
    });

  return (
    <div className="min-w-0">
      <label htmlFor={`${id}-tim`} className="mb-1 block text-xs font-medium text-ink-muted">
        {nhan}
      </label>
      <ONhap
        id={`${id}-tim`}
        type="search"
        value={kim}
        onChange={(e) => setKim(e.target.value)}
        placeholder="Tìm tên (gõ có dấu hay không đều được)"
        autoComplete="off"
        className="w-full"
      />
      <p className="mt-1 min-w-0 break-words text-xs text-ink-muted" aria-live="polite">
        {nguoiDaChon ? (
          <>
            Đã chọn: <b className="text-ink">{nguoiDaChon.name}</b>
          </>
        ) : (
          "Chưa chọn ai."
        )}
      </p>

      {nhanVien.length > 0 && nhom.length === 0 ? (
        <p className="mt-2 rounded-control bg-surface-sunken px-3 py-2 text-sm text-ink-muted">
          Không tìm thấy ai khớp “{kim.trim()}”.
        </p>
      ) : null}

      {nhom.length === 0 ? null : (
        <div
          role="radiogroup"
          aria-label={nhan}
          className="mt-2 max-h-72 min-w-0 overflow-y-auto overflow-x-hidden rounded-control border border-line"
        >
          {nhom.map((g) => {
            const mo = moHet || moTay.has(g.ma);
            const vungId = `${id}-nhom-${g.ma}`;
            return (
              <div key={g.ma} className="border-b border-line last:border-b-0">
                <button
                  type="button"
                  aria-expanded={mo}
                  aria-controls={vungId}
                  onClick={() => daoNhom(g.ma)}
                  disabled={moHet}
                  className="flex min-h-10 w-full items-center gap-2 bg-surface-sunken px-3 text-left text-sm font-medium text-ink disabled:cursor-default"
                >
                  {mo ? (
                    <ChevronDown className="size-4 shrink-0" aria-hidden />
                  ) : (
                    <ChevronRight className="size-4 shrink-0" aria-hidden />
                  )}
                  <span className="min-w-0 flex-1 break-words">{g.nhan}</span>
                  <span className="shrink-0 text-xs text-ink-muted">{g.nguoi.length}</span>
                </button>
                {mo ? (
                  <ul id={vungId} className="min-w-0">
                    {g.nguoi.map((n) => {
                      const chon = n.id === daChon;
                      const tenNgan = (n.tenNgan ?? "").trim();
                      return (
                        <li key={n.id}>
                          <label
                            className={`flex min-h-10 min-w-0 cursor-pointer items-center gap-2 px-3 py-1.5 text-sm ${
                              chon ? "bg-brand-50 text-brand-800" : "text-ink hover:bg-surface-sunken"
                            }`}
                          >
                            <input
                              type="radio"
                              name={`${id}-nguoi`}
                              value={n.id}
                              checked={chon}
                              onChange={() => onChon(n.id)}
                              className="size-4 shrink-0 accent-brand-600"
                            />
                            <span className="min-w-0 flex-1 break-words">
                              {n.name}
                              {tenNgan && !n.name.includes(tenNgan) ? (
                                <span className="text-ink-muted"> ({tenNgan})</span>
                              ) : null}
                            </span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
