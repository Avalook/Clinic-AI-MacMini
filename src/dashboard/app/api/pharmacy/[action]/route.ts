// Proxy các thao tác nhà thuốc xuống FastAPI.
//
// Trước đây bốn màn /pharmacy đọc thẳng Supabase và KHÔNG có đường ghi nào —
// RLS chỉ cấp SELECT, nên kể cả gắn nút thì trình duyệt cũng không ghi được.
// Mọi thao tác kho đi qua đây.
//
// Danh sách trắng ở dưới quyết định đường nào hợp lệ. Một `[action]` trần sẽ
// mở luôn cả những đường thêm sau này mà chưa ai cân nhắc có nên cho trình
// duyệt gọi không.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getCallerAuthHeaders, proxyJsonToBackend } from "../../../../lib/backend-proxy";

/** Thao tác cho phép → đường backend. */
const ACTIONS: Record<string, string> = {
  "sua-lo": "/api/v1/pharmacy/sua-lo",
  "huy-lo-het-han": "/api/v1/pharmacy/huy-lo-het-han",
  "hoan-huy-lo": "/api/v1/pharmacy/hoan-huy-lo",
  "so-ngay-canh-bao": "/api/v1/pharmacy/so-ngay-canh-bao",
  receive: "/api/v1/pharmacy/receive",
  dispense: "/api/v1/pharmacy/dispense",
  refuse: "/api/v1/pharmacy/refuse",
  "close-line": "/api/v1/pharmacy/close-line",
  adjust: "/api/v1/pharmacy/adjust",
  discard: "/api/v1/pharmacy/discard",
  // Contract tiền–thuốc CP4: xác định thuốc kho, số mua, chọn / bỏ / đổi lô.
  "xac-dinh-thuoc": "/api/v1/pharmacy/xac-dinh-thuoc",
  "so-luong-mua": "/api/v1/pharmacy/so-luong-mua",
  "phan-lo": "/api/v1/pharmacy/phan-lo",
  "bo-phan-lo": "/api/v1/pharmacy/bo-phan-lo",
  "doi-lo": "/api/v1/pharmacy/doi-lo",
  // CP5: huỷ phần đã bán chưa giao (cần căn cứ), khách trả thuốc (chưa xử lý).
  "huy-phan-chua-giao": "/api/v1/pharmacy/huy-phan-chua-giao",
  "khach-tra": "/api/v1/pharmacy/khach-tra",
  // 25/09: Kho thuốc — thêm / sửa thuốc trong danh mục (tên, giá, hướng dẫn).
  "luu-thuoc": "/api/v1/pharmacy/danh-muc",
  // 28/09: giao không lô → gán lô sau ở Kho thuốc (từ 27/10 chỉ còn khi kho chưa đủ lô để máy tự trừ).
  "gan-lo": "/api/v1/pharmacy/gan-lo",
  // 29/09: phiếu nhập nhiều dòng · phiếu kiểm kho (bắt buộc Idempotency-Key).
  "phieu-nhap": "/api/v1/pharmacy/phieu-nhap",
  "kiem-kho": "/api/v1/pharmacy/kiem-kho",
  // 30/09 (V8): khách chỉ đến mua thuốc — mở / lấy lại lượt Bán lẻ.
  "ban-le": "/api/v1/pharmacy/ban-le",
  // 14/10 (G3b): gắn / gỡ mã vạch của thuốc (người có quyền kho).
  "gan-ma-vach": "/api/v1/pharmacy/gan-ma-vach",
  "go-ma-vach": "/api/v1/pharmacy/go-ma-vach",
  // 14/10 (G7): tách KHO / QUẦY — phiếu chuyển (bắt buộc Idempotency-Key), hoàn tác,
  // bật / tắt tách theo cơ sở (máy chủ kiểm `config.clinic.manage`).
  "chuyen-kho": "/api/v1/pharmacy/chuyen-kho",
  "hoan-tac-chuyen-kho": "/api/v1/pharmacy/hoan-tac-chuyen-kho",
  "tach-kho-quay": "/api/v1/pharmacy/tach-kho-quay",
  // 17/10 (việc B): quyết định thuốc khách trả chờ kiểm — nhập lại bán được / huỷ (một lần).
  "xu-ly-thuoc-tra": "/api/v1/pharmacy/xu-ly-thuoc-tra",
  // 09/10: bán theo đơn khám cũ — nối / gỡ nối đơn gốc của lượt Bán lẻ.
  "ban-le-theo-don": "/api/v1/pharmacy/ban-le/theo-don",
  "ban-le-go-don": "/api/v1/pharmacy/ban-le/go-don",
  // Từ khung chọn khách: mở lượt + nối đơn + thêm dòng trong một giao dịch.
  "ban-le-mo-theo-don": "/api/v1/pharmacy/ban-le/mo-theo-don",
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Đường ĐỌC cho phép (29/09/2026 — kho kiểu KiotViet) → đường backend. Tham
 *  số chỉ chuyển nguyên văn; máy chủ đọc lại (ngày rác → hôm nay). */
const DOC: Record<string, (q: URLSearchParams) => string | null> = {
  "so-ngay-canh-bao": () => "/api/v1/pharmacy/so-ngay-canh-bao",
  "the-kho": (q) => {
    const id = q.get("id") ?? "";
    return UUID_RE.test(id) ? `/api/v1/pharmacy/the-kho/${id}` : null;
  },
  "xuat-nhap-ton": (q) =>
    `/api/v1/pharmacy/xuat-nhap-ton?${new URLSearchParams({
      tu: q.get("tu") ?? "",
      den: q.get("den") ?? "",
    })}`,
  "phieu-kho": (q) =>
    `/api/v1/pharmacy/phieu-kho?${new URLSearchParams({ loai: q.get("loai") ?? "NHAP" })}`,
  // 30/09 (V8): tìm khách để mở lượt mua thuốc · hoá đơn thuốc của lượt Bán lẻ.
  "tim-khach": (q) =>
    `/api/v1/pharmacy/ban-le/tim-khach?${new URLSearchParams({ q: q.get("q") ?? "" })}`,
  "ban-le": (q) => {
    const id = q.get("id") ?? "";
    return UUID_RE.test(id) ? `/api/v1/pharmacy/ban-le/${id}` : null;
  },
  // 14/10 (G3b): quét mã → thuốc / lô · dữ liệu in tem lô.
  "tra-ma": (q) => `/api/v1/pharmacy/tra-ma?${new URLSearchParams({ ma: q.get("ma") ?? "" })}`,
  // 17/10: nhập khác đơn vị bán → xem trước quy đổi (chỉ đọc, không nhớ hệ số).
  "quy-doi": (q) => {
    const id = q.get("drug_catalog_id") ?? "";
    return UUID_RE.test(id)
      ? `/api/v1/pharmacy/quy-doi?${new URLSearchParams({
          drug_catalog_id: id,
          unit: q.get("unit") ?? "",
          he_so: q.get("he_so") ?? "",
          so_luong: q.get("so_luong") ?? "",
        })}`
      : null;
  },
  "tem-lo": (q) =>
    `/api/v1/pharmacy/tem-lo?${new URLSearchParams({
      ids: q.get("ids") ?? "",
      phieu: q.get("phieu") ?? "",
    })}`,
  // 09/10: chọn khách cũ → lịch sử đơn thuốc theo trang (chưa mở lượt).
  "lich-su-don": (q) => {
    const id = q.get("clinic_patient_id") ?? "";
    return UUID_RE.test(id)
      ? `/api/v1/pharmacy/ban-le/lich-su-don?${new URLSearchParams({
          clinic_patient_id: id,
          trang: q.get("trang") ?? "0",
        })}`
      : null;
  },
};

export async function GET(
  request: Request,
  { params }: { params: Promise<{ action: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const { action } = await params;
  if (action === "xuat-nhap-ton-xlsx") {
    const query = new URL(request.url).searchParams;
    const q = new URLSearchParams({ tu: query.get("tu") ?? "", den: query.get("den") ?? "" });
    const headers = await getCallerAuthHeaders();
    const base = process.env.CLINIC_API_URL;
    if (!headers || !base) return NextResponse.json({ error: "Chưa đăng nhập hoặc thiếu CLINIC_API_URL" }, { status: 401 });
    const res = await fetch(`${base}/api/v1/pharmacy/xuat-nhap-ton.xlsx?${q}`, { headers, cache: "no-store" });
    return new NextResponse(res.body, { status: res.status, headers: {
      "Content-Type": res.headers.get("Content-Type") ?? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": res.headers.get("Content-Disposition") ?? 'attachment; filename="xuat-nhap-ton.xlsx"',
      "Cache-Control": "private, no-store",
    } });
  }
  const path = DOC[action]?.(new URL(request.url).searchParams) ?? null;
  if (!path) {
    return NextResponse.json({ error: `Không đọc được: ${action}` }, { status: 400 });
  }
  return proxyJsonToBackend("GET", path, undefined);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ action: string }> },
) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  // Không gác vai ở proxy (24/09/2026): backend hỏi QUYỀN "Nhà thuốc"
  // (`pharmacy.dispense`) — người được cấp khối trên màn Phân quyền làm được
  // ngay, không ăn 403 ở cửa ngoài.

  const { action } = await params;
  const path = ACTIONS[action];
  if (!path) {
    return NextResponse.json(
      { error: `Thao tác không hợp lệ: ${action}` },
      { status: 400 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // Chuyển tiếp khoá chống-gửi-trùng (review CP5 P1-A). Trước bản này proxy
  // KHÔNG chuyển header, nên chốt chống trùng của /pharmacy/dispense (16/09)
  // chưa từng chạy khi bấm từ giao diện.
  const khoa = request.headers.get("Idempotency-Key") ?? undefined;
  return proxyJsonToBackend("POST", path, body, khoa);
}
