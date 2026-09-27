"use client";

/**
 * Ô SỐ dùng chung (27/09/2026 — bản giao diện mẫu, mục 5).
 *
 * `<input type="text" inputMode="decimal">` thay cho `type="number"`:
 *   · gõ được "36,6" lẫn "36.6"; rời ô thì chuẩn hoá về dấu chấm (cùng dạng máy
 *     chủ lưu — `phieu_kham/khung.py::_doc_so`);
 *   · `kichThuoc` cho phép "12 x 8" / "12 x 8 x 5" (kích thước, đo hai chiều);
 *   · LĂN CHUỘT CHỈ ĐỔI SỐ KHI Ô ĐANG ĐƯỢC CHỌN (bản mẫu: "an toàn dữ liệu") —
 *     cuộn trang lướt qua không bao giờ đổi số bệnh án; bước lăn theo hàng
 *     thập phân đang có (36.6 → 36.7, không phải 37.6);
 *   · chữ không đọc được thì GIỮ NGUYÊN và tô viền lỗi — không tự xoá.
 *
 * Mọi phép biến đổi nằm ở `lib/o-so.ts` (hàm thuần, có test). Ô rộng 96px
 * (bản mẫu `.in.so`) + đơn vị bên phải; trong bảng dùng `rong="day"`.
 *
 * 27/09/2026 (đợt 3, màn đo sinh hiệu trên điện thoại):
 *   · `nguyen` — chỉ số đếm được (huyết áp, mạch, SpO₂…) mở BÀN PHÍM SỐ
 *     (`inputMode="numeric"`) thay bàn phím thập phân. Máy chủ vẫn là nơi
 *     quyết "phải là số nguyên"; ô không tự cắt phần thập phân;
 *   · `loi` / `canhBao` — tô viền theo ô máy chủ chỉ ra (`truong`); ô tự nó
 *     KHÔNG biết ngưỡng nào là bất thường;
 *   · `ref` — màn cần chuyển focus ô kế khi bấm Enter.
 */

import {
  useEffect,
  useImperativeHandle,
  useRef,
  type InputHTMLAttributes,
  type Ref,
} from "react";

import { buocLan, chuanHoaSo, locKhiGo } from "@/lib/o-so";

const O =
  "min-h-10 rounded-control border bg-surface px-2.5 text-right text-base " +
  "tabular-nums text-ink outline-none transition-colors placeholder:text-ink-faint " +
  "focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15 sm:min-h-8 sm:text-body " +
  "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-soft " +
  "aria-invalid:border-danger";

export default function OSo({
  value,
  onChange,
  kichThuoc = false,
  donVi,
  rong = "hep",
  nguyen = false,
  loi = false,
  canhBao = false,
  ref: refNgoai,
  className = "",
  onBlur,
  ...rest
}: {
  value: string;
  /** Nhận chuỗi đã lọc (lúc gõ) / đã chuẩn hoá (lúc rời ô, lúc lăn). */
  onChange: (v: string) => void;
  /** Cho gõ kích thước "12 x 8" (phiếu kết quả). Phiếu khám: không — máy chủ
   *  chỉ nhận một số. */
  kichThuoc?: boolean;
  /** Đơn vị hiện bên phải ô ("ngày", "tuổi", "mm"…). */
  donVi?: string | null;
  /** `hep` = 96px (bản mẫu) · `day` = đầy ô bảng. */
  rong?: "hep" | "day";
  /** Chỉ số nguyên (huyết áp, mạch, SpO₂…) → bàn phím số trên điện thoại. */
  nguyen?: boolean;
  /** Máy chủ nói ô này lỗi → viền đỏ (`aria-invalid`). */
  loi?: boolean;
  /** Máy chủ nhắc ô này bất thường → viền vàng. Không chặn gì. */
  canhBao?: boolean;
  ref?: Ref<HTMLInputElement>;
  className?: string;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "value" | "onChange" | "inputMode">) {
  const ref = useRef<HTMLInputElement>(null);
  useImperativeHandle(refNgoai, () => ref.current as HTMLInputElement, []);

  // React gắn `wheel` dạng passive — preventDefault trong onWheel không chặn
  // được trang cuộn. Gắn tay, passive: false.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const lan = (e: WheelEvent) => {
      if (document.activeElement !== el || el.readOnly || el.disabled) return;
      const moi = buocLan(el.value, e.deltaY < 0 ? 1 : -1);
      if (moi === null) return;
      e.preventDefault();
      onChange(moi);
    };
    el.addEventListener("wheel", lan, { passive: false });
    return () => el.removeEventListener("wheel", lan);
  }, [onChange]);

  const chuan = chuanHoaSo(value, kichThuoc);
  const o = (
    <input
      {...rest}
      ref={ref}
      type="text"
      inputMode={nguyen ? "numeric" : "decimal"}
      autoComplete="off"
      value={value}
      // Lỗi tại chỗ (chữ không đọc được) HOẶC máy chủ báo ô này lỗi (đợt 3:
      // `loi` ở màn sinh hiệu, `aria-invalid` truyền vào ở phiếu khám).
      aria-invalid={chuan === null || loi || rest["aria-invalid"] ? true : undefined}
      title={rest.title ?? "Bấm vào ô rồi lăn chuột để tăng / giảm"}
      onChange={(e) => onChange(locKhiGo(e.target.value))}
      onBlur={(e) => {
        if (chuan !== null && chuan !== value) onChange(chuan);
        onBlur?.(e);
      }}
      className={`${O} ${canhBao ? "border-warning" : "border-line"} ${
        rong === "hep" ? "w-24 shrink-0" : "w-full"
      } ${className}`}
    />
  );
  if (!donVi) return o;
  return (
    <span className="inline-flex max-w-full items-center gap-1.5">
      {o}
      <span className="whitespace-nowrap text-meta text-ink-faint">{donVi}</span>
    </span>
  );
}
