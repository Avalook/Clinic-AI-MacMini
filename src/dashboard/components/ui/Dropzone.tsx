"use client";

/**
 * Ô chọn tệp: BẤM vào vùng trống để chọn, hoặc KÉO THẢ tệp vào (lát 5, 26/09/2026).
 *
 * Tách khỏi KhungTep để mọi màn nhận tệp dùng chung một cách cư xử: ô input ẩn
 * được xoá giá trị ngay sau khi chọn (chọn lại ĐÚNG tệp ấy vẫn bắn sự kiện), và
 * trạng thái "đang kéo vào" chỉ tắt khi con trỏ rời hẳn ô — không nhấp nháy khi
 * lướt qua chữ con bên trong.
 */

import { useRef, useState, type ReactNode } from "react";
import { UploadCloud } from "lucide-react";

export default function Dropzone({
  onChon,
  nhan,
  phu,
  accept,
  multiple = true,
  disabled = false,
  gon = false,
}: {
  onChon: (files: File[]) => void;
  nhan: ReactNode;
  phu?: ReactNode;
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  /** Ô thấp (đã có tệp bên dưới) thay vì ô to mời gửi. */
  gon?: boolean;
}) {
  const oChon = useRef<HTMLInputElement>(null);
  const [keoVao, setKeoVao] = useState(false);

  return (
    <div
      onDragOver={(e) => {
        if (disabled) return;
        e.preventDefault();
        setKeoVao(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
        setKeoVao(false);
      }}
      onDrop={(e) => {
        if (disabled) return;
        e.preventDefault();
        setKeoVao(false);
        const ds = Array.from(e.dataTransfer.files);
        if (ds.length) onChon(ds);
      }}
      className={`rounded-control border-2 border-dashed transition-colors ${
        keoVao ? "border-brand-500 bg-brand-50" : "border-line bg-surface"
      }`}
    >
      <input
        ref={oChon}
        type="file"
        multiple={multiple}
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const ds = e.target.files ? Array.from(e.target.files) : [];
          e.target.value = "";
          if (ds.length) onChon(ds);
        }}
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => oChon.current?.click()}
        className={`flex w-full flex-col items-center justify-center gap-1 rounded-control px-4 text-center text-ink-soft hover:bg-surface-muted disabled:opacity-60 ${
          gon ? "min-h-16 py-3" : "min-h-40 py-8"
        }`}
      >
        <UploadCloud className={gon ? "size-5" : "size-9"} aria-hidden />
        <span className="text-body font-semibold text-ink">{nhan}</span>
        {phu ? <span className="text-meta text-ink-muted">{phu}</span> : null}
      </button>
    </div>
  );
}
