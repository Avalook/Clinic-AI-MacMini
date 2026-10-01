"use client";

// NÚT "+ DỊCH VỤ" — LÀM THÊM TẠI QUẦY (Tuyền 01/10/2026, sau buổi thực nghiệm).
//
// Lễ tân (Tiếp đón) hay người đo sinh hiệu tick "+ Nước tiểu" cho một khách là
// có chỉ định NGAY — không cần bác sĩ. Bỏ tick khi chưa làm, chưa thu là huỷ.
// Danh sách nút (nước tiểu, lấy máu…) do QUẢN LÝ quản ở /settings/day-noi.
//
// MÀN CHỈ VẼ. Nút nào hiện ở màn này, nút nào đang tick, bấm được không, câu vì
// sao không bỏ được — máy chủ trả (`GET /api/lam-them?noi=&luot=`). Tick / bỏ
// tick gửi `POST /api/lam-them` (thao_tac "dat"); máy chủ gác quyền theo lego
// của màn (Tiếp đón / Sinh hiệu) và mọi luật.
//
// Một lần đọc cho CẢ danh sách lượt (`useLamThem`), mỗi dòng vẽ `NutLamThem`.
// Tự cập nhật khi chỉ định / danh sách nút đổi ở bất cứ đâu (dòng SSE chung).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import ChipChon from "@/components/ui/ChipChon";
import { chiaLoLamThem } from "@/lib/lam-them";

import { useNgheBang } from "../dung-nghe-bang";

export type NoiLamThem = "tiep_don" | "sinh_hieu";

export interface NutDichVu {
  service_code: string;
  nhan: string;
  ten: string;
  gia: number | null;
}

export interface TrangThaiNut {
  chon: boolean;
  doi_duoc: boolean;
  order_id: string | null;
  order_version: number | null;
  state_revision: number;
  ghi_chu: string | null;
  luot_mo: boolean;
}

export interface GoiLamThem {
  noi: NoiLamThem;
  nut: NutDichVu[];
  luot: Record<string, Record<string, TrangThaiNut>>;
}

const BANG_NGHE = ["service_order", "lam_them_tai_quay", "visit"] as const;

/** Đọc nút + trạng thái cho nhiều lượt một lần. `visitIds` rỗng → không hỏi. */
export function useLamThem(noi: NoiLamThem, visitIds: readonly string[]) {
  const khoa = useMemo(() => [...new Set(visitIds)].sort().join(","), [visitIds]);
  const [goi, setGoi] = useState<GoiLamThem | null>(null);
  const [lan, setLan] = useState(0);
  useNgheBang(BANG_NGHE, () => setLan((n) => n + 1));

  useEffect(() => {
    if (!khoa) return;
    let huy = false;
    void (async () => {
      try {
        const cacLo = chiaLoLamThem(khoa.split(","));
        const cacGoi = await Promise.all(
          cacLo.map(async (lo) => {
            const r = await fetch(
              `/api/lam-them?noi=${noi}&luot=${encodeURIComponent(lo.join(","))}`,
              { cache: "no-store" },
            );
            if (!r.ok) return null;
            return (await r.json().catch(() => null)) as GoiLamThem | null;
          }),
        );
        const hopLe = cacGoi.filter((x): x is GoiLamThem => Boolean(x && Array.isArray(x.nut)));
        if (!huy && hopLe.length === cacLo.length && hopLe[0]) {
          setGoi({
            noi,
            nut: hopLe[0].nut,
            luot: Object.assign({}, ...hopLe.map((x) => x.luot)),
          });
        }
      } catch {
        // mất mạng: giữ bản cũ, tin SSE kế tiếp hỏi lại
      }
    })();
    return () => {
      huy = true;
    };
  }, [noi, khoa, lan]);

  const napLai = useCallback(() => setLan((n) => n + 1), []);
  return { goi: khoa ? goi : null, napLai };
}

function tien(n: number | null): string {
  return n == null ? "" : ` · ${n.toLocaleString("vi-VN")}đ`;
}

/** Các nút của MỘT lượt. Lượt đã check-out / không có nút → không vẽ gì. */
export function NutLamThem({
  goi,
  visitId,
  napLai,
  className = "",
}: {
  goi: GoiLamThem | null;
  visitId: string;
  napLai: () => void;
  className?: string;
}) {
  const [dang, setDang] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const khoaLenh = useRef<Record<string, string>>({});
  // Kết quả vừa bấm — chỉ sống tới khi bản đọc lại về (gói mới ≠ gói lúc bấm thì
  // bỏ), để ô không nhảy về trạng thái cũ trong lúc chờ.
  const [vuaDat, setVuaDat] = useState<{ goc: GoiLamThem | null; gia: Record<string, boolean> }>({
    goc: null,
    gia: {},
  });
  const giaVuaDat = vuaDat.goc === goi ? vuaDat.gia : {};
  const cuaLuot = goi?.luot[visitId];
  if (!goi || goi.nut.length === 0 || !cuaLuot) return null;
  const nut = goi.nut.filter((n) => cuaLuot[n.service_code]?.luot_mo);
  if (nut.length === 0) return null;

  async function dat(n: NutDichVu, chon: boolean) {
    if (!goi || dang) return;
    const tt = goi.luot[visitId]?.[n.service_code];
    if (!tt) return;
    const maLenh = `${visitId}:${n.service_code}:${chon}`;
    const idempotencyKey = khoaLenh.current[maLenh] ?? crypto.randomUUID();
    khoaLenh.current[maLenh] = idempotencyKey;
    setDang(n.service_code);
    setLoi(null);
    try {
      const r = await fetch("/api/lam-them", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thao_tac: "dat",
          du_lieu: {
            visit_id: visitId,
            service_code: n.service_code,
            noi: goi.noi,
            chon,
            expected_order_id: tt.order_id,
            expected_version: tt.order_version,
            expected_state_revision: tt.state_revision,
            idempotency_key: idempotencyKey,
          },
        }),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) {
        delete khoaLenh.current[maLenh];
        setLoi(d?.message ?? d?.error ?? `Không ${chon ? "thêm" : "bỏ"} được (HTTP ${r.status}).`);
        napLai();
        return;
      }
      delete khoaLenh.current[maLenh];
      setVuaDat({ goc: goi, gia: { ...giaVuaDat, [n.service_code]: chon } });
      napLai();
    } catch {
      setLoi("Mất kết nối — chưa lưu, bấm lại.");
    } finally {
      setDang(null);
    }
  }

  return (
    <div className={`flex min-w-0 flex-wrap items-center gap-1.5 ${className}`}>
      {nut.map((n) => {
        const tt = cuaLuot[n.service_code];
        // Bản đọc lại chưa về mà vừa bấm xong: hiện theo lần bấm.
        const hien = giaVuaDat[n.service_code] ?? tt.chon;
        return (
          <span key={n.service_code} title={tt.ghi_chu ?? `${n.ten}${tien(n.gia)}`}>
            <ChipChon
              chon={hien}
              disabled={!tt.doi_duoc || dang !== null}
              onDoi={() => void dat(n, !hien)}
            >
              {hien ? n.nhan : `+ ${n.nhan}`}
              {tt.ghi_chu && !tt.doi_duoc ? (
                <span className="text-meta text-ink-muted">({tt.ghi_chu})</span>
              ) : null}
            </ChipChon>
          </span>
        );
      })}
      {loi ? (
        <p role="alert" className="w-full rounded-control bg-danger-bg px-2 py-1 text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
