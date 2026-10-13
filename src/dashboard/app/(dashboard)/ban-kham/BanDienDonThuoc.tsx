"use client";

// Khách đã KHÁM XONG ra bàn tư vấn để điền đơn thuốc (Tuyền 13/10/2026): bác sĩ
// chính ghi thuốc trên tờ phơi / điền dở, bác sĩ tư vấn điền tiếp đúng đơn của
// lượt và in tại bàn. Thẻ khách + sinh hiệu dùng chung với bàn tư vấn; thân là
// khối Đơn thuốc mở sẵn, đơn tự lưu. Nút [Xong kê đơn] chỉ là MỐC "đã được bác sĩ
// tư vấn kê đơn" (hành trình + nhóm ở cột trái): không khoá đơn, quầy thuốc không
// chờ; bấm [Mở lại] là hoàn tác.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

import type { ClinicalCompletionGate } from "@/lib/clinical-completion";
import type { DatChiDinh, DauPhieu } from "@/lib/phieu-kham";

import { TheKhach, TheSinhHieu } from "../_lam-viec/phieu-kham/TheKhach";
import KhoiDonThuocBanTuVan from "./KhoiDonThuocBanTuVan";

export default function BanDienDonThuoc({
  visitId,
  clinicPatientId,
  choGhi,
  daXong,
  onTrangThai,
  datChiDinh,
  onDaDat,
}: {
  visitId: string;
  clinicPatientId: string;
  choGhi: boolean;
  /** Bác sĩ tư vấn đã bấm "Xong kê đơn" cho lượt này (máy chủ trả). */
  daXong: boolean;
  onTrangThai: (g: ClinicalCompletionGate) => void;
  datChiDinh: DatChiDinh;
  onDaDat: () => void;
}) {
  const [dau, setDau] = useState<DauPhieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  // Đơn đã lưu hết chưa — [Xong kê đơn] đợi, như [Xong tư vấn] đợi ô tư vấn.
  const [cong, setCong] = useState<ClinicalCompletionGate | null>(null);
  const baoCong = useCallback(
    (g: ClinicalCompletionGate) => {
      setCong(g);
      onTrangThai(g);
    },
    [onTrangThai],
  );
  const [dangGui, setDangGui] = useState(false);
  const [loiXong, setLoiXong] = useState<string | null>(null);
  const danhDau = async (xong: boolean) => {
    setLoiXong(null);
    if (xong) {
      if (!cong) {
        setLoiXong("Đang tải đơn thuốc — thử lại sau một chút.");
        return;
      }
      if (!cong.ok) {
        if (!cong.luuNot) {
          setLoiXong(cong.message ?? "Đơn thuốc chưa lưu xong.");
          return;
        }
        setDangGui(true);
        const daLuu = await cong.luuNot();
        setDangGui(false);
        if (!daLuu) {
          setLoiXong("Đơn thuốc vừa gõ CHƯA lưu được — xem dòng đỏ trong khối Đơn thuốc rồi bấm lại.");
          return;
        }
      }
    }
    setDangGui(true);
    try {
      const r = await fetch("/api/phieu-kham", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thao_tac: "xong-ke-don", visit_id: visitId, xong }),
      });
      const d = (await r.json().catch(() => null)) as { error?: unknown } | null;
      if (!r.ok) {
        setLoiXong(typeof d?.error === "string" && d.error ? d.error : "Không ghi được — thử lại.");
        return;
      }
      onDaDat();
    } catch {
      setLoiXong("Mất kết nối — chưa ghi được.");
    } finally {
      setDangGui(false);
    }
  };

  useEffect(() => {
    let bo = false;
    fetch(`/api/phieu-kham?visit_id=${visitId}&xem=dau-phieu`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: DauPhieu | null) => {
        if (bo) return;
        setDau(d);
        if (!d) setLoi("Không đọc được hồ sơ khách — tải lại trang.");
      })
      .catch(() => {
        if (!bo) setLoi("Mất kết nối — không đọc được hồ sơ khách.");
      });
    return () => {
      bo = true;
    };
  }, [visitId]);

  return (
    <div className="space-y-4">
      {dau ? (
        <>
          <TheKhach dau={dau} />
          <TheSinhHieu dau={dau} />
        </>
      ) : loi ? (
        <p role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : (
        <p className="text-body text-ink-muted">Đang tải…</p>
      )}
      <KhoiDonThuocBanTuVan
        visitId={visitId}
        clinicPatientId={clinicPatientId}
        choGhi={choGhi}
        moSan
        onTrangThai={baoCong}
        datChiDinh={datChiDinh}
        onDaDat={onDaDat}
      />
      {choGhi ? (
        <div className="sticky bottom-16 z-10 flex flex-wrap items-center justify-end gap-2 rounded-card border border-hairline bg-surface p-4 md:bottom-3">
          {loiXong ? (
            <p role="alert" className="mr-auto text-meta text-danger">
              {loiXong}
            </p>
          ) : null}
          {daXong ? (
            <>
              <Chip tone="success">Đã xong kê đơn thuốc</Chip>
              <Button type="button" variant="secondary" disabled={dangGui} onClick={() => void danhDau(false)}>
                Mở lại
              </Button>
            </>
          ) : (
            <Button type="button" size="lg" variant="primary" disabled={dangGui} onClick={() => void danhDau(true)}>
              {dangGui ? "Đang ghi…" : "Xong kê đơn thuốc"}
            </Button>
          )}
        </div>
      ) : null}
    </div>
  );
}
