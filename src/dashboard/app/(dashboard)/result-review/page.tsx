// Duyệt kết quả — Doctor duyệt kết quả XN (image_9 + image_3).
// Hàng đợi kết quả chờ duyệt: xem chi tiết, ký duyệt / trả lại chỉnh sửa.

// Nhập hàm getSupabaseServer để lấy client Supabase phía server
import { getSupabaseServer } from "../../../lib/supabase-server";
// Nhập hàm requireNavAccess để kiểm tra quyền truy cập trang (dựa trên vai trò người dùng)
import { requireNavAccess } from "../../../lib/clinic-session";
// Nhập component ResultReviewBoard để hiển thị bảng duyệt kết quả
import ResultReviewBoard from "./ResultReviewBoard";

// Ép Next.js render trang này động (không cache) — luôn lấy dữ liệu mới nhất
export const dynamic = "force-dynamic";

// Component chính của trang duyệt kết quả (server component)
export default async function ResultReviewPage() {
  // Kiểm tra quyền truy cập trang /result-review — nếu không có quyền sẽ redirect hoặc từ chối
  await requireNavAccess("/result-review");
  // Lấy client Supabase phía server (dùng cookie phiên đăng nhập)
  const supabase = await getSupabaseServer();

  // Truy vấn Supabase để lấy danh sách kết quả xét nghiệm cần bác sĩ duyệt
  // Chọn các cột cần thiết của kết quả xét nghiệm
  // Lấy thông tin bệnh nhân từ bảng clinic_patient qua khóa ngoại clinic_patient_id
  const { data: results, error } = await supabase
    .from("lab_result") // Từ bảng lab_result (kết quả xét nghiệm)
    .select(
      `lab_result_id, test_code, test_name, result_value, result_numeric,
       result_unit, reference_range_low, reference_range_high, flag,
       triage_group, requires_doctor_review, is_finalized, result_received_at,
       patient:clinic_patient_id(full_name, phone_primary)`,
    )
    .eq("requires_doctor_review", true) // Lọc: chỉ lấy kết quả cần bác sĩ duyệt
    .order("result_received_at", { ascending: false }) // Sắp xếp theo thời gian nhận kết quả giảm dần (mới nhất trước)
    .limit(100); // Giới hạn tối đa 100 bản ghi

  // Nếu có lỗi khi truy vấn
  if (error) {
    return (
      // Hiển thị thông báo lỗi màu đỏ
      <div className="p-6 text-sm text-danger">
        Không đọc được kết quả: {error.message}
      </div>
    );
  }

  // Định nghĩa interface cho dữ liệu bệnh nhân thô (từ Supabase trả về dạng mảng)
  interface PatientRaw {
    full_name: string | null; // Tên đầy đủ của bệnh nhân, có thể null
    phone_primary: string | null; // Số điện thoại chính, có thể null
  }
  // Định nghĩa kiểu Raw: lấy toàn bộ trường của results nhưng thay patient bằng dạng mảng
  type Raw = Omit<(typeof results)[number], "patient"> & {
    patient: PatientRaw[] | null; // Bệnh nhân dạng mảng (Supabase trả về mảng)
  };
  // Chuẩn hóa dữ liệu: chuyển patient từ mảng sang object đầu tiên (hoặc null)
  const normalized = (results ?? []).map((r: Raw) => ({
    ...r, // Giữ nguyên các trường khác
    patient: r.patient?.[0] ?? null, // Lấy bệnh nhân đầu tiên trong mảng, nếu rỗng thì null
  }));

  // Render component ResultReviewBoard với danh sách kết quả đã chuẩn hóa
  return <ResultReviewBoard results={normalized} />;
}