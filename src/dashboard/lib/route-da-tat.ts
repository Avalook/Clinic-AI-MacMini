// ROUTE /api ĐÃ TẮT (24/09/2026) — không màn nào gọi nữa.
//
// Rà 88 route: 17 route không còn lời gọi nào từ giao diện (đường cũ đã có
// đường mới thay). Luật "cũ thì OFF, không xoá" (Tuyền 23/09): route trả 410
// ở MỘT chỗ (proxy.ts) thay vì sửa từng file — file giữ nguyên, bỏ một dòng ở
// danh sách dưới là bật lại. Tuyền bấm thật xong mới quyết xoá hẳn.

export const ROUTE_DA_TAT: readonly RegExp[] = [
  /^\/api\/dispatch\/alerts-call\/?$/,
  /^\/api\/cskh\/ket-qua\/[^/]+\/cho-phep-gui\/?$/,
  /^\/api\/cskh\/zalo\/?$/,
  /^\/api\/lab-result\/?$/,
  /^\/api\/sono\/?$/,
  /^\/api\/service-log\/?$/,
  /^\/api\/ultrasound\/image\/?$/,
  /^\/api\/visits\/[^/]+\/charges\/?$/,
  /^\/api\/visits\/[^/]+\/service-orders(\/(current|draft|draft\/approve|draft\/discard|duplicates|remove))?\/?$/,
  /^\/api\/work-items\/[^/]+\/blockers\/?$/,
  /^\/api\/patients\/check-phone\/?$/,
];

export function laRouteDaTat(pathname: string): boolean {
  return ROUTE_DA_TAT.some((r) => r.test(pathname));
}
