"use client";

// PHIẾU ĐIỀU TRỊ — MỘT component cho mọi chỗ điền (Tuyền chốt 07/10/2026, sau
// bấm thử staging): khối 4 "Điều trị" ở Bàn khám VÀ khung kết quả ở phòng dịch
// vụ (`PhieuKetQua` chuyển sang đây khi mẫu là PHIEU_DIEU_TRI). Cùng dữ liệu: phiếu
// kết quả (`form_instance`) của CHÍNH chỉ định, mẫu PHIEU_DIEU_TRI — bàn khám
// điền thì phòng thấy và ngược lại.
//
// GỌN như bản Tuyền chọn: các ô chữ to, MỖI Ô MỘT NHÃN (tên ô, không lặp tên mục),
// dòng "Tự lưu khi gõ", chân "Bản n · người sửa · giờ". KHÔNG có "Hoàn tất phiếu"
// — Xong dịch vụ là mốc hoàn thành, mỗi lần lưu là ghi nhận (máy chủ giữ lịch sử
// từng bản, `form_instance_lich_su`). Vẫn In được.
//
// Tự lưu qua hàng đợi chung `lib/use-tu-luu` + revision chống ghi đè của engine
// phiếu kết quả (`/api/phieu`).

import { useCallback, useEffect, useRef, useState } from "react";

import BaoLoiCanhNut from "@/components/ui/BaoLoiCanhNut";
import Button, { buttonClass } from "@/components/ui/Button";
import TrangThaiLuu from "@/components/ui/TrangThaiLuu";
import { nhanLoi } from "@/lib/loi-api";
import { gopGiaTri, MAU_PHIEU_DIEU_TRI, tachGiaTri } from "@/lib/phieu-ket-qua";
import { LOI_MAT_KET_NOI, nenThuLai, type KetQuaGui } from "@/lib/tu-luu";
import { useTuLuu } from "@/lib/use-tu-luu";
import { INPUT, LABEL } from "../form-ui";

const CHO_LUU_MS = 1200;

/** Ô của phiếu (máy chủ trả theo khung — tên ô là nhãn duy nhất). */
export interface ODieuTri {
  ma: string;
  ten: string;
  gia_tri: string;
}

/** Bản đọc sẵn (thẻ chỉ đọc / xem lại lượt) — `dieu_tri_ban_kham.doc_the`. */
export interface BanDieuTri {
  revision: number;
  sua_luc: string | null;
  nguoi_sua: string | null;
  o: ODieuTri[];
}

