// CỔNG GIÁM SÁT THEO TÊN MIỀN (09/10/2026).
//
// Trung tâm giám sát AI sống ở tên miền riêng (giamsat.dr4women.io.vn) cho đội
// vận hành ClinicAI. Hai chiều chặn, cùng một bảng đường:
//   · ở host giám sát: CHỈ mở trang giám sát + đăng nhập; mọi đường khác quay về
//     /giam-sat — tên miền này không phải lối vào thứ hai của cả ứng dụng.
//   · ở host khác (tên miền chính): /giam-sat và API của nó là 404 — phòng khám
//     không thấy lối vào. Staging / máy dev mở lại bằng GIAMSAT_CHO_HOST_CHINH=1
//     (quyền `giamsat.view` vẫn gác — đây chỉ là lớp tên miền).
//
// Host tin được: Caddy chọn khối site THEO chính header Host, nên request tới
// tên miền chính không mang được Host giám sát vào đây.

const MAC_DINH = "giamsat.dr4women.io.vn,giamsat.localhost";

/** Danh sách host giám sát (env `GIAMSAT_HOST`, phẩy ngăn). */
export function hostGiamSat(env: string | undefined = process.env.GIAMSAT_HOST): string[] {
  return (env?.trim() ? env : MAC_DINH)
    .split(",")
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean);
}

/** Header Host (có thể kèm cổng) có phải host giám sát không. */
export function laHostGiamSat(host: string | null | undefined, ds: string[] = hostGiamSat()): boolean {
  if (!host) return false;
  const ten = host.trim().toLowerCase().replace(/:\d+$/, "");
  return ds.includes(ten);
}

const MO_TREN_HOST_GIAM_SAT = ["/giam-sat", "/api/ops/agent", "/login", "/auth", "/chon-co-so", "/api/loi"];

const khop = (path: string, goc: string) => path === goc || path.startsWith(`${goc}/`) || path.startsWith(`${goc}?`);

/** Ở host giám sát, đường này có được mở không. */
export function moTrenHostGiamSat(path: string): boolean {
  return MO_TREN_HOST_GIAM_SAT.some((g) => khop(path, g));
}

/** Đường của riêng trung tâm giám sát (trang + API proxy). */
export function laDuongGiamSat(path: string): boolean {
  return khop(path, "/giam-sat") || khop(path, "/api/ops/agent");
}

/** Staging / máy dev: cho mở /giam-sat ở host chính (quyền vẫn gác). */
export function choHostChinh(env: string | undefined = process.env.GIAMSAT_CHO_HOST_CHINH): boolean {
  return ["1", "true", "yes"].includes((env ?? "").trim().toLowerCase());
}

export type QuyetDinhCong = "di_tiep" | "ve_giam_sat" | "khong_thay";

/** Quyết định của cổng cho một request — hàm thuần để test. */
export function quyetDinhCong(host: string | null | undefined, path: string, ds?: string[], choChinh?: boolean): QuyetDinhCong {
  if (laHostGiamSat(host, ds)) return moTrenHostGiamSat(path) ? "di_tiep" : path.startsWith("/api") ? "khong_thay" : "ve_giam_sat";
  if (laDuongGiamSat(path) && !(choChinh ?? choHostChinh())) return "khong_thay";
  return "di_tiep";
}
