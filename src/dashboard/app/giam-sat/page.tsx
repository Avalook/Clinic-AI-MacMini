// TRUNG TÂM GIÁM SÁT AI — trang riêng của đội vận hành ClinicAI (09/10/2026).
//
// Sống ở tên miền giamsat.dr4women.io.vn (proxy.ts + lib/cong-giam-sat.ts chặn
// lối vào từ tên miền chính). NẰM NGOÀI nhóm `(dashboard)`: không thanh bên, không
// lẫn vào app của phòng khám — một màn, một việc.
//
// Ra khỏi nhóm ấy thì layout KHÔNG gác hộ, nên trang tự gác: phải đăng nhập là
// nhân viên VÀ có quyền NỘI BỘ `giamsat.view` (migration 20261009880000 — quản lý
// phòng khám không tự cấp được). Thiếu quyền → 404, không nói cho người ngoài
// biết ở đây có gì.

import { notFound } from "next/navigation";

import { logout } from "../(auth)/login/actions";
import { getQuyenCuaToi, requireClinicRole } from "../../lib/clinic-session";
import { getCurrentStaff } from "../../lib/current-staff";
import TrungTamGiamSat from "./TrungTamGiamSat";

export const dynamic = "force-dynamic";
export const metadata = { title: "Trung tâm giám sát · ClinicAI" };

export default async function TrangGiamSat({ searchParams }: { searchParams: Promise<{ demo?: string }> }) {
  await requireClinicRole();
  const quyen = await getQuyenCuaToi();
  if (!quyen?.includes("giamsat.view")) notFound();
  const [{ demo }, staff] = await Promise.all([searchParams, getCurrentStaff()]);
  const ten = staff?.full_name ?? staff?.short_name ?? "";

  return (
    <div className="min-h-screen bg-[#f8f8f8]">
      <header className="sticky top-0 z-20 border-b border-black/10 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-3 px-4 lg:px-6">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-b from-[#3f3f46] to-[#18181b] text-sm font-semibold text-white" aria-hidden>
              C
            </span>
            <span className="text-sm font-medium text-[#18181b]">
              ClinicAI <span className="text-[#a1a1aa]">/</span> Giám sát
            </span>
          </div>
          <div className="flex items-center gap-3">
            {ten ? <span className="hidden text-xs text-[#71717a] sm:inline">{ten}</span> : null}
            <form action={logout}>
              <button
                type="submit"
                className="h-8 rounded-lg border border-black/10 bg-white px-3 text-xs font-medium text-[#18181b] hover:bg-[#fafafa]"
              >
                Đăng xuất
              </button>
            </form>
          </div>
        </div>
      </header>
      <TrungTamGiamSat demo={demo === "1"} />
    </div>
  );
}
