// GET /api/appointments/quote?date=YYYY-MM-DD&location_id=...&doctor_id=...
// Capacity Phase 1 (T-20260629-CAP-01) — proxy xuống FastAPI.
// Logic tính ngân sách + tải hiện có đã chuyển xuống capacity_service.py (backend).
// Frontend chỉ chuyển tiếp request + token, KHÔNG chứa logic nghiệp vụ.

// Nhập NextResponse từ next/server để tạo phản hồi HTTP cho Next.js
import { NextResponse } from "next/server";
// Nhập hàm getSupabaseServer để lấy client Supabase phía server
import { getSupabaseServer } from "../../../../lib/supabase-server";

// Lấy URL API backend từ biến môi trường CLINIC_API_URL, loại bỏ khoảng trắng thừa và dấu / ở cuối
const API_BASE = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

// Hàm xử lý GET request đến /api/appointments/quote
export async function GET(request: Request) {
  // Lấy client Supabase phía server (dùng cookie phiên đăng nhập)
  const supabase = await getSupabaseServer();
  // Lấy thông tin người dùng hiện tại từ Supabase
  const {
    data: { user },
  } = await supabase.auth.getUser();
  // Nếu không có người dùng (chưa đăng nhập) thì trả về lỗi 401
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  // Kiểm tra nếu API_BASE chưa được cấu hình
  if (!API_BASE) {
    // Trả về lỗi 503 Service Unavailable với thông báo tiếng Việt
    return NextResponse.json(
      { error: "CLINIC_API_URL chưa được cấu hình trên server." },
      { status: 503 },
    );
  }

  // Lấy các tham số query từ URL request
  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date"); // Ngày cần báo giá
  const location_id = searchParams.get("location_id"); // ID cơ sở (tùy chọn)
  const doctor_id = searchParams.get("doctor_id"); // ID bác sĩ (tùy chọn)

  // location_id KHÔNG bắt buộc: backend mặc định dùng cơ sở của người đang đăng
  // nhập, đúng như khi nó ghi lịch. Trình duyệt không có nguồn đáng tin để đoán
  // cơ sở, và một cú đoán sai ở đây tô màu lưới theo sai chỗ.
  // Kiểm tra nếu thiếu tham số date (bắt buộc)
  if (!date) {
    // Trả về lỗi 400 Bad Request với thông báo tiếng Việt
    return NextResponse.json({ error: "Thiếu date." }, { status: 400 });
  }

  // Lấy session hiện tại từ Supabase (chứa access_token)
  const {
    data: { session },
  } = await supabase.auth.getSession();
  // Trích xuất access_token từ session
  const token = session?.access_token;
  // Nếu không có token nghĩa là người dùng chưa đăng nhập
  if (!token) {
    // Trả về lỗi 401 Unauthorized với thông báo tiếng Việt
    return NextResponse.json({ error: "Chưa đăng nhập" }, { status: 401 });
  }

  // Tạo object headers cho request HTTP
  const headers: Record<string, string> = {
    // Gắn access token của người dùng vào header Authorization dạng Bearer
    Authorization: `Bearer ${token}`,
  };
  // Lấy API key dùng chung từ biến môi trường BACKEND_API_KEY
  const apiKey = process.env.BACKEND_API_KEY;
  // Nếu có API key thì thêm vào header X-API-Key để xác thực giữa các service
  if (apiKey) headers["X-API-Key"] = apiKey;

  // Build query string for backend
  // Tạo query string để gửi đến backend
  const params = new URLSearchParams({ date }); // Thêm tham số date
  if (location_id) params.set("location_id", location_id); // Thêm location_id nếu có
  if (doctor_id) params.set("doctor_id", doctor_id); // Thêm doctor_id nếu có

  try {
    // Gửi GET request đến backend FastAPI với query string
    const res = await fetch(
      `${API_BASE}/api/v1/appointments/quote?${params.toString()}`,
      { headers, cache: "no-store" }, // Không cache để luôn lấy dữ liệu mới nhất
    );
    // Đọc nội dung response dưới dạng text
    const text = await res.text();
    // Khởi tạo payload mặc định là object rỗng
    let payload: unknown = {};
    try {
      // Thử parse text thành JSON
      payload = text ? JSON.parse(text) : {};
    } catch {
      // Nếu parse thất bại, dùng text gốc làm thông báo lỗi
      payload = { error: text || "Lỗi máy chủ" };
    }
    // Trả về payload và status nguyên vẹn từ backend cho trình duyệt
    return NextResponse.json(payload, { status: res.status });
  } catch {
    // Nếu fetch thất bại (mất kết nối, backend down...)
    return NextResponse.json(
      // Trả về lỗi 502 Bad Gateway với thông báo tiếng Việt
      { error: "Không kết nối được máy chủ xử lý" },
      { status: 502 },
    );
  }
}