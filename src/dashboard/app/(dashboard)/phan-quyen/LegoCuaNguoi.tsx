"use client";

// 21 LEGO của một người (Tuyền 25/09/2026): mỗi dòng = một node thanh bên, một
// CÔNG TẮC. Bật lego = có đủ mọi việc của màn ấy. "Một phần" = có vài khối (thường
// vì khối ấy nằm trong lego khác đang bật) — bật để đủ.
//
// Phòng dịch vụ là LEGO TO + LEGO NHỎ: bật rồi chọn phòng (phạm vi ROOM); "Tất cả
// phòng" = toàn phòng khám. "▾ Chi tiết" chỉ để XEM khối bên trong, không tick lẻ.
// Máy chủ giữ luật (`permission.manage`); màn này chỉ gửi và vẽ lại.

import { useCallback, useEffect, useState } from "react";

import Chip from "@/components/ui/Chip";
import CongTac from "@/components/ui/CongTac";

interface Lego {
  ma: string;
  ten: string;
  cac_duong: string[];
  khoi: { ma: string; ten: string }[];
  bat: boolean;
  mot_phan: boolean;
  mac_dinh_cho: string;
  tat_ca_phong?: boolean;
  phong_ids?: string[];
}

interface LegoCuaNguoiDl {
  lego: Lego[];
  luon_bat: { ten: string; duong: string }[];
  phong: { id: string; ten: string }[];
}

export default function LegoCuaNguoi({
  staffId,
  onLoi,
}: {
  staffId: string;
  onLoi: (loi: string | null) => void;
}) {
  const [dl, setDl] = useState<LegoCuaNguoiDl | null>(null);
  const [dangLam, setDangLam] = useState<string | null>(null);
  const [bung, setBung] = useState<string | null>(null);

  const doc = useCallback(async () => {
    const r = await fetch(`/api/phan-quyen?lego=${staffId}`, { cache: "no-store" });
    if (!r.ok) {
      onLoi("Không đọc được lego của người này.");
      return;
    }
    onLoi(null);
    setDl((await r.json()) as LegoCuaNguoiDl);
  }, [staffId, onLoi]);

  useEffect(() => {
    let huy = false;
    void fetch(`/api/phan-quyen?lego=${staffId}`, { cache: "no-store" }).then(async (r) => {
      if (huy) return;
      if (!r.ok) {
        onLoi("Không đọc được lego của người này.");
        return;
      }
      onLoi(null);
      setDl((await r.json()) as LegoCuaNguoiDl);
    });
    return () => {
      huy = true;
    };
  }, [staffId, onLoi]);

  const doi = async (ma: string, bat: boolean, phongIds?: string[]) => {
    setDangLam(ma);
    const r = await fetch("/api/phan-quyen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thao_tac: "doi-lego",
        staff_id: staffId,
        du_lieu: { ma, bat, phong_ids: phongIds && phongIds.length > 0 ? phongIds : null },
      }),
    });
    setDangLam(null);
    if (!r.ok) {
      const d = (await r.json().catch(() => null)) as { message?: string } | null;
      onLoi(d?.message ?? "Không đổi được lego.");
      return;
    }
    await doc();
  };

  if (!dl) return <p className="text-body text-ink-muted">Đang đọc lego…</p>;

  return (
    <ul className="mt-3 flex flex-col gap-2">
      {dl.luon_bat.map((l) => (
        <li
          key={l.duong}
          className="flex min-h-10 items-center justify-between gap-2 rounded-control border border-line bg-surface px-3 py-2"
        >
          <span className="text-body text-ink">{l.ten}</span>
          <Chip tone="neutral">Luôn bật</Chip>
        </li>
      ))}
      {dl.lego.map((l, i) => {
        const theoPhong = l.tat_ca_phong !== undefined;
        const chonPhong = new Set(l.phong_ids ?? []);
        return (
          <li key={l.ma} className="rounded-control border border-line bg-surface px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-body font-medium text-ink">
                  <span className="mr-1 tabular-nums text-ink-muted">{i + 1}.</span>
                  {l.ten}
                  {l.mot_phan ? (
                    <span className="ml-2">
                      <Chip tone="warning">Một phần</Chip>
                    </span>
                  ) : null}
                </p>
                <button
                  type="button"
                  onClick={() => setBung(bung === l.ma ? null : l.ma)}
                  className="text-meta text-ink-muted hover:underline"
                >
                  {bung === l.ma ? "▴ Thu gọn" : "▾ Chi tiết"}
                </button>
              </div>
              <CongTac
                bat={l.bat}
                motPhan={l.mot_phan}
                nhan={`${l.ten}: ${l.bat ? "đang bật" : "đang tắt"}`}
                disabled={dangLam !== null}
                onDoi={(bat) => void doi(l.ma, bat)}
              />
            </div>

            {bung === l.ma ? (
              <div className="mt-2 border-t border-line pt-2 text-meta text-ink-muted">
                <p>Màn: {l.cac_duong.join(" · ")}</p>
                <p>Gồm: {l.khoi.map((k) => k.ten).join(" · ")}</p>
                <p>Gói mẫu thường có: {l.mac_dinh_cho}</p>
              </div>
            ) : null}

            {theoPhong && l.bat ? (
              <fieldset className="mt-2 border-t border-line pt-2">
                <legend className="text-meta font-semibold text-ink">Phòng được làm</legend>
                <label className="flex min-h-10 items-center gap-2 text-body text-ink">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={Boolean(l.tat_ca_phong)}
                    disabled={dangLam !== null}
                    onChange={(e) => {
                      if (e.target.checked) void doi(l.ma, true);
                    }}
                  />
                  Tất cả phòng
                </label>
                <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
                  {dl.phong.map((p) => (
                    <label key={p.id} className="flex min-h-10 items-center gap-2 text-body text-ink">
                      <input
                        type="checkbox"
                        className="size-4 accent-brand-600"
                        checked={!l.tat_ca_phong && chonPhong.has(p.id)}
                        disabled={dangLam !== null}
                        onChange={(e) => {
                          const moi = new Set(l.tat_ca_phong ? [] : chonPhong);
                          if (e.target.checked) moi.add(p.id);
                          else moi.delete(p.id);
                          // Bỏ hết phòng = về "tất cả phòng", không tắt lego —
                          // muốn tắt thì gạt công tắc.
                          void doi(l.ma, true, [...moi]);
                        }}
                      />
                      {p.ten}
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
