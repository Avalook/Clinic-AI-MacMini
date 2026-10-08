// CHỌN CƠ SỞ — sau đăng nhập và khi bấm chip cơ sở trên thanh trên (08/10/2026,
// mở Hào Nam). Mọi nhân viên vào được mọi cơ sở đang bật; máy chủ trả danh sách
// + cơ sở gợi ý (ca trực hôm nay → cơ sở mặc định). Trang chỉ vẽ và gửi lựa chọn.

import { MapPin } from "lucide-react";
import { redirect } from "next/navigation";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { chonCoSo } from "./actions";
import { duongVeAnToan } from "./duong-ve";

type CoSo = { id: string; code: string; name: string; address: string | null };
type DanhSach = {
  co_so: CoSo[];
  goi_y: string | null;
  theo_lich: boolean;
  dang_chon: string;
};

export default async function ChonCoSoPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const next = duongVeAnToan((await searchParams).next);
  const ds = await fetchFromBackend<DanhSach>("/api/v1/me/co-so");
  // Một cơ sở (hay tài khoản TV/đối tác — máy chủ không trả danh sách): không
  // có gì để chọn, đi thẳng như trước khi có hai cơ sở.
  if (!ds || ds.co_so.length <= 1) redirect(next);

  const macDinh = ds.goi_y ?? ds.dang_chon;
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-brand-100 px-4">
      <form
        action={chonCoSo}
        className="w-full max-w-sm space-y-4 rounded-2xl bg-white/90 p-7 shadow-[0_4px_24px_rgba(0,0,0,0.08)]"
      >
        <input type="hidden" name="next" value={next} />
        <div className="space-y-1 text-center">
          <h1 className="text-lg font-semibold text-ink">Hôm nay làm ở cơ sở nào?</h1>
          <p className="text-sm text-ink-muted">
            Lịch hẹn, hàng chờ, kho thuốc sẽ theo cơ sở bạn chọn. Đổi lại được ở
            thanh trên.
          </p>
        </div>
        <div className="space-y-2">
          {ds.co_so.map((c) => {
            const laGoiY = c.id === macDinh;
            return (
              <button
                key={c.id}
                type="submit"
                name="co_so"
                value={c.id}
                autoFocus={laGoiY}
                className={`flex min-h-14 w-full items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors hover:border-brand-600 hover:bg-brand-50 ${
                  laGoiY ? "border-brand-600 bg-brand-50" : "border-line bg-white"
                }`}
              >
                <MapPin size={18} className="mt-0.5 shrink-0 text-brand-600" aria-hidden />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-ink">
                    {c.name}
                    {laGoiY && ds.theo_lich ? (
                      <span className="ml-2 text-xs font-medium text-brand-700">
                        theo lịch trực hôm nay
                      </span>
                    ) : null}
                  </span>
                  {c.address ? (
                    <span className="block truncate text-xs text-ink-muted">{c.address}</span>
                  ) : null}
                </span>
              </button>
            );
          })}
        </div>
      </form>
    </div>
  );
}
