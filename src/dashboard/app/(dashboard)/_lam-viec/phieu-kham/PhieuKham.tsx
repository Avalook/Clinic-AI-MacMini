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
// TỰ LƯU CHẮC CHẮN (đợt 3, 27/09/2026 — góp ý B9): hàng đợi chung
// `lib/use-tu-luu` — tuần tự, lưu nốt khi rời màn / đóng tab, lỗi mạng tự thử
// lại, trạng thái "Đang lưu… / Đã lưu hh:mm / Chưa lưu — [Lưu ngay] / Lưu lỗi —
// [Thử lại]" hiện ở MỌI cỡ màn (dòng dính cùng thanh khối). Ô máy chủ báo lỗi
// (số/ngày không đọc được → lưu RỖNG) hiện lỗi NGAY DƯỚI ô, không ở đầu cột.
//
// BA LOẠI MỤC
//   · mục có ô (B, D, G…)    gõ tại đây.
//   · mục mang sang          hành chính, sinh hiệu, ghi chú tư vấn — chỉ đọc.
//   · mục liên kết (C, E, F) dữ liệu thật ở chỗ khác (chỉ định, đơn thuốc);
//                            shell cắm màn thật vào qua props.

import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { buttonClass } from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import TrangThaiLuu from "@/components/ui/TrangThaiLuu";
import { gopTrangThai, LOI_MAT_KET_NOI, type TrangThaiLuu as TTLuu } from "@/lib/tu-luu";
import { useTuLuu } from "@/lib/use-tu-luu";
import NganGap from "@/components/ui/NganGap";
import {
  coGiaTriO,
  dungGoiLuu,
  gopCanhBao,
  ghiDuoc,
  giaTriBanDau,
  gomNhom,
  KHOI_PHIEU,
  soODaDien,
  type CheDoPhieu,
  type ChiDinhVaKetQua,
  type KetQuaMotChiDinh,
  type DauPhieu,
  type DinhNghiaPhieu,
  type DongThuoc,
  type GiaTriO,
  type MauKetQuaNgan,
  type MauThuoc,
  type MucPhieu,
  type ONhap,
  type ThuThuatNguon,
  type CanhBaoO,
} from "@/lib/phieu-kham";
import ChiDinhThuThuat from "./ChiDinhThuThuat";
import DonThuocPhieu from "./DonThuocPhieu";
import KetQuaChiDinh, { TepChuaGan } from "./KetQuaChiDinh";
import { KhoiTuVan } from "./KhoiDauPhieu";
import { TheKhach, TheSinhHieu } from "./TheKhach";
import TieuDeKhoi from "./TieuDeKhoi";
import { idOPhieu, NhomOPhieu } from "./ONhapPhieu";

/** Khoảng lặng trước khi tự lưu — gõ liên tục thì không bắn từng phím. */
const CHO_TU_LUU_MS = 1500;

export type { CanhBaoO } from "@/lib/phieu-kham";

/** Kết quả một lần lưu phiếu. `da_gui` = mã các ô vừa gửi (cảnh báo của ô
 *  khác giữ nguyên). `thuLai` = lỗi mạng/máy chủ tạm, hàng đợi tự thử lại. */
export type KetQuaLuu =
  | { ok: true; canh_bao?: unknown; da_gui?: string[] }
  | { ok: false; loi: string; thuLai: boolean };

export interface ThamChieu {
  thu_thuat: ThuThuatNguon[];
  mau_thuoc: MauThuoc[];
}

const NHAN_CHE_DO: Record<CheDoPhieu, { ten: string; tone: "neutral" | "warning" } | null> = {
  editable: null,
  finalized_locked: { ten: "Chỉ xem", tone: "neutral" },
  amendment_mode: { ten: "Đang đính chính", tone: "warning" },
};

/** Ba khối — định nghĩa ở lib/phieu-kham (dùng chung với bản in). */
const KHOI = KHOI_PHIEU;

