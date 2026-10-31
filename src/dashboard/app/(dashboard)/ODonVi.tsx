"use client";

// Ô đơn vị dùng chung (31/10/2026): gõ tay được + gợi ý chọn sẵn, đơn vị của thuốc
// đó lên trước rồi tới đơn vị phổ biến. Dùng `SearchSelect` chứ không dùng datalist:
// datalist trên iPhone không mở danh sách và chọn hay trượt.

import { useMemo } from "react";

import { unaccentVi } from "../../lib/validation";
import SearchSelect from "./SearchSelect";

/** Chỉ là gợi ý cho đỡ gõ — đơn vị thật do người dùng khai ở Danh mục kho. */
export const DON_VI_PHO_BIEN = [
  "gói",
  "hộp",
  "viên",
  "vỉ",
  "lọ",
  "ống",
  "chai",
  "tuýp",
  "miếng",
  "túi",
] as const;

export default function ODonVi({
  value,
  onChange,
  cuaThuoc = [],
  disabled = false,
  invalid = false,
  placeholder = "Chọn hoặc gõ đơn vị",
  ariaLabel = "Đơn vị",
}: {
  value: string;
  onChange: (v: string) => void;
  /** Đơn vị của chính thuốc này — lên đầu danh sách. */
  cuaThuoc?: readonly (string | null | undefined)[];
  disabled?: boolean;
  invalid?: boolean;
  placeholder?: string;
  ariaLabel?: string;
}) {
  const options = useMemo(() => {
    const da = new Set<string>();
    const ra: { value: string; label: string }[] = [];
    for (const dv of [...cuaThuoc, ...DON_VI_PHO_BIEN]) {
      const chu = (dv ?? "").trim();
      const khoa = unaccentVi(chu);
      if (!chu || da.has(khoa)) continue;
      da.add(khoa);
      ra.push({ value: chu, label: chu });
    }
    return ra;
  }, [cuaThuoc]);

  return (
    <SearchSelect
      options={options}
      value={value}
      onChange={onChange}
      choGoTu
      disabled={disabled}
      invalid={invalid}
      placeholder={placeholder}
      ariaLabel={ariaLabel}
    />
  );
}
