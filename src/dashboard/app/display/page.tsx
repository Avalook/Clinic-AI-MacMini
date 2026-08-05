// Màn hình TV phòng chờ — hiển thị số đang gọi theo khu (image_15 + 2 ảnh V2).
// Public, không cần đăng nhập. Chỉ đọc appointment + queue_number hôm nay.

// Nhập hàm getSupabaseServer để lấy client Supabase phía server
import { getSupabaseServer } from "../../lib/supabase-server";
// Nhập hàm vnTodayRangeUtc để lấy khoảng thời gian hôm nay theo múi giờ Việt Nam (UTC)
import { vnTodayRangeUtc } from "../../lib/datetime";
// Nhập component DisplayBoard để hiển thị bảng gọi số
import DisplayBoard from "./DisplayBoard";

// Ép Next.js render trang này động (không cache) — luôn lấy dữ liệu mới nhất
export const dynamic = "force-dynamic";

// Component chính của trang hiển thị (server component, chạy phía server)
export default async function DisplayPage() {
  // Lấy client Supabase phía server (dùng cookie phiên đăng nhập)
  const supabase = await getSupabaseServer();
  // Lấy khoảng thời gian bắt đầu và kết thúc của hôm nay theo múi giờ Việt Nam (chuyển sang UTC)
  const { startUtc, endUtc } = vnTodayRangeUtc();

  // Lịch hôm nay có số thứ tự + trạng thái — nguồn cho bảng gọi số.
  // Truy vấn Supabase để lấy danh sách lịch hẹn hôm nay
  // KHÔNG lấy tên bệnh nhân. Màn này treo ở phòng chờ và không cần đăng
  // nhập: bất cứ thứ gì select ở đây đều đi thẳng vào payload trình duyệt,
  // nên "không render" là chưa đủ — phải không tải về.
  // Chọn các cột cần thiết: id, thời gian bắt đầu, trạng thái, số thứ tự, kênh đặt lịch
  // Lấy tên bác sĩ từ bảng staff qua khóa ngoại doctor_id
  // Lấy tên dịch vụ từ bảng service_type qua khóa ngoại service_type_id
  const { data: appts, error } = await supabase
    .from("appointment") // Từ bảng appointment (lịch hẹn)
    .select(
      `id, slot_start, status, queue_number, booking_channel,
       doctor:staff!doctor_id(full_name),
       service:service_type!service_type_id(name)`,
    )
    .gte("slot_start", startUtc) // Lọc: slot_start >= thời gian bắt đầu hôm nay
    .lt("slot_start", endUtc) // Lọc: slot_start < thời gian kết thúc hôm nay
    .not("status", "in", "(CANCELLED,NO_SHOW,DOCTOR_DECLINED)") // Loại bỏ các trạng thái đã hủy/vắng mặt/bác sĩ từ chối
    .order("slot_start", { ascending: true }) // Sắp xếp theo thời gian bắt đầu tăng dần
    .limit(200); // Giới hạn tối đa 200 bản ghi

  // Nếu có lỗi khi truy vấn
  if (error) {
    return (
      // Hiển thị màn hình lỗi toàn màn hình với nền tối và chữ trắng
      <div className="flex h-screen items-center justify-center bg-ink text-white">
        <p className="text-lg">Không đọc được dữ liệu: {error.message}</p>
      </div>
    );
  }

  // Định nghĩa interface cho dữ liệu bác sĩ thô (từ Supabase trả về dạng mảng)
  interface DoctorRaw {
    full_name: string | null; // Tên đầy đủ của bác sĩ, có thể null
  }
  // Định nghĩa interface cho dữ liệu dịch vụ thô (từ Supabase trả về dạng mảng)
  interface ServiceRaw {
    name: string | null; // Tên dịch vụ, có thể null
  }
  // Định nghĩa kiểu Raw: lấy toàn bộ trường của appts nhưng thay doctor/service bằng dạng mảng
  type Raw = Omit<(typeof appts)[number], "doctor" | "service"> & {
    doctor: DoctorRaw[] | null; // Bác sĩ dạng mảng (Supabase trả về mảng)
    service: ServiceRaw[] | null; // Dịch vụ dạng mảng (Supabase trả về mảng)
  };
  // Chuẩn hóa dữ liệu: chuyển doctor/service từ mảng sang object đầu tiên (hoặc null)
  const normalized = (appts ?? []).map((a: Raw) => ({
    ...a, // Giữ nguyên các trường khác
    doctor: a.doctor?.[0] ?? null, // Lấy bác sĩ đầu tiên trong mảng, nếu rỗng thì null
    service: a.service?.[0] ?? null, // Lấy dịch vụ đầu tiên trong mảng, nếu rỗng thì null
  }));

  // Render component DisplayBoard với dữ liệu lịch hẹn đã chuẩn hóa
  return <DisplayBoard appts={normalized} />;
}