export default function PhieuKham({
  dinhNghia,
  duLieu,
  cheDo,
  dauPhieu,
  ketQuaChiDinh,
  tepChuaGan = [],
  onLuu,
  donThuoc,
  thuThuat,
  oChiDinhCls,
  oThuThuat,
  thamChieuNgoai,
  ketQua,
  nutIn,
  chiMuc,
  dauTrang,
  chanRay,
  maThuThuat,
  onTomTat,
  tuLuuKem,
  onTrangThaiLuu,
  baoLoiDon,
  oDichVuKham,
}: {
  /** Khung của ĐÚNG phiên bản phiếu đang ghim. */
  dinhNghia: DinhNghiaPhieu;
  /** Dữ liệu đang có — shell đọc từ chỗ lưu của nó. */
  duLieu: Record<string, ONhap>;
  /** Do clinical shell quyết. Lạ = chỉ đọc. */
  cheDo: CheDoPhieu;
  dauPhieu: DauPhieu | null;
  ketQuaChiDinh: ChiDinhVaKetQua[];
  /** Tệp của lượt CHƯA gắn chỉ định (tải ở màn Khách hàng) — hiện riêng ở khối
   *  2, không ghép vào chỉ định nào (27/09/2026, đợt 3). */
  tepChuaGan?: KetQuaMotChiDinh[];
  /** Shell ghi xuống chỗ lưu (sau khi qua cổng `kiem_luu` ở máy chủ).
   *  `keepalive` = trang đang đóng. */
  onLuu: (goi: Record<string, ONhap>, keepalive: boolean) => Promise<KetQuaLuu>;
  /** Hàng đợi tự lưu KHÁC của cùng màn (đơn thuốc mục E) — gộp vào một dòng
   *  trạng thái, [Lưu ngay] lưu cả hai. */
  tuLuuKem?: { trangThai: TTLuu; luuNgay: () => Promise<boolean> };
  /** Báo trạng thái tự lưu (đã gộp) + hàm lưu nốt — shell dựng cổng Hoàn tất. */
  onTrangThaiLuu?: (tt: TTLuu, luuNgay: () => Promise<boolean>) => void;
  /** Ô tick DỊCH VỤ KHÁM theo mã KiotViet (28/09/2026) — vẽ ngay dưới mục
   *  đầu của khối 1 ("Bác sĩ tư vấn ghi"); shell truyền vào. */
  oDichVuKham?: ReactNode;
  /** Lỗi lưu đơn thuốc (kèm ô lý do) — vẽ NGAY trong mục E (góp ý B8). */
  baoLoiDon?: ReactNode;
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
    clinicPatientId?: string;
    onDoi: () => void;
    nhanGiay?: Record<string, string>;
    /** Ô "bắt buộc" ở thẻ từng chỉ định chưa thu (27/09: chuyển từ danh mục). */
    onDoiBatBuoc?: (
      orderId: string,
      batBuoc: boolean,
    ) => Promise<{ ok: true } | { ok: false; loi: string }>;
  };
  /** Mã dịch vụ thủ thuật — kết quả của chúng hiện ở khối 3 (bản mẫu). */
  maThuThuat?: ReadonlySet<string>;
  /** Nút mở bản in của phiếu — shell biết lượt nào nên shell dựng. */
  nutIn?: ReactNode;
  /** Chỉ vẽ các mục này (vd `["B"]` ở bàn tư vấn). Bỏ trống = cả phiếu. */
  chiMuc?: string[];
  /** Đầu cột trái — dải "Hành trình hôm nay" (bản mẫu: timeline đứng trên thẻ khách). */
  dauTrang?: ReactNode;
  /** Chân cột phải dưới "In phiếu khám" — nút Hoàn tất của bàn khám (Tuyền 27/09). */
  chanRay?: ReactNode;
  /** Chế độ `chiMuc` (bàn tư vấn): báo số ô đã điền của các mục đang vẽ + tên
   *  phiếu — chip "N ô đã điền" của công tắc Thông tin cơ bản (bản mẫu). */
  onTomTat?: (soDien: number, tenPhieu: string) => void;
}) {
  const [gia, setGia] = useState<Record<string, GiaTriO>>(() => giaTriBanDau(duLieu));
  const [khoi, setKhoi] = useState<1 | 2 | 3>(1);
  const [thamChieu, setThamChieu] = useState<ThamChieu | null>(null);
  const [canhBao, setCanhBao] = useState<CanhBaoO[]>([]);

  const ghi = ghiDuoc(cheDo);

  // Tự lưu đọc BẢN MỚI NHẤT lúc gửi (hàng đợi tuần tự — lần sau thấy kết quả
  // lần trước). `doi` cập nhật ref ngay trong sự kiện gõ.
  const giaRef = useRef(gia);
  const duLieuRef = useRef(duLieu);
  useEffect(() => {
    giaRef.current = gia;
    duLieuRef.current = duLieu;
  }, [gia, duLieu]);

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

  // Trước đợt 3: hẹn lưu bị XOÁ lúc rời màn mà không lưu nốt — đổi khách trong
  // 1,5 giây sau phím cuối là mất chữ. Nay `useTuLuu` lưu nốt khi rời màn.
  const gui = useCallback(
    async (keepalive: boolean) => {
      const kq = await onLuu(dungGoiLuu(giaRef.current, duLieuRef.current), keepalive).catch(
        (): KetQuaLuu => ({ ok: false, loi: LOI_MAT_KET_NOI, thuLai: true }),
      );
      if (!kq.ok) return kq;
      setCanhBao((cu) => gopCanhBao(cu, kq.da_gui ?? [], kq.canh_bao));
      return { ok: true } as const;
    },
    [onLuu],
  );
  const tuLuu = useTuLuu({ gui, choMs: CHO_TU_LUU_MS, tat: !ghi });
  const ttPhieu = tuLuu.trangThai;
  const ttKem = tuLuuKem?.trangThai;
  const ttLuu = useMemo(() => (ttKem ? gopTrangThai(ttPhieu, ttKem) : ttPhieu), [ttPhieu, ttKem]);
  const luuPhieu = tuLuu.luuNgay;
  const luuKem = tuLuuKem?.luuNgay;
  const luuCaHai = useCallback(async () => {
    const [a, b] = await Promise.all([luuPhieu(), luuKem ? luuKem() : Promise.resolve(true)]);
    return a && b;
  }, [luuPhieu, luuKem]);
  useEffect(() => {
    onTrangThaiLuu?.(ttLuu, luuCaHai);
  }, [ttLuu, luuCaHai, onTrangThaiLuu]);

  const doi = (ma: string, v: GiaTriO) => {
    if (!ghi) return;
    const moi = { ...giaRef.current, [ma]: v };
    giaRef.current = moi;
    setGia(moi);
    tuLuu.danhDau();
  };

  const loiO = useMemo(
    () => Object.fromEntries(canhBao.map((c) => [c.ma, c.loi] as const)),
    [canhBao],
  );

  // [link] tới một ô: mở đúng khối chứa ô rồi cuộn + đặt con trỏ vào ô.
  const denO = (ma: string) => {
    const muc = dinhNghia.khung.find((m) => m.block.some((o) => o.ma === ma));
    const k = KHOI.find((x) => muc && x.muc.includes(muc.ma));
    if (k) setKhoi(k.so);
    setTimeout(() => {
      const el = document.getElementById(idOPhieu(ma));
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
      el?.querySelector<HTMLElement>("input, textarea, button")?.focus({ preventScroll: true });
    }, 0);
  };

  const nhomTheoMuc = useMemo(
    () =>
      Object.fromEntries(dinhNghia.khung.map((m) => [m.ma, gomNhom(m.block)] as const)),
    [dinhNghia.khung],
  );

  const veO = (m: MucPhieu) =>
    (nhomTheoMuc[m.ma] ?? []).map((n, i) => (
      <NhomOPhieu key={`${m.ma}-${i}`} nhom={n} gia={gia} onDoi={doi} chiDoc={!ghi} loiO={loiO} />
    ));

  // `editable` CỐ Ý không có nhãn (null) — `??` sẽ coi null là "thiếu" và vẽ
  // nhầm "Chế độ lạ" lên một phiếu đang ghi được (bấm thật 23/09). Hỏi có khoá.
  const nhanCheDo =
    cheDo in NHAN_CHE_DO ? NHAN_CHE_DO[cheDo] : { ten: "Chế độ lạ — chỉ đọc", tone: "neutral" as const };

  // Tóm tắt trên nút khối — như bản mẫu: số ô đã điền · chỉ định & kết quả ·
  // thuốc & hẹn.
  const oTheoMuc = (ds: string[]) =>
    dinhNghia.khung.filter((m) => ds.includes(m.ma)).flatMap((m) => m.block.map((o) => o.ma));
  const soDien = oTheoMuc(["A", "B"]).filter((ma) => coGiaTriO(gia[ma])).length;
  const khoaChiMuc = chiMuc?.join(",") ?? "";
  const soDienChiMuc = khoaChiMuc
    ? oTheoMuc(khoaChiMuc.split(",")).filter((ma) => coGiaTriO(gia[ma])).length
    : 0;
  useEffect(() => {
    if (khoaChiMuc) onTomTat?.(soDienChiMuc, dinhNghia.ten.replace(/^Phiếu\s+/i, ""));
  }, [khoaChiMuc, soDienChiMuc, dinhNghia.ten, onTomTat]);
  const laTT = (c: ChiDinhVaKetQua) => Boolean(maThuThuat?.has(c.service_code));
  const ketQuaCls = ketQuaChiDinh.filter((c) => !laTT(c));
  const ketQuaTT = ketQuaChiDinh.filter(laTT);
  const coKq = ketQuaCls.filter((c) => c.ket_qua_trang_thai === "CO_KET_QUA").length;
  // Chip "N mới" trên nút khối 2: kết quả đã về mà chưa ai xem.
  const coKqMoi = ketQuaCls.filter(
    (c) => c.ket_qua_trang_thai === "CO_KET_QUA" && !c.da_xem_luc,
  ).length;
  const soThuoc = (donThuoc?.dong ?? []).filter((d) => d.ten_thuoc.trim()).length;
  const coHen = oTheoMuc(["G"]).some((ma) => /follow_date|ngay/.test(ma) && coGiaTriO(gia[ma]));
  const tomTat: Record<1 | 2 | 3, string> = {
    1: `${soDien} ô đã điền`,
    2: ketQuaCls.length ? `${ketQuaCls.length} chỉ định · ${coKq} có KQ` : "chưa chỉ định",
    3:
      [soThuoc ? `${soThuoc} thuốc` : "", ketQuaTT.length ? `${ketQuaTT.length} dịch vụ` : "", coHen ? "có hẹn" : ""]
        .filter(Boolean)
        .join(" · ") || "chưa có gì",
  };

  const dongTrangThai = (
    <TrangThaiLuu
      tt={ttLuu}
      onLuuNgay={() => void luuCaHai()}
      chuaGo={ghi ? "Tự lưu khi gõ" : "Chỉ xem"}
    />
  );
  // Tóm tắt NGẮN các ô máy chủ vừa để trống — mỗi tên là link tới đúng ô (câu
  // lỗi đầy đủ nằm dưới chính ô).
  const tomTatLoiO =
    canhBao.length > 0 ? (
      <p role="alert" className="text-meta text-danger">
        {canhBao.length} ô chưa lưu được giá trị:{" "}
        {canhBao.map((c, i) => (
          <Fragment key={c.ma}>
            {i > 0 ? ", " : ""}
            <button type="button" className="font-semibold underline" onClick={() => denO(c.ma)}>
              {c.ten}
            </button>
          </Fragment>
        ))}
      </p>
    ) : null;

  // THẺ CON của từng mục — tên + câu phụ Y HỆT bản giao diện mẫu (`manKham`,
  // M/app.js:401-448). `ma` ô không đổi; chỉ đổi cách trình bày.
  const tieuDeMuc: Record<string, { ten: string; phu?: ReactNode }> = {
    A: {
      ten: "Bác sĩ tư vấn ghi",
      phu: ghi ? "mang sang từ Bàn tư vấn · bác sĩ chính sửa tiếp được" : "mang sang từ Bàn tư vấn",
    },
    B: { ten: `Khai thác & khám — ${dinhNghia.ten.replace(/^Phiếu\s+/i, "")}`, phu: "theo phiếu khám của phòng khám" },
    C: { ten: "Danh mục chỉ định", phu: "xếp như phiếu chỉ định giấy · giá KiotViet" },
    D: { ten: "Chẩn đoán và xử lý" },
    E: { ten: "Đơn thuốc", phu: "xếp như phiếu giấy · giá KiotViet" },
    F: { ten: "Dịch vụ khác (thủ thuật · điều trị)" },
    G: { ten: "Hẹn khám" },
  };
  const GOI_Y_KHOI: Record<1 | 2 | 3, string | null> = {
    1: null,
    2: "tick là thêm · kết quả về tự hiện bên dưới",
    3: null,
  };

  // B4 (đợt 3, 27/09/2026 — góp ý bác sĩ + thư ký y khoa): mỗi thẻ mục GẬP/MỞ
  // được. Mặc định mở nếu là mục LÀM VIỆC đầu của khối (bỏ qua mục mang sang
  // như A — phiếu mới thì B "Khai thác & khám" mở sẵn) hoặc đã có dữ liệu, đóng
  // nếu trống; lần bấm cuối được nhớ theo người dùng (localStorage — NganGap).
  const coTuVan = (dauPhieu?.tu_van ?? []).some((t) => t.noi_dung.trim());
  const coLienKet = (m: MucPhieu): boolean => {
    switch (m.lien_ket?.loai) {
      case "chi_dinh_cls":
        return ketQuaCls.length > 0;
      case "don_thuoc":
        return soThuoc > 0;
      case "chi_dinh_thu_thuat":
        return ketQuaTT.length > 0 || (thuThuat?.daChon.length ?? 0) > 0;
      case "mang_sang":
        return m.ma === "A" && coTuVan;
      default:
        return false;
    }
  };
  const nho = (ma: string) => `phieu-kham:${dinhNghia.form_id}:${ma}`;
  const mucDau = (ds: MucPhieu[]) => ds.find((m) => m.lien_ket?.loai !== "mang_sang")?.ma;

  const theMuc = (m: MucPhieu, laDau: boolean) => {
    const td = tieuDeMuc[m.ma] ?? { ten: m.ten };
    const soDienMuc = soODaDien(m.block, gia);
    const noiDung = (
      <>
        {m.ma === "A" && dauPhieu ? <KhoiTuVan dau={dauPhieu} choSua={ghi} /> : null}
        {m.lien_ket?.loai === "chi_dinh_cls" ? oChiDinhCls : null}
        {m.lien_ket?.loai === "don_thuoc" ? baoLoiDon : null}
        {m.lien_ket?.loai === "don_thuoc" ? (
          <DonThuocPhieu
            dong={donThuoc?.dong ?? []}
            mauThuoc={tc?.mau_thuoc ?? []}
            onDoi={ghi ? donThuoc?.onDoi : undefined}
          />
        ) : null}
        {m.lien_ket?.loai === "chi_dinh_thu_thuat" && oThuThuat ? oThuThuat : null}
        {m.lien_ket?.loai === "chi_dinh_thu_thuat" && ketQuaTT.length > 0 ? (
          <KetQuaChiDinh ds={ketQuaTT} {...(ketQua ?? {})} />
        ) : null}
        {m.lien_ket?.loai === "chi_dinh_thu_thuat" && !oThuThuat ? (
          <ChiDinhThuThuat
            ds={tc?.thu_thuat ?? []}
            daChon={thuThuat?.daChon ?? []}
            onChon={ghi ? thuThuat?.onChon : undefined}
          />
        ) : null}
        {veO(m)}
      </>
    );
    return (
      <Fragment key={m.ma}>
        {/* Khối 2: "Đã chỉ định & kết quả" đứng TRÊN danh mục (bản mẫu). */}
        {m.lien_ket?.loai === "chi_dinh_cls" && (ketQuaCls.length > 0 || tepChuaGan.length > 0) ? (
          <TheCon ten="Đã chỉ định & kết quả" moSan nhoKhoa={nho("KET_QUA")}>
            {ketQuaCls.length > 0 ? <KetQuaChiDinh ds={ketQuaCls} {...(ketQua ?? {})} /> : null}
            <TepChuaGan tep={tepChuaGan} />
          </TheCon>
        ) : null}
        <TheCon
          ten={td.ten}
          phu={td.phu}
          chip={soDienMuc > 0 ? <Chip tone="neutral">{soDienMuc} ô đã điền</Chip> : null}
          moSan={laDau || soDienMuc > 0 || coLienKet(m)}
          nhoKhoa={nho(m.ma)}
        >
          {noiDung}
        </TheCon>
      </Fragment>
    );
  };

  if (chiMuc) {
    const mucChi = dinhNghia.khung.filter((m) => chiMuc.includes(m.ma));
    // Bàn tư vấn: chỉ các mục được mở (vd B) — không đầu phiếu, không cột phải.
    return (
      <div className="space-y-4">
        {tomTatLoiO}
        {mucChi.map((m) => theMuc(m, m.ma === mucDau(mucChi)))}
        {dongTrangThai}
      </div>
    );
  }

  const hanhChinh = dinhNghia.khung.find((m) => m.ma === "HANH_CHINH");
  const mucKhoi = dinhNghia.khung.filter((m) => (KHOI[khoi - 1]?.muc ?? []).includes(m.ma));

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_12.5rem] xl:grid-cols-[minmax(0,1fr)_15rem]">
      {/* CỘT PHẢI — ba nút khối + In + Hoàn tất, dính khi cuộn (bản mẫu `ray`).
          Màn hẹp: thanh cuộn ngang dính dưới thanh đầu trang; dòng trạng thái
          lưu nằm NGAY DƯỚI thanh ấy (cùng khối dính) — 375 vẫn thấy (đợt 3). */}
      <aside className="sticky top-16 z-10 min-w-0 lg:order-last lg:top-20">
        <div className="rounded-card border border-hairline bg-surface">
          <div className="flex gap-2 overflow-x-auto p-2 lg:flex-col lg:overflow-visible lg:p-3">
            {KHOI.map((k) => {
              const dang = khoi === k.so;
              const moi = k.so === 2 ? coKqMoi : 0;
              return (
                <button
                  key={k.so}
                  type="button"
                  aria-pressed={dang}
                  onClick={() => setKhoi(k.so)}
                  className={`grid min-h-12 shrink-0 grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-2 rounded-control p-2 text-left ring-1 ring-inset lg:min-h-14 lg:w-full ${
                    dang ? "bg-surface-selected ring-brand-100" : "bg-surface ring-line hover:bg-surface-sunken"
                  }`}
                >
                  <span
                    className={`grid size-8 place-items-center rounded-control font-semibold ${
                      dang ? "bg-brand-600 text-white" : "bg-surface-sunken text-ink-muted"
                    }`}
                  >
                    {k.so}
                  </span>
                  <span className="min-w-0 pr-1">
                    <b className={`block text-emph font-semibold leading-tight ${dang ? "text-brand-700" : "text-ink"}`}>
                      {k.ten}
                    </b>
                    <small className="block text-meta text-ink-muted">{tomTat[k.so]}</small>
                  </span>
                  {moi > 0 ? <Chip tone="success">{moi} mới</Chip> : <span />}
                </button>
              );
            })}
            <div className="flex shrink-0 items-center gap-2 border-l border-hairline pl-2 lg:mt-2 lg:flex-col lg:items-stretch lg:border-l-0 lg:border-t lg:pl-0 lg:pt-3">
              {nutIn}
              {chanRay}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-2 border-t border-hairline px-3 py-1 lg:justify-center">
            {nhanCheDo ? <span className="text-meta text-ink-muted">{nhanCheDo.ten} ·</span> : null}
            {dongTrangThai}
          </div>
        </div>
      </aside>

      <div className="min-w-0 space-y-4">
        {dauTrang}
        {tomTatLoiO}

        {/* Thẻ khách + thẻ sinh hiệu Y HỆT bản giao diện mẫu (27/09/2026). */}
        {dauPhieu ? (
          <>
            <TheKhach dau={dauPhieu} />
            <TheSinhHieu dau={dauPhieu} />
          </>
        ) : null}
        {hanhChinh ? veO(hanhChinh) : null}

        <TieuDeKhoi so={khoi} ten={KHOI[khoi - 1]?.ten ?? ""} phu={GOI_Y_KHOI[khoi] ?? undefined} />

        {mucKhoi.map((m, i) => (
          <Fragment key={`muc-${m.ma}`}>
            {theMuc(m, m.ma === mucDau(mucKhoi))}
            {/* Dưới dòng "Bác sĩ tư vấn ghi" (Tuyền 28/09/2026). */}
            {khoi === 1 && i === 0 ? oDichVuKham : null}
          </Fragment>
        ))}

        <div className="flex justify-between gap-2 pb-8">
          {khoi > 1 ? (
            <button
              type="button"
              className={buttonClass("ghost", "md")}
              onClick={() => setKhoi((khoi - 1) as 1 | 2)}
            >
              ← {KHOI[khoi - 2]?.ten}
            </button>
          ) : (
            <span />
          )}
          {khoi < 3 ? (
            <button
              type="button"
              className={buttonClass("secondary", "md")}
              onClick={() => setKhoi((khoi + 1) as 2 | 3)}
            >
              Sang: {KHOI[khoi]?.ten} →
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** Thẻ con của một mục — bản mẫu `.card` + `.card-h` (tiêu đề 14/600 trái, câu
 *  phụ phải). Đợt 3 (27/09/2026): đầu thẻ là nút gập/mở (`NganGap`, bàn phím
 *  được), kèm chip "N ô đã điền". */
function TheCon({
  ten,
  phu,
  chip,
  moSan,
  nhoKhoa,
  children,
}: {
  ten: string;
  phu?: ReactNode;
  chip?: ReactNode;
  moSan: boolean;
  nhoKhoa: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-card border border-hairline bg-surface p-4">
      <NganGap co="the" tieuDe={ten} phu={phu} chip={chip} moSan={moSan} nhoKhoa={nhoKhoa}>
        {children}
      </NganGap>
    </section>
  );
}
