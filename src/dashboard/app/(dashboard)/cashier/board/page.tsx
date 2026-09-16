/**
 * Quầy thu ngân — hiện khách đang chờ, dịch vụ/thuốc của họ, và thu tiền.
 *
 * TRANG NÀY TỪNG LÀ "ĐỐI SOÁT CHI PHÍ": một quy trình đối soát đầy đủ với
 * checklist trước khi đối soát, nguồn sai lệch, biên bản nguồn ngoài, nút "Bắt
 * đầu đối soát" — mà phần lớn nút đều `disabled` kèm title "Chưa có API".
 * Tuyền chốt 16/09: "thu ngân thì cần gì đối soát, nó là thu ngân dịch vụ
 * luôn, hiện các dịch vụ khách đó khám ra và tính tiền là xong á".
 *
 * Quầy nào hiện ô nào là theo VAI, và vai đọc từ máy chủ chứ không từ URL:
 * thu ngân thuốc chỉ thấy thuốc, thu ngân dịch vụ chỉ thấy dịch vụ, thu ngân
 * tổng hợp và quản lý thấy cả hai. FastAPI gác lần nữa ở `/cashier/board`.
 */

import { requireNavAccess, getVaiChinh } from "@/lib/clinic-session";

import QuayThuNgan, { type Quay } from "./QuayThuNgan";

export const metadata = { title: "Quầy thu ngân · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function CashierBoardPage() {
  await requireNavAccess("/cashier/board");
  const role = await getVaiChinh();
  const quay: Quay =
    role === "CASHIER_THUOC" ? "thuoc" : role === "CASHIER_DV" ? "dich_vu" : "ca_hai";
  const ten =
    quay === "thuoc"
      ? "Quầy thuốc"
      : quay === "dich_vu"
        ? "Quầy dịch vụ"
        : "Quầy thu ngân";
  const today = new Date().toLocaleDateString("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">{ten}</h1>
          <p className="text-sm text-ink-muted">
            Khách đã khám xong, chờ trả tiền. Bấm “Đã nhận đủ” là ghi sổ.
          </p>
        </div>
        <span className="rounded-control border border-line bg-surface px-3 py-1.5 text-sm text-ink-soft">
          {today}
        </span>
      </header>

      <QuayThuNgan quay={quay} />
    </main>
  );
}
