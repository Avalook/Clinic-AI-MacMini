// Proxy màn lượt khám (lát 1) xuống FastAPI.
//
// Trang này không quyết định gì. Nó xác nhận có phiên đăng nhập, chọn đúng một
// đường backend theo DANH SÁCH TRẮNG, rồi chuyển nguyên thân và khoá gửi lại.
// Vai nào được làm gì là việc của backend (require_role + service tự gác lần
// hai) — chép luật ấy vào đây là tạo bản thứ ba chờ ngày lệch.
//
// Mã trong đường dẫn phải là UUID: chuỗi tự do nối vào URL là cách mở một đường
// backend không nằm trong danh sách.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Thao tác cho phép → đường backend. */
const THAO_TAC: Record<string, (id: string) => string> = {
  "check-in": () => "/api/v1/luot-kham/check-in",
  "sinh-hieu": (id) => `/api/v1/luot-kham/visits/${id}/vitals`,
  // 25/09: ô "Bỏ qua bác sĩ tư vấn" — áp ngay vào vị trí khách.
  "bo-qua-tu-van": (id) => `/api/v1/luot-kham/visits/${id}/bo-qua-tu-van`,
  // [Bắt đầu] đo sinh hiệu (23/09/2026) — thay [Gọi vào đo]. `goi-do` còn trong
  // danh sách trắng cho tới khi chắc không màn nào gọi, nhưng màn Đo sinh hiệu
  // đã thôi dùng.
  "bat-dau-do": (id) => `/api/v1/luot-kham/visits/${id}/vitals/start`,
  "goi-do": (id) => `/api/v1/luot-kham/visits/${id}/goi-do`,
  "nhan-kham": (id) => `/api/v1/luot-kham/consultations/${id}/start`,
  // Bác sĩ tư vấn bấm Xong → khối Hành trình chuyển khách sang bác sĩ chính (H3).
  "xong-tu-van": (id) => `/api/v1/luot-kham/consultations/${id}/xong-tu-van`,
  "ghi-chu": (id) => `/api/v1/luot-kham/consultations/${id}/notes`,
  // Ô chữ tự do của bác sĩ tư vấn (24/09/2026) — id là PHIÊN TƯ VẤN.
  "noi-dung-tu-van": (id) =>
    `/api/v1/luot-kham/consultations/${id}/noi-dung-tu-van`,
  // Lát CD-01: MỘT lệnh thay cho nhập-nháp rồi duyệt. Bác sĩ và thư ký y khoa
  // ngang quyền (Tuyền, tin số 149). Khoá gửi lại bắt buộc.
  // Hai đường cũ bên dưới còn sống cho tới khi mọi màn đã chuyển sang đây.
  "chi-dinh": (id) => `/api/v1/luot-kham/consultations/${id}/service-orders`,
  "nhap-chi-dinh": (id) =>
    `/api/v1/luot-kham/consultations/${id}/draft-orders`,
  "duyet-chi-dinh": (id) =>
    `/api/v1/luot-kham/consultations/${id}/authorize-orders`,
  "ket-thuc-kham": (id) => `/api/v1/luot-kham/consultations/${id}/complete`,
  "xep-phong": (id) => `/api/v1/luot-kham/orders/${id}/dispatch`,
  "bat-dau-dich-vu": (id) => `/api/v1/luot-kham/orders/${id}/start`,
  "xong-dich-vu": (id) => `/api/v1/luot-kham/orders/${id}/complete`,
  // Nút "Đã khám xong" — máy chủ tự chọn kết quả phiên theo chỉ định còn lại.
  "kham-xong": (id) => `/api/v1/luot-kham/consultations/${id}/kham-xong`,
  "duyet-ket-qua": (id) => `/api/v1/luot-kham/orders/${id}/duyet-ket-qua`,
  // Gọi khách vào phòng — id là CHỖ CHỜ (queue entry), không phải phiên/chỉ định.
  "goi-khach": (id) => `/api/v1/luot-kham/hang-cho/${id}/goi`,
  // Bác sĩ miễn / chuyển theo dõi một yêu cầu của vòng đọc (Slice 1) — id là
  // YÊU CẦU (round_requirement).
  "quyet-yeu-cau": (id) => `/api/v1/luot-kham/yeu-cau/${id}/quyet`,
  // Khách xác nhận dịch vụ sẽ làm (Lifecycle v1, ConfirmServiceSelection) —
  // id là LƯỢT KHÁM. Khoá gửi lại là bắt buộc; backend từ chối nếu thiếu.
  "chon-dich-vu": (id) =>
    `/api/v1/luot-kham/visits/${id}/service-selection/confirm`,
  // Thực hiện dịch vụ (Lifecycle v1 Slice 5) — id là CHỈ ĐỊNH. Khoá gửi lại
  // bắt buộc; "xong" và "gián đoạn" phải kèm attempt_id trong thân.
  "bat-dau-v1": (id) => `/api/v1/luot-kham/orders/${id}/execution/bat-dau`,
  "xong-v1": (id) => `/api/v1/luot-kham/orders/${id}/execution/xong`,
  "khong-lam-v1": (id) => `/api/v1/luot-kham/orders/${id}/execution/khong-lam`,
  "gian-doan-v1": (id) => `/api/v1/luot-kham/orders/${id}/execution/gian-doan`,
  "lam-lai-v1": (id) => `/api/v1/luot-kham/orders/${id}/execution/lam-lai`,
  // V4 (30/09/2026): huỷ lần Bắt đầu bấm nhầm — chỉ khi chưa điền phiếu.
  "huy-bat-dau-v1": (id) => `/api/v1/luot-kham/orders/${id}/execution/huy-bat-dau`,
  // Điều phối chính thức (Lifecycle v1 Slice 4) — id là CHỈ ĐỊNH. Khoá gửi lại
  // bắt buộc. Màn hình chuyển sang dùng ở Slice 6.
  "xep-phong-v1": (id) => `/api/v1/luot-kham/orders/${id}/routing/assign`,
  "huy-xep-phong-v1": (id) => `/api/v1/luot-kham/orders/${id}/routing/invalidate`,
  // Phòng khách chọn ở quầy TRƯỚC khi thu tiền (24/09/2026) — id là CHỈ ĐỊNH.
  // Không phải xếp phòng chính thức: thu xong dây H4 xếp đúng phòng này.
  "phong-du-kien": (id) => `/api/v1/luot-kham/orders/${id}/routing/phong-du-kien`,
  // 29/09: trưởng ca chuyển dịch vụ ĐANG LÀM sang phòng khác (bắt buộc lý do).
  "chuyen-phong-dang-lam": (id) =>
    `/api/v1/luot-kham/orders/${id}/routing/chuyen-phong-dang-lam`,
  // 25/09: bật / tắt "Bắt buộc" của một chỉ định (chưa thu tiền).
  "bat-buoc": (id) => `/api/v1/luot-kham/orders/${id}/bat-buoc`,
  // 28/09: món kèm dịch vụ (đầu dò) — id là CHỈ ĐỊNH.
  "phu-thu": (id) => `/api/v1/luot-kham/orders/${id}/phu-thu`,
  // 28/09: tick dịch vụ khám theo mã KiotViet (tiền khám) — id là LƯỢT.
  "phi-kham": (id) => `/api/v1/luot-kham/visits/${id}/phi-kham`,
};

