// "Lĩnh vực" CSKH phân loại lúc đặt lịch — DÙNG LẠI 5 service_code chuyên khoa
// (PK/SK/NT/HMVS/NK = 5 form khám) để map được sang form khám sau này
// (xem lib/form-schemas: getFormSchema / resolveServiceCode). Lưu MÃ; UI hiển label.

export const LINH_VUC_OPTIONS: { code: string; label: string }[] = [
  { code: "PK", label: "Phụ khoa" },
  { code: "SK", label: "Sản khoa" },
  { code: "NT", label: "Nội tiết" },
  { code: "HMVS", label: "Hiếm muộn - Vô sinh" },
  { code: "NK", label: "Nam khoa" },
];

const LINH_VUC_LABEL: Record<string, string> = Object.fromEntries(
  LINH_VUC_OPTIONS.map((o) => [o.code, o.label]),
);

/** Mã lĩnh vực → nhãn tiếng Việt (rỗng nếu null). */
export function linhVucLabel(code: string | null | undefined): string {
  return code ? (LINH_VUC_LABEL[code] ?? code) : "";
}
