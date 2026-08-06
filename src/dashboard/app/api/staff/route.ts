// GET/PATCH /api/staff — hồ sơ nhân sự. Proxy mỏng sang FastAPI.
//
// Không tự viết luật ở đây. Ai được sửa nhân sự đã do backend quyết
// (_STAFF_MANAGEMENT_GUARD = require_role(MANAGEMENT) trong routers/staff.py);
// một bản sao luật ở tầng này là một bản sao sẽ lệch.
import { NextResponse } from "next/server";
import { fetchFromBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";

export interface StaffRow {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
  primary_location_id: string | null;
  employment_type: string;
  is_training: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // Hồ sơ cá nhân + pháp lý. `null` khi chưa ai nhập.
  date_of_birth: string | null;
  gender: string | null;
  national_id_number: string | null;
  phone: string | null;
  email: string | null;
  license_number: string | null;
  license_issued_on: string | null;
  practice_scope: string | null;
}

export async function GET() {
  const rows = await fetchFromBackend<StaffRow[]>("/api/v1/staff");
  if (!rows) {
    return NextResponse.json({ error: "Không đọc được danh sách nhân sự" }, { status: 502 });
  }
  return NextResponse.json({ items: rows });
}

export async function PATCH(request: Request) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Dữ liệu gửi lên không hợp lệ" }, { status: 400 });
  }

  const id = typeof body.id === "string" ? body.id.trim() : "";
  if (!id) {
    return NextResponse.json({ error: "Thiếu mã nhân sự" }, { status: 400 });
  }
  delete body.id;

  // Chỉ chuyển tiếp đúng những trường StaffUpdateDTO nhận. Gửi thừa một khoá
  // lạ thì Pydantic trả 422 với câu tiếng Anh, và người dùng thấy một lỗi
  // không liên quan gì tới ô họ vừa sửa.
  const allowed = [
    "full_name",
    "short_name",
    "primary_department",
    "primary_location_id",
    "employment_type",
    "is_training",
    "is_active",
    // Hồ sơ cá nhân + pháp lý (migration 20260806000005). Trước đây màn hình
    // liệt kê chúng trong khối "Chưa lưu được" vì database chưa có cột.
    "date_of_birth",
    "gender",
    "national_id_number",
    "phone",
    "email",
    "license_number",
    "license_issued_on",
    "practice_scope",
  ] as const;
  const payload: Record<string, unknown> = {};
  for (const key of allowed) {
    if (key in body) payload[key] = body[key];
  }
  if (Object.keys(payload).length === 0) {
    return NextResponse.json({ error: "Không có gì để lưu" }, { status: 400 });
  }

  return proxyJsonToBackend("PATCH", `/api/v1/staff/${encodeURIComponent(id)}`, payload);
}
