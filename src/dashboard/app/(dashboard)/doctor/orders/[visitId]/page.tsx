/**
 * Chỉ định dịch vụ for one visit.
 *
 * The catalogue is fetched on the server: it is the same for every doctor and
 * changes rarely, so shipping it with the page beats a round-trip after paint.
 */

import { notFound } from "next/navigation";

import { fetchCatalogue, fetchVisitPatient } from "@/lib/orders-server";

import OrderComposer from "./OrderComposer";

export const metadata = { title: "Chỉ định dịch vụ · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function OrdersPage({
  params,
}: {
  params: Promise<{ visitId: string }>;
}) {
  const { visitId } = await params;
  const [catalogue, patient] = await Promise.all([
    fetchCatalogue(),
    fetchVisitPatient(visitId),
  ]);

  if (!catalogue.ok) {
    return (
      <main className="page-in p-6">
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">Không tải được bảng dịch vụ</p>
          <p className="mt-1 text-sm text-danger">
            {catalogue.reason === "forbidden"
              ? "Chỉ bác sĩ, bác sĩ siêu âm và thư ký y khoa được tạo chỉ định."
              : "Không kết nối được máy chủ."}
          </p>
        </div>
      </main>
    );
  }

  if (catalogue.data.length === 0) notFound();

  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">
            Khám phụ khoa &amp; Tạo chỉ định
          </h1>
          <p className="mt-1 text-sm text-ink-muted">
            Thăm khám, đánh giá và chỉ định dịch vụ phù hợp.
          </p>
        </div>
        <p className="rounded-control border border-line bg-surface px-3 py-2 text-xs text-ink-muted shadow-card">
          Dịch vụ được chuyển tới đúng phòng thực hiện
        </p>
      </header>
      <OrderComposer
        visitId={visitId}
        patient={patient}
        catalogue={catalogue.data}
      />
    </main>
  );
}
