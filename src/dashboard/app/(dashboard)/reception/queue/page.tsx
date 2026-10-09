/**
 * Tiếp đón khách (trước 16/09/2026 tên "Hàng đợi tiếp nhận").
 *
 * Trên cùng THANH TÌM + LỌC (09/10/2026) lọc cả hai khối. Hai khối: "Lịch hẹn" (bảng lịch chung, có Check-in / Không đến /
 * Hoàn tác ở HÔM NAY; thanh tuần/ngày y hệt Trang chủ — 29/09/2026: bấm dòng
 * ngày khác mở popover Đổi lịch tại chỗ để đổi sang hôm nay + check-in); bên dưới DANH SÁCH TIẾP ĐÓN (27/09/2026, đợt 3 — bản mẫu
 * Tuyền duyệt): mỗi lịch / lượt hôm nay một dòng, chia buổi, chip trạng thái do
 * máy chủ tính (`GET /api/v1/reception/danh-sach`). Trước đó phần dưới đọc
 * worklist `bang_dieu_phoi` của kernel và chỉ gồm người đã check-in.
 */

import { fetchFromBackend } from "@/lib/backend-proxy";
import {
  getQuyenCuaToi,
  getVaiChinh,
  moDuocMan,
  requireNavAccess,
} from "@/lib/clinic-session";
import { QUYEN_DOI_DICH_VU_KHAM, QUYEN_GHI_CHAM_SOC, coMotQuyen } from "@/lib/quyen-cua-toi";
import { currentWeekStartVn, weekStartOf } from "@/lib/roster";
import type { GoiTiepDon } from "@/lib/tiep-don";
import ManTiepDon from "./ManTiepDon";
import LiveBoardSync from "../../LiveBoardSync";
import { dungLichHenTuan, type GoiLichHen } from "../../home/lich-hen-ngay";

export const metadata = { title: "Tiếp đón khách · ClinicAI" };

// The queue is the page. Caching it would show the desk a stale room.
export const dynamic = "force-dynamic";

export default async function ReceptionQueuePage({
  searchParams,
}: {
  searchParams: Promise<{ weekAppt?: string }>;
}) {
  await requireNavAccess("/reception/queue");
  // CHECK-IN Ở ĐÂY, KHÔNG Ở TRANG CHỦ (Tuyền chốt 18/09/2026): lịch hẹn HÔM
  // NAY, cùng bảng và cùng phép dựng với Trang chủ (lich-hen-ngay.ts), chỉ
  // khác là bật cột Check-in / Không đến / Hoàn tác.
  // THANH TUẦN / NGÀY Y HỆT TRANG CHỦ (29/09/2026): ‹ tuần › + Cả tuần · T2…CN,
  // `?weekAppt=` + `?ngay=`. Tham số rác → tuần này (không ném).
  const { weekAppt: rawTuan } = await searchParams;
  const tuan = (rawTuan ? weekStartOf(rawTuan) : null) ?? currentWeekStartVn();
  // DANH SÁCH TIẾP ĐÓN (27/09/2026, đợt 3 — bản mẫu Tuyền duyệt): một gói của
  // máy chủ, đã chia buổi và tính chip trạng thái. Nút "+ Thêm khách hàng" hỏi
  // ĐÚNG luật cửa của trang đích (`moDuocMan`), không hỏi vai.
  const [danhSach, goi, role, themKhachDuoc, quyen, moHoSoKhach, moHoSoBenhNhan] = await Promise.all([
    fetchFromBackend<GoiTiepDon>("/api/v1/reception/danh-sach"),
    fetchFromBackend<GoiLichHen>(
      `/api/v1/home/bang-dieu-khien?week_appt=${tuan}&week_roster=${tuan}`,
    ),
    getVaiChinh(),
    moDuocMan("/patients/new"),
    getQuyenCuaToi(),
    moDuocMan("/customers"),
    moDuocMan("/patient-list"),
  ]);
  const { apptDays, dutyByDate } = dungLichHenTuan(goi, tuan);

  return (
    <>
      <LiveBoardSync />
    <main className="page-in flex min-w-0 flex-col gap-3">
      {/* KHÔNG có tiêu đề trang và không có ô ngày ở đây.
          
          Thanh trên cùng của ứng dụng đã hiện đúng hai thứ đó — "Hàng đợi tiếp
          nhận" và "Thứ Năm, 06/08/2026". Lặp lại lần nữa chỉ đẩy phần việc thật
          xuống dưới một màn hình. */}

      {/* Thanh tìm + lọc TRÊN CÙNG (09/10/2026), lọc cả bảng Lịch hẹn lẫn danh
          sách tiếp đón — thân màn là client (`ManTiepDon`) giữ bộ lọc chung. */}
      <ManTiepDon
        danhSach={danhSach}
        tuan={tuan}
        themKhachDuoc={themKhachDuoc}
        bangLich={
          goi === null
            ? null
            : {
                days: apptDays,
                role,
                dutyByDate,
                choDoSinhHieu: false,
                choCheckIn: true,
                chonNgay: true,
                duocDoiLich: quyen === null ? undefined : quyen.includes("booking.manage"),
                moHoSoKhach,
                // ⋯ "Gọi / ghi chăm sóc" làm TẠI CHỖ; "Mở hồ sơ khách" → Danh sách
                // bệnh nhân `?chon=` — hỏi đúng luật cửa của trang đích (29/09/2026).
                duocGhiChamSoc: coMotQuyen(quyen, QUYEN_GHI_CHAM_SOC),
                // ⋯ "Đổi dịch vụ khám" tại chỗ (V5, 30/09/2026).
                duocDoiDichVu: coMotQuyen(quyen, QUYEN_DOI_DICH_VU_KHAM),
                duocXemHoSo: moHoSoBenhNhan,
                // Nút Check-in theo LEGO Tiếp đón, không theo vai (đợt 3, 27/09).
                duocCheckIn:
                  quyen === null ? undefined : quyen.includes("reception.checkin.perform"),
                duocDatLich: quyen === null ? undefined : quyen.includes("booking.create"),
              }
        }
      />
    </main>
    </>
  );
}