interface PhieuMo {
  id: string;
  revision: number;
  sua_luc: string | null;
  nguoi_sua: string | null;
  khung: { block?: { ma: string; ten: string }[] }[];
  du_lieu: Record<string, { gia_tri: unknown; nguon: string }>;
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

function chanBan(revision: number, nguoi: string | null, luc: string | null): string {
  return revision > 0 ? `Bản ${revision} · ${nguoi ?? "?"} · ${gio(luc)}` : "Chưa ghi.";
}

async function goi<T>(
  than: Record<string, unknown>,
  keepalive = false,
): Promise<{ ok: true; data: T } | { ok: false; loi: string; status: number }> {
  try {
    const r = await fetch("/api/phieu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
      keepalive,
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) return { ok: false, loi: nhanLoi(d, "Không lưu được phiếu điều trị."), status: r.status };
    return { ok: true, data: d as T };
  } catch {
    return { ok: false, loi: LOI_MAT_KET_NOI, status: 0 };
  }
}

/** Kết quả nút [Xong] ở phòng — cùng dạng `PhieuKetQua.onHoanTat`. */
export interface KetQuaXong {
  daDongDichVu: boolean;
  viSao: string | null;
  laLanSua: boolean;
  conTrong: string[];
  dichVuCau?: string | null;
}

export default function PhieuDieuTri({
  serviceOrderId,
  choGhi,
  banDoc,
  onXong,
}: {
  serviceOrderId: string;
  /** Ghi được (lượt còn mở, người có quyền điền). false = chỉ đọc `banDoc`. */
  choGhi: boolean;
  /** Bản đọc sẵn khi chỉ đọc (không mở / không tạo phiếu). */
  banDoc?: BanDieuTri | null;
  /** Ở PHÒNG (qua `PhieuKetQua`): nút [Xong] đóng dịch vụ đang làm — lưu nốt
   *  rồi đi lệnh của engine phiếu (đóng dịch vụ bằng lệnh module Thực hiện).
   *  Bàn khám không truyền: thẻ có [Xong] riêng. */
  onXong?: (kq: KetQuaXong) => void;
}) {
  if (!choGhi) return <PhieuDieuTriDoc serviceOrderId={serviceOrderId} ban={banDoc ?? null} />;
  return <PhieuDieuTriGhi serviceOrderId={serviceOrderId} onXong={onXong} />;
}

function InPhieu({ serviceOrderId }: { serviceOrderId: string }) {
  return (
    <a
      href={`/print/ket-qua/${serviceOrderId}`}
      target="_blank"
      rel="noopener"
      className={buttonClass("ghost", "sm")}
    >
      In phiếu
    </a>
  );
}

function PhieuDieuTriDoc({ serviceOrderId, ban }: { serviceOrderId: string; ban: BanDieuTri | null }) {
  const co = (ban?.o ?? []).filter((o) => o.gia_tri.trim());
  return (
    <section aria-label="Phiếu điều trị" className="space-y-3">
      {co.length ? (
        co.map((o) => (
          <div key={o.ma} className="space-y-1">
            <p className={LABEL}>{o.ten}</p>
            <p className="whitespace-pre-line text-body text-ink">{o.gia_tri}</p>
          </div>
        ))
      ) : (
        <p className="text-body text-ink-muted">Chưa ghi phiếu điều trị.</p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 text-meta text-ink-muted">
        <span>{ban ? chanBan(ban.revision, ban.nguoi_sua, ban.sua_luc) : "Chưa ghi."}</span>
        {ban ? <InPhieu serviceOrderId={serviceOrderId} /> : null}
      </div>
    </section>
  );
}

function PhieuDieuTriGhi({
  serviceOrderId,
  onXong,
}: {
  serviceOrderId: string;
  onXong?: (kq: KetQuaXong) => void;
}) {
  const [phieu, setPhieu] = useState<PhieuMo | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangXong, setDangXong] = useState(false);
  const [loiXong, setLoiXong] = useState<string | null>(null);
  const [gia, setGia] = useState<Record<string, string>>({});
  const [chan, setChan] = useState<{ revision: number; nguoi: string | null; luc: string | null }>({
    revision: 0,
    nguoi: null,
    luc: null,
  });
  const phieuRef = useRef<PhieuMo | null>(null);
  const giaRef = useRef<Record<string, string>>({});
  // Revision trong ref: mỗi lần lưu gửi số MỚI NHẤT (hàng đợi tuần tự).
  const revision = useRef(0);

  const gui = useCallback(async (keepalive: boolean): Promise<KetQuaGui> => {
    const p = phieuRef.current;
    if (!p) return { ok: true };
    const kq = await goi<{ revision: number; luu_luc: string; nguoi_sua: string | null }>(
      {
        thao_tac: "luu",
        phieu_id: p.id,
        du_lieu: { expected_revision: revision.current, du_lieu: gopGiaTri(giaRef.current) },
      },
      keepalive,
    );
    if (!kq.ok) return { ok: false, loi: kq.loi, thuLai: nenThuLai(kq.status) };
    revision.current = kq.data.revision;
    setChan({ revision: kq.data.revision, nguoi: kq.data.nguoi_sua, luc: kq.data.luu_luc });
    return { ok: true };
  }, []);
  const tuLuu = useTuLuu({ gui, choMs: CHO_LUU_MS });
  const lamSach = tuLuu.lamSach;

  useEffect(() => {
    let huy = false;
    void goi<PhieuMo>({
      thao_tac: "mo",
      du_lieu: { service_order_id: serviceOrderId, form_id: `KQ_${MAU_PHIEU_DIEU_TRI}` },
    }).then((kq) => {
      if (huy) return;
      if (!kq.ok) {
        setLoi(kq.loi);
        return;
      }
      setLoi(null);
      phieuRef.current = kq.data;
      revision.current = kq.data.revision;
      giaRef.current = tachGiaTri(kq.data.du_lieu);
      setGia(giaRef.current);
      setChan({ revision: kq.data.revision, nguoi: kq.data.nguoi_sua, luc: kq.data.sua_luc });
      setPhieu(kq.data);
      lamSach();
    });
    return () => {
      huy = true;
    };
  }, [serviceOrderId, lamSach]);

  const xong = async () => {
    const p = phieuRef.current;
    if (!p || !onXong) return;
    setDangXong(true);
    setLoiXong(null);
    // Lưu nốt chữ vừa gõ TRƯỚC khi đóng dịch vụ (cùng hàng đợi tự lưu).
    if (!(await tuLuu.luuNgay())) {
      setDangXong(false);
      setLoiXong("Chữ vừa gõ CHƯA lưu được nên chưa Xong — bấm [Thử lại] ở dòng lưu rồi bấm lại.");
      return;
    }
    const kq = await goi<{
      revision: number;
      dich_vu?: { da_dong: boolean; vi_sao: string | null; cau?: string | null };
    }>({
      thao_tac: "hoan-tat",
      phieu_id: p.id,
      du_lieu: { expected_revision: revision.current, thuc_hien_boi: null, ly_do_sua: null },
    });
    setDangXong(false);
    if (!kq.ok) {
      setLoiXong(kq.loi);
      return;
    }
    revision.current = kq.data.revision;
    onXong({
      daDongDichVu: kq.data.dich_vu?.da_dong ?? false,
      viSao: kq.data.dich_vu?.vi_sao ?? null,
      laLanSua: false,
      conTrong: [],
      dichVuCau: kq.data.dich_vu?.cau ?? null,
    });
  };

  if (loi) {
    return (
      <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-body text-danger">
        {loi}
      </p>
    );
  }
  if (!phieu) return <p className="text-body text-ink-muted">Đang mở phiếu điều trị…</p>;

  const cacO = phieu.khung.flatMap((m) => m.block ?? []);
  return (
    <section aria-label="Phiếu điều trị" className="space-y-3">
      {cacO.map((o) => (
        <label key={o.ma} className="block space-y-1">
          <span className={LABEL}>{o.ten}</span>
          <textarea
            value={gia[o.ma] ?? ""}
            aria-label={o.ten}
            onChange={(e) => {
              giaRef.current = { ...giaRef.current, [o.ma]: e.target.value };
              setGia(giaRef.current);
              tuLuu.danhDau();
            }}
            onBlur={() => {
              if (tuLuu.trangThai.chua_luu) void tuLuu.luuNgay();
            }}
            className={`${INPUT} min-h-28 resize-y leading-relaxed sm:min-h-28`}
          />
        </label>
      ))}
      <div className="flex flex-wrap items-center justify-between gap-2 text-meta text-ink-muted">
        <span>{chanBan(chan.revision, chan.nguoi, chan.luc)}</span>
        <span className="flex flex-wrap items-center gap-2">
          <TrangThaiLuu tt={tuLuu.trangThai} onLuuNgay={() => void tuLuu.luuNgay()} />
          <InPhieu serviceOrderId={serviceOrderId} />
        </span>
      </div>
      {onXong ? (
        <div className="space-y-2">
          <BaoLoiCanhNut>{loiXong}</BaoLoiCanhNut>
          <Button size="md" variant="primary" disabled={dangXong} onClick={() => void xong()}>
            {dangXong ? "Đang ghi…" : "Xong"}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
