import type { ComponentProps } from "react";
import SoLuot from "./SoLuot";
import { cheSdt, dinhDangSdt } from "../../lib/sdt";

export type TenKhachProps = {
  ten: string;
  ma?: string | null;
  sdt?: string | number | null;
  /** Nơi gọi chọn chế độ; nơi nhạy cảm phải nhận sẵn số đã che từ API. */
  che?: "day_du" | "che" | "an";
  bo?: "ngang" | "doc";
  soLuot?: ComponentProps<typeof SoLuot>;
};

export default function TenKhach({
  ten, ma, sdt, che = "day_du", bo = "ngang", soLuot,
}: TenKhachProps) {
  const so = che === "an" ? null : che === "che" ? cheSdt(sdt) : dinhDangSdt(sdt);
  return (
    <span className="flex min-w-0 max-w-full items-start gap-2">
      {soLuot ? <SoLuot {...soLuot} /> : null}
      <span className={`flex min-w-0 flex-1 flex-col gap-1 ${bo === "ngang" ? "md:flex-row md:flex-wrap md:items-baseline md:gap-x-2" : ""}`}>
        <span title={ten} className={`min-w-0 truncate text-body font-semibold text-ink ${bo === "ngang" ? "md:flex-1" : ""}`}>{ten}</span>
        {ma || so ? (
          <span className={`flex min-w-0 max-w-full flex-wrap items-baseline gap-1 text-meta text-ink-muted ${bo === "ngang" ? "md:contents" : ""}`}>
            {ma ? <span className={`min-w-0 break-all ${bo === "ngang" ? "md:order-3 md:basis-full" : ""}`}>{ma}</span> : null}
            {ma && so ? <span aria-hidden className={bo === "ngang" ? "md:hidden" : ""}>·</span> : null}
            {so ? <span className={`max-w-full shrink-0 break-all tabular-nums ${bo === "ngang" ? "md:order-2" : ""}`}>
              {bo === "ngang" ? <span aria-hidden className="hidden md:inline">· </span> : null}{so}
            </span> : null}
          </span>
        ) : null}
      </span>
    </span>
  );
}