/** Các bảng đọc — `?xem=` → đường backend. Không có `xem` = bảng lượt khám. */
function duongDoc(url: URL): string | null {
  const xem = url.searchParams.get("xem");
  // `ngay` (29/09/2026): xem lại + sửa một ngày cũ (Đo sinh hiệu, Bàn khám tư
  // vấn, Bàn khám, phòng dịch vụ). Chỉ chuyển đúng dạng yyyy-mm-dd; máy chủ tự
  // đọc lại (rác → hôm nay).
  const ngay = url.searchParams.get("ngay") ?? "";
  const coNgay = /^\d{4}-\d{2}-\d{2}$/.test(ngay);
  if (!xem) {
    return coNgay ? `/api/v1/luot-kham/bang?ngay=${ngay}` : "/api/v1/luot-kham/bang";
  }
  if (xem === "phong-hom-nay") return "/api/v1/luot-kham/phong-hom-nay";
  if (xem === "ket-qua-cho-duyet") return "/api/v1/luot-kham/ket-qua-cho-duyet";
  if (xem === "cho-quyet") return "/api/v1/luot-kham/cho-quyet";
  // Xem lại một lượt (chỉ đọc, backend cắt theo vai) — batch pilot 18/09.
  if (xem === "xem-luot") {
    const luot = url.searchParams.get("luot") ?? "";
    return UUID_RE.test(luot) ? `/api/v1/xem-luot/${luot}` : null;
  }
  if (xem === "chi-dinh-hom-nay") return "/api/v1/luot-kham/chi-dinh-hom-nay";
  // Món kèm dịch vụ (đầu dò) của một lượt (28/09/2026).
  if (xem === "phu-thu") {
    const luot = url.searchParams.get("luot") ?? "";
    return UUID_RE.test(luot) ? `/api/v1/luot-kham/visits/${luot}/phu-thu` : null;
  }
  // Dịch vụ khám chọn được + đã chọn của một lượt (28/09/2026).
  if (xem === "phi-kham") {
    const luot = url.searchParams.get("luot") ?? "";
    return UUID_RE.test(luot) ? `/api/v1/luot-kham/visits/${luot}/phi-kham` : null;
  }
  // Bảng hành trình chung (nhóm 3, 24/09/2026).
  if (xem === "hanh-trinh") {
    // Xem lại ngày khác (30/09/2026). Chỉ chuyển tiếp dạng YYYY-MM-DD; máy chủ
    // vẫn tự bỏ qua ngày rác.
    const ngay = url.searchParams.get("ngay") ?? "";
    return /^\d{4}-\d{2}-\d{2}$/.test(ngay)
      ? `/api/v1/hanh-trinh/hom-nay?ngay=${ngay}`
      : "/api/v1/hanh-trinh/hom-nay";
  }
  // Khung đầy đủ Hành trình khách của một lượt (29/09/2026) — mọi thành viên
  // nội bộ, máy chủ quyết.
  if (xem === "hanh-trinh-khach") {
    const luot = url.searchParams.get("luot") ?? "";
    return UUID_RE.test(luot) ? `/api/v1/luot-kham/visits/${luot}/hanh-trinh-khach` : null;
  }
  // Gợi ý phòng theo luật (Slice 4) — chỉ đọc, không đổi gì.
  if (xem === "goi-y-phong") {
    const cd = url.searchParams.get("chi_dinh") ?? "";
    return UUID_RE.test(cd) ? `/api/v1/luot-kham/orders/${cd}/routing/recommendation` : null;
  }
  // Một chỉ định trong phòng: trạng thái thực hiện + hai revision + mẫu kết
  // quả. Màn phòng đọc cái này trước khi bấm 5 lệnh thực hiện.
  if (xem === "thuc-hien") {
    const cd = url.searchParams.get("chi_dinh") ?? "";
    return UUID_RE.test(cd)
      ? `/api/v1/luot-kham/orders/${cd}/execution`
      : null;
  }
  if (xem === "hang-cho") {
    const q = new URLSearchParams();
    // Hàng TƯ VẤN chung (24/09/2026).
    if (url.searchParams.get("tu_van") === "true") {
      q.set("tu_van", "true");
    } else {
      const phong = url.searchParams.get("phong") ?? "";
      if (phong && !UUID_RE.test(phong)) return null;
      if (phong) q.set("phong", phong);
    }
    // `ngay` (29/09/2026): xem lại hàng chờ của một ngày cũ.
    if (coNgay) q.set("ngay", ngay);
    const qs = q.toString();
    return qs ? `/api/v1/luot-kham/hang-cho?${qs}` : "/api/v1/luot-kham/hang-cho";
  }
  return null;
}

