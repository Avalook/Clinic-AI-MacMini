/**
 * Tiếp đón khách (trước 16/09/2026 tên "Hàng đợi tiếp nhận").
 *
 * The first screen to read the workflow kernel instead of staff_task. The board
 * is whatever the node catalogue puts in the `bang_dieu_phoi` workspace, so a
 * clinic that reorganises its front desk changes a row in node_definition, not
 * this file.
 */

import { Hourglass, UsersRound, Activity } from "lucide-react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import { requireNavAccess } from "@/lib/clinic-session";
import { fetchWorklist } from "@/lib/worklist-server";
import { isOverdue } from "@/lib/work-item-status";

import { fetchFromBackend } from "@/lib/backend-proxy";
import { getClinicStaffId, getVaiChinh } from "@/lib/clinic-session";
import { currentWeekStartVn, todayVn } from "@/lib/roster";
import QueueBoard from "./QueueBoard";
import LiveBoardSync from "../../LiveBoardSync";
import WeeklyAppointmentsTable from "../../home/WeeklyAppointmentsTable";
import { dungLichHenTuan, type GoiLichHen } from "../../home/lich-hen-ngay";

export const metadata = { title: "Tiếp đón khách · ClinicAI" };

// The queue is the page. Caching it would show the desk a stale room.
export const dynamic = "force-dynamic";

export default async function ReceptionQueuePage() {
  await requireNavAccess("/reception/queue");
  // CHECK-IN Ở ĐÂY, KHÔNG Ở TRANG CHỦ (Tuyền chốt 18/09/2026): lịch hẹn HÔM
  // NAY, cùng bảng và cùng phép dựng với Trang chủ (lich-hen-ngay.ts), chỉ
  // khác là bật cột Check-in / Không đến / Hoàn tác. Hàng đợi bên dưới vẫn
  // chỉ gồm người đã check-in.
  const tuan = currentWeekStartVn();
  const [result, goi, role, staffId] = await Promise.all([
    fetchWorklist("bang_dieu_phoi"),
    fetchFromBackend<GoiLichHen>(
      `/api/v1/home/bang-dieu-khien?week_appt=${tuan}&week_roster=${tuan}`,
    ),
    getVaiChinh(),
    getClinicStaffId(),
  ]);
  const homNay = todayVn();
  const { apptDays, dutyByDate } = dungLichHenTuan(goi, tuan);
  const lichHomNay = apptDays.filter((d) => d.date === homNay);

  return (
    <>
      <LiveBoardSync />
    <main className="page-in flex min-w-0 flex-col gap-3">
      {/* KHÔNG có tiêu đề trang và không có ô ngày ở đây.
          
          Thanh trên cùng của ứng dụng đã hiện đúng hai thứ đó — "Hàng đợi tiếp
          nhận" và "Thứ Năm, 06/08/2026". Lặp lại lần nữa chỉ đẩy phần việc thật
          xuống dưới một màn hình. */}

      {/* Check-in đứng TRÊN hàng đợi và ngoài nhánh lỗi của hàng đợi: hàng
          đợi không tải được thì quầy vẫn phải check-in được khách. */}
      <section aria-label="Lịch hẹn hôm nay" className="rounded-card border border-line bg-surface p-3 shadow-card sm:p-4">
        <h2 className="mb-2 text-sm font-semibold text-ink">
          Lịch hẹn hôm nay — check-in khi khách đến
        </h2>
        {goi === null ? (
          <p className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
            Không đọc được lịch hẹn hôm nay — máy chủ không trả lời. Đừng coi
            đây là không có ai hẹn; tải lại trang.
          </p>
        ) : lichHomNay.every((d) => d.items.length === 0) ? (
          <p className="px-1 py-4 text-sm text-ink-muted">Hôm nay chưa có lịch hẹn nào.</p>
        ) : (
          <WeeklyAppointmentsTable
            days={lichHomNay}
            role={role}
            staffId={staffId}
            dutyByDate={dutyByDate}
            choDoSinhHieu={false}
            choCheckIn
          />
        )}
      </section>
      {!result.ok ? (
        /* An outage must not look like an empty waiting room. */
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">
            Không tải được hàng đợi
          </p>
          <p className="mt-1 text-sm text-danger">
            {result.reason === "no-session"
              ? "Phiên đăng nhập đã hết hạn — đăng nhập lại để xem hàng đợi."
              : result.reason === "unreachable"
                ? "Không kết nối được máy chủ. ĐỪNG coi đây là hàng đợi trống — hãy kiểm tra danh sách giấy."
                : "Máy chủ từ chối yêu cầu. ĐỪNG coi đây là hàng đợi trống."}
            {result.detail ? ` (${result.detail})` : ""}
          </p>
        </div>
      ) : (
        <>
          <StatRow>
            <StatCard
              label="Đang chờ tiếp nhận"
              value={result.items.filter((i) => i.status === "PENDING").length}
              tone="brand"
              icon={<UsersRound size={23} />}
            />
            <StatCard
              label="Đang xử lý"
              value={result.items.filter((i) => i.status === "IN_PROGRESS").length}
              tone="neutral"
              icon={<Activity size={23} />}
            />
            <StatCard
              label="Quá SLA"
              value={result.items.filter((i) => isOverdue(i)).length}
              tone="danger"
              icon={<Hourglass size={23} />}
            />
          </StatRow>

          {/* Thứ tự do QueueBoard tự xếp theo `call_order` của backend — cùng
              nguồn với bảng gọi số, và chính nó là thứ lễ tân kéo. Xếp sẵn ở
              đây theo "chờ lâu nhất" chỉ tạo một thứ tự thứ hai. */}
          <QueueBoard items={result.items} />
        </>
      )}
    </main>
    </>
  );
}
