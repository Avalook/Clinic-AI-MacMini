"use client";

// PHIẾU KHÁM CỦA MỘT LƯỢT — clinical shell nối gói bảy phiếu v5 vào Bàn khám
// (Tuyền 23/09/2026 tối: "form sửa theo như này đi… làm luôn").
//
//   · Phiếu: đọc/ghi `phieu_kham_luot` qua `/api/phieu-kham`. TỰ LƯU theo nhịp
//     gõ — KHÔNG có nút "Lưu hồ sơ" ("tôi bảo không cần nút lưu hồ sơ đó mà").
//     Hai người cùng gõ → máy chủ trả 409, màn nói ra và tải lại, không đè.
//   · Mục C / F: danh mục có giá → chỉ định thật (lệnh của Bàn khám truyền vào).
//   · Kết quả: hiện ngay dưới mục C; bác sĩ [Điền kết quả] tại chỗ.
//   · Mục E: đơn thuốc tự lưu qua đường đơn bệnh án sẵn có → tới nhà thuốc.
//   · KHÔNG KHOÁ: chế độ luôn "editable"; Hoàn tất ở Bàn khám chỉ là mốc giờ.
//   · TỰ LƯU CHẮC CHẮN (đợt 3, 27/09/2026 — góp ý B9): phiếu và đơn thuốc đi
//     hàng đợi chung `lib/use-tu-luu` (tuần tự, lưu nốt khi đổi khách / đóng
//     tab, lỗi mạng tự thử lại). Cổng Hoàn tất mang `luuNot`: bấm Hoàn tất khi
//     còn chữ chưa lưu thì Bàn khám lưu nốt rồi mới gửi.

import { lenhHoanTac } from "../hoan-tac";
import ChonDichVuKham from "../ChonDichVuKham";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import BaoLoiCanhNut from "@/components/ui/BaoLoiCanhNut";
import Button, { buttonClass } from "@/components/ui/Button";
import { congTuLuu, type ClinicalCompletionGate } from "@/lib/clinical-completion";
import { SU_KIEN_BANG, SU_KIEN_THAI_KY } from "@/lib/nhip-lam-moi";
import { LOI_MAT_KET_NOI, nenThuLai, type KetQuaGui, type TrangThaiLuu } from "@/lib/tu-luu";
import { useTuLuu } from "@/lib/use-tu-luu";
import {
  donTuDong,
  dongTuDon,
  gopSoLuongQuayDien,
  nhomThuThuat,
  phanThayDoi,
  type ChiDinhVaKetQua,
  type KetQuaMotChiDinh,
  type DauPhieu,
  type DinhNghiaPhieu,
  type DongDonMayChu,
  type DongThuoc,
  type MauKetQuaNgan,
  type NhomCls,
  type ONhap,
} from "@/lib/phieu-kham";
import { guiThaoTac } from "../api";
import DanhMucChiDinh from "./DanhMucChiDinh";
import OLamTruocThuSau from "../OLamTruocThuSau";
import HanhTrinhLuot from "./HanhTrinhLuot";
import LichSuSuaPhieu from "./LichSuSuaPhieu";
import DatLichTaiKham from "./DatLichTaiKham";
import { KhungDatLichTaiKham } from "./ONhapPhieu";
import PhieuKham, { type KetQuaLuu, type ThamChieu } from "./PhieuKham";
import KetQuaChiDinh from "./KetQuaChiDinh";
import GhiChuLuot from "./GhiChuLuot";
import KhoiDichVuHoSo from "./KhoiDichVuHoSo";
import KhoiDieuTri from "./KhoiDieuTri";

interface PhieuLuot extends DinhNghiaPhieu {
  du_lieu: Record<string, ONhap>;
  revision: number;
}

interface ThamChieuDu extends ThamChieu {
  chi_dinh_cls: NhomCls[];
}

const CHO_LUU_DON_MS = 1500;
/** Bảng mà đổi thì danh sách chỉ định + kết quả có thể đổi. */
const BANG_KET_QUA = new Set(["service_order", "form_instance", "tep_ket_qua"]);

