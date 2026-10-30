"use client";

// TÀI KHOẢN NGÂN HÀNG NHẬN CHUYỂN KHOẢN (31/10/2026).
//
// `ChonTaiKhoan` — trong khối chia hình thức (`ChiaHinhThuc`, mọi lối thu): có
// phần chuyển khoản thì chọn tài khoản nhận. Máy chủ trả sẵn danh sách dùng được
// ở cơ sở của lượt + tài khoản tự chọn (`mac_dinh`: mặc định của cơ sở, hoặc
// tài khoản duy nhất). Một tài khoản → chỉ ghi tên, không hỏi.
//
// `DoiTaiKhoan` — ở Lịch sử thu: sửa tài khoản của phiếu đã thu (chọn nhầm);
// đổi lại là hoàn tác. Máy chủ ghi vết.
//
// Màn không quyết gì: tài khoản nào dùng được / mặc định / ai sửa được là của
// `services/tai_khoan_nhan_service.py`.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import ONhap from "@/components/ui/ONhap";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { useNgheBang } from "../dung-nghe-bang";

export interface TaiKhoan {
  id: string;
  ten_goi: string;
  ngan_hang: string;
  so_tai_khoan: string;
  chu_tai_khoan: string;
  location_id: string | null;
  ten_co_so: string | null;
  mac_dinh: boolean;
  dang_dung: boolean;
  so_lan_thu: number;
}

interface DanhSach {
  tai_khoan: TaiKhoan[];
  dung_duoc: string[];
  mac_dinh: string | null;
  quan_ly: boolean;
}

async function docDanhSach(visitId?: string | null): Promise<DanhSach | null> {
  try {
    const q = visitId ? `?visit_id=${encodeURIComponent(visitId)}` : "";
    const r = await fetch(`/api/tai-khoan-nhan${q}`, { cache: "no-store" });
    return r.ok ? ((await r.json()) as DanhSach) : null;
  } catch {
    // Mất mạng: giữ danh sách cũ — máy chủ vẫn tự chọn mặc định khi ghi.
    return null;
  }
}

/** Danh mục từ máy chủ; tự tải lại khi Quản lý thêm / tắt tài khoản. */
export function useTaiKhoanNhan(visitId?: string | null) {
  const [ds, setDs] = useState<DanhSach | null>(null);
  const tai = useCallback(async () => {
    const d = await docDanhSach(visitId);
    if (d) setDs(d);
  }, [visitId]);
  useEffect(() => {
    let huy = false;
    void docDanhSach(visitId).then((d) => {
      if (!huy && d) setDs(d);
    });
    return () => {
      huy = true;
    };
  }, [visitId]);
  useNgheBang(["tai_khoan_nhan"], tai);
  const dung = (ds?.tai_khoan ?? []).filter((t) => ds?.dung_duoc.includes(t.id));
  return { ds, dung, macDinh: ds?.mac_dinh ?? null, tai };
}

export const tenTaiKhoan = (t: Pick<TaiKhoan, "ten_goi" | "so_tai_khoan">) =>
  `${t.ten_goi} · ${t.so_tai_khoan}`;

/** Chọn tài khoản nhận cho phần chuyển khoản. `chon` null = chưa chọn. */
export function ChonTaiKhoan({
  dung,
  chon,
  onChon,
}: {
  dung: TaiKhoan[];
  chon: string | null;
  onChon: (id: string) => void;
}) {
  if (dung.length === 0) return null;
  if (dung.length === 1) {
    return (
      <p className="text-meta text-ink-muted">
        Vào tài khoản <span className="font-medium text-ink">{tenTaiKhoan(dung[0])}</span>
      </p>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2" role="radiogroup" aria-label="Tài khoản nhận">
      <span className="text-meta text-ink-soft">Vào tài khoản</span>
      {dung.map((t) => (
        <ChipChon key={t.id} kieu="mot" ten="tai-khoan-nhan" chon={chon === t.id} onDoi={() => onChon(t.id)}>
          {t.ten_goi}
          <span className="text-meta text-ink-muted"> · {t.so_tai_khoan}</span>
        </ChipChon>
      ))}
    </div>
  );
}

/** Lịch sử thu: tài khoản nhận của một phiếu + [Sửa] (đổi lại = hoàn tác). */
export function DoiTaiKhoan({
  paymentCycleId,
  visitId,
  taiKhoanId,
  tenHienTai,
  choSua,
  onXong,
}: {
  paymentCycleId: string;
  visitId?: string | null;
  taiKhoanId: string | null;
  tenHienTai: string | null;
  choSua: boolean;
  onXong: () => void;
}) {
  const [mo, setMo] = useState(false);
  const [chon, setChon] = useState<string | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const { dung } = useTaiKhoanNhan(mo ? visitId : undefined);
  const khac = dung.filter((t) => t.id !== taiKhoanId);
  // Chỉ còn MỘT tài khoản khác → chọn sẵn (không bắt bấm thêm).
  const chonHieuLuc = chon ?? (khac.length === 1 ? khac[0].id : null);

  async function luu() {
    if (!chonHieuLuc) return;
    setDang(true);
    setLoi(null);
    try {
      const r = await fetch("/api/payment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "doi-tai-khoan",
          paymentCycleId,
          taiKhoanId: chonHieuLuc,
          taiKhoanCu: taiKhoanId,
          lyDo: lyDo.trim() || null,
        }),
      });
      const d = (await r.json().catch(() => null)) as { ok?: boolean } | null;
      if (!r.ok || !d?.ok) {
        setLoi(loiDocDuoc(d, `Chưa sửa được (HTTP ${r.status}).`));
        return;
      }
      setMo(false);
      setChon(null);
      setLyDo("");
      onXong();
    } catch {
      setLoi("Mất kết nối — chưa sửa.");
    } finally {
      setDang(false);
    }
  }

  return (
    <div className="space-y-1">
      <p className="flex flex-wrap items-center gap-2 text-meta text-ink-muted">
        Chuyển khoản vào: <span className="font-medium text-ink">{tenHienTai ?? "Chưa phân loại"}</span>
        {choSua && !mo ? (
          <Button type="button" size="sm" variant="ghost" onClick={() => setMo(true)}>
            Sửa tài khoản
          </Button>
        ) : null}
      </p>
      {mo ? (
        <div className="space-y-2 rounded-control border border-line bg-surface px-3 py-2">
          <ChonTaiKhoan dung={khac} chon={chonHieuLuc} onChon={setChon} />
          {dung.length > 0 && khac.length === 0 ? (
            <p className="text-meta text-ink-muted">Không còn tài khoản nào khác đang dùng.</p>
          ) : null}
          <ONhap
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            maxLength={500}
            placeholder="Lý do (không bắt buộc) — vd: chọn nhầm tài khoản"
            aria-label="Lý do sửa tài khoản nhận"
            className="w-full"
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="primary" disabled={!chonHieuLuc || dang} onClick={() => void luu()}>
              {dang ? "Đang lưu…" : "Lưu tài khoản"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setMo(false)}>
              Thôi
            </Button>
          </div>
          {loi ? (
            <p role="alert" className="text-meta text-danger">
              {loi}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
