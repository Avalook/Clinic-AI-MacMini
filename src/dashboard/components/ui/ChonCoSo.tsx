/**
 * Chọn CƠ SỞ cho màn báo cáo (08/10/2026 — mở cơ sở thứ hai Hào Nam).
 *
 * Hai dạng, cùng một nhãn "Tất cả cơ sở" đứng đầu (mặc định):
 *   · `ChonCoSoLink` — dãy link `?co_so=` cho màn dựng ở máy chủ (/reports tab
 *     Vận hành, /ops tab Toàn cảnh); cùng kiểu với thanh tab của các màn ấy.
 *   · `ChonCoSoO` — ô chọn cho màn client (tab Cuối ngày).
 *
 * Phòng khám chỉ có một cơ sở thì không vẽ gì: một lựa chọn duy nhất không
 * phải là lựa chọn. Lọc số liệu do máy chủ làm — đây chỉ là ô chọn.
 */

import Link from "next/link";
import { buttonClass } from "./Button";
import OChon from "./OChon";

export interface CoSo {
  id: string;
  name: string;
}

export function ChonCoSoLink({
  coSo,
  dangChon,
  href,
  className = "",
}: {
  coSo: CoSo[];
  /** id đang chọn; null = Tất cả cơ sở. */
  dangChon: string | null;
  href: (id: string | null) => string;
  className?: string;
}) {
  if (coSo.length < 2) return null;
  return (
    <nav aria-label="Cơ sở" className={`flex flex-wrap gap-2 print:hidden ${className}`}>
      {[{ id: null, name: "Tất cả cơ sở" }, ...coSo].map((c) => (
        <Link
          key={c.id ?? "tat-ca"}
          href={href(c.id)}
          aria-current={c.id === dangChon ? "page" : undefined}
          className={buttonClass(c.id === dangChon ? "soft" : "ghost", "sm")}
        >
          {c.name}
        </Link>
      ))}
    </nav>
  );
}

export function ChonCoSoO({
  coSo,
  dangChon,
  onChon,
}: {
  coSo: CoSo[];
  /** "" = Tất cả cơ sở. */
  dangChon: string;
  onChon: (id: string) => void;
}) {
  if (coSo.length < 2) return null;
  return (
    <OChon aria-label="Cơ sở" value={dangChon} onChange={(e) => onChon(e.target.value)}>
      <option value="">Tất cả cơ sở</option>
      {coSo.map((c) => (
        <option key={c.id} value={c.id}>
          {c.name}
        </option>
      ))}
    </OChon>
  );
}
