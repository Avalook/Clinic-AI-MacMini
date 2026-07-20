"use client";

// Combobox "gõ-để-tìm" dùng chung (Tỉnh, Phường/xã, …). Lọc KHÔNG dấu
// (unaccentVi) nên gõ "ninh" ra "Ninh Bình", gõ "n" lọc dần. Có bàn phím
// (↑/↓/Enter/Esc) + nút xoá. Giao diện khớp INPUT chung của dashboard.

import { useMemo, useRef, useState } from "react";
import { unaccentVi } from "../../lib/validation";
import { INPUT } from "./form-ui";

export interface SearchOption {
  value: string;
  label: string;
}

export default function SearchSelect({
  options,
  value,
  onChange,
  placeholder = "— Chọn —",
  disabled = false,
  invalid = false,
  emptyText = "Không tìm thấy",
  ariaLabel,
}: {
  options: SearchOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
  emptyText?: string;
  ariaLabel?: string;
}) {
  const selected = options.find((o) => o.value === value) ?? null;
  // query === null → hiển thị nhãn đã chọn; chuỗi → đang gõ để tìm.
  const [query, setQuery] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0); // chỉ số đang được tô (điều hướng bàn phím)
  const blurT = useRef<ReturnType<typeof setTimeout> | null>(null);

  const filtered = useMemo(() => {
    if (query == null || query.trim() === "") return options;
    const t = unaccentVi(query.trim());
    return options.filter((o) => unaccentVi(o.label).includes(t));
  }, [query, options]);

  const inputValue = query == null ? (selected?.label ?? "") : query;

  function choose(opt: SearchOption) {
    onChange(opt.value);
    setQuery(null);
    setOpen(false);
  }
  function clear() {
    onChange("");
    setQuery(null);
    setHi(0);
  }

  return (
    <div className="relative">
      <input
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-label={ariaLabel}
        autoComplete="off"
        disabled={disabled}
        value={inputValue}
        placeholder={placeholder}
        style={selected && !disabled ? { paddingRight: 34 } : undefined}
        className={
          INPUT +
          (invalid ? " border-[#dc2626]" : "") +
          (disabled ? " cursor-not-allowed opacity-60" : "")
        }
        onFocus={() => {
          if (!disabled) {
            if (blurT.current) clearTimeout(blurT.current); // huỷ đóng-trễ khi refocus
            setOpen(true);
            setHi(0);
          }
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setHi(0);
        }}
        onBlur={() => {
          blurT.current = setTimeout(() => {
            setOpen(false);
            setQuery(null);
          }, 150);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
            setHi((h) => Math.min(h + 1, filtered.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHi((h) => Math.max(h - 1, 0));
          } else if (e.key === "Enter") {
            if (open && filtered[hi]) {
              e.preventDefault();
              choose(filtered[hi]);
            }
          } else if (e.key === "Escape") {
            setOpen(false);
            setQuery(null);
          }
        }}
      />
      {selected && !disabled && (
        <button
          type="button"
          aria-label="Xoá lựa chọn"
          onMouseDown={(e) => {
            e.preventDefault();
            clear();
          }}
          className="absolute right-2 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded text-[15px] leading-none text-[#a1a1aa] hover:bg-[#fce7f3] hover:text-[#dc2626]"
        >
          ×
        </button>
      )}
      {open && !disabled && (
        <ul className="absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-[#e4e4e7] bg-white shadow-lg">
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-[#a1a1aa]">{emptyText}</li>
          ) : (
            filtered.map((o, i) => (
              <li
                key={o.value}
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(o);
                }}
                onMouseEnter={() => setHi(i)}
                className={
                  "cursor-pointer px-3 py-2 text-sm " +
                  (i === hi ? "bg-[#fce7f3] " : "hover:bg-[#fdf2f8] ") +
                  (o.value === value
                    ? "font-medium text-[#9d2463]"
                    : "text-[#171717]")
                }
              >
                {o.label}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
