"use client";

// Ô NGÀY DUY NHẤT (gộp ngày/tháng/năm thành 1 control) — D19.
//   • Hiển thị + nhập DD/MM/YYYY (không phụ thuộc locale trình duyệt).
//   • KẸP PHẠM VI NGAY KHI GÕ: ngày 1–31, tháng 1–12, năm [minYear..maxYear]
//     (ô ngày sinh max=hôm nay → 1900..năm nay). KHÔNG lọt ngày 33 / tháng 34 /
//     năm 3245.
//   • Gõ LIÊN TỤC: số đầu ≥4 = ngày 1 chữ số, ≥2 = tháng 1 chữ số → tự nhảy ô.
//     "782019" → 07/08/2019; "07082019" → 07/08/2019.
//   • XÓA mượt: khi backspace KHÔNG tự thêm lại "/" → xóa được qua cả dấu gạch.
//   • Luôn re-mask từ CHUỖI SỐ thuần (bỏ "/") → tránh kẹt khi input controlled tự
//     chèn "/" rồi đọc lại (bug "07/82" → tháng 12).
//   • value/onChange dùng ISO "yyyy-mm-dd".

import { useRef, useState } from "react";
import { CalendarDays } from "lucide-react";
import { daysInMonth } from "../../lib/validation";
import { INPUT } from "./form-ui";

