"use client";

// Quầy gỡ DÒNG THUỐC LỆCH trước khi thu (kế hoạch đơn vị mẹ/con mục 12, T3 — 26/11).
//
// Một dòng chưa giá / chưa gắn thuốc kho khoá cả hoá đơn thuốc của lượt. Trước đây quầy
// chỉ có "bỏ tick" (mất doanh thu dòng đó). Ở đây ba đường, cả ba đi lệnh máy chủ:
//   · Gán sang thuốc đúng trong danh mục (đổi tên + đơn vị theo thuốc đó) — hoàn tác được;
//   · Điền giá cho thuốc chưa có giá — chỉ người có quyền Sửa giá thuốc, người khác thấy
//     nút khoá kèm lý do (máy chủ trả cờ `dien_gia_duoc`, màn không tự suy quyền);
//   · Khách không lấy — đúng lệnh bỏ tick có sẵn.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { tienVn, type MauThuoc } from "@/lib/phieu-kham";

import { INPUT } from "../form-ui";

interface DongLech {
  prescription_id: string;
  van_de: string | null;
  drug_catalog_id: string | null;
  dien_gia_duoc: boolean;
  ly_do_khong_dien_gia: string | null;
  thuoc_chua_gia: boolean;
  bo_gan_duoc: boolean;
}

async function gui(
  than: Record<string, unknown>,
): Promise<{ loi: string | null; nhac?: string | null }> {
  try {
    const r = await fetch("/api/quay-thuoc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    const d = (await r.json().catch(() => null)) as {
      message?: string;
      error?: string;
      nhac?: string | null;
    } | null;
    if (r.ok) return { loi: null, nhac: d?.nhac ?? null };
    return {
      loi: d?.message ?? d?.error ?? `Không lưu được (HTTP ${r.status}).`,
    };
  } catch {
    return { loi: "Mất kết nối — CHƯA lưu." };
  }
}

export default function GoDongLech({
  visitId,
  ten,
  lan,
  mauThuoc,
  onKhongLay,
  onXong,
}: {
  visitId: string;
  /** Tên dòng theo id — lấy từ đơn bán màn cha đã nạp. */
  ten: Record<string, string>;
  /** Đổi mỗi lần đơn bán nạp lại → nạp lại dòng lệch. */
  lan: unknown;
  mauThuoc: MauThuoc[];
  onKhongLay: (prescriptionId: string) => Promise<void>;
  onXong: (loi: string | null, cau: string) => Promise<void>;
}) {
  const [dong, setDong] = useState<DongLech[]>([]);
  useEffect(() => {
    let bo = false;
    fetch(`/api/quay-thuoc?visit_id=${visitId}&xem=dong-lech`, {
      cache: "no-store",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { dong?: DongLech[] } | null) => {
        if (!bo) setDong(d?.dong ?? []);
      })
      .catch(() => {
        if (!bo) setDong([]);
      });
    return () => {
      bo = true;
    };
  }, [visitId, lan]);

  if (dong.length === 0) return null;
  // Thuốc chọn được để gán: đã ở danh mục kho và có giá.
  const coGia = mauThuoc.filter(
    (m) => m.drug_catalog_id && typeof m.gia === "number",
  );
  return (
    <section
      aria-label="Dòng thuốc cần xử lý trước khi thu"
      className="space-y-2 rounded-control border border-warning bg-warning-bg p-2"
    >
      <p className="text-meta font-semibold text-warning">
        {dong.some((d) => d.van_de)
          ? "Dòng thuốc cần xử lý trước khi thu — gán thuốc đúng, điền giá, hoặc khách không lấy"
          : "Vừa gán thuốc cho dòng dưới — bấm Hoàn tác gán nếu chọn nhầm"}
      </p>
      {dong.map((d) => (
        <MotDong
          key={d.prescription_id}
          d={d}
          ten={ten[d.prescription_id] ?? "Dòng thuốc"}
          coGia={coGia}
          onKhongLay={onKhongLay}
          onXong={onXong}
        />
      ))}
    </section>
  );
}

