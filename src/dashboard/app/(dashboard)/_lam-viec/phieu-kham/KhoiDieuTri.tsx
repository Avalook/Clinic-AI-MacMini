"use client";

// KHỐI 4 "ĐIỀU TRỊ" của hồ sơ khám (Tuyền chốt 07/10/2026, T6): hai ô chữ tự do
// "Cảm nhận" + "Vấn đề sau điều trị" của LƯỢT — bảng riêng `luot_dieu_tri_ghi`,
// không thuộc 7 mẫu phiếu. TỰ LƯU (hàng đợi chung `lib/use-tu-luu`, như
// `OTuVanTuLuu`); mỗi lần lưu máy chủ thêm MỘT phiên bản, màn hiện bản mới
// nhất. Người khác vừa lưu (409) → nạp bản mới, không đè im lặng.
// Dùng được cả lượt không có phiếu (Điều trị, Khác).

import { useCallback, useEffect, useRef, useState } from "react";

import TrangThaiLuu from "@/components/ui/TrangThaiLuu";
import { nhanLoi, type ThanLoi } from "@/lib/loi-api";
import { LOI_MAT_KET_NOI, nenThuLai, type KetQuaGui } from "@/lib/tu-luu";
import { useTuLuu } from "@/lib/use-tu-luu";
import { INPUT, LABEL } from "../../form-ui";

const CHO_LUU_MS = 1200;

export interface BanDieuTri {
  phien_ban: number;
  cam_nhan: string;
  van_de_sau: string;
  ghi_luc: string | null;
  ghi_boi: string | null;
}

function gio(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleString("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
      })
    : "";
}

export default function KhoiDieuTri({ visitId, choGhi }: { visitId: string; choGhi: boolean }) {
  const [ban, setBan] = useState<BanDieuTri | null | undefined>(undefined);
  const [camNhan, setCamNhan] = useState("");
  const [vanDe, setVanDe] = useState("");
  const giaTri = useRef({ cam: "", van: "" });
  const daLuu = useRef({ cam: "", van: "", ban: 0 });

  const doc = useCallback(async (): Promise<BanDieuTri | null> => {
    const r = await fetch(`/api/ho-so-kham?visit_id=${visitId}&xem=dieu-tri`, { cache: "no-store" }).catch(
      () => null,
    );
    const d = r && r.ok ? ((await r.json().catch(() => null)) as { dieu_tri: BanDieuTri | null } | null) : null;
    return d?.dieu_tri ?? null;
  }, [visitId]);
  const apDung = useCallback((b: BanDieuTri | null) => {
    setBan(b);
    giaTri.current = { cam: b?.cam_nhan ?? "", van: b?.van_de_sau ?? "" };
    daLuu.current = { ...giaTri.current, ban: b?.phien_ban ?? 0 };
    setCamNhan(giaTri.current.cam);
    setVanDe(giaTri.current.van);
  }, []);
  const nap = useCallback(() => doc().then(apDung), [doc, apDung]);

  useEffect(() => {
    let huy = false;
    void doc().then((b) => {
      if (!huy) apDung(b);
    });
    return () => {
      huy = true;
    };
  }, [doc, apDung]);

  const gui = useCallback(
    async (keepalive: boolean): Promise<KetQuaGui> => {
      const { cam, van } = giaTri.current;
      if (cam === daLuu.current.cam && van === daLuu.current.van) return { ok: true };
      const r = await fetch("/api/ho-so-kham", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visit_id: visitId, cam_nhan: cam, van_de_sau: van, phien_ban: daLuu.current.ban }),
        keepalive,
      }).catch(() => null);
      if (!r) return { ok: false, loi: LOI_MAT_KET_NOI, thuLai: true };
      const d = (await r.json().catch(() => null)) as (ThanLoi & { dieu_tri?: BanDieuTri }) | null;
      if (!r.ok) {
        if (r.status === 409) void nap();
        return { ok: false, loi: nhanLoi(d, "Không lưu được khối Điều trị."), thuLai: nenThuLai(r.status) };
      }
      if (d?.dieu_tri) {
        daLuu.current = { cam, van, ban: d.dieu_tri.phien_ban };
        setBan(d.dieu_tri);
      }
      return { ok: true };
    },
    [visitId, nap],
  );
  const tuLuu = useTuLuu({ gui, choMs: CHO_LUU_MS, tat: !choGhi });

  if (ban === undefined) return <p className="text-body text-ink-muted">Đang mở khối Điều trị…</p>;

  const o = (nhan: string, gia: string, dat: (v: string) => void, khoa: "cam" | "van") => (
    <label className="block space-y-1">
      <span className={LABEL}>{nhan}</span>
      <textarea
        value={gia}
        disabled={!choGhi}
        aria-label={nhan}
        onChange={(e) => {
          giaTri.current = { ...giaTri.current, [khoa]: e.target.value };
          dat(e.target.value);
          tuLuu.danhDau();
        }}
        onBlur={() => {
          if (tuLuu.trangThai.chua_luu) void tuLuu.luuNgay();
        }}
        className={`${INPUT} min-h-28 resize-y leading-relaxed sm:min-h-28`}
      />
    </label>
  );

  return (
    <section aria-label="Điều trị" className="space-y-3 rounded-card border border-hairline bg-surface p-4">
      {o("Cảm nhận", camNhan, setCamNhan, "cam")}
      {o("Vấn đề sau điều trị", vanDe, setVanDe, "van")}
      <div className="flex flex-wrap items-center justify-between gap-2 text-meta text-ink-muted">
        <span>
          {ban ? `Bản ${ban.phien_ban} · ${ban.ghi_boi ?? "?"} · ${gio(ban.ghi_luc)}` : "Chưa ghi."}
        </span>
        {choGhi ? <TrangThaiLuu tt={tuLuu.trangThai} onLuuNgay={() => void tuLuu.luuNgay()} /> : null}
      </div>
    </section>
  );
}
