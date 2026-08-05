// Command Center — Cổng trung tâm điều khiển toàn hệ thống.
// Chỉ MANAGEMENT + TRUONG_CA (isOpsAdmin) mới được vào.
// Tổng hợp: trạng thái hệ thống, vai trò, màn hình, hạ tầng, số liệu vận hành.

// Nhập hàm getSupabaseServer để lấy client Supabase phía server
import { getSupabaseServer } from "../../../lib/supabase-server";
// Nhập hằng số VN_TZ (múi giờ Việt Nam) từ file datetime
import { VN_TZ } from "../../../lib/datetime";
// Nhập các hàm kiểm tra quyền truy cập và lấy vai trò
import { requireNavAccess, getClinicRole } from "../../../lib/clinic-session";
// Nhập hàm isOpsAdmin để kiểm tra quyền quản trị vận hành
import { isOpsAdmin } from "../../../lib/roles";
// Nhập component PortalBoard để hiển thị cổng trung tâm
import PortalBoard from "./PortalBoard";

// Ép Next.js render trang này động (không cache) — luôn lấy dữ liệu mới nhất
export const dynamic = "force-dynamic";

// Component chính của trang Command Center (server component)
export default async function PortalPage() {
  // Kiểm tra quyền truy cập trang /portal — nếu không có quyền sẽ redirect hoặc từ chối
  await requireNavAccess("/portal");
  // Lấy vai trò của người dùng hiện tại
  const role = await getClinicRole();
  // Nếu không có vai trò hoặc không phải quản trị vận hành
  if (!role || !isOpsAdmin(role)) {
    // requireNavAccess đã redirect, nhưng giữ guard phòng hờ.
    // Trả về null (không render gì) — phòng hờ nếu requireNavAccess chưa redirect
    return null;
  }

  // Lấy client Supabase phía server (dùng cookie phiên đăng nhập)
  const supabase = await getSupabaseServer();

  // Danh sách nhân viên KHÔNG phụ thuộc mấy con số bên dưới — nó chỉ nằm
  // trước vì được viết trước. Đợi nó xong rồi mới bắn khối kia là cộng thêm
  // một lượt ~210ms sang Seoul cho không.
  // Tạo query lấy danh sách nhân viên (chưa thực thi — chỉ tạo query builder)
  const qStaff = supabase
    .from("staff") // Từ bảng staff (nhân viên)
    .select(
      // Chọn các cột cần thiết của nhân viên
      "id, full_name, short_name, primary_department, employment_type, is_active, auth_user_id",
    )
    .order("primary_department", { ascending: true }) // Sắp xếp theo phòng ban tăng dần
    .order("full_name", { ascending: true }); // Sắp xếp theo tên tăng dần

  // Lấy số liệu hôm nay: lịch hẹn, bệnh nhân, lượt khám
  // Lấy thời gian hiện tại
  const vnNow = new Date();
  // Chuyển thời gian hiện tại sang múi giờ Việt Nam
  const vnToday = new Date(
    vnNow.toLocaleString("en-US", { timeZone: VN_TZ }),
  );
  // Tính thời điểm bắt đầu ngày hôm nay (00:00:00) theo UTC
  const dayStart = new Date(
    Date.UTC(
      vnToday.getFullYear(), // Năm
      vnToday.getMonth(), // Tháng
      vnToday.getDate(), // Ngày
      0, // Giờ 0
      0, // Phút 0
      0, // Giây 0
    ),
  ).toISOString();
  // Tính thời điểm kết thúc ngày hôm nay (23:59:59.999) theo UTC
  const dayEnd = new Date(
    Date.UTC(
      vnToday.getFullYear(), // Năm
      vnToday.getMonth(), // Tháng
      vnToday.getDate(), // Ngày
      23, // Giờ 23
      59, // Phút 59
      59, // Giây 59
      999, // Miligiây 999
    ),
  ).toISOString();

  // Chạy song song tất cả các truy vấn để tối ưu hiệu năng
  const [
    { data: staffRows }, // Kết quả danh sách nhân viên
    apptTodayRes, // Kết quả đếm lịch hẹn hôm nay
    patientTodayRes, // Kết quả đếm bệnh nhân mới hôm nay
    visitTodayRes, // Kết quả đếm lượt khám hôm nay
    pendingTaskRes, // Kết quả đếm việc đang chờ
    eventLogRes, // Kết quả danh sách sự kiện gần đây
  ] = await Promise.all([
    qStaff, // Truy vấn danh sách nhân viên
    supabase
      .from("appointment") // Từ bảng appointment (lịch hẹn)
      .select("*", { count: "exact", head: true }) // Chỉ đếm số lượng, không lấy dữ liệu
      .gte("slot_start", dayStart) // Lọc: slot_start >= đầu ngày
      .lt("slot_start", dayEnd), // Lọc: slot_start < cuối ngày
    supabase
      .from("patient") // Từ bảng patient (bệnh nhân)
      .select("*", { count: "exact", head: true }) // Chỉ đếm số lượng, không lấy dữ liệu
      .gte("created_at", dayStart) // Lọc: created_at >= đầu ngày
      .lt("created_at", dayEnd), // Lọc: created_at < cuối ngày
    supabase
      .from("visit") // Từ bảng visit (lượt khám)
      .select("*", { count: "exact", head: true }) // Chỉ đếm số lượng, không lấy dữ liệu
      .gte("created_at", dayStart) // Lọc: created_at >= đầu ngày
      .lt("created_at", dayEnd), // Lọc: created_at < cuối ngày
    supabase
      .from("work_item") // Từ bảng work_item (công việc)
      .select("*", { count: "exact", head: true }) // Chỉ đếm số lượng, không lấy dữ liệu
      .in("status", ["PENDING", "IN_PROGRESS"]), // Lọc: trạng thái đang chờ hoặc đang xử lý
    supabase
      .from("event_log") // Từ bảng event_log (nhật ký sự kiện)
      .select("event_id, event_type, aggregate_type, source, occurred_at") // Chọn các cột cần thiết
      .order("occurred_at", { ascending: false }) // Sắp xếp theo thời gian giảm dần (mới nhất trước)
      .limit(10), // Giới hạn 10 sự kiện gần nhất
  ]);

  // Ép kiểu dữ liệu nhân viên từ kết quả truy vấn
  const staff = (staffRows as
    | {
        id: string; // ID nhân viên
        full_name: string; // Tên đầy đủ
        short_name: string | null; // Tên viết tắt, có thể null
        primary_department: string; // Phòng ban chính
        employment_type: string; // Loại hợp đồng
        is_active: boolean; // Có đang hoạt động không
        auth_user_id: string | null; // ID người dùng xác thực, có thể null
      }[]
    | null) ?? []; // Nếu null thì dùng mảng rỗng

  // Ép kiểu dữ liệu sự kiện từ kết quả truy vấn
  const events = (eventLogRes.data as
    | {
        event_id: string; // ID sự kiện
        event_type: string; // Loại sự kiện
        aggregate_type: string; // Loại đối tượng
        source: string; // Nguồn ghi
        occurred_at: string; // Thời gian xảy ra
      }[]
    | null) ?? []; // Nếu null thì dùng mảng rỗng

  return (
    // Render component PortalBoard với dữ liệu đã lấy
    <PortalBoard
      staff={staff} // Danh sách nhân viên
      counts={{
        appointmentsToday: apptTodayRes.count ?? 0, // Số lịch hẹn hôm nay
        patientsToday: patientTodayRes.count ?? 0, // Số bệnh nhân mới hôm nay
        visitsToday: visitTodayRes.count ?? 0, // Số lượt khám hôm nay
        pendingTasks: pendingTaskRes.count ?? 0, // Số việc đang chờ
      }}
      recentEvents={events} // Danh sách sự kiện gần đây
    />
  );
}