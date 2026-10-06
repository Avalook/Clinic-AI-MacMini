"use client";

// KHÁCH CÒN NỢ LÚC VỀ (01/10/2026 — Tuyền chốt sau sự cố 30/09).
//
// Máy chủ CHẶN check-out (cả "về giữa chừng") khi khách còn khoản đã làm / đã
// mua mà chưa thu (`cong_no_service.no_khi_ve`). Khối này chỉ VẼ đúng thứ máy
// chủ trả trong `no_khi_ve` và cho hai đường qua:
//
//   * "Thu ngay" → quầy thu có sẵn, chọn sẵn lượt này (`?luot=`). Không có lego
//     thu tiền thì là dòng chữ "nhờ thu ngân", không dẫn vào ngõ cụt.
//   * "Ghi nợ" + lý do → `POST /api/reception/checkout {hanh_dong:"ghi_no"}`.
//     Đã ghi nợ (khách chưa về) thì "Huỷ ghi nợ" (bấm nhầm) — hoàn tác được.
//
// Không tự suy "còn nợ hay không", không cộng tiền: mọi con số từ máy chủ.
// Dùng chung ở nút Check-out nhanh, màn Check-out và khối Lượt tồn đọng.

import Link from "next/link";
import { useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import { coQuyen } from "@/lib/quyen-client";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { INPUT } from "../form-ui";
import { useQuyen } from "../QuyenContext";

export interface DongNo {
  loai: "dich_vu" | "thuoc" | string;
  source_id: string;
  ten: string;
  so_tien: number | null;
}

/** Tiền thừa lúc về (06/10/2026, E2a) — máy chủ tính, màn chỉ vẽ. */
export interface TienThuaKhiVe {
  tong: number;
  dong: { ten: string | null; so_tien: number; loai: string; ly_do: string | null }[];
  giu_lai: { id: string; so_tien: number; ly_do: string; boi: string | null; luc: string | null } | null;
  /** Còn tiền thừa chưa hoàn / chưa giữ lại phủ đủ → chặn check-out. */
  chan: boolean;
}

/** Hình dạng `no_khi_ve` của `GET /api/v1/reception/checkout*`. */
export interface NoKhiVe {
  tong: number;
  dong: DongNo[];
  /** Còn nợ (hoặc tiền thừa chưa xử lý) → máy chủ chặn check-out. */
  chan: boolean;
  /** Chỉ phần NỢ chặn (06/10/2026); thiếu = dữ liệu cũ, dùng `chan`. */
  chan_no?: boolean;
  tien_thua?: TienThuaKhiVe | null;
  /** Quầy thu nhận lượt này ngay chưa, theo loại — máy chủ quyết. */
  thu_ngay?: Partial<Record<"dich_vu" | "thuoc", boolean>>;
  ghi_no: {
    id: string;
    so_tien: number;
    ly_do: string;
    nguoi_ghi: string | null;
    luc: string | null;
    phu_du: boolean;
  } | null;
}

const tien = (n: number | null | undefined) =>
  `${Math.round(n ?? 0).toLocaleString("vi-VN")}đ`;

/** Có gì để vẽ không (còn nợ, hoặc đã ghi nợ). */
export function coNo(no: NoKhiVe | null | undefined): no is NoKhiVe {
  return (
    !!no &&
    (no.dong.length > 0 || no.ghi_no !== null || (no.tien_thua?.tong ?? 0) > 0)
  );
}

export default function KhoanNoKhiVe({
  visitId,
  no,
  onDoi,
  choThuNgay = true,
}: {
  visitId: string;
  no: NoKhiVe;
  /** Lượt ngày trước chưa ghi nợ không nằm ở quầy thu hôm nay → tắt lối
   *  "Thu ngay" (khỏi dẫn vào ngõ cụt), chỉ còn Ghi nợ. */
  choThuNgay?: boolean;
  /** Sau khi ghi / huỷ ghi nợ — nơi dùng hỏi lại máy chủ. */
  onDoi: () => void;
}) {
  const quyen = useQuyen();
  const [mo, setMo] = useState<"ghi" | "huy" | "giu" | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const loai = new Set(no.dong.map((d) => d.loai));
  const thuDuoc = (!choThuNgay ? [] : [
    loai.has("dich_vu") && no.thu_ngay?.dich_vu && coQuyen(quyen, "payment.service.collect")
      ? { href: `/thu-ngan/dich-vu?luot=${encodeURIComponent(visitId)}`, nhan: "Thu ngay — dịch vụ" }
      : null,
    loai.has("thuoc") && no.thu_ngay?.thuoc && coQuyen(quyen, "payment.medicine.collect")
      ? { href: `/thu-ngan/thuoc?luot=${encodeURIComponent(visitId)}`, nhan: "Thu ngay — thuốc" }
      : null,
  ]).filter((x): x is { href: string; nhan: string } => x !== null);

  // Nợ chặn riêng (tiền thừa có hộp riêng bên dưới).
  const chanNo = no.chan_no ?? no.chan;
  const tt = no.tien_thua ?? null;

  async function gui(
    hanhDong:
      | "ghi_no"
      | "huy_ghi_no"
      | "hoan_tien_thua"
      | "giu_lai_tien_thua"
      | "huy_giu_lai_tien_thua",
  ) {
    setLoi(null);
    setDangGui(true);
    try {
      const r = await fetch("/api/reception/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hanh_dong: hanhDong, visit_id: visitId, ly_do: lyDo.trim() }),
      });
      const d = (await r.json().catch(() => null)) as { ok?: boolean } | null;
      if (!r.ok || !d?.ok) {
        setLoi(loiDocDuoc(d, `Không lưu được (HTTP ${r.status}).`));
        return;
      }
      setMo(null);
      setLyDo("");
      onDoi();
    } catch {
      setLoi("Mất kết nối — chưa lưu.");
    } finally {
      setDangGui(false);
    }
  }

  const ghi = no.ghi_no;
  return (
    <section
      aria-label="Khoản khách còn nợ"
      className={`w-full space-y-2 rounded-control border px-3 py-2 ${
        no.chan ? "border-danger bg-danger-bg" : "border-line bg-surface"
      }`}
    >
      {no.dong.length > 0 ? (
        <>
          <p className={`text-body font-semibold ${chanNo ? "text-danger" : "text-ink"}`}>
            Khách còn nợ {tien(no.tong)}
            {chanNo ? " — chưa check-out được" : ""}
          </p>
          <ul className="space-y-0.5 text-meta text-ink">
            {no.dong.map((d) => (
              <li key={d.source_id} className="flex justify-between gap-3">
                <span className="min-w-0 truncate">
                  {d.loai === "thuoc" ? "Thuốc · " : ""}
                  {d.ten}
                </span>
                <span className="shrink-0 tabular-nums">
                  {d.so_tien === null ? "chưa có giá" : tien(d.so_tien)}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {ghi ? (
        <p className="text-meta text-ink-muted">
          {ghi.phu_du ? "Đã ghi nợ" : "Đã ghi nợ (chưa gồm khoản mới)"} {tien(ghi.so_tien)}
          {ghi.nguoi_ghi ? ` · ${ghi.nguoi_ghi}` : ""} — “{ghi.ly_do}”
        </p>
      ) : null}

      {tt && tt.tong > 0 ? (
        <div className="space-y-1 border-t border-line pt-2">
          <p className={`text-body font-semibold ${tt.chan ? "text-danger" : "text-ink"}`}>
            Tiền thừa {tien(tt.tong)}
            {tt.chan ? " — hoàn cho khách hoặc giữ lại (ghi lý do) rồi mới check-out" : ""}
          </p>
          <ul className="space-y-0.5 text-meta text-ink">
            {tt.dong.map((d, i) => (
              <li key={`${d.ten ?? ""}-${i}`} className="flex justify-between gap-3">
                <span className="min-w-0 truncate">
                  {d.ten ?? "—"} · {d.loai === "KHONG_LAM" ? "không làm" : "đã bỏ"}
                </span>
                <span className="shrink-0 tabular-nums">{tien(d.so_tien)}</span>
              </li>
            ))}
          </ul>
          {tt.giu_lai ? (
            <p className="text-meta text-ink-muted">
              Đã giữ lại {tien(tt.giu_lai.so_tien)}
              {tt.giu_lai.boi ? ` · ${tt.giu_lai.boi}` : ""} — “{tt.giu_lai.ly_do}”
            </p>
          ) : null}
          {mo === null ? (
            <div className="flex flex-wrap items-center gap-2">
              {tt.chan ? (
                <Button
                  size="sm"
                  variant="primary"
                  disabled={dangGui}
                  onClick={() => void gui("hoan_tien_thua")}
                >
                  {dangGui ? "Đang hoàn…" : `Đã hoàn cho khách — hoàn ${tien(tt.tong)} tiền mặt`}
                </Button>
              ) : null}
              {tt.chan ? (
                <Button size="sm" variant="secondary" onClick={() => setMo("giu")}>
                  Giữ lại
                </Button>
              ) : null}
              {tt.giu_lai ? (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={dangGui}
                  onClick={() => void gui("huy_giu_lai_tien_thua")}
                >
                  Huỷ giữ lại
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {mo ? (
        <div className="space-y-2">
          <label className="block text-meta text-ink-muted">
            {mo === "ghi"
              ? "Lý do ghi nợ (bắt buộc) — vd: khách quên ví, hẹn mai chuyển khoản"
              : mo === "giu"
                ? "Lý do giữ lại tiền thừa (bắt buộc) — vd: khách để lại trừ lần sau"
                : "Lý do huỷ ghi nợ (bắt buộc)"}
            <input
              value={lyDo}
              onChange={(e) => setLyDo(e.target.value)}
              maxLength={500}
              autoFocus
              className={`${INPUT} mt-1`}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={mo === "huy" ? "danger" : "primary"}
              disabled={dangGui || lyDo.trim().length < 3}
              onClick={() =>
                void gui(mo === "ghi" ? "ghi_no" : mo === "giu" ? "giu_lai_tien_thua" : "huy_ghi_no")
              }
            >
              {dangGui
                ? "Đang lưu…"
                : mo === "ghi"
                  ? `Ghi nợ ${tien(no.tong)}`
                  : mo === "giu"
                    ? `Giữ lại ${tien(tt?.tong ?? 0)}`
                    : "Huỷ ghi nợ"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={dangGui}
              onClick={() => {
                setMo(null);
                setLoi(null);
              }}
            >
              Thôi
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {chanNo
            ? thuDuoc.map((t) => (
                <Link key={t.href} href={t.href} className={buttonClass("primary", "sm")}>
                  {t.nhan}
                </Link>
              ))
            : null}
          {chanNo && thuDuoc.length === 0 && choThuNgay ? (
            <span className="text-meta text-ink-muted">Nhờ thu ngân thu, hoặc</span>
          ) : null}
          {chanNo ? (
            <Button size="sm" variant="secondary" onClick={() => setMo("ghi")}>
              Ghi nợ
            </Button>
          ) : null}
          {ghi ? (
            <Button size="sm" variant="ghost" onClick={() => setMo("huy")}>
              Huỷ ghi nợ
            </Button>
          ) : null}
        </div>
      )}

      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
