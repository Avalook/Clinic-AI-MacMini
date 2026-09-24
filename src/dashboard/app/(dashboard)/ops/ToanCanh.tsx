// Tab "Toàn cảnh" của /ops — trước 18/09/2026 là màn riêng /portal ("Command
// Center"), gộp vào đây vì cùng người dùng (Quản lý) và trùng nửa nội dung.
// Chỉ MANAGEMENT + TRUONG_CA (isOpsAdmin) mới được vào.
// Tổng hợp: trạng thái hệ thống, vai trò, màn hình, hạ tầng, số liệu vận hành.
//
// 24/09/2026: đọc qua backend `/reports/toan-canh` — tab từng đọc thẳng 6 bảng
// bằng Supabase và tính "hôm nay" theo nửa đêm UTC (lệch 7 giờ).

import { fetchFromBackend } from "../../../lib/backend-proxy";
import { vaiLamViec } from "../../../lib/clinic-session";
import { isOpsAdmin } from "../../../lib/roles";
import PortalBoard from "./PortalBoard";

type ToanCanhData = {
  staff: {
    id: string;
    full_name: string;
    short_name: string | null;
    primary_department: string;
    employment_type: string;
    is_active: boolean;
    auth_user_id: string | null;
  }[];
  counts: {
    appointmentsToday: number;
    patientsToday: number;
    visitsToday: number;
    pendingTasks: number;
  };
  recentEvents: {
    event_id: string;
    event_type: string;
    aggregate_type: string;
    source: string;
    occurred_at: string;
  }[];
};

export default async function ToanCanh() {
  const role = await vaiLamViec(isOpsAdmin);
  if (!role || !isOpsAdmin(role)) {
    // requireNavAccess đã redirect, nhưng giữ guard phòng hờ.
    return null;
  }

  const d = await fetchFromBackend<ToanCanhData>("/api/v1/reports/toan-canh");

  return (
    <PortalBoard
      staff={d?.staff ?? []}
      counts={
        d?.counts ?? {
          appointmentsToday: 0,
          patientsToday: 0,
          visitsToday: 0,
          pendingTasks: 0,
        }
      }
      recentEvents={d?.recentEvents ?? []}
    />
  );
}
