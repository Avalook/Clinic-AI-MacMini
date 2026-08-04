// Cấu trúc phòng khám — quản lý tự khai, không ai phải sửa code.
//
// Yêu cầu của Quang (04/08/2026): *"lỡ họ có 2 tầng, 5 tầng thì sao, mọi thứ
// code backend là phải có id phòng khám, id cơ sở"*. Phòng khám thứ hai khai
// khác mà không đụng gì tới Dr4Women.

import { requireNavAccess } from "../../../../lib/clinic-session";
import { fetchFromBackend } from "../../../../lib/backend-proxy";
import ClinicConfigBoard from "./ClinicConfigBoard";
import type { ConfigLocation, ConfigStaff, NodeDef } from "./types";

export const dynamic = "force-dynamic";

export default async function ClinicConfigPage() {
  await requireNavAccess("/settings/clinic-config");

  const [overview, staff] = await Promise.all([
    fetchFromBackend<{ locations: ConfigLocation[]; nodes: NodeDef[] }>(
      "/api/v1/clinic-config/overview",
    ),
    fetchFromBackend<{ items: ConfigStaff[] }>("/api/v1/clinic-config/staff"),
  ]);

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">
          Cấu trúc phòng khám
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Cơ sở nào có mấy tầng, phòng nào nằm ở tầng nào, phòng nào làm việc
          gì, và ai đảm nhiệm được bước nào. Khai ở đây, không phải sửa code.
        </p>
      </header>

      <ClinicConfigBoard
        initialLocations={overview?.locations ?? []}
        initialStaff={staff?.items ?? []}
        nodes={overview?.nodes ?? []}
        // `null` = backend không trả lời. Nói ra, thay vì hiện một sơ đồ trống
        // trông y hệt "phòng khám chưa khai gì" rồi để người ta khai lại.
        ok={overview !== null && staff !== null}
      />
    </main>
  );
}
