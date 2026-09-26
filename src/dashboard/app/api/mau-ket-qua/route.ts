// Mẫu kết quả — proxy mỏng sang FastAPI cho màn `/settings/mau-ket-qua` (27/09/2026).
//
//   GET  /api/mau-ket-qua?xem=bang-gan              → dịch vụ + mẫu đã gắn + quyền
//   GET  /api/mau-ket-qua?xem=de-xuat               → máy đề xuất mẫu cho dịch vụ chưa gắn
//   GET  /api/mau-ket-qua?xem=bieu-mau&form_id=KQ_X → khung đang dùng (để sửa)
//   POST {thao_tac: "gan" | "go", service_code, mau}
//   POST {thao_tac: "tao", ten, nhom, chep_tu?}
//   POST {thao_tac: "xuat-ban", form_id, khung, expected_version, ten?}
//
// Tầng này chỉ kiểm HÌNH của mã (chuỗi tự do không nối được vào đường dẫn
// backend). Quyền và luật khung (kiểu ô, mã trùng…) ở máy chủ.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const FORM_RE = /^KQ_[A-Z0-9_]{1,60}$/;
const MA_RE = /^[A-Za-z0-9_-]{1,64}$/;

function sai(message: string) {
  return NextResponse.json({ error: "BAD_REQUEST", message }, { status: 400 });
}

export async function GET(request: Request) {
  const q = new URL(request.url).searchParams;
  const xem = q.get("xem");
  if (xem === "bang-gan") {
    return proxyJsonToBackend("GET", "/api/v1/mau-ket-qua/bang-gan", undefined);
  }
  if (xem === "de-xuat") {
    return proxyJsonToBackend("GET", "/api/v1/mau-ket-qua/de-xuat", undefined);
  }
  if (xem === "bieu-mau") {
    const f = q.get("form_id") ?? "";
    if (!FORM_RE.test(f)) return sai("Mã mẫu không hợp lệ.");
    return proxyJsonToBackend("GET", `/api/v1/bieu-mau/${f}`, undefined);
  }
  return sai("Không rõ cần đọc gì.");
}

interface Than {
  thao_tac?: string;
  service_code?: unknown;
  mau?: unknown;
  ten?: unknown;
  nhom?: unknown;
  chep_tu?: unknown;
  form_id?: unknown;
  khung?: unknown;
  expected_version?: unknown;
}

export async function POST(request: Request) {
  let b: Than;
  try {
    b = (await request.json()) as Than;
  } catch {
    return sai("Dữ liệu gửi lên không đọc được.");
  }
  const chu = (v: unknown) => (typeof v === "string" ? v.trim() : "");

  if (b.thao_tac === "gan" || b.thao_tac === "go") {
    const sc = chu(b.service_code);
    const mau = chu(b.mau);
    if (!MA_RE.test(sc) || !MA_RE.test(mau)) return sai("Mã dịch vụ / mã mẫu không hợp lệ.");
    return proxyJsonToBackend("POST", `/api/v1/mau-ket-qua/${b.thao_tac}`, {
      service_code: sc,
      mau,
    });
  }
  if (b.thao_tac === "tao") {
    const chep = chu(b.chep_tu);
    if (chep && !FORM_RE.test(chep)) return sai("Mẫu để chép không hợp lệ.");
    return proxyJsonToBackend("POST", "/api/v1/mau-ket-qua/tao", {
      ten: chu(b.ten),
      nhom: chu(b.nhom) || "Khác",
      chep_tu: chep || null,
    });
  }
  if (b.thao_tac === "xuat-ban") {
    const f = chu(b.form_id);
    if (!FORM_RE.test(f)) return sai("Mã mẫu không hợp lệ.");
    if (!Array.isArray(b.khung)) return sai("Thiếu khung mẫu.");
    const v = Number(b.expected_version);
    if (!Number.isInteger(v) || v < 1) return sai("Thiếu phiên bản đang sửa.");
    return proxyJsonToBackend("POST", `/api/v1/bieu-mau/${f}/xuat-ban`, {
      khung: b.khung,
      expected_version: v,
      ten: chu(b.ten) || null,
    });
  }
  return sai("Không rõ thao tác.");
}
