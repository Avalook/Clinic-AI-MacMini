// Đọc dữ liệu điều phối cho các server component.
//
// Năm màn cần các lát khác nhau của cùng một nguồn. Gom vào đây để không màn nào
// tự nghĩ ra một đường đọc riêng — và để `ok: false` (backend không trả lời)
// được xử lý y hệt ở cả năm chỗ.

import { fetchFromBackend } from "../../../lib/backend-proxy";
import type {
  DispatchAlert,
  DispatchHistoryRow,
  DispatchPatient,
  DispatchRoom,
  RouteTemplate,
} from "./types";

export interface LiveSlice {
  patients: DispatchPatient[];
  rooms: DispatchRoom[];
  alerts: DispatchAlert[];
  ok: boolean;
}

/** Vị trí bệnh nhân + tải từng phòng + cảnh báo. Ba màn dùng chung lát này. */
export async function loadLive(): Promise<LiveSlice> {
  const [ov, al] = await Promise.all([
    fetchFromBackend<{ patients: DispatchPatient[]; rooms: DispatchRoom[] }>(
      "/api/v1/dispatch/overview",
    ),
    fetchFromBackend<{ items: DispatchAlert[] }>("/api/v1/dispatch/alerts"),
  ]);
  return {
    patients: ov?.patients ?? [],
    rooms: ov?.rooms ?? [],
    alerts: al?.items ?? [],
    // `null` = backend không trả lời, KHÁC HẲN "phòng khám đang vắng".
    ok: ov !== null,
  };
}

export async function loadRoutes(): Promise<RouteTemplate[]> {
  const rt = await fetchFromBackend<{ items: RouteTemplate[] }>(
    "/api/v1/dispatch/routes",
  );
  return rt?.items ?? [];
}

export async function loadHistory(): Promise<DispatchHistoryRow[]> {
  const hi = await fetchFromBackend<{ items: DispatchHistoryRow[] }>(
    "/api/v1/dispatch/history?limit=200",
  );
  return hi?.items ?? [];
}
