// CỘT TỔNG QUAN bên phải bảng lịch hẹn — "Tải bác sĩ" và "Cần xử lý" (Tuyền chốt
// Trang chủ 27/09/2026: "thích mục tải bác sĩ và cần xử lý của C").
//
// Chỉ vẽ: mọi con số do backend đếm (man_trang_chu_service — tai_bac_si,
// can_xu_ly). Đường dẫn đã lọc qua cửa trang ở page.tsx (lego tắt → dòng chữ,
// không dẫn vào ngõ cụt). Không có `style={{}}`: thanh tải dùng bậc 1/12 của
// Tailwind.

import Link from "next/link";
import { ChevronRight, CircleCheck, TriangleAlert } from "lucide-react";

import { mauTheoMa } from "@/components/ui/mau-theo-ma";
import { doctorName } from "../../../lib/doctor-name";

export interface TaiBacSiRow {
  doctor_id: string | null;
  ten: string | null;
  so_lich: number;
  da_den: number;
}

export interface CanXuLyRow {
  ma: string;
  so: number;
  phut?: number;
}

// Bậc độ dài thanh — viết đủ tên lớp để Tailwind sinh ra chúng.
const BAC = [
  "w-0", "w-1/12", "w-2/12", "w-3/12", "w-4/12", "w-5/12", "w-6/12",
  "w-7/12", "w-8/12", "w-9/12", "w-10/12", "w-11/12", "w-full",
] as const;

const NHAN_CAN_XU_LY: Record<string, (r: CanXuLyRow) => string> = {
  khach_tre: (r) => `${r.so} khách trễ quá ${r.phut ?? 15}′ chưa check-in`,
  chua_xep_bac_si: (r) => `${r.so} lịch chưa xếp bác sĩ`,
  viec_qua_han: (r) => `${r.so} việc quá hạn`,
};

const O = "rounded-card border border-line bg-surface p-4 shadow-card";

export default function CotTongQuan({
  taiBacSi,
  canXuLy,
  hrefCanXuLy,
}: {
  taiBacSi: TaiBacSiRow[];
  canXuLy: CanXuLyRow[];
  /** Mã dòng → đường dẫn tài khoản này mở được (thiếu = dòng chữ). */
  hrefCanXuLy: Record<string, string | undefined>;
}) {
  const tong = taiBacSi.reduce((s, r) => s + r.so_lich, 0);
  const daDen = taiBacSi.reduce((s, r) => s + r.da_den, 0);
  const lonNhat = Math.max(1, ...taiBacSi.map((r) => r.so_lich));
  const viec = canXuLy.filter((r) => r.so > 0 && NHAN_CAN_XU_LY[r.ma]);

  return (
    <aside aria-label="Tổng quan hôm nay" className="space-y-3">
      <section className={O}>
        <h2 className="text-emph font-semibold text-ink">Tải bác sĩ hôm nay</h2>
        <p className="mt-0.5 text-meta text-ink-muted">
          {tong > 0 ? `${tong} lịch · ${daDen} đã đến` : "Chưa có lịch hẹn hôm nay"}
        </p>
        <ul className="mt-3 space-y-3">
          {taiBacSi.map((r) => {
            const ten = r.doctor_id ? doctorName(r.ten ?? "") || "Bác sĩ" : "Chưa xếp bác sĩ";
            const mau = mauTheoMa(r.doctor_id);
            return (
              <li key={r.doctor_id ?? "chua-xep"}>
                <div className="flex items-baseline justify-between gap-2 text-body">
                  <span className="truncate text-ink">{ten}</span>
                  <span className="shrink-0 tabular-nums text-meta text-ink-muted">
                    {r.da_den}/{r.so_lich} lịch
                  </span>
                </div>
                <div className={`mt-1.5 h-1.5 overflow-hidden rounded-full ${mau}`}>
                  <div
                    className={`h-full rounded-full bg-current ${BAC[Math.round((r.so_lich / lonNhat) * 12)]}`}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className={O}>
        <h2 className="text-emph font-semibold text-ink">Cần xử lý</h2>
        {viec.length === 0 ? (
          <p className="mt-2 flex items-center gap-2 text-body text-ink-muted">
            <CircleCheck className="size-4 text-success" aria-hidden />
            Không có việc tồn
          </p>
        ) : (
          <ul className="mt-2 -mx-2">
            {viec.map((r) => {
              const nhan = NHAN_CAN_XU_LY[r.ma](r);
              const href = hrefCanXuLy[r.ma];
              const trong = (
                <>
                  <TriangleAlert className="size-4 shrink-0 text-warning" aria-hidden />
                  <span className="flex-1">{nhan}</span>
                  {href ? <ChevronRight className="size-4 text-ink-faint" aria-hidden /> : null}
                </>
              );
              const lop = "flex items-center gap-2 rounded-control px-2 py-1.5 text-body text-ink";
              return (
                <li key={r.ma}>
                  {href ? (
                    <Link href={href} className={`${lop} hover:bg-surface-sunken`}>
                      {trong}
                    </Link>
                  ) : (
                    <div className={lop}>{trong}</div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </aside>
  );
}
