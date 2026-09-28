/**
 * Tiếp đón khách (trước 16/09/2026 tên "Hàng đợi tiếp nhận").
 *
 * Hai khối: trên cùng "Lịch hẹn hôm nay" (bảng lịch chung, có Check-in / Không
 * đến / Hoàn tác); bên dưới DANH SÁCH TIẾP ĐÓN (27/09/2026, đợt 3 — bản mẫu
 * Tuyền duyệt): mỗi lịch / lượt hôm nay một dòng, chia buổi, chip trạng thái do
 * máy chủ tính (`GET /api/v1/reception/danh-sach`). Trước đó phần dưới đọc
 * worklist `bang_dieu_phoi` của kernel và chỉ gồm người đã check-in.
 */

import { fetchFromBackend } from "@/lib/backend-proxy";
import {
  getClinicStaffId,
  getQuyenCuaToi,
  getVaiChinh,
  moDuocMan,
  requireNavAccess,
} from "@/lib/clinic-session";
import { currentWeekStartVn, todayVn } from "@/lib/roster";
import type { GoiTiepDon } from "@/lib/tiep-don";
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
  // khác là bật cột Check-in / Không đến / Hoàn tác.
  const tuan = currentWeekStartVn();
  // DANH SÁCH TIẾP ĐÓN (27/09/2026, đợt 3 — bản mẫu Tuyền duyệt): một gói của
  // máy chủ, đã chia buổi và tính chip trạng thái. Nút "+ Thêm khách hàng" hỏi
  // ĐÚNG luật cửa của trang đích (`moDuocMan`), không hỏi vai.
  const [danhSach, goi, role, staffId, themKhachDuoc, quyen] = await Promise.all([
    fetchFromBackend<GoiTiepDon>("/api/v1/reception/danh-sach"),
    fetchFromBackend<GoiLichHen>(
      `/api/v1/home/bang-dieu-khien?week_appt=${tuan}&week_roster=${tuan}`,
    ),
    getVaiChinh(),
    getClinicStaffId(),
    moDuocMan("/patients/new"),
    getQuyenCuaToi(),
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
            // Nút Check-in theo LEGO Tiếp đón, không theo vai (đợt 3, 27/09).
            duocCheckIn={quyen === null ? undefined : quyen.includes("reception.checkin.perform")}
          />
        )}
      </section>
      {danhSach === null || !Array.isArray(danhSach.buoi) ? (
        /* Máy chủ im không được trông như phòng chờ trống. */
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">Không tải được danh sách tiếp đón</p>
          <p className="mt-1 text-sm text-danger">
            Máy chủ không trả lời, phiên đăng nhập đã hết, hoặc tài khoản chưa có
            lego “Tiếp đón khách”. ĐỪNG coi đây là không có khách — tải lại trang;
            bảng Lịch hẹn hôm nay ở trên vẫn check-in được.
          </p>
        </div>
      ) : (
        <QueueBoard goi={danhSach} themKhachDuoc={themKhachDuoc} />
      )}
    </main>
    </>
  );
}
