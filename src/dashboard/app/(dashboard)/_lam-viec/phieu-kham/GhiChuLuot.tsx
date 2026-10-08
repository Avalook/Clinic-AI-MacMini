"use client";

// Ô CHỮ TỰ DO của hồ sơ lượt "KHÁC" (Tuyền chốt 07/10/2026 — bấm thử staging):
// MỘT ô to, tự lưu, không đè — mỗi lần lưu máy chủ thêm MỘT phiên bản (bảng
// `luot_ghi_chu`), màn hiện bản mới nhất + "Bản n · ai · giờ". Người khác vừa
// lưu (409) → nạp bản mới, không đè im lặng. MÁY CHỦ quyết ô có hiện không (lượt
// nhóm Khác, hoặc lượt đã có ghi chú) và ghi được không.

import { useCallback, useEffect, useRef, useState } from "react";

import TrangThaiLuu from "@/components/ui/TrangThaiLuu";
import { nhanLoi, type ThanLoi } from "@/lib/loi-api";
import { LOI_MAT_KET_NOI, nenThuLai, type KetQuaGui } from "@/lib/tu-luu";
import { useTuLuu } from "@/lib/use-tu-luu";
import { INPUT, LABEL } from "../../form-ui";

const CHO_LUU_MS = 1200;

interface BanGhiChu {
  phien_ban: number;
  noi_dung: string;
  ghi_luc: string | null;
  ghi_boi: string | null;
}

interface GhiChu {
  hien: boolean;
  ghi_duoc: boolean;
  ban: BanGhiChu | null;
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

export default function GhiChuLuot({ visitId, choGhi }: { visitId: string; choGhi: boolean }) {
  const [gc, setGc] = useState<GhiChu | null>(null);
  const [chu, setChu] = useState("");
  const giaTri = useRef("");
  const daLuu = useRef({ chu: "", ban: 0 });

  const doc = useCallback(async (): Promise<GhiChu | null> => {
    const r = await fetch(`/api/ho-so-kham?visit_id=${visitId}&xem=ghi-chu`, { cache: "no-store" }).catch(
      () => null,
    );
    return r && r.ok ? ((await r.json().catch(() => null)) as GhiChu | null) : null;
  }, [visitId]);
  const apDung = useCallback((g: GhiChu | null) => {
    setGc(g);
    giaTri.current = g?.ban?.noi_dung ?? "";
    daLuu.current = { chu: giaTri.current, ban: g?.ban?.phien_ban ?? 0 };
    setChu(giaTri.current);
  }, []);
  const nap = useCallback(() => doc().then(apDung), [doc, apDung]);

  useEffect(() => {
    let huy = false;
    void doc().then((g) => {
      if (!huy) apDung(g);
    });
    return () => {
      huy = true;
    };
  }, [doc, apDung]);

  const ghiDuoc = choGhi && Boolean(gc?.ghi_duoc);
  const gui = useCallback(
    async (keepalive: boolean): Promise<KetQuaGui> => {
      const noiDung = giaTri.current;
      if (noiDung === daLuu.current.chu) return { ok: true };
      const r = await fetch("/api/ho-so-kham", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visit_id: visitId, noi_dung: noiDung, phien_ban: daLuu.current.ban }),
        keepalive,
      }).catch(() => null);
      if (!r) return { ok: false, loi: LOI_MAT_KET_NOI, thuLai: true };
      const d = (await r.json().catch(() => null)) as (ThanLoi & { ban?: BanGhiChu }) | null;
      if (!r.ok) {
        if (r.status === 409) void nap();
        return { ok: false, loi: nhanLoi(d, "Không lưu được ghi chú."), thuLai: nenThuLai(r.status) };
      }
      if (d?.ban) {
        daLuu.current = { chu: noiDung, ban: d.ban.phien_ban };
        setGc((g) => (g ? { ...g, ban: d.ban ?? null } : g));
      }
      return { ok: true };
    },
    [visitId, nap],
  );
  const tuLuu = useTuLuu({ gui, choMs: CHO_LUU_MS, tat: !ghiDuoc });

  if (!gc || !gc.hien) return null;
  const ban = gc.ban;
  return (
    <section aria-label="Ghi chú" className="space-y-2 rounded-card border border-hairline bg-surface p-4">
      <label className="block space-y-1">
        <span className={LABEL}>Ghi chú</span>
        {ghiDuoc ? (
          <textarea
            value={chu}
            aria-label="Ghi chú"
            placeholder="Khách đến vì gì, đã trao đổi / làm gì…"
            onChange={(e) => {
              giaTri.current = e.target.value;
              setChu(e.target.value);
              tuLuu.danhDau();
            }}
            onBlur={() => {
              if (tuLuu.trangThai.chua_luu) void tuLuu.luuNgay();
            }}
            className={`${INPUT} min-h-40 resize-y leading-relaxed sm:min-h-40`}
          />
        ) : (
          <p className="whitespace-pre-line text-body text-ink">{chu || "—"}</p>
        )}
      </label>
      <div className="flex flex-wrap items-center justify-between gap-2 text-meta text-ink-muted">
        <span>{ban ? `Bản ${ban.phien_ban} · ${ban.ghi_boi ?? "?"} · ${gio(ban.ghi_luc)}` : "Chưa ghi."}</span>
        {ghiDuoc ? <TrangThaiLuu tt={tuLuu.trangThai} onLuuNgay={() => void tuLuu.luuNgay()} /> : null}
      </div>
    </section>
  );
}
