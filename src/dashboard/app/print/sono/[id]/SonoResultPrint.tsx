"use client";

// PHIẾU KẾT QUẢ XÉT NGHIỆM / SIÊU ÂM — khổ NGANG (A4 landscape). Nút In gọi
// window.print(); CSS @media print giữ đúng layout in (ẩn nút, sheet full khổ).
// Next.js giữ layout in vì sheet là HTML tĩnh + @page size landscape.

import { VN_TZ } from "../../../../lib/datetime";

export interface SonoPrintData {
  kind: "SA" | "XN";
  service_name: string;
  status: string;
  result_text: string;
  started_at: string | null;
  sent_to_lab_at: string | null;
  finished_at: string | null;
  patient_name: string;
  patient_code: string;
  date_of_birth: string;
  gender: string;
  phone: string;
}

function fmtVn(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: VN_TZ,
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour12: false,
  }).format(d);
}

function ymdToDmy(s: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : s || "—";
}

export default function SonoResultPrint({ data }: { data: SonoPrintData }) {
  const isXn = data.kind === "XN";
  const title = isXn ? "PHIẾU KẾT QUẢ XÉT NGHIỆM" : "PHIẾU KẾT QUẢ SIÊU ÂM";

  return (
    <div className="screen-bg">
      {/* CSS in ấn khổ NGANG */}
      <style>{`
        @page { size: A4 landscape; margin: 10mm; }
        .screen-bg { background: #f4f4f5; min-height: 100vh; padding: 24px; display: flex; flex-direction: column; align-items: center; gap: 16px; }
        .sheet { background: #fff; width: 1123px; max-width: 100%; padding: 28px 36px; box-shadow: 0 1px 8px rgba(0,0,0,0.12); color: #171717; }
        @media print {
          .screen-bg { background: #fff !important; padding: 0 !important; min-height: auto !important; }
          .no-print { display: none !important; }
          .sheet { width: 100% !important; box-shadow: none !important; padding: 0 !important; font-size: 12px !important; }
          tr, td, th { page-break-inside: avoid; }
        }
      `}</style>

      <div className="no-print flex gap-2">
        <button
          onClick={() => window.print()}
          className="rounded-lg bg-[#ec4899] px-4 py-2 text-sm font-medium text-white hover:brightness-95"
        >
          In phiếu (khổ ngang)
        </button>
      </div>

      <div className="sheet">
        <header className="mb-4 flex items-start justify-between border-b-2 border-[#171717] pb-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-[#52525b]">
              Phòng khám Dr4women
            </p>
            <h1 className="text-lg font-bold">{title}</h1>
          </div>
          <div className="text-right text-xs text-[#52525b]">
            <p>Ngày in: {fmtVn(new Date().toISOString())}</p>
          </div>
        </header>

        {/* Thông tin BN — 2 cột ngang */}
        <section className="mb-4 grid grid-cols-2 gap-x-10 gap-y-1 text-sm">
          <div className="flex justify-between border-b border-[#e4e4e7] py-1">
            <span className="text-[#71717a]">Họ tên</span>
            <span className="font-medium">{data.patient_name || "—"}</span>
          </div>
          <div className="flex justify-between border-b border-[#e4e4e7] py-1">
            <span className="text-[#71717a]">Mã BN</span>
            <span className="font-medium">{data.patient_code || "—"}</span>
          </div>
          <div className="flex justify-between border-b border-[#e4e4e7] py-1">
            <span className="text-[#71717a]">Ngày sinh</span>
            <span className="font-medium">{ymdToDmy(data.date_of_birth)}</span>
          </div>
          <div className="flex justify-between border-b border-[#e4e4e7] py-1">
            <span className="text-[#71717a]">Giới tính</span>
            <span className="font-medium">{data.gender || "—"}</span>
          </div>
          <div className="flex justify-between border-b border-[#e4e4e7] py-1">
            <span className="text-[#71717a]">SĐT</span>
            <span className="font-medium">{data.phone || "—"}</span>
          </div>
          <div className="flex justify-between border-b border-[#e4e4e7] py-1">
            <span className="text-[#71717a]">Dịch vụ</span>
            <span className="font-medium">{data.service_name || "—"}</span>
          </div>
        </section>

        {/* Mốc thời gian */}
        <section className="mb-4">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-[#fafafa]">
                {isXn ? (
                  <>
                    <th className="border border-[#e4e4e7] px-3 py-1.5 text-left">Lấy mẫu</th>
                    <th className="border border-[#e4e4e7] px-3 py-1.5 text-left">Gửi lab</th>
                    <th className="border border-[#e4e4e7] px-3 py-1.5 text-left">Có kết quả</th>
                  </>
                ) : (
                  <>
                    <th className="border border-[#e4e4e7] px-3 py-1.5 text-left">Bắt đầu</th>
                    <th className="border border-[#e4e4e7] px-3 py-1.5 text-left">Hoàn tất</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              <tr>
                {isXn ? (
                  <>
                    <td className="border border-[#e4e4e7] px-3 py-1.5">{fmtVn(data.started_at)}</td>
                    <td className="border border-[#e4e4e7] px-3 py-1.5">{fmtVn(data.sent_to_lab_at)}</td>
                    <td className="border border-[#e4e4e7] px-3 py-1.5">{fmtVn(data.finished_at)}</td>
                  </>
                ) : (
                  <>
                    <td className="border border-[#e4e4e7] px-3 py-1.5">{fmtVn(data.started_at)}</td>
                    <td className="border border-[#e4e4e7] px-3 py-1.5">{fmtVn(data.finished_at)}</td>
                  </>
                )}
              </tr>
            </tbody>
          </table>
        </section>

        {/* Kết quả */}
        <section className="mb-6">
          <p className="mb-1 text-sm font-semibold">Kết quả / Mô tả</p>
          <div className="min-h-[120px] whitespace-pre-wrap rounded border border-[#e4e4e7] p-3 text-sm">
            {data.result_text || ""}
          </div>
        </section>

        <footer className="mt-8 flex justify-end gap-16 text-center text-sm">
          <div>
            <p className="text-[#71717a]">Người thực hiện</p>
            <div className="mt-12 border-t border-[#171717] px-8 pt-1 text-xs text-[#71717a]">
              Ký, ghi rõ họ tên
            </div>
          </div>
          <div>
            <p className="text-[#71717a]">Bác sĩ phụ trách</p>
            <div className="mt-12 border-t border-[#171717] px-8 pt-1 text-xs text-[#71717a]">
              Ký, ghi rõ họ tên
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
