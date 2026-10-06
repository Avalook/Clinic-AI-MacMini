"use client";

// SỔ SỬA / BỎ CHỈ ĐỊNH (Khối 2, Tuyền chốt 06/10/2026) — một danh sách cho hai
// chỗ: mục "Lịch sử sửa" của phiếu khám và khung Hành trình khách.
//
// CHỈ VẼ. Máy chủ viết câu (`cau`), nhãn vai, có hoàn tác được không
// (`hoan_tac_duoc`) — `so_sua_chi_dinh_service.dong_so`. Bấm Hoàn tác gửi đúng
// lệnh của máy chủ; màn tự tải lại qua dòng SSE chung (bảng `so_sua_chi_dinh`).

import { useCallback, useEffect, useState } from "react";

import Chip, { type ChipTone } from "@/components/ui/Chip";
import NutHoanTac from "@/components/ui/NutHoanTac";

import type { SoSua } from "@/lib/so-sua-chi-dinh";

import { useNgheBang } from "../dung-nghe-bang";
import { docBang } from "./api";
import { lenhHoanTac } from "./hoan-tac";

const TONE: Record<string, ChipTone> = {
  THEM: "success",
  BO: "danger",
  HOAN_TAC: "info",
  DOI: "warning",
};

/** Bảng phải nghe để sổ tự tải lại — cần trigger `trg_notify_so_sua_chi_dinh`. */
const BANG_SO = ["so_sua_chi_dinh"] as const;

function luc(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

/** Danh sách dòng sổ (mới nhất trước). `choHoanTac` = hiện nút ở dòng máy chủ cho phép. */
export function DanhSachSoSua({
  so,
  choHoanTac = false,
  onDoi,
}: {
  so: SoSua;
  choHoanTac?: boolean;
  onDoi?: () => void;
}) {
  if (so.dong.length === 0) {
    return <p className="text-meta text-ink-muted">Chưa có lần thêm / bỏ chỉ định nào.</p>;
  }
  return (
    <ol className="space-y-2">
      {so.dong.map((d) => (
        <li key={d.id} className="space-y-0.5">
          <p className="flex flex-wrap items-center gap-2 text-meta text-ink">
            <Chip tone={TONE[d.hanh_dong ?? ""] ?? "neutral"}>{d.hanh_dong_nhan || "—"}</Chip>
            <span className="font-semibold">{d.boi ?? "Không rõ người bấm"}</span>
            {d.boi_vai ? <span className="text-ink-muted">({d.boi_vai})</span> : null}
            <span className="tabular-nums text-ink-muted">{luc(d.luc)}</span>
            {choHoanTac && d.hoan_tac_duoc ? (
              <NutHoanTac
                goi={lenhHoanTac("hoan-tac-bo-chi-dinh", d.id)}
                onXong={onDoi}
                moTa={`Đặt lại: ${d.ten_muc ?? ""}`}
              />
            ) : null}
          </p>
          <p className="text-meta text-ink">{d.cau}</p>
          <p className="text-meta text-ink-muted">
            {[
              d.bac_si_chinh ? `Bàn ${d.bac_si_chinh}` : null,
              d.phong_kham,
              d.chi_dinh_goc_boi && d.hanh_dong !== "THEM"
                ? `chỉ định gốc: ${d.chi_dinh_goc_boi}`
                : null,
              d.ly_do ? `lý do: ${d.ly_do}` : null,
              d.da_bao_bac_si_luc ? `đã báo bác sĩ chính ${luc(d.da_bao_bac_si_luc)}` : null,
              d.hoan_tac_boi ? `${d.hoan_tac_boi} hoàn tác ${luc(d.hoan_tac_luc)}` : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </li>
      ))}
    </ol>
  );
}

/** Tự đọc sổ của một lượt + tải lại khi bảng sổ đổi (dòng SSE chung). */
export function SoSuaChiDinhTuTai({ visitId }: { visitId: string }) {
  const [kq, setKq] = useState<{ id: string; so?: SoSua; loi?: string } | null>(null);
  const [lanNap, setLanNap] = useState(0);
  useEffect(() => {
    let huy = false;
    void docBang<SoSua>("so-sua-chi-dinh", { luot: visitId }).then((r) => {
      if (huy) return;
      setKq(r.ok ? { id: visitId, so: r.data } : { id: visitId, loi: r.loi });
    });
    return () => {
      huy = true;
    };
  }, [visitId, lanNap]);
  const napLai = useCallback(() => setLanNap((n) => n + 1), []);
  useNgheBang(BANG_SO, napLai);
  if (kq?.id !== visitId) return <p className="text-meta text-ink-muted">Đang đọc…</p>;
  if (kq.loi) return <p className="text-body text-danger">{kq.loi}</p>;
  if (!kq.so) return null;
  return (
    <div className="space-y-1">
      {kq.so.chi_xem ? (
        <p className="text-meta text-ink-muted">Lượt chuyển từ hồ sơ cũ — chỉ xem.</p>
      ) : null}
      <DanhSachSoSua so={kq.so} choHoanTac onDoi={napLai} />
      {kq.so.bi_cat ? (
        <p className="text-meta text-ink-muted">Chỉ hiện các lần sửa gần nhất.</p>
      ) : null}
    </div>
  );
}
