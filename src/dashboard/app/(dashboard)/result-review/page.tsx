// Duyệt kết quả — Doctor duyệt kết quả XN (image_9 + image_3).
// Hàng đợi kết quả chờ duyệt: xem chi tiết, ký duyệt / trả lại chỉnh sửa.

import { getClinicRole, requireNavAccess } from "../../../lib/clinic-session";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { isPhysicianRole } from "../../../lib/roles";
import ResultReviewBoard from "./ResultReviewBoard";
import TepChoPhepGui, { type TepChoPhep } from "./TepChoPhepGui";

type ResultRow = Parameters<typeof ResultReviewBoard>[0]["results"][number];

export const dynamic = "force-dynamic";

export default async function ResultReviewPage() {
  await requireNavAccess("/result-review");

  // ĐỌC QUA BACKEND (15/09/2026), không đọc thẳng Supabase: thư ký chỉ được thấy
  // kết quả khách của bác sĩ mình được phân — luật ấy nằm ở FastAPI.
  const data = await fetchFromBackend<{ items: ResultRow[] }>(
    "/api/v1/lab/results/cho-duyet",
  );
  if (data === null) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được kết quả. Thử tải lại trang.
      </div>
    );
  }
  const normalized = data.items ?? [];

  // Tệp kết quả chờ bác sĩ cho phép gửi (15/09/2026). Chỉ bác sĩ có hàng chờ
  // này — backend cũng gác bằng vai.
  const role = await getClinicRole();
  const tep = isPhysicianRole(role)
    ? await fetchFromBackend<{ items: TepChoPhep[] }>("/api/v1/cskh/ket-qua/cho-phep-gui")
    : null;

  return (
    <div className="flex h-full flex-col">
      {tep ? (
        <div className="px-4 pt-4">
          <TepChoPhepGui items={tep.items ?? []} />
        </div>
      ) : null}
      <div className="min-h-0 flex-1">
        <ResultReviewBoard results={normalized} />
      </div>
    </div>
  );
}