async function doc<T>(url: string): Promise<T | null> {
  const r = await fetch(url, { cache: "no-store" }).catch(() => null);
  if (!r || !r.ok) return null;
  return (await r.json().catch(() => null)) as T | null;
}

async function ghi(
  than: unknown,
  keepalive = false,
): Promise<{ ok: boolean; status: number; d: Record<string, unknown> | null }> {
  try {
    const r = await fetch("/api/phieu-kham", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
      // Trang đang đóng: trình duyệt giữ yêu cầu sống sau khi trang chết.
      keepalive,
    });
    const d = (await r.json().catch(() => null)) as Record<string, unknown> | null;
    return { ok: r.ok, status: r.status, d };
  } catch {
    return { ok: false, status: 0, d: null };
  }
}

function cauLoi(d: Record<string, unknown> | null, macDinh: string): string {
  const m = d?.message ?? d?.detail ?? d?.error;
  return typeof m === "string" && m ? m : macDinh;
}

export default function PhieuKhamLuot({
  visitId,
  clinicPatientId,
  choGhi: choGhiVao,
  datChiDinh,
  onDaDat,
  onTrangThai,
  chiMuc,
  chanRay,
  onTomTat,
  xemLai = false,
  formIdDau,
}: {
  visitId: string;
  clinicPatientId: string;
  /** Người đang mở được ghi (bác sĩ / thư ký của lượt) — máy chủ vẫn kiểm lại. */
  choGhi: boolean;
  datChiDinh: (
    codes: string[],
    /** Mã dịch vụ bác sĩ tick "Bắt buộc" (25/09/2026). */
    batBuoc: string[],
  ) => Promise<{ ok: true } | { ok: false; loi: string }>;
  onDaDat: () => void;
  /** Báo cho nút Hoàn tất: còn đang lưu dở / lỗi lưu thì nói ra. */
  onTrangThai?: (g: ClinicalCompletionGate) => void;
  /** Chỉ vẽ các mục này của phiếu (bàn tư vấn: `["B"]`). */
  chiMuc?: string[];
  /** Nút Hoàn tất của bàn khám — vẽ ở chân cột phải (Tuyền 27/09/2026). */
  chanRay?: ReactNode;
  /** Bàn tư vấn: số ô đã điền của các mục `chiMuc` + tên phiếu (chip công tắc). */
  onTomTat?: (soDien: number, tenPhieu: string) => void;
  /** XEM LẠI một lượt CŨ (29/09/2026 — "Lượt khám trước" / bệnh án chỉ xem):
   *  khoá mọi ô, không tick dịch vụ khám, không tự lưu. */
  xemLai?: boolean;
  /** Mở đúng phiếu này thay vì phiếu theo dịch vụ hiện tại (xem "Phiếu cũ"). */
  formIdDau?: string;
}) {
  const choGhi = choGhiVao && !xemLai;
  const [chonPhieu, setChonPhieu] = useState<string | null>(null);
  const [phieu, setPhieu] = useState<PhieuLuot | null>(null);
  const [chonDuoc, setChonDuoc] = useState<{ form_id: string; ten: string }[] | null>(null);
  const [dau, setDau] = useState<DauPhieu | null>(null);
  const [ketQua, setKetQua] = useState<ChiDinhVaKetQua[]>([]);
  // Tệp của lượt CHƯA gắn chỉ định (tải ở màn Khách hàng — đợt 3, 27/09).
  const [tepChuaGan, setTepChuaGan] = useState<KetQuaMotChiDinh[]>([]);
  const [mauDuPhong, setMauDuPhong] = useState<MauKetQuaNgan[]>([]);
  const [tc, setTc] = useState<ThamChieuDu | null>(null);
  const [don, setDon] = useState<DongThuoc[]>([]);
  /** Lỗi NẠP phiếu (lỗi lưu nằm ở hàng đợi tự lưu). */
  const [loi, setLoi] = useState<string | null>(null);
  const [canLyDo, setCanLyDo] = useState(false);
  const [lyDo, setLyDo] = useState("");
  const revision = useRef(0);
  /** Bản đã lưu gần nhất — tự lưu chỉ gửi phần khác bản này (lát 2). */
  const daLuu = useRef<Record<string, ONhap>>({});
  const soLanSuaDon = useRef(0);
  /** Đơn MỚI NHẤT — hàng đợi đọc lúc gửi (kèm mã dòng lần lưu trước vừa gắn). */
  const donRef = useRef<DongThuoc[]>([]);
  /** Lý do đính chính gửi kèm lần lưu KẾ TIẾP (nút "Lưu đơn kèm lý do"). */
  const lyDoRef = useRef<string | null>(null);
  const datDon = useCallback((d: DongThuoc[]) => {
    donRef.current = d;
    setDon(d);
  }, []);

  const napPhieu = useCallback(
    async (formId: string | null) => {
      const d = await doc<PhieuLuot & { form_id: string | null; chon_duoc?: { form_id: string; ten: string }[] }>(
        `/api/phieu-kham?visit_id=${visitId}&xem=phieu${formId ? `&chon=${formId}` : ""}`,
      );
      if (!d) {
        setLoi("Không đọc được phiếu khám của lượt này.");
        return;
      }
      if (!d.form_id) {
        setChonDuoc(d.chon_duoc ?? []);
        setPhieu(null);
        return;
      }
      revision.current = d.revision;
      daLuu.current = d.du_lieu ?? {};
      setChonDuoc(null);
      setPhieu(d);
    },
    [visitId],
  );

  const napKetQua = useCallback(async () => {
    const d = await doc<{
      chi_dinh: ChiDinhVaKetQua[];
      mau_du_phong: MauKetQuaNgan[];
      tep_chua_gan?: KetQuaMotChiDinh[];
    }>(`/api/phieu-kham?visit_id=${visitId}`);
    if (d) {
      setKetQua(d.chi_dinh);
      setMauDuPhong(d.mau_du_phong);
      setTepChuaGan(d.tep_chua_gan ?? []);
    }
  }, [visitId]);

  const napDon = useCallback(async () => {
    const d = await doc<{ dong: DongDonMayChu[] }>(
      `/api/phieu-kham?visit_id=${visitId}&xem=don-thuoc`,
    );
    return d ? d.dong.map(dongTuDon) : null;
  }, [visitId]);

  useEffect(() => {
    let huy = false;
    void (async () => {
      const [dp, t, dn] = await Promise.all([
        doc<DauPhieu>(`/api/phieu-kham?visit_id=${visitId}&xem=dau-phieu`),
        doc<ThamChieuDu>("/api/phieu-kham?xem=tham-chieu"),
        napDon(),
        napPhieu(formIdDau ?? null),
        napKetQua(),
      ]);
      if (huy) return;
      setDau(dp);
      setTc(t);
      if (dn) datDon(dn);
    })();
    return () => {
      huy = true;
    };
  }, [visitId, formIdDau, napPhieu, napKetQua, napDon, datDon]);

  // SỐ LƯỢNG DO QUẦY THU THUỐC ĐIỀN (C14, 01/10/2026): bác sĩ vội để trống, quầy
  // điền lúc thu — màn kê đơn đang mở tự hiện số ấy + nhãn "SL do thu ngân điền".
  // Chỉ gộp dòng bác sĩ còn để trống (`gopSoLuongQuayDien`) — không đè chữ đang gõ.
  useEffect(() => {
    let hen: ReturnType<typeof setTimeout> | undefined;
    const khiBangDoi = (ev: Event) => {
      const bang = (ev as CustomEvent<string | null>).detail;
      if (bang !== null && bang !== "prescription") return;
      if (document.visibilityState === "hidden") return;
      clearTimeout(hen);
      hen = setTimeout(() => {
        void napDon().then((may) => {
          if (!may) return;
          const gop = gopSoLuongQuayDien(donRef.current, may);
          if (gop) datDon(gop);
        });
      }, 400);
    };
    window.addEventListener(SU_KIEN_BANG, khiBangDoi);
    return () => {
      clearTimeout(hen);
      window.removeEventListener(SU_KIEN_BANG, khiBangDoi);
    };
  }, [napDon, datDon]);

  // KẾT QUẢ TỰ HIỆN (lát 4, 26/09/2026). Màn này tự fetch nên `router.refresh`
  // không với tới — nghe chung dòng tin của RealtimeRefresher (không mở kết nối
  // riêng). CHỈ nạp lại danh sách chỉ định + kết quả (chỉ đọc); phiếu đang gõ
  // KHÔNG nạp lại để không đè chữ người đang nhập.
  useEffect(() => {
    let hen: ReturnType<typeof setTimeout> | undefined;
    const khiBangDoi = (ev: Event) => {
      const bang = (ev as CustomEvent<string | null>).detail;
      if (bang !== null && !BANG_KET_QUA.has(bang)) return;
      if (document.visibilityState === "hidden") return;
      clearTimeout(hen);
      hen = setTimeout(() => void napKetQua(), 250);
    };
    window.addEventListener(SU_KIEN_BANG, khiBangDoi);
    return () => {
      clearTimeout(hen);
      window.removeEventListener(SU_KIEN_BANG, khiBangDoi);
    };
  }, [napKetQua]);

  const onLuu = useCallback(
    async (goi: Record<string, ONhap>, keepalive: boolean): Promise<KetQuaLuu> => {
      if (!phieu) return { ok: false, loi: "Chưa mở phiếu.", thuLai: false };
      const thayDoi = phanThayDoi(goi, daLuu.current);
      const daGui = Object.keys(thayDoi);
      if (daGui.length === 0) return { ok: true };
      const kq = await ghi(
        {
          thao_tac: "luu-phieu",
          visit_id: visitId,
          form_id: phieu.form_id,
          thay_doi: thayDoi,
        },
        keepalive,
      );
      if (!kq.ok) {
        return {
          ok: false,
          loi: kq.status === 0 ? LOI_MAT_KET_NOI : cauLoi(kq.d, "Không lưu được phiếu."),
          // 409 ở đường "chỉ ô vừa đổi" = hai người cùng MỞ phiếu lần đầu (dòng
          // phiếu vừa được người kia tạo). Gửi lại phần đổi là GỘP vào bản của
          // họ, không đè — nên thử lại, KHÔNG nạp lại (nạp lại xoá chữ vừa gõ).
          thuLai: kq.status === 409 || nenThuLai(kq.status),
        };
      }
      revision.current = Number(kq.d?.revision ?? revision.current + 1);
      daLuu.current = { ...daLuu.current, ...thayDoi };
      // Hai ô kinh cuối / dự kiến sinh vừa ghi sang thai kỳ (máy chủ quyết) →
      // khối Thai kỳ bên dưới nạp lại (29/09/2026).
      if (kq.d?.thai_ky) {
        window.dispatchEvent(new CustomEvent(SU_KIEN_THAI_KY, { detail: clinicPatientId }));
      }
      return { ok: true, canh_bao: kq.d?.canh_bao, da_gui: daGui };
    },
    [phieu, visitId, clinicPatientId],
  );

  // ĐƠN THUỐC mục E — cùng hàng đợi. Gửi đọc `donRef` lúc gửi, nên lần sau luôn
  // mang MÃ dòng mà lần trước vừa tạo (hai lần lưu song song từng đẻ dòng trùng).
  const guiDon = useCallback(
    async (keepalive: boolean): Promise<KetQuaGui> => {
      const lan = soLanSuaDon.current;
      const dong = donRef.current;
      const lyDoGui = lyDoRef.current;
      const kq = await ghi(
        {
          thao_tac: "luu-don",
          visit_id: visitId,
          dong: dong.filter((d) => d.ten_thuoc.trim()).map(donTuDong),
          ly_do: lyDoGui,
        },
        keepalive,
      );
      if (!kq.ok) {
        if (kq.d?.error === "PRESCRIPTION_CORRECTION_REASON_REQUIRED") setCanLyDo(true);
        return {
          ok: false,
          loi:
            kq.status === 0
              ? "Mất kết nối — đơn thuốc CHƯA được lưu."
              : `Đơn thuốc: ${cauLoi(kq.d, "Không lưu được đơn thuốc.")}`,
          thuLai: nenThuLai(kq.status),
        };
      }
      lyDoRef.current = null;
      setCanLyDo(false);
      setLyDo("");
      if (keepalive) return { ok: true };
      // Nạp lại để dòng mới có MÃ — lần lưu sau không tạo trùng. Chưa gõ thêm
      // thì lấy nguyên bản máy chủ; đã gõ thêm thì chỉ gắn mã theo thứ tự dòng
      // có tên (máy chủ trả theo thứ tự tạo), không đè chữ vừa gõ.
      const moi = await napDon();
      if (!moi) return { ok: true };
      if (soLanSuaDon.current === lan) {
        // Dòng CHƯA có tên (vừa bấm "+ Thuốc ngoài danh mục") không gửi lên
        // máy chủ — giữ lại, không thì nạp lại xoá mất dòng trước khi kịp gõ.
        const chuaTen = dong.filter((d) => !d.ten_thuoc.trim());
        datDon(chuaTen.length ? [...moi, ...chuaTen] : moi);
        return { ok: true };
      }
      let k = 0;
      datDon(
        donRef.current.map((d) => {
          if (!d.ten_thuoc.trim()) return d;
          const may = moi[k++];
          return d.id || !may ? d : { ...d, id: may.id };
        }),
      );
      return { ok: true };
    },
    [visitId, napDon, datDon],
  );
  const tuLuuDon = useTuLuu({ gui: guiDon, choMs: CHO_LUU_DON_MS, tat: !choGhi });
  const tuLuuKem = useMemo(
    () => ({ trangThai: tuLuuDon.trangThai, luuNgay: tuLuuDon.luuNgay }),
    [tuLuuDon.trangThai, tuLuuDon.luuNgay],
  );

  const doiDon = (dong: DongThuoc[]) => {
    soLanSuaDon.current += 1;
    datDon(dong);
    tuLuuDon.danhDau();
  };

  // CỔNG HOÀN TẤT: phiếu + đơn đã lưu hết chưa. Còn chữ chưa lưu → kèm `luuNot`
  // để Bàn khám lưu nốt rồi gửi (không bắt bấm lại).
  const [luuPhieu, setLuuPhieu] = useState<{
    tt: TrangThaiLuu;
    luuNgay: () => Promise<boolean>;
  } | null>(null);
  const baoLuu = useCallback(
    (tt: TrangThaiLuu, luuNgay: () => Promise<boolean>) => setLuuPhieu({ tt, luuNgay }),
    [],
  );
  const phieuDangVe = Boolean(phieu) && !chonDuoc;
  useEffect(() => {
    if (!onTrangThai) return;
    if (!phieuDangVe) {
      onTrangThai(loi ? { ok: false, code: null, message: loi } : { ok: true, code: null, message: null });
      return;
    }
    onTrangThai(
      luuPhieu
        ? congTuLuu(luuPhieu.tt, luuPhieu.luuNgay)
        : congTuLuu(tuLuuDon.trangThai, tuLuuDon.luuNgay, "Đơn thuốc"),
    );
  }, [phieuDangVe, loi, luuPhieu, tuLuuDon.trangThai, tuLuuDon.luuNgay, onTrangThai]);

  const daDat = useMemo(() => new Set(ketQua.map((k) => k.service_code)), [ketQua]);
  // "Trên phiếu giấy: SÂ 2D TC-BT" — nhãn phiếu chỉ định giấy của từng mã (27/09).
  const nhanGiay = useMemo(() => {
    const ra: Record<string, string> = {};
    for (const n of tc?.chi_dinh_cls ?? []) {
      for (const m of n.muc) if (m.service_code && !ra[m.service_code]) ra[m.service_code] = m.nhan;
    }
    return ra;
  }, [tc]);
  // Mã thủ thuật — kết quả của chúng hiện ở khối 3, không lẫn vào khối 2.
  const maThuThuat = useMemo(
    () => new Set((tc?.thu_thuat ?? []).flatMap((t) => (t.service_code ? [t.service_code] : []))),
    [tc],
  );
  const goiYMau = useMemo(() => {
    const ra: Record<string, string> = {};
    for (const n of tc?.chi_dinh_cls ?? []) {
      for (const m of n.muc) {
        if (m.service_code && m.form_id_ket_qua) {
          ra[m.service_code] = m.form_id_ket_qua.replace(/^KQ_/, "");
        }
      }
    }
    for (const t of tc?.thu_thuat ?? []) {
      if (t.service_code && t.form_id_ket_qua) {
        ra[t.service_code] = t.form_id_ket_qua.replace(/^KQ_/, "");
      }
    }
    return ra;
  }, [tc]);

  const dat = async (codes: string[], batBuoc: string[]) => {
    const kq = await datChiDinh(codes, batBuoc);
    if (kq.ok) {
      onDaDat();
      void napKetQua();
    }
    return kq;
  };

  // Bật / tắt "Bắt buộc" của chỉ định đã đặt (chưa thu tiền) — 25/09/2026.
  const doiBatBuoc = async (orderId: string, batBuoc: boolean) => {
    const kq = await guiThaoTac("bat-buoc", orderId, { bat_buoc: batBuoc });
    if (kq.ok) void napKetQua();
    return kq.ok ? ({ ok: true } as const) : ({ ok: false, loi: kq.loi } as const);
  };

  // DỊCH VỤ CỦA LƯỢT (07/10/2026, T1/T5) — đầu hồ sơ; xem lại lượt cũ thì không.
  const dsCls = (tc?.chi_dinh_cls ?? []) as NhomCls[];
  const choKetQua = (ds: ChiDinhVaKetQua[]) => (
    <KetQuaChiDinh
      ds={ds}
      mauDuPhong={mauDuPhong}
      goiYMau={goiYMau}
      nhanGiay={nhanGiay}
      choDien={choGhi}
      clinicPatientId={clinicPatientId}
      onDoi={() => {
        void napKetQua();
        onDaDat();
      }}
    />
  );
  const khoiDichVu =
    xemLai || chiMuc ? null : (
      <KhoiDichVuHoSo
        visitId={visitId}
        choGhi={choGhi}
        onDaDoi={() => {
          void napPhieu(null);
          void napKetQua();
          onDaDat();
        }}
        vePhieuCu={(f) => (
          <PhieuKhamLuot
            key={`cu-${f}`}
            visitId={visitId}
            clinicPatientId={clinicPatientId}
            choGhi={false}
            xemLai
            formIdDau={f}
            datChiDinh={async () => ({ ok: false, loi: "Phiếu cũ chỉ xem." })}
            onDaDat={() => undefined}
          />
        )}
      />
    );

  if (chonDuoc) {
    // HỒ SƠ TỐI GIẢN (07/10/2026, T3): loại khám không gắn phiếu (Điều trị,
    // Khác) — dịch vụ của lượt, khối Điều trị, kê chỉ định CLS / thủ thuật; phiếu
    // khám đầy đủ là TUỲ CHỌN.
    return (
      <div className="space-y-3">
        {khoiDichVu}
        {/* Lượt "Khác": MỘT ô chữ to tự do (máy chủ quyết có hiện không). */}
        <GhiChuLuot visitId={visitId} choGhi={choGhi} />
        <KhoiDieuTri visitId={visitId} choGhi={choGhi} />
        {ketQua.length > 0 ? (
          <section className="space-y-2 rounded-card border border-hairline bg-surface p-4">
            <h2 className="text-title text-ink">Đã chỉ định &amp; kết quả</h2>
            {choKetQua(ketQua)}
          </section>
        ) : null}
        {choGhi ? (
          <section className="space-y-2 rounded-card border border-hairline bg-surface p-4">
            <h2 className="text-title text-ink">Kê chỉ định</h2>
            <DanhMucChiDinh nhom={dsCls} daDat={daDat} daChiDinh={ketQua} onDat={dat} chiDoc={!choGhi} />
            <DanhMucChiDinh
              nhom={nhomThuThuat(tc?.thu_thuat)}
              daDat={daDat}
              daChiDinh={ketQua}
              onDat={dat}
              chiDoc={!choGhi}
            />
          </section>
        ) : null}
      <section className="space-y-3 rounded-card border border-hairline bg-surface p-4">
        <h2 className="text-title text-ink">Ghi phiếu khám đầy đủ (tuỳ chọn)</h2>
        <p className="text-body text-ink-muted">
          Loại dịch vụ của lượt không gắn phiếu khám. Cần ghi khám đầy đủ thì chọn một phiếu.
        </p>
        <div className="flex flex-wrap gap-2">
          {chonDuoc.map((p) => (
            <Button
              key={p.form_id}
              type="button"
              variant={chonPhieu === p.form_id ? "primary" : "secondary"}
              disabled={!choGhi}
              onClick={() => {
                setChonPhieu(p.form_id);
                void napPhieu(p.form_id);
              }}
            >
              {p.ten}
            </Button>
          ))}
        </div>
      </section>
      </div>
    );
  }

  if (!phieu) {
    return loi ? (
      <p role="alert" className="text-body text-danger">
        {loi}
      </p>
    ) : (
      <p className="text-body text-ink-muted">Đang mở phiếu khám…</p>
    );
  }

  // Khối 3 chia nhóm như bản mẫu (27/09/2026, đợt 3): Thủ thuật · ghế ĐTT ·
  // định hướng điều trị — nhóm do máy chủ gửi.
  const dsNhomThuThuat: NhomCls[] = nhomThuThuat(tc?.thu_thuat);

  // Ô "Ngày tái khám" → khung đặt LỊCH HẸN THẬT dưới nhóm Hẹn khám (02/10/2026).
  // Bàn tư vấn (chỉ mục B) và chế độ chỉ xem không vẽ.
  const veDatLich =
    choGhi && !chiMuc
      ? (ngay: string) => <DatLichTaiKham visitId={visitId} ngay={ngay} />
      : null;

  return (
    <KhungDatLichTaiKham.Provider value={veDatLich}>
    <div className="space-y-2">
      <PhieuKham
        key={`${phieu.form_id}-${phieu.version}`}
        dinhNghia={phieu}
        duLieu={phieu.du_lieu}
        cheDo={choGhi ? "editable" : "finalized_locked"}
        chiMuc={chiMuc}
        dauPhieu={dau}
        // Bàn tư vấn chỉ vẽ mục B — dải hành trình là của phiếu bác sĩ chính.
        dauTrang={
          chiMuc ? undefined : (
            <>
              {khoiDichVu}
              <HanhTrinhLuot visitId={visitId} />
              {/* Lượt "Khác" đã chọn ghi phiếu đầy đủ: ô ghi chú vẫn ở đây. */}
              <GhiChuLuot visitId={visitId} choGhi={choGhi} />
            </>
          )
        }
        oDieuTri={chiMuc ? undefined : <KhoiDieuTri visitId={visitId} choGhi={choGhi} />}
        // Tick dịch vụ khám (mã KiotViet) → tiền khám tính theo đó (28/09/2026).
        oDichVuKham={chiMuc || xemLai ? undefined : <ChonDichVuKham visitId={visitId} />}
        chanRay={chanRay}
        onTomTat={onTomTat}
        tuLuuKem={tuLuuKem}
        onTrangThaiLuu={baoLuu}
        // Lỗi lưu đơn thuốc NGAY TRONG mục E, cạnh chỗ gõ (góp ý B8, đợt 3) —
        // trước đợt 3 nó ở đầu phiếu, xa mục E.
        baoLoiDon={
          tuLuuDon.trangThai.loi ? (
            <BaoLoiCanhNut className="space-y-2">
              <p>{tuLuuDon.trangThai.loi}</p>
              {canLyDo ? (
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    value={lyDo}
                    onChange={(e) => setLyDo(e.target.value)}
                    placeholder="Lý do đính chính đơn (đơn đã thu tiền / đã cấp)"
                    aria-label="Lý do đính chính đơn thuốc"
                    className="min-h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 text-body text-ink"
                  />
                  <Button
                    type="button"
                    variant="primary"
                    disabled={!lyDo.trim()}
                    onClick={() => {
                      lyDoRef.current = lyDo.trim();
                      void tuLuuDon.luuNgay();
                    }}
                  >
                    Lưu đơn kèm lý do
                  </Button>
                </div>
              ) : (
                <Button type="button" size="sm" variant="danger" onClick={() => void tuLuuDon.luuNgay()}>
                  Thử lại
                </Button>
              )}
            </BaoLoiCanhNut>
          ) : null
        }
        nutIn={
          <>
          {/* In phiếu khám (Tuyền 24/09/2026: "chỗ cho in phiếu khám của bệnh nhân
              đâu?"). Mở tab riêng, ngoài thanh bên → in sạch khổ A4. Bản mẫu:
              nút ở CHÂN CỘT PHẢI, trên Hoàn tất (27/09). */}
          <a
            href={`/print/phieu-kham/${visitId}`}
            target="_blank"
            rel="noopener"
            className={`${buttonClass("secondary", "md")} lg:w-full`}
          >
            In phiếu khám
          </a>
          <LichSuSuaPhieu visitId={visitId} dinhNghia={phieu} />
          {/* Tick "Làm trước – thu sau" (30/09/2026 tối): dây "thu trước khi
              làm" bật thì chưa thu chỉ lượt có tick mới xếp phòng / làm. Ô tự
              ẩn khi dây tắt; cờ bấm được do máy chủ trả. Màn hẹp: cột phải là
              thanh cuộn ngang — khoá bề rộng để chữ xuống dòng (bấm thật 375
              ngày 30/09: câu dài kéo ô ra ~1000px, nút In trôi khỏi màn). */}
          {choGhi ? (
            <div className="w-72 shrink-0 lg:w-full">
              <OLamTruocThuSau visitId={visitId} />
            </div>
          ) : null}
          </>
        }
        ketQuaChiDinh={ketQua}
        tepChuaGan={tepChuaGan}
        onLuu={onLuu}
        thamChieuNgoai={tc}
        donThuoc={{ dong: don, onDoi: choGhi ? doiDon : undefined }}
        oChiDinhCls={
          <DanhMucChiDinh
            nhom={tc?.chi_dinh_cls ?? []}
            daDat={daDat}
            daChiDinh={ketQua}
            onDat={dat}
            chiDoc={!choGhi}
          />
        }
        oThuThuat={
          <DanhMucChiDinh
            nhom={dsNhomThuThuat}
            daDat={daDat}
            daChiDinh={ketQua}
            onDat={dat}
            chiDoc={!choGhi}
          />
        }
        maThuThuat={maThuThuat}
        ketQua={{
          mauDuPhong,
          goiYMau,
          nhanGiay,
          // Ô "bắt buộc" của chỉ định đã đặt: nay ở thẻ từng chỉ định (27/09).
          onDoiBatBuoc: choGhi ? doiBatBuoc : undefined,
          // Hoàn tác chỉ định (01/10/2026) — quầy thu cập nhật ngay (hoá đơn
          // máy chủ dựng lại); đã thu thì hỏi xác nhận, thành tiền thừa.
          onBoChiDinh: choGhi && !xemLai ? (id) => lenhHoanTac("huy-chi-dinh", id) : undefined,
          choDien: choGhi,
          clinicPatientId,
          onDoi: () => {
            void napKetQua();
            onDaDat();
          },
        }}
      />
    </div>
    </KhungDatLichTaiKham.Provider>
  );
}
