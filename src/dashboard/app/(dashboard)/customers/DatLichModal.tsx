"use client";

// Đặt lịch ngay tại màn Quản lý khách hàng — tái khám, hoặc khám mới.
//
// QUANG 10/08/2026: hai nút "Tái khám" và "Đặt lịch khám mới" phải "hiện ra cái
// đặt lịch giống form như trong trang này cũng có đó".
//
// DÙNG LẠI `AppointmentBooking`, KHÔNG DÙNG `BookingHub`. BookingHub là cả một
// màn: lưới khung giờ theo bác sĩ, giữ chỗ, thanh bước 1-2-3, danh sách khách
// bên trái. Nhét nó vào một hộp thoại là mang theo cả bốn thứ đó cùng vòng đời
// giữ chỗ của nó. `AppointmentBooking` đúng là cái form, và đã được ba màn khác
// dùng lại rồi.
//
// VÌ SAO KHÔNG ĐIỀU HƯỚNG SANG /appointments?bn=… THAY VÌ MỞ HỘP THOẠI: chuyển
// trang là mất ngữ cảnh khách đang mở, và CSKH phải tự tìm lại người vừa nãy.
// Việc đặt lịch tái khám xảy ra NGAY SAU khi vừa khám xong, trong cùng một câu
// chuyện với khách đang đứng đó.

import { X } from "lucide-react";
import AppointmentBooking from "../patients/AppointmentBooking";
import type { Opt } from "./CustomersView";

export interface KhoaDichVu {
  serviceId: string;
  label: string;
}

export default function DatLichModal({
  tenKhach,
  clinicPatientId,
  services,
  doctors,
  locations,
  defaultLocationId,
  khoaDichVu,
  lichTruocId,
  onDong,
  onXong,
}: {
  tenKhach: string;
  clinicPatientId: string;
  services: Opt[];
  doctors: Opt[];
  locations: Opt[];
  defaultLocationId?: string;
  /** Có = TÁI KHÁM (dịch vụ khoá theo lượt trước). Không có = khám mới. */
  khoaDichVu?: KhoaDichVu;
  /** Có = lịch mới nối vào chuỗi tái khám (`appointment.lich_truoc_id`). */
  lichTruocId?: string;
  onDong: () => void;
  /** Nhận id lịch VỪA TẠO, để màn chuyển hẳn sang lượt mới. */
  onXong: (appointmentId: string) => void;
}) {
  // "TÁI KHÁM" LÀ CÓ NỐI CHUỖI, không phải "có khoá dịch vụ".
  //
  // Chỗ này từng đọc `khoaDichVu`, mà `khoaDichVu` chỉ dựng được khi lượt trước
  // có `service_type_id`. Lượt thiếu dịch vụ ⇒ tiêu đề nói "Đặt lịch khám mới"
  // và câu dưới nói "KHÔNG nối vào chuỗi tái khám" — trong khi `lichTruocId`
  // vẫn được gửi và nó nối thật. Màn hình nói ngược với việc nó đang làm.
  const laTaiKham = Boolean(lichTruocId);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={laTaiKham ? "Đặt lịch tái khám" : "Đặt lịch khám mới"}
      className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-black/40 p-4"
      onClick={onDong}
    >
      <div
        className="w-full max-w-xl space-y-3 rounded-2xl border border-line bg-surface p-4 shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line pb-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">
              {laTaiKham ? "Đặt lịch tái khám" : "Đặt lịch khám mới"} — {tenKhach}
            </h2>
            <p className="mt-0.5 text-label leading-snug text-ink-muted">
              {laTaiKham ? (
                <>
                  {khoaDichVu ? (
                    <>
                      Giữ nguyên dịch vụ <b>{khoaDichVu.label}</b> của lượt đang
                      xem.{" "}
                    </>
                  ) : (
                    <>Lượt đang xem chưa chọn dịch vụ — chọn dịch vụ bên dưới. </>
                  )}
                  Lịch này sẽ được ghi là tái khám nối tiếp lượt đó.
                </>
              ) : (
                <>
                  Đợt khám mới — chọn dịch vụ bất kỳ. Lịch này KHÔNG nối vào
                  chuỗi tái khám của lượt trước.
                </>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={onDong}
            aria-label="Đóng"
            className="shrink-0 rounded-lg p-1 text-ink-muted hover:bg-surface-muted"
          >
            <X className="size-4" />
          </button>
        </div>

        <AppointmentBooking
          clinicPatientId={clinicPatientId}
          services={services}
          doctors={doctors}
          locations={locations}
          defaultLocationId={defaultLocationId}
          khoaDichVu={khoaDichVu}
          lichTruocId={lichTruocId}
          onBooked={onXong}
        />
      </div>
    </div>
  );
}
