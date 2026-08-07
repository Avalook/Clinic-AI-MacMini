// Lịch chờ xếp bác sĩ — hàng đợi của quản lý.
//
// Khách gọi đặt trước 2–3 tuần hoặc cả tháng, lúc lịch trực chưa công bố. CSKH
// ghi nguyện vọng và để trống bác sĩ; màn này là nơi việc ấy được hoàn tất.
//
// "Đang chờ" = `doctor_id IS NULL`. Không phải một trạng thái mới trên
// appointment — tám giá trị hiện có được cả hệ thống lọc theo, và một giá trị
// thứ chín sẽ rơi im lặng qua mọi bộ lọc.

import { redirect } from "next/navigation";
import { getClinicRole } from "../../../../lib/clinic-session";
import { isOpsAdmin } from "../../../../lib/roles";
import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { listBookableDoctors } from "../../../../lib/doctors-server";
import HangChoView, { type DongCho } from "./HangChoView";

export const dynamic = "force-dynamic";

export default async function ChoXepBacSiPage() {
  // Trưởng ca xếp được cùng Quản lý: người trực tiếp biết ai đang rảnh thường
  // là trưởng ca. Backend gác lại bằng chính bảng chuyển tiếp (MANAGE_ROLES).
  const role = await getClinicRole();
  if (!isOpsAdmin(role)) redirect("/home");

  const [data, doctors] = await Promise.all([
    fetchFromBackend<{ items: DongCho[] }>("/api/v1/appointments/cho-xep-bac-si"),
    listBookableDoctors(),
  ]);

  return (
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">
          Lịch chờ xếp bác sĩ
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Khách đã hẹn giờ nhưng chưa có bác sĩ — thường là lịch đặt trước khi
          lịch trực tuần đó được công bố.
        </p>
      </header>

      {/* Không gọi được backend thì NÓI RA. Một hàng chờ rỗng vì hỏng trông y
          hệt một hàng chờ rỗng vì đã xếp xong hết. */}
      {data === null ? (
        <p className="rounded-card bg-danger-bg px-4 py-3 text-sm text-danger">
          Không đọc được hàng chờ. Thử tải lại trang.
        </p>
      ) : (
        <HangChoView rows={data.items ?? []} doctors={doctors} />
      )}
    </main>
  );
}
