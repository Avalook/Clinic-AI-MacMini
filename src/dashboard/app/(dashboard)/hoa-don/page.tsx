import { requireNavAccess } from "@/lib/clinic-session";
import { layCoSo } from "@/lib/danh-muc";
import DanhSachHoaDon, { type LocBanDau } from "./DanhSachHoaDon";

export const dynamic = "force-dynamic";
export const metadata = { title: "Danh sách hoá đơn" };

const NGAY = /^\d{4}-\d{2}-\d{2}$/;

/** Link từ khối Dòng tiền của báo cáo (14/10/2026): mở sẵn đúng ngày / ca / cơ sở
 *  / nhóm hoá đơn. Chỉ chép chuỗi — máy chủ kiểm giá trị (rác thì không lọc). */
export default async function TrangHoaDon({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  await requireNavAccess("/hoa-don");
  const coSo = await layCoSo();
  const sp = await searchParams;
  const mot = (k: string) => {
    const v = sp[k];
    return typeof v === "string" ? v.slice(0, 64) : undefined;
  };
  const tu = mot("tu");
  const den = mot("den");
  const banDau: LocBanDau = {
    ...(tu && NGAY.test(tu) ? { tu } : {}),
    ...(den && NGAY.test(den) ? { den } : {}),
    ca: mot("ca"),
    co_so: mot("co_so"),
    nhom: mot("nhom"),
    hinh_thuc: mot("hinh_thuc"),
    loai: mot("loai"),
  };
  return <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
    <header><h1 className="text-title font-semibold text-ink">Danh sách hoá đơn</h1></header>
    <DanhSachHoaDon coSo={coSo} banDau={banDau} />
  </main>;
}
