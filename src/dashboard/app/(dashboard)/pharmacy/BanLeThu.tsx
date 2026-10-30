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
//
// 16/10/2026 (Tuyền bấm thử "bán theo đơn"): lời báo "Đã mở lượt bán theo đơn
// khám … — N thuốc đã thêm / không thêm được: …" GIỮ ở đầu khung (không phải
// toast) tới khi nhân viên thao tác tiếp hoặc bấm "Ẩn"; chip "Vượt số kê — đã
// mua X / kê Y" và nhắc lần khám quá 2 tháng hiện ngay cạnh giỏ (số liệu đến từ
// lịch sử đơn thuốc — máy chủ tính, ở đây chỉ vẽ); dòng đơn cũ chưa gắn thuốc kho
// có nút "Chọn thuốc kho" mở danh mục ở giỏ.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import Button from "@/components/ui/Button";
import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";
import { useNgheBang } from "../dung-nghe-bang";
import ChinhDonQuay, { type TheoDonDong } from "../thu-ngan/ChinhDonQuay";
import { nhanPhan } from "@/lib/hinh-thuc-thu";
import { taiAnhChuyenKhoan } from "../thu-ngan/AnhChuyenKhoan";
import type { KetQuaChia } from "../thu-ngan/ChiaHinhThuc";
import type { GiamGiaResult } from "../thu-ngan/GiamGia";
import NutHoanTac from "../thu-ngan/NutHoanTac";
import { NhomThu, type ChoXacMinh, type HoaDon } from "../thu-ngan/QuayThuNgan";
import { CHAM } from "./DongThuoc";
import LichSuDonThuoc, { type GoiLichSu } from "./LichSuDonThuoc";
import { anNoiDon, useNoiDon } from "./thong-bao-noi-don";

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
  // Gói lịch sử đơn thuốc (LichSuDonThuoc báo lên) → chip "Vượt số kê" ở giỏ.
  const [goiDon, setGoiDon] = useState<GoiLichSu | null>(null);
  // "Chọn thuốc kho" ở dòng đơn cũ → mở danh mục ở giỏ với tên thuốc đó.
  const [goiYThuoc, setGoiYThuoc] = useState<{ ten: string; lan: number } | null>(null);
  const noiDon = useNoiDon(visitId);

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
    anNoiDon();
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

  // Lời báo nối đơn — hiện cả lúc hoá đơn còn đang tải, để không lỡ.
  const baoNoi = noiDon ? (
    <div
      role="status"
      className="flex flex-wrap items-start gap-2 bg-brand-50 px-4 py-2 text-meta text-brand-700"
    >
      <p className="min-w-0 flex-1 whitespace-pre-line">{noiDon}</p>
      <Button type="button" className={CHAM} size="sm" variant="ghost" onClick={anNoiDon}>
        Ẩn
      </Button>
    </div>
  ) : null;

  if (!doc) {
    return loi ? (
      <p role="alert" className="text-meta text-danger">
        {loi}
      </p>
    ) : (
      <div className="space-y-2">
        {baoNoi}
        <p className="text-meta text-ink-muted">Đang tải hoá đơn thuốc…</p>
      </div>
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
  // Đơn cũ đang bán theo: số kê / đã mua theo từng thuốc kho, cho chip ở giỏ.
  const donNoi = goiDon?.don.find((d) => d.da_noi);
  const theoDon: Record<string, TheoDonDong> = {};
  for (const d of donNoi?.dong ?? []) {
    if (d.drug_catalog_id) theoDon[d.drug_catalog_id] = d;
  }
  return (
    <div className="overflow-hidden rounded-card border border-line">
      {baoNoi}
      {loi ? (
        <p role="alert" className="bg-danger-bg px-4 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {xong ? (
        <p className="whitespace-pre-line bg-success-bg px-4 py-2 text-meta text-success">{xong}</p>
      ) : null}
      {doc.clinic_patient_id ? (
        <LichSuDonThuoc
          visitId={visitId}
          clinicPatientId={doc.clinic_patient_id}
          choSua={choSua}
          lanTai={lanTai}
          onGoi={setGoiDon}
          onChonThuocKho={(ten) => setGoiYThuoc({ ten, lan: (goiYThuoc?.lan ?? 0) + 1 })}
          onDoi={async (cau, loiMoi) => {
            anNoiDon();
            setXong(cau);
            setLoi(loiMoi);
            setGoiYThuoc(null);
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
          theoDon={donNoi ? theoDon : undefined}
          nhacChung={donNoi ? goiDon?.nhac_chung : undefined}
          goiYThuoc={goiYThuoc}
          onDoi={async (cau, loiMoi) => {
            anNoiDon();
            setXong(cau);
            setLoi(loiMoi);
            await tai();
            router.refresh();
          }}
        />
      ) : null}
      <NhomThu
        quay="thuoc"
        visitId={doc.visit_id}
        tieu_de="Tiền thuốc (bán lẻ)"
        hd={doc.da_thu ? undefined : doc.hoa_don}
        daThu={doc.da_thu}
        cho={doc.cho_xac_minh ?? undefined}
        dangThu={dangThu}
        onThu={(hd: HoaDon, chia: KetQuaChia | null, giam?: GiamGiaResult) => {
          // Số xem trước do GiamGia tính; máy chủ tính lại và quyết số thật.
          const discount = giam?.params ?? undefined;
          const tongSauGiam = discount ? giam!.tongSauGiam : hd.tong;
          const mienPhi = tongSauGiam === 0 && !!discount;
          const pt = chia?.coChuyenKhoan ? "TRANSFER" : "CASH";
          void gui(
            {
              visitId,
              clinicPatientId: doc.clinic_patient_id,
              kind: "thuoc",
              quay: "thuoc",
              billRevision: hd.revision,
              // Luôn là tổng GỐC — máy chủ so với hoá đơn của nó rồi tự trừ giảm.
              amount: hd.tong,
              method: mienPhi ? "CASH" : pt,
              phan: mienPhi ? undefined : chia?.phan,
              ...(discount
                ? {
                    discount_type: discount.discount_type,
                    discount_value: discount.discount_value,
                    discount_reason: discount.discount_reason,
                  }
                : {}),
            },
            mienPhi
              ? "Đã ghi nhận miễn phí — lượt bán lẻ đã tự đóng. Giao thuốc ở các dòng dưới."
              : `Đã thu ${tien(tongSauGiam)} (${chia ? nhanPhan(chia.phan) : "Tiền mặt"}) — lượt bán lẻ đã tự đóng. Giao thuốc ở các dòng dưới.`,
            dinhDanhThaoTac(
              "thu",
              visitId,
              "thuoc",
              hd.revision,
              JSON.stringify(mienPhi ? null : chia?.phan),
              String(hd.tong),
              discount ? `${discount.discount_type}:${discount.discount_value}` : "",
            ),
            mienPhi ? null : (chia?.anh ?? null),
          );
        }}
        onXacMinh={(ma: string, soNhan: number) =>
          void gui(
            {
              action: "xac-minh",
              paymentCycleId: doc.cho_xac_minh?.payment_cycle_id,
              visitId,
              kind: "thuoc",
              quay: "thuoc",
              reference: ma,
              soTienThucNhan: soNhan,
            },
            "Đã xác minh — tiền thuốc đã thu, lượt bán lẻ đã tự đóng.",
          )
        }
        onDoi={(cau?: string) => {
          if (cau) {
            anNoiDon();
            setXong(cau);
          }
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
