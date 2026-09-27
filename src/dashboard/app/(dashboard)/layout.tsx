import { redirect } from "next/navigation";
import Shell from "./Shell";
import DeclinedNotice, { type DeclinedItem } from "./DeclinedNotice";
import { NotificationProvider } from "./NotificationContext";
import { BookingPolicyProvider } from "./BookingPolicyContext";
import RealtimeRefresher from "./RealtimeRefresher";
import { logout } from "../(auth)/login/actions";
import { maTraVeBackend } from "../../lib/backend-proxy";
import { getCurrentStaff } from "../../lib/current-staff";
import {
  getQuyenCuaToi,
  getVaiHomNay,
  getViTriHomNay,
} from "../../lib/clinic-session";
import { ROLE_LABEL, canWriteIntake } from "../../lib/roles";
import { fmtDayTime } from "../../lib/datetime";
import { getBookingPolicy } from "../../lib/booking-policy";
import { fetchFromBackend } from "../../lib/backend-proxy";
import { getFeatureMode } from "../../lib/feature-mode";

interface DeclinedRow {
  id: string;
  slot_start: string;
  patient: { full_name: string } | null;
  doctor: { full_name: string } | null;
}

// MỌI TRANG TRONG NHÓM NÀY PHỤ THUỘC PHIÊN ⇒ KHÔNG trang nào được dựng tĩnh.
//
// Đo trên prod 18/09/2026: các trang chỉ-chuyển-hướng (/sono, /lab-queue,
// /result-review, /queue, /portal…) bị `next build` dựng sẵn lúc KHÔNG có phiên
// — layout này chạy, thấy chưa đăng nhập, redirect("/login") — và lệnh ấy bị
// đông cứng vào trang. Người ĐÃ đăng nhập bấm một đường cũ (kể cả link thông
// báo) là bị đá về trang đăng nhập. Khai ở layout một lần thay cho từng trang.
export const dynamic = "force-dynamic";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Vai hôm nay: vai theo vị trí trong lịch đứng trước, vai tài khoản đứng cuối.
  const vaiHomNay = await getVaiHomNay();
  const vaiTaiKhoan = vaiHomNay[vaiHomNay.length - 1] ?? null;
  // Vai CHÍNH quyết định nhãn vai + thanh bên dự phòng + mọi thứ "vẽ màn nào".
  const role = vaiHomNay[0] ?? null;
  if (!role || !vaiTaiKhoan) {
    // MÁY CHỦ BẬN ≠ HẾT PHIÊN (kiểm toán 27/09/2026): trước đây `/me` lỗi tạm
    // (429 bộ chặn dồn dập, 502 lúc deploy, 503 DB treo) cũng đá về /login giữa
    // ca. Chỉ 401/403 mới là phiên hỏng; còn lại ném lỗi → trang lỗi có nút
    // "Thử lại", người dùng vẫn đăng nhập.
    const ma = await maTraVeBackend("/api/v1/me");
    if (ma === 401 || ma === 403) redirect("/login");
    throw new Error("Máy chủ đang bận — bấm Thử lại sau vài giây.");
  }
  // Tài khoản của cái tivi không có việc gì trong bảng điều khiển. Backend đã
  // từ chối vai này ở mọi endpoint (get_current_identity), nên vào đây cũng chỉ
  // thấy một trang lỗi — đưa thẳng ra bảng gọi số là câu trả lời đúng.
  if (vaiTaiKhoan === "DISPLAY") redirect("/display");
  // Và người NGOÀI phòng khám cũng vậy, vì cùng một lý do. Khác một điểm: vai
  // này KHÔNG bị chặn ở /api/v1/me (dashboard cần /me để biết mình là ai), nên
  // thiếu dòng này thì đối tác vào được khung bảng điều khiển — thanh bên trống
  // trơn, trang chủ hỏng vặt — thay vì ra thẳng chỗ gửi kết quả.
  if (vaiTaiKhoan === "PARTNER") redirect("/doi-tac");

  // Identity comes from the staff row linked to the authenticated user.
  //
  // PHÒNG KHÁM + CƠ SỞ ĐI KÈM TÊN, KHÔNG PHẢI TUỲ CHỌN. Yêu cầu "tài khoản nào
  // cũng phải có id phòng khám, cơ sở khám để không bị nhầm nữa" chỉ có tác dụng
  // nếu người dùng ĐỌC được nó. Lưu đúng trong database mà không hiện ra thì
  // đúng cái nhầm đó vẫn xảy ra — lễ tân đặt lịch cho cơ sở khác mà không có gì
  // trên màn hình mâu thuẫn với họ.
  //
  // Một truy vấn ít hơn: getCurrentStaff() đã đọc staff + membership + tên cơ
  // sở và được cache theo lượt render, còn khối cũ ở đây gọi lại bảng staff lần
  // thứ hai cho đúng một cột.
  const staff = await getCurrentStaff();
  const staffId = staff?.id ?? null;
  const who = staff?.full_name ?? staff?.short_name ?? "";
  const place = [staff?.clinic_name, staff?.location_name]
    .filter(Boolean)
    .join(" · ");
  // Đứng vị trí khác vai tài khoản → ghi rõ là vai HÔM NAY, kẻo người dùng
  // tưởng tài khoản mình bị đổi vai.
  const nhanVai =
    role === vaiTaiKhoan ? ROLE_LABEL[role] : `${ROLE_LABEL[role]} (hôm nay)`;
  const identity = [nhanVai, who, place]
    .filter(Boolean)
    .join(" · ");

  // BA THỨ NÀY KHÔNG PHỤ THUỘC NHAU — nên chúng đi CÙNG LÚC.
  //
  // Layout chạy lại ở MỌI lần chuyển trang, và trước đây nó chờ ba lượt mạng
  // nối đuôi nhau. Supabase ở Seoul, phòng khám ở Việt Nam: đo được ~180ms mỗi
  // lượt, nên riêng khối này tốn ~540ms trước khi trang bắt đầu làm việc của
  // nó. Gộp lại còn một lượt.
  //
  // Đo trực tiếp (04/08): 4 truy vấn tuần tự 830ms → song song 213ms.
  // `getClinicId()` ĐÃ BỎ khỏi khối này (06/08/2026): nó chỉ tồn tại để
  // truyền xuống RealtimeRefresher làm bộ lọc, mà nay máy chủ tự lọc theo
  // token. Một truy vấn ít đi trên MỌI lần dựng trang.
  const [declinedRows, bookingPolicy, featureMode, phamViThuKy, viTri, quyen] =
    await Promise.all([
    vaiHomNay.some(canWriteIntake) ? loadDeclined() : Promise.resolve([]),
    getBookingPolicy(),
    getFeatureMode(),
    // Thư ký chưa được phân bác sĩ nào thì mọi màn đều trống — nói RÕ vì sao,
    // kẻo trông như "hôm nay không có khách" (Tuyền chốt 15/09/2026).
    vaiTaiKhoan === "TKYK"
      ? fetchFromBackend<{ la_thu_ky: boolean; bac_si: { id: string }[] }>(
          "/api/v1/thu-ky/pham-vi",
        )
      : Promise.resolve(null),
    // Thanh bên theo VỊ TRÍ hôm nay (Tuyền 16/09/2026). Đi CÙNG vòng với ba lời
    // gọi kia — layout chạy lại ở mọi lần chuyển trang, nên thêm một vòng nối
    // đuôi là thêm độ trễ cho MỌI màn. `null` (backend im) thì rơi về menu
    // theo vai, không làm hỏng trang.
    // Cùng một lời gọi `getVaiHomNay` đã dùng (cache theo lượt render).
    getViTriHomNay(),
    // Quyền THẬT của người này. Đi cùng vòng, không nối đuôi: layout chạy lại
    // ở mọi lần chuyển trang. Hỏng thì rỗng → thanh bên rơi về theo vai.
    getQuyenCuaToi(),
  ]);
  const viTriHomNay = viTri?.vi_tri ?? [];
  const thuKyChuaPhan =
    vaiTaiKhoan === "TKYK" && role === "TKYK" && (phamViThuKy === null || phamViThuKy.bac_si.length === 0);

  // Reception / CSKH / management get a top-right notice of appointments a
  // doctor declined (from today onward), so they can re-assign them.
  const declined: DeclinedItem[] = declinedRows.map((r) => ({
    id: r.id,
    patientName: r.patient?.full_name ?? "—",
    time: fmtDayTime(r.slot_start),
    doctorName: r.doctor?.full_name ?? "—",
  }));

  return (
    <NotificationProvider
      staffId={staffId}
      tenViTri={Object.fromEntries(
        (viTri?.danh_muc ?? []).map((v) => [v.code, v.ten]),
      )}
    >
      <BookingPolicyProvider policy={bookingPolicy}>
        <Shell
          role={role}
          identity={identity}
          tenNguoi={who || undefined}
          featureMode={featureMode}
          viTriHomNay={viTriHomNay}
          phong={viTri?.phong ?? {}}
          quyen={quyen}
          leaveAction={logout}
        >
          {thuKyChuaPhan && (
            <div className="mb-3 rounded-card border border-warning bg-warning-bg px-4 py-3 text-sm text-warning">
              Bạn chưa được phân đi cùng bác sĩ nào nên chưa thấy khách. Báo quản
              lý phân trong Cấu hình phòng khám → Thư ký đi cùng bác sĩ.
            </div>
          )}
          {children}
          <DeclinedNotice items={declined} />
          <RealtimeRefresher />
        </Shell>
      </BookingPolicyProvider>
    </NotificationProvider>
  );
}

/** Lịch bác sĩ đã từ chối, từ hôm nay trở đi — để CSKH xếp lại bác sĩ khác. */
async function loadDeclined(): Promise<DeclinedRow[]> {
  // 24/09/2026: đọc qua backend `GET /api/v1/appointments/bac-si-tu-choi` thay vì
  // đọc thẳng `appointment` bằng Supabase.
  const data = await fetchFromBackend<{ items: DeclinedRow[] }>(
    "/api/v1/appointments/bac-si-tu-choi",
  );
  return data?.items ?? [];
}
