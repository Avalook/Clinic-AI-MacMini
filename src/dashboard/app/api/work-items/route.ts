// Bảng việc của một khu làm việc.
//
//   GET /api/work-items?workspace=khu_van_hanh[&mine_only=1]
//
// Proxy mỏng. Vai nào được xem khu nào là việc của backend
// (`require_workspace_read_access`) — chép luật ấy sang đây là tạo bản thứ hai
// chờ ngày nói ngược với bản thật.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const KHU_RE = /^[a-z0-9_]{1,64}$/;

export async function GET(request: Request) {
  const url = new URL(request.url);
  const khu = url.searchParams.get("workspace") ?? "";
  if (!KHU_RE.test(khu)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Khu làm việc không hợp lệ." },
      { status: 400 },
    );
  }
  const chiCuaToi = url.searchParams.get("mine_only") === "1";
  const duong =
    `/api/v1/work-items?workspace=${encodeURIComponent(khu)}` +
    (chiCuaToi ? "&mine_only=true" : "");
  return proxyJsonToBackend("GET", duong, undefined);
}
