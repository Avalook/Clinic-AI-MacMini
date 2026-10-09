"use client";

// Lượt BÁN LẺ ở Nhà thuốc: kê + thu tiền thuốc ngay tại quầy (V8, 30/09/2026).
//
// Không có luật mới ở đây — ghép lại đúng hai khối đã có của quầy thu thuốc:
//   · `ChinhDonQuay` — "Lấy thêm thuốc / vật tư / TPCN" (dòng QUAY,
//     `quay_thuoc_service.luu_dong_them`);
//   · `NhomThu` — thu tiền thuốc (`POST /api/payment`, kind "thuoc"), số tiền
//     và dấu hoá đơn do máy chủ tính (`GET /api/pharmacy/ban-le?id=`).
// Thu xong máy chủ tự đóng lượt; giao thuốc / chọn lô ở các dòng bên dưới như
// mọi lượt khác.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";
import { useNgheBang } from "../dung-nghe-bang";
import ChinhDonQuay from "../thu-ngan/ChinhDonQuay";
import { nhanPhan } from "@/lib/hinh-thuc-thu";
import { taiAnhChuyenKhoan } from "../thu-ngan/AnhChuyenKhoan";
import type { KetQuaChia } from "../thu-ngan/ChiaHinhThuc";
import NutHoanTac from "../thu-ngan/NutHoanTac";
import { NhomThu, type ChoXacMinh, type HoaDon } from "../thu-ngan/QuayThuNgan";
import LichSuDonThuoc from "./LichSuDonThuoc";

interface DocBanLe {
  visit_id: string;
  clinic_patient_id: string;
  ten_khach: string | null;
  da_dong: boolean;
  da_thu: boolean;
  /** Lần thu đã thu — nút "Hoàn tác lần thu" (01/10/2026). */
  lan_da_thu?: string | null;
  cho_xac_minh: ChoXacMinh | null;
  hoa_don: HoaDon;
  duoc_thu: boolean;
}

const tien = (n: number) => n.toLocaleString("vi-VN") + "đ";

