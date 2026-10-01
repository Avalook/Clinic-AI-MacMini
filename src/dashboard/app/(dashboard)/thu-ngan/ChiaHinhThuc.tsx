"use client";

// CHIA LẦN THU THEO HÌNH THỨC (Tuyền 01/10/2026): "khách chuyển khoản 200k mà
// đưa tiền mặt 500k cũng ghi được. Bỏ nút QR, chuyển khoản với QR là một."
//
// Tick Tiền mặt / Chuyển khoản; tick cả hai thì gõ MỘT số (phần kia = tổng − số
// ấy, tự điền). Tiền mặt có ô "Khách đưa" → hiện "Trả lại khách X" (chỉ hiển
// thị — sổ ghi đúng số thu). Chuyển khoản có ô chụp / chọn ảnh màn hình chuyển
// khoản (không bắt buộc) — cha tải ảnh lên SAU khi máy chủ ghi lần thu.
//
// Màn chỉ cộng để HIỂN THỊ; máy chủ kiểm lại tổng (`phan_thu.ap_phan`) và
// Postgres ép lần cuối. Dùng ở mọi khối thu: HoaDonMot, NhomThu, NoKhac (quầy
// dịch vụ / thuốc) và BanLeThu (Nhà thuốc).

import { useEffect, useId, useState } from "react";

import ChipChon from "@/components/ui/ChipChon";
import { docSoTien, tien, type PhanGui } from "@/lib/hinh-thuc-thu";

export interface KetQuaChia {
  /** Các phần sẽ gửi (đã đúng tổng khi `hopLe`). */
  phan: PhanGui[];
  hopLe: boolean;
  /** Câu nhắc khi chưa hợp lệ (thiếu số, khách đưa ít hơn…). */
  nhac: string | null;
  /** Ảnh chuyển khoản đã chọn — cha tải lên khi có mã lần thu. */
  anh: File | null;
  /** Có phần chuyển khoản → lần thu chờ xác minh. */
  coChuyenKhoan: boolean;
}

const O_SO =
  "min-h-10 w-32 rounded-control border border-line bg-surface px-3 text-right text-sm tabular-nums text-ink sm:min-h-8";

export function tinhChia(
  tong: number,
  tm: boolean,
  ck: boolean,
  soCk: number | null,
  khachDua: number | null,
): Omit<KetQuaChia, "anh"> {
  if (!tm && !ck) {
    return { phan: [], hopLe: false, nhac: "Chọn hình thức thu.", coChuyenKhoan: false };
  }
  let phanTm = 0;
  let phanCk = 0;
  if (tm && ck) {
    if (soCk == null || soCk <= 0 || soCk >= tong) {
      return {
        phan: [],
        hopLe: false,
        nhac: `Gõ số chuyển khoản (lớn hơn 0, nhỏ hơn ${tien(tong)}).`,
        coChuyenKhoan: true,
      };
    }
    phanCk = soCk;
    phanTm = tong - soCk;
  } else if (tm) {
    phanTm = tong;
  } else {
    phanCk = tong;
  }
  if (tm && khachDua != null && khachDua > 0 && khachDua < phanTm) {
    return {
      phan: [],
      hopLe: false,
      nhac: `Khách đưa ${tien(khachDua)} — còn thiếu ${tien(phanTm - khachDua)} tiền mặt.`,
      coChuyenKhoan: ck,
    };
  }
  const phan: PhanGui[] = [];
  if (phanTm > 0) {
    phan.push({
      hinh_thuc: "CASH",
      so_tien: phanTm,
      ...(khachDua != null && khachDua > phanTm ? { khach_dua: khachDua } : {}),
    });
  }
  if (phanCk > 0) phan.push({ hinh_thuc: "TRANSFER", so_tien: phanCk });
  return { phan, hopLe: phan.length > 0, nhac: null, coChuyenKhoan: phanCk > 0 };
}

