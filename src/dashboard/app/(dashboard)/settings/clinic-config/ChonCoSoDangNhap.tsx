"use client";

// CÔNG TẮC CHỌN CƠ SỞ KHI ĐĂNG NHẬP + CƠ SỞ MẶC ĐỊNH (Tuyền 08/10/2026).
// Kim Ngưu tạm đóng → tắt hỏi, mặc định Hào Nam: nhân viên đăng nhập vào thẳng.
// Kim Ngưu mở lại → bật. Màn chỉ vẽ và gửi; máy chủ kiểm cơ sở hợp lệ và áp
// cơ sở mặc định cho mọi request không mang cơ sở chọn.

import { MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import CongTac from "@/components/ui/CongTac";
import OChon from "@/components/ui/OChon";

type CoSo = { location_id: string; name: string; is_active: boolean };

export default function ChonCoSoDangNhap({
  locations,
  onLoi,
}: {
  locations: CoSo[];
  onLoi: (cau: string | null) => void;
}) {
  const [hoiChon, setHoiChon] = useState<boolean | null>(null);
  const [macDinh, setMacDinh] = useState<string>("");
  const [dangLuu, setDangLuu] = useState(false);

  useEffect(() => {
    let huy = false;
    void fetch("/api/clinic-config?what=overview", { cache: "no-store" })
      .then((r) => r.json())
      .catch(() => null)
      .then((d: { chon_co_so?: { hoi_chon: boolean; mac_dinh: string | null } } | null) => {
        if (huy || !d?.chon_co_so) return;
        setHoiChon(d.chon_co_so.hoi_chon);
        setMacDinh(d.chon_co_so.mac_dinh ?? "");
      });
    return () => {
      huy = true;
    };
  }, []);

  const dangBat = locations.filter((l) => l.is_active);
  // Một cơ sở thì không có gì để chọn — khỏi hiện công tắc.
  if (dangBat.length < 2 || hoiChon === null) return null;

  async function luu(hoi: boolean, md: string) {
    setDangLuu(true);
    onLoi(null);
    try {
      const res = await fetch("/api/clinic-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ what: "chon-co-so", hoi_chon: hoi, mac_dinh: md || null }),
      });
      if (!res.ok) {
        const b = (await res.json().catch(() => ({}))) as { error?: string; detail?: string };
        throw new Error(b.error ?? b.detail ?? "Không lưu được.");
      }
      setHoiChon(hoi);
      setMacDinh(md);
    } catch (e) {
      onLoi(e instanceof Error ? e.message : String(e));
    } finally {
      setDangLuu(false);
    }
  }

  return (
    <section className="rounded-card border border-line bg-surface px-4 py-3 shadow-card">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <MapPin className="size-4 shrink-0 text-brand-600" aria-hidden="true" />
        <div className="flex items-center gap-2">
          <CongTac
            bat={hoiChon}
            disabled={dangLuu}
            nhan="Hỏi chọn cơ sở khi đăng nhập"
            onDoi={(b) => void luu(b, macDinh)}
          />
          <span className="text-body text-ink">Hỏi chọn cơ sở khi đăng nhập</span>
        </div>
        <label className="flex items-center gap-2 text-body text-ink">
          Cơ sở mặc định
          <OChon
            value={macDinh}
            disabled={dangLuu}
            onChange={(e) => void luu(hoiChon, e.target.value)}
          >
            <option value="">Theo tài khoản</option>
            {dangBat.map((l) => (
              <option key={l.location_id} value={l.location_id}>
                {l.name}
              </option>
            ))}
          </OChon>
        </label>
      </div>
      <p className="mt-1 text-label text-ink-muted">
        {hoiChon
          ? "Đăng nhập xong mọi người chọn cơ sở (cơ sở mặc định được chọn sẵn)."
          : "Đăng nhập là vào thẳng cơ sở mặc định. Đổi cơ sở bằng nút 📍 trên thanh trên."}
      </p>
    </section>
  );
}