export default function BanLeThu({ visitId }: { visitId: string }) {
  const router = useRouter();
  const [doc, setDoc] = useState<DocBanLe | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dangThu, setDangThu] = useState(false);
  // Nối đơn thêm dòng ở máy chủ → nạp lại khối "Lấy thêm thuốc" (nó tự giữ dữ liệu).
  const [lanNoi, setLanNoi] = useState(0);
  // Mỗi lần nạp lại lượt → lịch sử đơn (đã mua / đang bán / đã nối) nạp lại theo.
  const [lanTai, setLanTai] = useState(0);

  const tai = useCallback(async () => {
    try {
      const r = await fetch(`/api/pharmacy/ban-le?${new URLSearchParams({ id: visitId })}`, {
        cache: "no-store",
      });
      const d = (await r.json().catch(() => null)) as
        | (DocBanLe & { message?: string; error?: string })
        | null;
      if (!r.ok || !d) {
        setLoi(d?.message ?? d?.error ?? "Không đọc được hoá đơn thuốc.");
        return;
      }
      setDoc(d);
      setLanTai((n) => n + 1);
    } catch {
      setLoi("Mất kết nối tới máy chủ.");
    }
  }, [visitId]);

  // Người khác thu / sửa đơn / nối – gỡ đơn gốc → hoá đơn và đơn ở đây tự cập nhật.
  useNgheBang(["payment_cycle", "prescription", "visit"], () => void tai());

  useEffect(() => {
    let bo = false;
    fetch(`/api/pharmacy/ban-le?${new URLSearchParams({ id: visitId })}`, { cache: "no-store" })
      .then(async (r) => ({ ok: r.ok, d: (await r.json().catch(() => null)) as DocBanLe | null }))
      .then(({ ok, d }) => {
        if (bo) return;
        if (ok && d) setDoc(d);
        else setLoi("Không đọc được hoá đơn thuốc.");
      })
      .catch(() => {
        if (!bo) setLoi("Mất kết nối tới máy chủ.");
      });
    return () => {
      bo = true;
    };
  }, [visitId]);

  const gui = async (
    than: Record<string, unknown>,
    cau: string,
    thaoTac?: string,
    anh?: File | null,
  ) => {
    setDangThu(true);
    setLoi(null);
    setXong(null);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (thaoTac) headers["Idempotency-Key"] = khoaThaoTac(thaoTac);
      const r = await fetch("/api/payment", {
        method: "POST",
        headers,
        body: JSON.stringify(than),
      });
      if (r.ok && thaoTac) xongThaoTac(thaoTac);
      const d = (await r.json().catch(() => null)) as
        | { message?: string; error?: string; status?: string; payment_cycle_id?: string | null }
        | null;
      if (r.ok && anh && d?.payment_cycle_id) {
        const loiAnh = await taiAnhChuyenKhoan(d.payment_cycle_id, anh);
        if (loiAnh) setLoi(`Đã ghi lần thu, nhưng ảnh chuyển khoản chưa lưu: ${loiAnh}`);
      }
      if (!r.ok) setLoi(d?.message ?? d?.error ?? "Không ghi được.");
      else
        setXong(
          d?.status === "PENDING_VERIFICATION"
            ? "Đã ghi CHỜ XÁC MINH — chưa tính là đã thu. Bấm “Đã nhận tiền” khi tiền về."
            : cau,
        );
    } catch {
      setLoi("Mất kết nối — CHƯA ghi được.");
    } finally {
      setDangThu(false);
    }
    await tai();
    router.refresh();
  };

  if (!doc) {
    return loi ? (
      <p role="alert" className="text-meta text-danger">
        {loi}
      </p>
    ) : (
      <p className="text-meta text-ink-muted">Đang tải hoá đơn thuốc…</p>
    );
  }

  if (!doc.duoc_thu) {
    return (
      <p className="rounded-control bg-surface-muted px-3 py-2 text-meta text-ink-soft">
        Lượt bán lẻ — tài khoản của bạn chưa có lego “Thu tiền thuốc” để kê thêm và thu tại đây.
      </p>
    );
  }

  const choSua = !doc.da_thu && !doc.cho_xac_minh;
  return (
    <div className="overflow-hidden rounded-card border border-line">
      {loi ? (
        <p role="alert" className="bg-danger-bg px-4 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {xong ? <p className="bg-success-bg px-4 py-2 text-meta text-success">{xong}</p> : null}
      {doc.clinic_patient_id ? (
        <LichSuDonThuoc
          visitId={visitId}
          clinicPatientId={doc.clinic_patient_id}
          choSua={choSua}
          lanTai={lanTai}
          onDoi={async (cau, loiMoi) => {
            setXong(cau);
            setLoi(loiMoi);
            setLanNoi((n) => n + 1);
            await tai();
            router.refresh();
          }}
        />
      ) : null}
      {choSua ? (
        <ChinhDonQuay
          key={lanNoi}
          visitId={visitId}
          onDoi={async (cau, loiMoi) => {
            setXong(cau);
            setLoi(loiMoi);
            await tai();
            router.refresh();
          }}
        />
      ) : null}
      <NhomThu
        quay="thuoc"
        tieu_de="Tiền thuốc (bán lẻ)"
        hd={doc.da_thu ? undefined : doc.hoa_don}
        daThu={doc.da_thu}
        cho={doc.cho_xac_minh ?? undefined}
        dangThu={dangThu}
        onThu={(hd: HoaDon, chia: KetQuaChia) =>
          void gui(
            {
              visitId,
              clinicPatientId: doc.clinic_patient_id,
              kind: "thuoc",
              quay: "thuoc",
              billRevision: hd.revision,
              amount: hd.tong,
              method: chia.coChuyenKhoan ? "TRANSFER" : "CASH",
              phan: chia.phan,
            },
            `Đã thu ${tien(hd.tong)} (${nhanPhan(chia.phan)}) — lượt bán lẻ đã tự đóng. Giao thuốc ở các dòng dưới.`,
            dinhDanhThaoTac("thu", visitId, "thuoc", hd.revision, JSON.stringify(chia.phan), String(hd.tong)),
            chia.anh,
          )
        }
        onXacMinh={(ma: string) =>
          void gui(
            {
              action: "xac-minh",
              paymentCycleId: doc.cho_xac_minh?.payment_cycle_id,
              visitId,
              kind: "thuoc",
              quay: "thuoc",
              reference: ma,
            },
            "Đã xác minh — tiền thuốc đã thu, lượt bán lẻ đã tự đóng.",
          )
        }
        onDoi={(cau?: string) => {
          if (cau) setXong(cau);
          void tai();
          router.refresh();
        }}
      />
      {doc.lan_da_thu ? (
        <div className="border-t border-line px-4 py-3">
          <NutHoanTac
            cycleId={doc.lan_da_thu}
            quay="thuoc"
            onXong={(cau) => {
              setXong(`${cau} Lượt bán lẻ mở lại để thu lại.`);
              void tai();
              router.refresh();
            }}
          />
        </div>
      ) : null}
    </div>
  );
}
