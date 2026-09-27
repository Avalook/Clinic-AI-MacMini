/**
 * Ô số liệu có xu hướng — nhãn, con số lớn, chênh lệch so với hôm qua và
 * đường 7 ngày. Kiểu ô KPI của Stripe (Tuyền chốt Trang chủ 27/09/2026).
 *
 * `tangLaTot` nói con số tăng là tin tốt (khách mới) hay tin xấu (việc tồn) —
 * chỉ để chọn màu chữ chênh lệch; không có dãy xu hướng thì ô chỉ hiện số.
 * Có `href` thì cả ô bấm được; không có thì là ô chữ (một ô trông bấm được mà
 * dẫn vào ngõ cụt tệ hơn ô chữ — cùng luật với StatCard).
 */

import Link from "next/link";
import type { ReactNode } from "react";

import DuongXuHuong from "./DuongXuHuong";

export default function OSoXuHuong({
  nhan,
  so,
  xuHuong,
  tangLaTot = true,
  href,
  phu,
}: {
  nhan: string;
  so: number;
  /** 7 giá trị, cũ → mới; phần tử cuối là hôm nay. */
  xuHuong?: readonly number[];
  tangLaTot?: boolean;
  href?: string;
  /** Dòng phụ khi không có xu hướng (vd "3 khách trễ · 2 kết quả chờ gửi"). */
  phu?: ReactNode;
}) {
  const coXuHuong = xuHuong && xuHuong.length >= 2;
  const chenh = coXuHuong ? xuHuong[xuHuong.length - 1] - xuHuong[xuHuong.length - 2] : 0;
  const tot = chenh === 0 ? null : chenh > 0 === tangLaTot;
  const mau = tot === null ? "text-ink-muted" : tot ? "text-success" : "text-warning";

  const than = (
    <>
      <span className="text-meta text-ink-muted">{nhan}</span>
      <span className="mt-1 text-hero font-semibold tabular-nums text-ink">{so}</span>
      {coXuHuong ? (
        <>
          <span className={`mt-0.5 text-meta ${mau}`}>
            {chenh > 0 ? "+" : chenh < 0 ? "−" : "±"}
            {Math.abs(chenh)} so với hôm qua
          </span>
          <DuongXuHuong so={xuHuong} className={`mt-2 ${mau}`} />
        </>
      ) : phu ? (
        <span className="mt-0.5 text-meta text-ink-muted">{phu}</span>
      ) : null}
    </>
  );

  const vo =
    "flex min-w-0 flex-col rounded-card bg-surface px-4 py-3 ring-1 ring-line transition-colors";
  return href ? (
    <Link href={href} className={`${vo} hover:ring-line-strong`}>
      {than}
    </Link>
  ) : (
    <div className={vo}>{than}</div>
  );
}
