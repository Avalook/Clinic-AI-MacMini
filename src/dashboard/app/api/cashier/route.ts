// /api/cashier — người đang chờ thu tiền hôm nay.
//
// Chuyển tiếp thẳng `/api/v1/cashier/board`. Ô nào hiện (thuốc / dịch vụ) do
// `modes` quyết định, còn VAI NÀO ĐƯỢC XEM thì FastAPI gác — lớp này không tự
// suy ra quyền từ vai, vì thế là viết luật lần thứ hai bằng ngôn ngữ khác.

import { NextResponse } from "next/server";
import { getCallerAuthHeaders, proxyJsonToBackend } from "../../../lib/backend-proxy";

const NGAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function GET(request: Request) {
  const url = new URL(request.url);
  // Giao dịch đã ghi (xem lại, kể cả dòng đã huỷ) — batch pilot 18/09.
  if (url.searchParams.get("xem") === "giao-dich") {
    const q = new URLSearchParams();
    for (const k of ["tu", "den"]) {
      const v = url.searchParams.get(k) ?? "";
      if (NGAY_RE.test(v)) q.set(k, v);
    }
    // Mỗi quầy chỉ xem sổ loại tiền của mình (01/10/2026).
    const loai = url.searchParams.get("kind");
    if (loai === "dich_vu" || loai === "thuoc") q.set("kind", loai);
    return proxyJsonToBackend("GET", `/api/v1/cashier/giao-dich?${q.toString()}`, undefined);
  }
  // Lịch sử gom theo khách + CSV + phiếu thu (quầy một hoá đơn, 27/09/2026).
  const xem = url.searchParams.get("xem");
  if (xem === "lich-su" || xem === "lich-su-csv") {
    const q = new URLSearchParams();
    for (const k of ["tu", "den"]) {
      const v = url.searchParams.get(k) ?? "";
      if (NGAY_RE.test(v)) q.set(k, v);
    }
    for (const k of ["tim", "hinh_thuc", "nguoi_thu"]) {
      const v = (url.searchParams.get(k) ?? "").slice(0, 200);
      if (v) q.set(k, v);
    }
    if (xem === "lich-su") {
      return proxyJsonToBackend("GET", `/api/v1/cashier/lich-su?${q.toString()}`, undefined);
    }
    const headers = await getCallerAuthHeaders();
    const base = process.env.CLINIC_API_URL;
    if (!headers || !base) {
      return NextResponse.json({ error: "Chưa đăng nhập hoặc thiếu CLINIC_API_URL" }, { status: 401 });
    }
    const res = await fetch(`${base}/api/v1/cashier/lich-su.csv?${q.toString()}`, {
      headers,
      cache: "no-store",
    });
    return new NextResponse(res.body, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") ?? "text/csv; charset=utf-8",
        "Content-Disposition":
          res.headers.get("Content-Disposition") ?? 'attachment; filename="lich-su-thu.csv"',
        "Cache-Control": "private, no-store",
      },
    });
  }
  if (xem === "phieu") {
    const id = url.searchParams.get("id") ?? "";
    const xin = url.searchParams.get("loai");
    const loai = xin === "hoan" || xin === "huong_dan" ? xin : "thu";
    if (!/^[0-9a-f-]{36}$/i.test(id)) {
      return NextResponse.json({ error: "Mã phiếu không hợp lệ" }, { status: 400 });
    }
    return proxyJsonToBackend("GET", `/api/v1/cashier/phieu/${id}?loai=${loai}`, undefined);
  }
  // Mọi phiếu thu đã thu của MỘT lượt (CSKH in hoá đơn thuốc trả khách, 28/09).
  if (xem === "phieu-luot") {
    const visit = url.searchParams.get("visit") ?? "";
    const kind = url.searchParams.get("kind") === "dich_vu" ? "dich_vu" : "thuoc";
    if (!/^[0-9a-f-]{36}$/i.test(visit)) {
      return NextResponse.json({ error: "Mã lượt không hợp lệ" }, { status: 400 });
    }
    return proxyJsonToBackend(
      "GET",
      `/api/v1/cashier/phieu-luot/${visit}?kind=${kind}`,
      undefined,
    );
  }
  const modes = url.searchParams.get("modes") ?? "dich_vu,thuoc";
  // Thanh ngày (02/10/2026): xem lại một ngày cũ. Chỉ chuyển đúng dạng
  // yyyy-mm-dd; máy chủ quyết khoảng (rác → hôm nay).
  const ngay = url.searchParams.get("ngay") ?? "";
  const duoiNgay = NGAY_RE.test(ngay) ? `&ngay=${ngay}` : "";
  // Giữ NGUYÊN mã và câu của máy chủ: bị chặn quyền (403) phải nói là bị chặn,
  // không được thành "Không đọc được danh sách" như mất kết nối (tự kiểm
  // 16/09/2026 — người dùng thấy câu ấy khi vai hôm nay không có quyền thu).
  const res = await proxyJsonToBackend(
    "GET",
    `/api/v1/cashier/board?modes=${encodeURIComponent(modes)}${duoiNgay}`,
    undefined,
  );
  if (res.status === 401 || res.status === 403) {
    // Giữ NGUYÊN câu của máy chủ (28/09/2026): câu cũ "Hôm nay bạn không đứng
    // quầy thu ngân" nói sai nguyên nhân khi lý do thật là thiếu lego. Quyền chỉ
    // có một nguồn (lego / lịch hôm nay), máy chủ nói đúng thiếu gì.
    const d = (await res.json().catch(() => null)) as {
      message?: string;
      detail?: unknown;
    } | null;
    const cau =
      d?.message ??
      (typeof d?.detail === "string" ? d.detail : null) ??
      "Bạn không có quyền thu tiền dịch vụ / tiền thuốc.";
    return NextResponse.json({ error: cau }, { status: res.status });
  }
  const d = res.ok
    ? ((await res.json()) as { items: unknown[]; paid: unknown[] })
    : null;
  if (d === null) {
    // null = không với tới backend. Trả danh sách rỗng ở đây thì quầy nói dối
    // "hôm nay không ai chờ thu", và thu ngân đóng máy đi về.
    return NextResponse.json(
      { error: "Không đọc được danh sách chờ thu" },
      { status: 502 },
    );
  }
  return NextResponse.json(d, {
    headers: { "Cache-Control": "private, no-store" },
  });
}
