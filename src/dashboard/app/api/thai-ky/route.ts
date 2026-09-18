// Proxy Thai kỳ xuống FastAPI. Không quyết gì ở đây: ai được đọc/ghi là việc
// của backend (chỉ bác sĩ ghi — `thai_ky_service`). Mã trên URL phải là UUID.
import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function coPhien(): Promise<boolean> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return Boolean(user);
}

export async function GET(request: Request) {
  if (!(await coPhien())) {
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  }
  const khach = new URL(request.url).searchParams.get("clinic_patient_id") ?? "";
  if (!UUID_RE.test(khach)) {
    return NextResponse.json({ error: "BAD_REQUEST", message: "Mã khách không hợp lệ." }, { status: 400 });
  }
  return proxyJsonToBackend("GET", `/api/v1/thai-ky?clinic_patient_id=${khach}`, undefined);
}

export async function POST(request: Request) {
  if (!(await coPhien())) {
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  }
  const than = (await request.json().catch(() => null)) as
    | { id?: unknown; du_lieu?: unknown }
    | null;
  if (!than || typeof than.du_lieu !== "object" || than.du_lieu === null) {
    return NextResponse.json({ error: "BAD_REQUEST", message: "Dữ liệu không đọc được." }, { status: 400 });
  }
  // Có `id` = cập nhật thai kỳ ấy; không có = tạo mới.
  if (typeof than.id === "string") {
    if (!UUID_RE.test(than.id)) {
      return NextResponse.json({ error: "BAD_REQUEST", message: "Mã thai kỳ không hợp lệ." }, { status: 400 });
    }
    return proxyJsonToBackend("PATCH", `/api/v1/thai-ky/${than.id}`, than.du_lieu);
  }
  return proxyJsonToBackend("POST", "/api/v1/thai-ky", than.du_lieu);
}