export default function ChiaHinhThuc({
  tong,
  onDoi,
}: {
  tong: number;
  onDoi: (kq: KetQuaChia) => void;
}) {
  const id = useId();
  const [tm, setTm] = useState(true);
  const [ck, setCk] = useState(false);
  const [soCkChu, setSoCkChu] = useState("");
  const [khachDuaChu, setKhachDuaChu] = useState("");
  const [anh, setAnh] = useState<File | null>(null);

  const soCk = docSoTien(soCkChu);
  const khachDua = docSoTien(khachDuaChu);
  const kq = tinhChia(tong, tm, ck, soCk, khachDua);
  const phanTm = kq.phan.find((p) => p.hinh_thuc === "CASH")?.so_tien ?? (tm && !ck ? tong : null);
  const traLai = tm && khachDua != null && phanTm != null && khachDua > phanTm ? khachDua - phanTm : null;

  const dauVet = JSON.stringify(kq) + (anh ? `${anh.name}:${anh.size}` : "");
  useEffect(() => {
    onDoi({ ...kq, anh: ck ? anh : null });
    // `dauVet` gói đủ mọi thứ cha cần — tránh gọi lại mỗi lần cha vẽ lại.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dauVet]);

  const tmCa = tm && ck;
  return (
    <div className="space-y-2" role="group" aria-label="Hình thức thu">
      <div className="flex flex-wrap items-center gap-2">
        <ChipChon chon={tm} onDoi={() => setTm((v) => !v)}>
          Tiền mặt
        </ChipChon>
        <ChipChon chon={ck} onDoi={() => setCk((v) => !v)}>
          Chuyển khoản
        </ChipChon>
        {tmCa ? (
          <span className="text-meta text-ink-muted">khách trả bằng cả hai</span>
        ) : null}
      </div>

      {tmCa ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <label className="flex items-center gap-2 text-meta text-ink-soft" htmlFor={`${id}-ck`}>
            Chuyển khoản
            <input
              id={`${id}-ck`}
              inputMode="numeric"
              value={soCkChu}
              onChange={(e) => setSoCkChu(e.target.value)}
              placeholder="vd 200000"
              className={O_SO}
            />
          </label>
          <label className="flex items-center gap-2 text-meta text-ink-soft" htmlFor={`${id}-tm`}>
            Tiền mặt
            <input
              id={`${id}-tm`}
              inputMode="numeric"
              value={soCk != null && soCk > 0 && soCk < tong ? (tong - soCk).toLocaleString("vi-VN") : ""}
              onChange={(e) => {
                const so = docSoTien(e.target.value);
                setSoCkChu(so != null && so < tong ? String(tong - so) : "");
              }}
              placeholder="tự tính"
              className={O_SO}
            />
          </label>
        </div>
      ) : null}

      {tm ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <label className="flex items-center gap-2 text-meta text-ink-soft" htmlFor={`${id}-dua`}>
            Khách đưa (tiền mặt)
            <input
              id={`${id}-dua`}
              inputMode="numeric"
              value={khachDuaChu}
              onChange={(e) => setKhachDuaChu(e.target.value)}
              placeholder="không bắt buộc"
              className={O_SO}
            />
          </label>
          {traLai != null ? (
            <span className="text-body font-semibold text-success">Trả lại khách {tien(traLai)}</span>
          ) : null}
        </div>
      ) : null}

      {ck ? (
        <label className="flex flex-wrap items-center gap-2 text-meta text-ink-soft">
          Ảnh chuyển khoản (không bắt buộc)
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => setAnh(e.target.files?.[0] ?? null)}
            className="max-w-full text-meta text-ink-soft file:mr-2 file:min-h-8 file:rounded-control file:border-0 file:bg-surface-muted file:px-3 file:text-meta file:font-medium file:text-ink"
          />
        </label>
      ) : null}

      {kq.nhac ? <p className="text-meta text-warning">{kq.nhac}</p> : null}
    </div>
  );
}