function MotDong({
  d,
  ten,
  coGia,
  onKhongLay,
  onXong,
}: {
  d: DongLech;
  ten: string;
  coGia: MauThuoc[];
  onKhongLay: (prescriptionId: string) => Promise<void>;
  onXong: (loi: string | null, cau: string) => Promise<void>;
}) {
  const [tim, setTim] = useState("");
  const [chon, setChon] = useState("");
  const [gia, setGia] = useState("");
  const [dang, setDang] = useState(false);
  const tu = tim.trim().toLowerCase();
  const goiY = (
    tu ? coGia.filter((m) => m.brand.toLowerCase().includes(tu)) : coGia
  ).slice(0, 30);

  const lam = async (than: Record<string, unknown>, cau: string) => {
    setDang(true);
    const kq = await gui(than);
    setDang(false);
    await onXong(kq.loi, kq.nhac ? `${cau} ${kq.nhac}` : cau);
  };

  return (
    <div className="space-y-2 rounded-control border border-line bg-surface p-2">
      <p className="text-body font-medium text-ink">{ten}</p>
      {d.van_de ? (
        <p className="text-meta text-warning">Đang chặn thu: {d.van_de}</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          placeholder="Tìm thuốc đúng trong danh mục"
          aria-label={`Tìm thuốc đúng cho ${ten}`}
          className={`${INPUT} w-full sm:w-56`}
          disabled={dang}
        />
        <select
          value={chon}
          onChange={(e) => setChon(e.target.value)}
          aria-label={`Chọn thuốc đúng cho ${ten}`}
          className={`${INPUT} w-full sm:w-64`}
          disabled={dang}
        >
          <option value="">— Chọn thuốc —</option>
          {goiY.map((m) => (
            <option
              key={m.drug_catalog_id ?? m.ma}
              value={m.drug_catalog_id ?? ""}
            >
              {m.brand} · {tienVn(m.gia)}
              {m.unit ? `/${m.unit}` : ""}
            </option>
          ))}
        </select>
        <Button
          variant="secondary"
          size="sm"
          disabled={dang || !chon}
          onClick={() =>
            void lam(
              {
                thao_tac: "gan-thuoc",
                du_lieu: {
                  prescription_id: d.prescription_id,
                  drug_catalog_id: chon,
                },
              },
              `Đã gán “${ten}” sang thuốc đúng.`,
            )
          }
        >
          Gán thuốc này
        </Button>
      </div>
      {d.thuoc_chua_gia && d.drug_catalog_id ? (
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-40">
            <input
              inputMode="numeric"
              value={gia}
              onChange={(e) => setGia(e.target.value)}
              placeholder="Giá bán (đồng)"
              aria-label={`Giá bán ${ten}`}
              className={INPUT}
              disabled={dang || !d.dien_gia_duoc}
            />
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={dang || !d.dien_gia_duoc || !gia.trim()}
            title={d.ly_do_khong_dien_gia ?? undefined}
            onClick={() =>
              void lam(
                {
                  thao_tac: "dien-gia",
                  du_lieu: {
                    drug_catalog_id: d.drug_catalog_id,
                    gia: gia.trim(),
                  },
                },
                `Đã điền giá cho “${ten}”.`,
              )
            }
          >
            Điền giá
          </Button>
          {d.ly_do_khong_dien_gia ? (
            <span className="text-meta text-ink-muted">
              {d.ly_do_khong_dien_gia}
            </span>
          ) : null}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        {d.van_de ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={dang}
            onClick={() => void onKhongLay(d.prescription_id)}
          >
            Khách không lấy
          </Button>
        ) : null}
        {d.bo_gan_duoc ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={dang}
            onClick={() =>
              void lam(
                {
                  thao_tac: "bo-gan-thuoc",
                  du_lieu: { prescription_id: d.prescription_id },
                },
                `Đã hoàn tác gán “${ten}”.`,
              )
            }
          >
            Hoàn tác gán
          </Button>
        ) : null}
      </div>
    </div>
  );
}