/** Thao tác không gắn với một dòng cụ thể trên đường dẫn. */
const KHONG_CAN_ID = new Set(["check-in"]);

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
  const duong = duongDoc(new URL(request.url));
  if (!duong) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Bảng cần đọc không hợp lệ." },
      { status: 400 },
    );
  }
  return proxyJsonToBackend("GET", duong, undefined);
}

export async function POST(request: Request) {
  if (!(await coPhien())) {
    return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  }

  let than: { thao_tac?: unknown; id?: unknown; du_lieu?: unknown };
  try {
    than = await request.json();
  } catch {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Dữ liệu gửi lên không đọc được." },
      { status: 400 },
    );
  }

  const tenThaoTac = typeof than.thao_tac === "string" ? than.thao_tac : "";
  const duong = THAO_TAC[tenThaoTac];
  if (!duong) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Thao tác không hợp lệ." },
      { status: 400 },
    );
  }
  const id = typeof than.id === "string" ? than.id : "";
  if (!KHONG_CAN_ID.has(tenThaoTac) && !UUID_RE.test(id)) {
    return NextResponse.json(
      { error: "BAD_REQUEST", message: "Mã không hợp lệ." },
      { status: 400 },
    );
  }

  const khoa = request.headers.get("Idempotency-Key") ?? undefined;
  return proxyJsonToBackend("POST", duong(id), than.du_lieu ?? {}, khoa);
}
