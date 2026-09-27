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

import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { buttonClass } from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import {
  dungGoiLuu,
  ghiDuoc,
  giaTriBanDau,
  gomNhom,
  KHOI_PHIEU,
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
import { KhoiTuVan } from "./KhoiDauPhieu";
import { TheKhach, TheSinhHieu } from "./TheKhach";
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

/** Ba khối — định nghĩa ở lib/phieu-kham (dùng chung với bản in). */
const KHOI = KHOI_PHIEU;

function coGiaTri(v: GiaTriO | undefined): boolean {
  return Array.isArray(v) ? v.length > 0 : Boolean(v && String(v).trim());
}

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
  nutIn,
  chiMuc,
  dauTrang,
  chanRay,
  maThuThuat,
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
    clinicPatientId?: string;
    onDoi: () => void;
    nhanGiay?: Record<string, string>;
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
}) {
  const [gia, setGia] = useState<Record<string, GiaTriO>>(() => giaTriBanDau(duLieu));
  const [khoi, setKhoi] = useState<1 | 2 | 3>(1);
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

  // Tóm tắt trên nút khối — như bản mẫu: số ô đã điền · chỉ định & kết quả ·
  // thuốc & hẹn.
  const oTheoMuc = (ds: string[]) =>
    dinhNghia.khung.filter((m) => ds.includes(m.ma)).flatMap((m) => m.block.map((o) => o.ma));
  const soDien = oTheoMuc(["A", "B"]).filter((ma) => coGiaTri(gia[ma])).length;
  const laTT = (c: ChiDinhVaKetQua) => Boolean(maThuThuat?.has(c.service_code));
  const ketQuaCls = ketQuaChiDinh.filter((c) => !laTT(c));
  const ketQuaTT = ketQuaChiDinh.filter(laTT);
  const coKq = ketQuaCls.filter((c) => c.ket_qua_trang_thai === "CO_KET_QUA").length;
  // Chip "N mới" trên nút khối 2: kết quả đã về mà chưa ai xem.
  const coKqMoi = ketQuaCls.filter(
    (c) => c.ket_qua_trang_thai === "CO_KET_QUA" && !c.da_xem_luc,
  ).length;
  const soThuoc = (donThuoc?.dong ?? []).filter((d) => d.ten_thuoc.trim()).length;
  const coHen = oTheoMuc(["G"]).some((ma) => /follow_date|ngay/.test(ma) && coGiaTri(gia[ma]));
  const tomTat: Record<1 | 2 | 3, string> = {
    1: `${soDien} ô đã điền`,
    2: ketQuaCls.length ? `${ketQuaCls.length} chỉ định · ${coKq} có KQ` : "chưa chỉ định",
    3:
      [soThuoc ? `${soThuoc} thuốc` : "", ketQuaTT.length ? `${ketQuaTT.length} dịch vụ` : "", coHen ? "có hẹn" : ""]
        .filter(Boolean)
        .join(" · ") || "chưa có gì",
  };

  const trangThaiLuu = dangLuu ? "Đang lưu…" : luuLuc ? `Đã lưu ${gioVn(luuLuc)}` : "Tự lưu khi gõ";

  // THẺ CON của từng mục — tên + câu phụ Y HỆT bản giao diện mẫu (`manKham`,
  // M/app.js:401-448). `ma` ô không đổi; chỉ đổi cách trình bày.
  const tieuDeMuc: Record<string, { ten: string; phu?: ReactNode }> = {
    A: { ten: "Bác sĩ tư vấn ghi", phu: "mang sang từ Bàn tư vấn" },
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

  const theMuc = (m: MucPhieu) => {
    const td = tieuDeMuc[m.ma] ?? { ten: m.ten };
    const noiDung = (
      <>
        {m.ma === "A" && dauPhieu ? <KhoiTuVan dau={dauPhieu} /> : null}
        {m.lien_ket?.loai === "chi_dinh_cls" ? oChiDinhCls : null}
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
        {m.lien_ket?.loai === "chi_dinh_cls" && ketQuaCls.length > 0 ? (
          <TheCon ten="Đã chỉ định & kết quả">
            <KetQuaChiDinh ds={ketQuaCls} {...(ketQua ?? {})} />
          </TheCon>
        ) : null}
        <TheCon ten={td.ten} phu={td.phu}>
          {noiDung}
        </TheCon>
      </Fragment>
    );
  };

  if (chiMuc) {
    // Bàn tư vấn: chỉ các mục được mở (vd B) — không đầu phiếu, không cột phải.
    return (
      <div className="space-y-4">
        {loi ? <p className="text-body text-danger">{loi}</p> : null}
        {dinhNghia.khung.filter((m) => chiMuc.includes(m.ma)).map((m) => theMuc(m))}
        <p className="text-meta text-ink-muted">{trangThaiLuu}</p>
      </div>
    );
  }

  const hanhChinh = dinhNghia.khung.find((m) => m.ma === "HANH_CHINH");
  const mucKhoi = dinhNghia.khung.filter((m) => (KHOI[khoi - 1]?.muc ?? []).includes(m.ma));

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_12.5rem] xl:grid-cols-[minmax(0,1fr)_15rem]">
      {/* CỘT PHẢI — ba nút khối + In + Hoàn tất, dính khi cuộn (bản mẫu `ray`).
          Màn hẹp: thanh cuộn ngang dính dưới thanh đầu trang. */}
      <aside className="sticky top-16 z-10 min-w-0 lg:order-last lg:top-20">
        <div className="flex gap-2 overflow-x-auto rounded-card border border-hairline bg-surface p-2 lg:flex-col lg:overflow-visible lg:p-3">
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
            <span className="hidden text-center text-meta text-ink-muted lg:block">
              {nhanCheDo ? `${nhanCheDo.ten} · ` : ""}
              {trangThaiLuu}
            </span>
          </div>
        </div>
      </aside>

      <div className="min-w-0 space-y-4">
        {dauTrang}
        {loi ? <p role="alert" className="text-body text-danger">{loi}</p> : null}
        {canhBao.length > 0 ? (
          <ul className="space-y-1 rounded-control bg-warning-bg p-3 text-body text-warning">
            {canhBao.map((c) => (
              <li key={c.ma}>
                {c.ten}: {c.loi}
              </li>
            ))}
          </ul>
        ) : null}

        {/* Thẻ khách + thẻ sinh hiệu Y HỆT bản giao diện mẫu (27/09/2026). */}
        {dauPhieu ? (
          <>
            <TheKhach dau={dauPhieu} />
            <TheSinhHieu dau={dauPhieu} />
          </>
        ) : null}
        {hanhChinh ? veO(hanhChinh) : null}

        <div className="flex scroll-mt-20 items-center gap-3 pt-4">
          <span className="grid size-8 shrink-0 place-items-center rounded-control bg-brand-600 text-emph font-semibold text-white">
            {khoi}
          </span>
          <h2 className="text-title font-semibold text-ink sm:text-hero">{KHOI[khoi - 1]?.ten}</h2>
          {GOI_Y_KHOI[khoi] ? (
            <span className="ml-auto hidden text-meta text-ink-muted sm:inline">{GOI_Y_KHOI[khoi]}</span>
          ) : null}
        </div>

        {mucKhoi.map((m) => theMuc(m))}

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

/** Thẻ con của một mục — bản mẫu `.card` + `.card-h` (tiêu đề 14/600 trái, câu phụ phải). */
function TheCon({ ten, phu, children }: { ten: string; phu?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-card border border-hairline bg-surface p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-emph font-semibold text-ink">{ten}</span>
        {phu ? <span className="text-meta text-ink-muted">{phu}</span> : null}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
