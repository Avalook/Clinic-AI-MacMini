"use client";

// Combobox "gõ-để-tìm" dùng chung (Tỉnh, Phường/xã, …). Lọc KHÔNG dấu
// (unaccentVi) nên gõ "ninh" ra "Ninh Bình", gõ "n" lọc dần. Có bàn phím
// (↑/↓/Enter/Esc) + nút xoá. Giao diện khớp INPUT chung của dashboard.

import { useId, useMemo, useRef, useState } from "react";
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
  const listboxId = useId();

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
        aria-autocomplete="list"
        aria-controls={listboxId}
        aria-activedescendant={
          open && filtered[hi] ? `${listboxId}-option-${hi}` : undefined
        }
        aria-invalid={invalid || undefined}
        aria-label={ariaLabel}
        autoComplete="off"
        disabled={disabled}
        value={inputValue}
        placeholder={placeholder}
        style={selected && !disabled ? { paddingRight: 34 } : undefined}
        className={
          INPUT +
          (invalid ? " border-danger" : "") +
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
          className="absolute right-2 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded text-[15px] leading-none text-ink-faint hover:bg-brand-100 hover:text-danger"
        >
          ×
        </button>
      )}
      {open && !disabled && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-line bg-white shadow-lg"
        >
          {filtered.length === 0 ? (
            <li
              role="option"
              aria-disabled="true"
              aria-selected="false"
              className="px-3 py-2 text-sm text-ink-faint"
            >
              {emptyText}
            </li>
          ) : (
            filtered.map((o, i) => (
              <li
                key={o.value}
                id={`${listboxId}-option-${i}`}
                role="option"
                aria-selected={o.value === value}
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(o);
                }}
                onMouseEnter={() => setHi(i)}
                className={
                  "cursor-pointer px-3 py-2 text-sm " +
                  (i === hi ? "bg-brand-100 " : "hover:bg-brand-50 ") +
                  (o.value === value
                    ? "font-medium text-brand-800"
                    : "text-ink")
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
