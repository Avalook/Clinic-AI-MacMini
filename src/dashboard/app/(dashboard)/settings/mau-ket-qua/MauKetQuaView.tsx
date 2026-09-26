"use client";

// Khung hai tab của màn Mẫu kết quả. Đọc bảng gắn MỘT lần ở đây (cả hai tab
// dùng: danh sách mẫu + quyền người xem), tab nào đổi dữ liệu thì gọi `napLai`.

import { useCallback, useEffect, useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";

import GanMau from "./GanMau";
import SuaMau from "./SuaMau";
import { docJson, type BangGan } from "./du-lieu";

type Tab = "gan" | "sua";

export default function MauKetQuaView() {
  const [tab, setTab] = useState<Tab>("gan");
  const [bang, setBang] = useState<BangGan | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [lanNap, setLanNap] = useState(0);

  useEffect(() => {
    let huy = false;
    void docJson<BangGan>("/api/mau-ket-qua?xem=bang-gan").then((kq) => {
      if (huy) return;
      if (kq.ok) {
        setBang(kq.d);
        setLoi(null);
      } else setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, [lanNap]);

  const napLai = useCallback(() => setLanNap((n) => n + 1), []);

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-title font-bold text-ink">Mẫu kết quả</h1>
        <p className="text-meta text-ink-muted">
          Gắn mẫu cho từng dịch vụ, sửa hoặc tạo mẫu kết quả. Xuất bản là tạo BẢN MỚI — phiếu đã
          điền vẫn giữ bản cũ.
        </p>
      </header>
      <ThanhTab
        nhan="Mẫu kết quả"
        chon={tab}
        onChon={setTab}
        muc={[
          { ma: "gan", nhan: "Gắn mẫu cho dịch vụ" },
          { ma: "sua", nhan: "Sửa · tạo mẫu" },
        ]}
      />
      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {!bang && !loi ? <p className="text-body text-ink-muted">Đang tải…</p> : null}
      {bang && tab === "gan" ? <GanMau bang={bang} onDoi={napLai} /> : null}
      {bang && tab === "sua" ? <SuaMau bang={bang} onDoi={napLai} /> : null}
    </section>
  );
}
