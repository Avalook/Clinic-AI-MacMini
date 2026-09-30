"use client";

// Ô CHỌN BÁC SĨ trong phòng nhiều bác sĩ (Tuyền chốt 30/09/2026): "chọn phòng
// siêu âm 2 máy rồi thì thêm cả lựa chọn các bác sĩ ở ngày đó nữa, rất open".
//
// Màn KHÔNG tự suy ai trực: danh sách do máy chủ trả kèm danh sách phòng (chỉ có
// phần tử khi phòng có ≥2 bác sĩ trực — một bác sĩ thì máy chủ tự gán, không
// hỏi). Lệnh ghi (`xep-phong-v1` / `phong-du-kien` kèm `bac_si_lam_id`) kiểm lại
// bác sĩ còn trực không. Chọn bác sĩ KHÔNG khoá ai bắt đầu làm.
//
// Một component cho mọi lối chọn phòng: `DoiPhong` (Bàn khám, Xem lượt, quầy thu
// sau khi chốt, trang phiếu, trưởng ca) và ô "Làm ở phòng" của quầy
// (`ChonDichVu`, `HoaDonMot`).

export interface LuaChonBacSi {
  staff_id: string;
  /** "BS X" — máy chủ đã viết sẵn. */
  ten: string;
  lan: number | null;
  /** Khách đang chờ / đang làm với bác sĩ này hôm nay. */
  dang_cho: number;
}

/** Phòng có ô chọn bác sĩ không — máy chủ chỉ trả danh sách khi ≥2 bác sĩ. */
export function coChonBacSi(ds: LuaChonBacSi[] | null | undefined): ds is LuaChonBacSi[] {
  return Array.isArray(ds) && ds.length >= 2;
}

export default function ChonBacSiLam({
  ds,
  value,
  onChon,
  disabled = false,
  co = "vua",
}: {
  ds: LuaChonBacSi[];
  /** Mã bác sĩ đang chọn; "" = bác sĩ nào rảnh cũng được. */
  value: string;
  onChon: (staffId: string) => void;
  disabled?: boolean;
  /** Theo ô chọn phòng đứng cạnh: "nho" (DoiPhong), "vua" (ô "Làm ở phòng"
   *  của `ChonDichVu`), "dong" (dòng hoá đơn `HoaDonMot`, rộng hết dòng). */
  co?: "nho" | "vua" | "dong";
}) {
  const kieu =
    co === "nho"
      ? "min-h-8 rounded-control border border-line bg-surface px-2 text-xs text-ink"
      : co === "dong"
        ? "w-full rounded-control border border-line bg-surface px-2 py-1 text-meta text-ink-soft"
        : "min-h-10 rounded-control border border-line bg-surface px-2 text-body text-ink";
  return (
    <select
      aria-label="Bác sĩ làm"
      value={value}
      disabled={disabled}
      onChange={(e) => onChon(e.target.value)}
      className={kieu}
    >
      <option value="">Bác sĩ nào rảnh cũng được</option>
      {ds.map((b) => (
        <option key={b.staff_id} value={b.staff_id}>
          {b.ten} · {b.dang_cho} đang chờ
        </option>
      ))}
    </select>
  );
}
