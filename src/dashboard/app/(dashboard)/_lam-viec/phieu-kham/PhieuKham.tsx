"use client";

// PHIẾU KHÁM — một màn vẽ cho cả bảy phiếu (NT · HMVS · PK · SK · NK · Thủ
// thuật · Sàn chậu chuyên sâu).
//
// Không có "màn Nội tiết", "màn Hiếm muộn" riêng. Khung (mục → ô) trích bằng
// máy từ tài liệu phiếu đã chốt; màn này vẽ đúng khung ấy. Thêm ô là sửa DỮ
// LIỆU khung, không sửa tệp này.
//
// ĐIỀU KHIỂN TỪ NGOÀI. Clinical shell đưa vào: khung đúng phiên bản, dữ liệu
// đang có, CHẾ ĐỘ (editable / finalized_locked / amendment_mode), và hàm
// `onLuu`. Màn này KHÔNG tự lưu xuống đâu, KHÔNG tự quyết hồ sơ đã chốt hay
// chưa, và KHÔNG có nút chốt — chốt là việc của shell. Nó chỉ tự lưu theo nhịp
// gõ và gửi gói `{khoá: {gia_tri, nguon}}` giữ đúng nguồn của từng ô.
//
// BA LOẠI MỤC
//   · mục có ô (B, D, G…)    gõ tại đây.
//   · mục mang sang          hành chính, sinh hiệu, ghi chú tư vấn — chỉ đọc.
//   · mục liên kết (C, E, F) dữ liệu thật ở chỗ khác (chỉ định, đơn thuốc);
//                            shell cắm màn thật vào qua props.

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import Chip from "@/components/ui/Chip";
import {
  dungGoiLuu,
  ghiDuoc,
  giaTriBanDau,
  gomNhom,
  type CheDoPhieu,
  type ChiDinhVaKetQua,
  type DauPhieu,
  type DinhNghiaPhieu,
  type DongThuoc,
  type GiaTriO,
  type MauKetQuaNgan,
  type MauThuoc,
  type MucPhieu,
  type ONhap,
  type ThuThuatNguon,
} from "@/lib/phieu-kham";
import ChiDinhThuThuat from "./ChiDinhThuThuat";
import DonThuocPhieu from "./DonThuocPhieu";
import KetQuaChiDinh from "./KetQuaChiDinh";
import { KhoiHanhChinh, KhoiTuVan } from "./KhoiDauPhieu";
import { NhomOPhieu } from "./ONhapPhieu";

/** Khoảng lặng trước khi tự lưu — gõ liên tục thì không bắn từng phím. */
const CHO_TU_LUU_MS = 1500;

export interface CanhBaoO {
  ma: string;
  ten: string;
  loi: string;
}

export type KetQuaLuu = { ok: true; canh_bao?: CanhBaoO[] } | { ok: false; loi: string };

export interface ThamChieu {
  thu_thuat: ThuThuatNguon[];
  mau_thuoc: MauThuoc[];
}

const NHAN_CHE_DO: Record<CheDoPhieu, { ten: string; tone: "neutral" | "warning" } | null> = {
  editable: null,
  finalized_locked: { ten: "Chỉ xem", tone: "neutral" },
  amendment_mode: { ten: "Đang đính chính", tone: "warning" },
};

