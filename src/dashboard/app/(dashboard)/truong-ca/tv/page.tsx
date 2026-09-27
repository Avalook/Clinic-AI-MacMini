// TV PHÒNG CHỜ — MỖI PHÒNG MỘT TV (Tuyền 27/09/2026 tối). Liệt kê TV của từng
// phòng (`/display?phong=<mã>`, màn đã lọc danh tính, máy TV đăng nhập tài khoản
// TV) + TV chung cả phòng khám (`/display`).
import Link from "next/link";
import { Tv } from "lucide-react";

import { buttonClass } from "@/components/ui/Button";
import { requireNavAccess } from "../../../../lib/clinic-session";
import { loadLive } from "../load";
import { tenPhong } from "../shared";

export const dynamic = "force-dynamic";

export default async function Page() {
  await requireNavAccess("/truong-ca/tv");
  const live = await loadLive();
  const phong = live.rooms.filter((r) => r.show_on_tv);
  return (
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">TV phòng chờ</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Mỗi phòng một TV — mở link trên máy TV (đăng nhập tài khoản TV) rồi để toàn màn hình.
          </p>
        </div>
        <Link href="/display" target="_blank" className={buttonClass("secondary", "md")}>
          <Tv className="size-4" aria-hidden="true" /> TV chung cả phòng khám
        </Link>
      </header>
      {!live.ok ? <p className="text-sm text-danger">Không đọc được danh sách phòng.</p> : null}
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {phong.map((r) => {
          const ten = tenPhong(r.name);
          const href = `/display?phong=${encodeURIComponent(r.code)}&ten=${encodeURIComponent(ten)}`;
          return (
            <li key={r.id} className="flex items-center justify-between gap-2 rounded-card border border-line bg-surface p-3 shadow-card">
              <div className="min-w-0">
                <p className="truncate text-body font-semibold text-ink">{ten}</p>
                <p className="truncate text-meta text-ink-muted">
                  {r.floor ?? "—"} · {r.waiting} chờ
                </p>
              </div>
              <Link href={href} target="_blank" className={`${buttonClass("soft", "sm")} shrink-0 gap-1.5`}>
                <Tv className="size-4" aria-hidden="true" /> Mở TV
              </Link>
            </li>
          );
        })}
      </ul>
      {phong.length === 0 && live.ok ? (
        <p className="text-sm text-ink-muted">Chưa phòng nào bật TV (Cấu trúc phòng khám).</p>
      ) : null}
    </main>
  );
}
