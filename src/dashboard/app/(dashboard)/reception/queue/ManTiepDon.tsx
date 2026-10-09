"use client";

// Thân màn Tiếp đón khách: thanh tìm + lọc TRÊN CÙNG (09/10/2026) giữ MỘT bộ
// lọc cho cả hai bảng bên dưới — "Lịch hẹn" (`WeeklyAppointmentsTable`, dùng
// chung với Trang chủ, nhận `loc` tuỳ chọn) và danh sách tiếp đón (`QueueBoard`).
// Trang (server) đọc dữ liệu + quyền rồi giao hết cho đây; ở đây không đọc gì.

import { useState, type ComponentProps } from "react";

import { LOC_MAC_DINH, type GoiTiepDon, type LocTiepDon } from "@/lib/tiep-don";

import WeekNav from "../../WeekNav";
import WeeklyAppointmentsTable from "../../home/WeeklyAppointmentsTable";
import QueueBoard from "./QueueBoard";
import ThanhLocTiepDon from "./ThanhLocTiepDon";

export default function ManTiepDon({
  danhSach,
  bangLich,
  tuan,
  themKhachDuoc,
}: {
  /** Gói danh sách tiếp đón — null = máy chủ không trả lời. */
  danhSach: GoiTiepDon | null;
  /** Đủ props của bảng Lịch hẹn (trừ `loc`) — null = không đọc được lịch hẹn. */
  bangLich: Omit<ComponentProps<typeof WeeklyAppointmentsTable>, "loc"> | null;
  tuan: string;
  themKhachDuoc: boolean;
}) {
  const [loc, setLoc] = useState<LocTiepDon>(LOC_MAC_DINH);
  const coDanhSach = danhSach !== null && Array.isArray(danhSach.buoi);

  return (
    <>
      <ThanhLocTiepDon
        loc={loc}
        onDoi={setLoc}
        dem={coDanhSach ? danhSach.dem : null}
        themKhachDuoc={themKhachDuoc}
      />

      {/* Check-in đứng TRÊN hàng đợi và ngoài nhánh lỗi của hàng đợi: hàng
          đợi không tải được thì quầy vẫn phải check-in được khách. */}
      <section
        aria-label="Lịch hẹn"
        className="rounded-card border border-line bg-surface p-3 shadow-card sm:p-4"
      >
        <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-2">
          <h2 className="text-emph font-semibold text-ink">Lịch hẹn — check-in khi khách đến</h2>
          <WeekNav gon week={tuan} basePath="/reception/queue" param="weekAppt" />
        </div>
        {bangLich === null ? (
          <p className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
            Không đọc được lịch hẹn hôm nay — máy chủ không trả lời. Đừng coi
            đây là không có ai hẹn; tải lại trang.
          </p>
        ) : (
          <WeeklyAppointmentsTable {...bangLich} loc={loc} />
        )}
      </section>

      {coDanhSach ? (
        <QueueBoard goi={danhSach} tab={loc.tab} tim={loc.tim} />
      ) : (
        /* Máy chủ im không được trông như phòng chờ trống. */
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">Không tải được danh sách tiếp đón</p>
          <p className="mt-1 text-sm text-danger">
            Máy chủ không trả lời, phiên đăng nhập đã hết, hoặc tài khoản chưa có
            lego “Tiếp đón khách”. ĐỪNG coi đây là không có khách — tải lại trang;
            bảng Lịch hẹn ở trên vẫn check-in được.
          </p>
        </div>
      )}
    </>
  );
}
