// Tab "Toàn cảnh" của /ops — trước 18/09/2026 là màn riêng /portal ("Command
// Center"), gộp vào đây vì cùng người dùng (Quản lý) và trùng nửa nội dung.
// Chỉ MANAGEMENT + TRUONG_CA (isOpsAdmin) mới được vào.
// Tổng hợp: trạng thái hệ thống, vai trò, màn hình, hạ tầng, số liệu vận hành.
//
// 24/09/2026: đọc qua backend `/reports/toan-canh` — tab từng đọc thẳng 6 bảng
// bằng Supabase và tính "hôm nay" theo nửa đêm UTC (lệch 7 giờ).
//
// 08/10/2026 (mở Hào Nam): ô chọn cơ sở `?co_so=` — máy chủ lọc bốn con số
// hôm nay; nhân sự và sự kiện vẫn là của cả phòng khám.

import { ChonCoSoLink } from "@/components/ui/ChonCoSo";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { getQuyenCuaToi, vaiLamViec } from "../../../lib/clinic-session";
import { layCoSo } from "../../../lib/danh-muc";
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

export default async function ToanCanh({ coSo: coSoChon }: { coSo?: string }) {
  // Lego 20 "Vận hành hệ thống" (`ops.view`) — mở full lego 30/09/2026: theo
  // quyền, không theo vai. Máy chủ chưa trả lời quyền → rơi về vai như trước.
  const quyen = await getQuyenCuaToi();
  const duoc =
    quyen === null
      ? isOpsAdmin(await vaiLamViec(isOpsAdmin))
      : quyen.includes("ops.view");
  if (!duoc) {
    // requireNavAccess đã redirect, nhưng giữ guard phòng hờ.
    return null;
  }

  // "" / thiếu = tất cả cơ sở. Mã lạ chuyển nguyên — máy chủ trả số 0.
  const chon = coSoChon ? coSoChon.slice(0, 64) : null;
  const [d, coSo] = await Promise.all([
    fetchFromBackend<ToanCanhData>(
      `/api/v1/reports/toan-canh${chon ? `?co_so=${encodeURIComponent(chon)}` : ""}`,
    ),
    layCoSo(),
  ]);

  return (
    <>
      <ChonCoSoLink
        coSo={coSo}
        dangChon={chon}
        href={(id) =>
          id ? `/ops?tab=toan-canh&co_so=${encodeURIComponent(id)}` : "/ops?tab=toan-canh"
        }
        className="px-4 pt-3 lg:px-5"
      />
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
    </>
  );
}
