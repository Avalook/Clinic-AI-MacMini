"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import { xuatBangDangXem } from "@/lib/xuat-bang-excel";

export default function XuatBangTrongVung({
  children,
  tenTep,
  thanhCongCu,
}: {
  children: ReactNode;
  tenTep: string;
  thanhCongCu?: ReactNode;
}) {
  const vung = useRef<HTMLDivElement>(null);
  const [coBang, setCoBang] = useState(false);

  useEffect(() => {
    const phanTu = vung.current;
    if (!phanTu) return;
    const capNhat = () => {
      const coDuLieu = phanTu.querySelector("table, ul.rounded-card, ul.space-y-3") !== null;
      const daCoNutXuat = Array.from(phanTu.querySelectorAll("button, a")).some((nut) =>
        (nut.textContent ?? "").includes("Xuất Excel"),
      );
      setCoBang(coDuLieu && !daCoNutXuat);
    };
    capNhat();
    const observer = new MutationObserver(capNhat);
    observer.observe(phanTu, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  const nutXuat = (
    <Button type="button" size="sm" variant="secondary" onClick={() => {
      if (vung.current) xuatBangDangXem(vung.current, tenTep);
    }}>
      Xuất Excel
    </Button>
  );

  return (
    <div className="flex flex-col gap-2">
      {thanhCongCu ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0 flex-1">{thanhCongCu}</div>
          {coBang ? nutXuat : null}
        </div>
      ) : coBang ? (
        <div className="flex justify-end">
          {nutXuat}
        </div>
      ) : null}
      <div ref={vung}>{children}</div>
    </div>
  );
}