function gioVn(d: Date): string {
  return d.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function PhieuKham({
  dinhNghia,
  duLieu,
  cheDo,
  dauPhieu,
  ketQuaChiDinh,
  onLuu,
  donThuoc,
  thuThuat,
  oChiDinhCls,
  oThuThuat,
  thamChieuNgoai,
  ketQua,
}: {
  /** Khung của ĐÚNG phiên bản phiếu đang ghim. */
  dinhNghia: DinhNghiaPhieu;
  /** Dữ liệu đang có — shell đọc từ chỗ lưu của nó. */
  duLieu: Record<string, ONhap>;
  /** Do clinical shell quyết. Lạ = chỉ đọc. */
  cheDo: CheDoPhieu;
  dauPhieu: DauPhieu | null;
  ketQuaChiDinh: ChiDinhVaKetQua[];
  /** Shell ghi xuống chỗ lưu (sau khi qua cổng `kiem_luu` ở máy chủ). */
  onLuu: (goi: Record<string, ONhap>) => Promise<KetQuaLuu>;
  /** Mục E: đơn thuốc thật của lượt. */
  donThuoc?: { dong: DongThuoc[]; onDoi?: (d: DongThuoc[]) => void };
  /** Mục F: thủ thuật đang có chỉ định + lệnh tạo chỉ định. */
  thuThuat?: { daChon: string[]; onChon?: (t: ThuThuatNguon, chon: boolean) => void };
  /** Mục C: màn ra chỉ định CLS thật. Kết quả theo chỉ định luôn hiện dưới nó. */
  oChiDinhCls?: ReactNode;
  /** Mục F: màn chỉ định thủ thuật thật (thay ô chọn của gói). */
  oThuThuat?: ReactNode;
  /** Shell đã nạp tham chiếu (mã + giá thật) thì khỏi nạp lại. */
  thamChieuNgoai?: ThamChieu | null;
  /** Bác sĩ điền kết quả ngay trong mục C. */
  ketQua?: {
    mauDuPhong: MauKetQuaNgan[];
    goiYMau: Record<string, string>;
    choDien: boolean;
    onDoi: () => void;
  };
}) {
  const [gia, setGia] = useState<Record<string, GiaTriO>>(() => giaTriBanDau(duLieu));
  const [thamChieu, setThamChieu] = useState<ThamChieu | null>(null);
  const [luuLuc, setLuuLuc] = useState<Date | null>(null);
  const [canhBao, setCanhBao] = useState<CanhBaoO[]>([]);
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const hen = useRef<ReturnType<typeof setTimeout> | null>(null);

  const ghi = ghiDuoc(cheDo);

  // Shell nạp lại dữ liệu (đổi lượt, tải lại) → màn theo bản mới. Chỉnh ngay
  // lúc render thay vì trong effect: không vẽ một nhịp bằng dữ liệu cũ.
  const [duLieuDaNhan, setDuLieuDaNhan] = useState(duLieu);
  if (duLieuDaNhan !== duLieu) {
    setDuLieuDaNhan(duLieu);
    setGia(giaTriBanDau(duLieu));
  }

  useEffect(() => {
    if (thamChieuNgoai !== undefined) return;
    let huy = false;
    void fetch("/api/phieu-kham?xem=tham-chieu")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!huy && d) setThamChieu(d as ThamChieu);
      })
      .catch(() => undefined);
    return () => {
      huy = true;
    };
  }, [thamChieuNgoai]);
  const tc = thamChieuNgoai ?? thamChieu;

  // Gỡ hẹn khi rời màn: một lần tự lưu bắn sau khi màn đã đóng là một lần ghi
  // mà không ai nhìn thấy kết quả.
  useEffect(
    () => () => {
      if (hen.current) clearTimeout(hen.current);
    },
    [],
  );

  const luu = useCallback(
    async (moi: Record<string, GiaTriO>) => {
      setDangLuu(true);
      const kq = await onLuu(dungGoiLuu(moi, duLieu)).catch(
        (): KetQuaLuu => ({ ok: false, loi: "Mất kết nối — nội dung CHƯA được lưu." }),
      );
      setDangLuu(false);
      if (!kq.ok) {
        setLoi(kq.loi);
        return;
      }
      setLoi(null);
      setLuuLuc(new Date());
      setCanhBao(kq.canh_bao ?? []);
    },
    [onLuu, duLieu],
  );

  const doi = (ma: string, v: GiaTriO) => {
    if (!ghi) return;
    const moi = { ...gia, [ma]: v };
    setGia(moi);
    if (hen.current) clearTimeout(hen.current);
    hen.current = setTimeout(() => void luu(moi), CHO_TU_LUU_MS);
  };

  const nhomTheoMuc = useMemo(
    () =>
      Object.fromEntries(dinhNghia.khung.map((m) => [m.ma, gomNhom(m.block)] as const)),
    [dinhNghia.khung],
  );

  const veO = (m: MucPhieu) =>
    (nhomTheoMuc[m.ma] ?? []).map((n, i) => (
      <NhomOPhieu key={`${m.ma}-${i}`} nhom={n} gia={gia} onDoi={doi} chiDoc={!ghi} />
    ));

  // `editable` CỐ Ý không có nhãn (null) — `??` sẽ coi null là "thiếu" và vẽ
  // nhầm "Chế độ lạ" lên một phiếu đang ghi được (bấm thật 23/09). Hỏi có khoá.
  const nhanCheDo =
    cheDo in NHAN_CHE_DO ? NHAN_CHE_DO[cheDo] : { ten: "Chế độ lạ — chỉ đọc", tone: "neutral" as const };

  return (
    <section className="space-y-4 rounded-card border border-hairline bg-surface p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-title text-ink">{dinhNghia.ten}</h2>
        <span className="text-meta text-ink-faint">
          {dinhNghia.form_id} · bản {dinhNghia.version}
        </span>
        {nhanCheDo ? <Chip tone={nhanCheDo.tone}>{nhanCheDo.ten}</Chip> : null}
        <span className="ml-auto text-meta text-ink-muted">
          {dangLuu ? "Đang lưu…" : luuLuc ? `Đã lưu ${gioVn(luuLuc)}` : "Tự lưu khi gõ"}
        </span>
      </header>

      {loi ? <p className="text-body text-danger">{loi}</p> : null}
      {canhBao.length > 0 ? (
        <ul className="space-y-1 rounded-control bg-warning-bg p-3 text-body text-warning">
          {canhBao.map((c) => (
            <li key={c.ma}>
              {c.ten}: {c.loi}
            </li>
          ))}
        </ul>
      ) : null}

      {dinhNghia.khung.map((m) => (
        <div key={m.ma} className="space-y-3">
          {m.ma !== "HANH_CHINH" ? (
            <h3 className="border-b border-hairline pb-1 text-emph font-semibold text-ink">
              {m.ten}
            </h3>
          ) : null}

          {m.ma === "HANH_CHINH" && dauPhieu ? (
            <KhoiHanhChinh dau={dauPhieu} truong={m.lien_ket?.truong ?? []} />
          ) : null}
          {m.ma === "A" && dauPhieu ? <KhoiTuVan dau={dauPhieu} /> : null}

          {m.lien_ket?.loai === "chi_dinh_cls" ? (
            <>
              {oChiDinhCls}
              <KetQuaChiDinh ds={ketQuaChiDinh} {...(ketQua ?? {})} />
            </>
          ) : null}

          {m.lien_ket?.loai === "don_thuoc" ? (
            <DonThuocPhieu
              dong={donThuoc?.dong ?? []}
              mauThuoc={tc?.mau_thuoc ?? []}
              onDoi={ghi ? donThuoc?.onDoi : undefined}
            />
          ) : null}

          {m.lien_ket?.loai === "chi_dinh_thu_thuat" && oThuThuat ? oThuThuat : null}
          {m.lien_ket?.loai === "chi_dinh_thu_thuat" && !oThuThuat ? (
            <ChiDinhThuThuat
              ds={tc?.thu_thuat ?? []}
              daChon={thuThuat?.daChon ?? []}
              onChon={ghi ? thuThuat?.onChon : undefined}
            />
          ) : null}

          {veO(m)}
        </div>
      ))}
    </section>
  );
}