/** ISO "yyyy-mm-dd" → "dd/mm/yyyy" để hiển thị; chuỗi khác → "". */
function isoToText(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

/** d/m/y (chuỗi ĐÃ kẹp) → ISO; "" nếu thiếu phần hoặc KHÔNG phải ngày lịch hợp lệ
 *  (vd 31/02). Đây là rào chốt cuối. */
function partsToIso(d: string, mo: string, y: string): string {
  if (!d || !mo || y.length !== 4) return "";
  const dd = Number(d);
  const mm = Number(mo);
  const yy = Number(y);
  if (!Number.isInteger(dd) || !Number.isInteger(mm) || !Number.isInteger(yy))
    return "";
  if (mm < 1 || mm > 12) return "";
  if (dd < 1 || dd > daysInMonth(mm, yy)) return "";
  return `${String(yy).padStart(4, "0")}-${String(mm).padStart(2, "0")}-${String(dd).padStart(2, "0")}`;
}

// Máy trạng thái: chuỗi SỐ thuần → {d, m, y} đã kẹp ngày 1–31 / tháng 1–12.
// Số đầu ≥4 (ngày) / ≥2 (tháng) = 1 chữ số → tự chốt & nhảy ô.
function maskContinuous(digits: string): { d: string; m: string; y: string } {
  let i = 0;
  let d = "";
  let m = "";
  let y = "";
  if (i < digits.length) {
    const a = digits[i];
    if (a >= "4") {
      d = "0" + a;
      i += 1;
    } else if (i + 1 < digits.length) {
      const two = digits.slice(i, i + 2);
      if (Number(two) >= 1 && Number(two) <= 31) {
        d = two;
        i += 2;
      } else {
        d = "0" + a; // 2 số > 31 → ngày = 0a, số sau sang tháng
        i += 1;
      }
    } else {
      d = a; // mới 1 số → chờ
      i += 1;
    }
  }
  if (d.length === 2 && i < digits.length) {
    const a = digits[i];
    if (a >= "2") {
      m = "0" + a;
      i += 1;
    } else if (i + 1 < digits.length) {
      const two = digits.slice(i, i + 2);
      if (Number(two) >= 1 && Number(two) <= 12) {
        m = two;
        i += 2;
      } else {
        m = "0" + a;
        i += 1;
      }
    } else {
      m = a;
      i += 1;
    }
  }
  if (m.length === 2 && i < digits.length) {
    y = digits.slice(i, i + 4);
  }
  return { d, m, y };
}

/** Dựng chuỗi hiển thị. Khi GÕ THÊM: tự chèn "/" sau ngày/tháng đã chốt (auto
 *  nhảy ô). Khi XÓA (deleting): KHÔNG chèn "/" cuối → backspace xóa được tiếp. */
function buildDisplay(d: string, m: string, y: string, deleting: boolean): string {
  const parts = [d];
  if (m !== "" || (d.length === 2 && !deleting)) parts.push(m);
  if (parts.length === 2 && (y !== "" || (m.length === 2 && !deleting))) parts.push(y);
  return parts.join("/");
}

export default function DateField({
  value,
  onChange,
  min,
  max,
  className,
  ariaLabel,
  invalid,
}: {
  /** ISO "yyyy-mm-dd" hoặc "". */
  value: string;
  /** Nhận ISO "yyyy-mm-dd" (đã hợp lệ) hoặc "". */
  onChange: (iso: string) => void;
  /** ISO chặn dưới/trên cho bộ chọn native + kẹp NĂM khi gõ tay. */
  min?: string;
  max?: string;
  className?: string;
  ariaLabel?: string;
  invalid?: boolean;
}) {
  const [text, setText] = useState(() => isoToText(value));
  const nativeRef = useRef<HTMLInputElement>(null);

  // Khoảng NĂM hợp lệ suy từ min/max (ngày sinh: max=hôm nay → ≤ năm nay).
  const curYear = new Date().getFullYear();
  const maxYear = max && /^\d{4}/.test(max) ? Number(max.slice(0, 4)) : curYear + 10;
  const minYear = min && /^\d{4}/.test(min) ? Number(min.slice(0, 4)) : 1900;

  const clampYear = (y: string): string => {
    if (y.length !== 4) return y; // chưa đủ 4 số → chưa kẹp (đang gõ)
    let n = Number(y);
    if (n < minYear) n = minYear;
    if (n > maxYear) n = maxYear;
    return String(n).padStart(4, "0");
  };

  function apply(digits: string, deleting: boolean) {
    const { d, m, y } = maskContinuous(digits.slice(0, 8));
    const yc = clampYear(y);
    setText(buildDisplay(d, m, yc, deleting));
    onChange(partsToIso(d, m, yc));
  }

  function onType(raw: string) {
    // deleting = chuỗi mới NGẮN hơn chuỗi đang hiển thị (người dùng backspace).
    const deleting = (raw ?? "").length < text.length;
    apply((raw ?? "").replace(/\D/g, ""), deleting);
  }

  function onBlur() {
    const digits = text.replace(/\D/g, "");
    if (!digits) return;
    // Rời ô: pad ngày/tháng 1 chữ số ("7" → "07") + format đầy đủ.
    const r = maskContinuous(digits);
    const d = r.d.length === 1 ? "0" + r.d : r.d;
    const m = r.m.length === 1 ? "0" + r.m : r.m;
    const yc = clampYear(r.y);
    setText(buildDisplay(d, m, yc, false));
    onChange(partsToIso(d, m, yc));
  }

  function openPicker() {
    try {
      nativeRef.current?.showPicker?.();
    } catch {
      /* trình duyệt cũ không hỗ trợ showPicker — bỏ qua */
    }
  }

  function onNative(v: string) {
    if (!v) return; // v = "yyyy-mm-dd"
    setText(isoToText(v));
    onChange(v); // bộ chọn native luôn cho ISO hợp lệ
  }

  return (
    <div className="relative flex items-center gap-2">
      <input
        type="text"
        inputMode="numeric"
        value={text}
        onChange={(e) => onType(e.target.value)}
        onBlur={onBlur}
        placeholder="DD/MM/YYYY"
        aria-label={ariaLabel}
        className={(className ?? INPUT) + (invalid ? " border-danger" : "")}
      />
      <button
        type="button"
        onClick={openPicker}
        aria-label="Chọn ngày từ lịch"
        className="shrink-0 rounded-lg border border-line bg-white p-2 text-ink-muted hover:bg-surface-sunken"
      >
        <CalendarDays size={18} />
      </button>
      <input
        ref={nativeRef}
        type="date"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onNative(e.target.value)}
        tabIndex={-1}
        aria-hidden
        className="pointer-events-none absolute h-0 w-0 opacity-0"
      />
    </div>
  );
}
