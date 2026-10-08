"use client";

// Quầy thu ngân: ai đang chờ, họ dùng gì, hết bao nhiêu, bấm một nút là xong.
//
// THAY CHO MÀN "ĐỐI SOÁT CHI PHÍ" cũ. Màn ấy dựng một quy trình đối soát đầy
// đủ — checklist trước khi đối soát, nguồn sai lệch, biên bản nguồn ngoài, nút
// "Bắt đầu đối soát" — mà phần lớn nút đều `disabled` kèm title "Chưa có API".
// Tuyền chốt 16/09: "thu ngân thì cần gì đối soát, nó là thu ngân dịch vụ
// luôn, hiện các dịch vụ khách đó khám ra và tính tiền là xong á".
//
// TIỀN DO MÁY CHỦ TÍNH (contract tiền–thuốc C3, 19/09/2026). Màn này KHÔNG tự
// cộng nữa: nó hiện `hoa_don` máy chủ dựng (số lượng × đơn giá từng dòng, tổng,
// lý do chưa thu được) và gửi lại `revision` của đúng hoá đơn ấy. Bản trước
// cộng đơn giá thuốc mà quên nhân số lượng.
//
// GIÁ TRỐNG PHẢI HIỆN RA LÀ TRỐNG, không được hiện thành 0đ. Hôm nay bảng giá
// mới có 1/39 dịch vụ và 0/80 thuốc có giá (phòng khám chưa gửi bảng giá). Một
// dòng "0đ" trông như miễn phí; một dòng "chưa có giá" trông như thiếu dữ liệu.
// Chỉ cái sau là sự thật, và chỉ cái sau khiến có người đi hỏi.

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";
import NutXemLuot from "../_lam-viec/NutXemLuot";
import NutCheckOut from "../_lam-viec/NutCheckOut";
import ChinhDonQuay from "./ChinhDonQuay";
import ChonDichVu, { type ChoKhachQuyet } from "./ChonDichVu";
import XepPhongDaThu, { type DaTraChoPhong } from "./XepPhongDaThu";
import NutInPhieu from "@/components/ui/NutInPhieu";
import ChonDichVuKham from "../_lam-viec/ChonDichVuKham";
import VatTuQuay from "./VatTuQuay";
import LieuTrinhQuay from "./LieuTrinhQuay";
import { useNgheBang } from "../dung-nghe-bang";
import HoaDonMot, { type LenhThuMot, type QuayThu } from "./HoaDonMot";
import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";
import SoLuot from "@/components/ui/SoLuot";
import { nhanPhan, tenHinhThuc, type PhanThu } from "@/lib/hinh-thuc-thu";
import { gio, nhanLamTruocThuSau, type LamTruoc } from "../_lam-viec/OLamTruocThuSau";
import AnhChuyenKhoan, { taiAnhChuyenKhoan, type AnhCk } from "./AnhChuyenKhoan";
import ChiaHinhThuc, { type KetQuaChia } from "./ChiaHinhThuc";
import NutHoanTac from "./NutHoanTac";

interface Dong {
  id: string;
  name: string;
  price: number | null;
  quantity?: string | null;
  dosage?: string | null;
}

interface DongHoaDon {
  source_id: string;
  ten: string;
  so_luong: number;
  don_vi: string | null;
  don_gia: number | null;
  thanh_tien: number | null;
  ben_thu: "CLINIC" | "EXTERNAL_PARTNER";
  van_de: string | null;
}

interface DongDoiTac extends DongHoaDon {
  /** Đối tác đã ghi nhận thu tiền khách (bàn đối tác) — null = chưa. */
  doi_tac_da_thu?: { so_tien: number; hinh_thuc: string; luc: string } | null;
}

export interface HoaDon {
  tong: number;
  revision: string;
  thu_duoc: boolean;
  van_de: string[];
  dong: DongHoaDon[];
  /** Khách trả TRỰC TIẾP cho đối tác (27/09/2026): hiện, không cộng. */
  dong_doi_tac?: DongDoiTac[];
  /** Phòng khám không còn khoản nào — chỉ còn dịch vụ khách trả đối tác. */
  chi_doi_tac_thu?: boolean;
}

interface Luot {
  visit_id: string;
  clinic_patient_id: string;
  full_name: string | null;
  patient_code: string | null;
  phone: string | null;
  so_booking?: number | null;
  so_tiep_don?: number | null;
  services: Dong[];
  drugs: Dong[];
  hoa_don?: { dich_vu?: HoaDon; thuoc?: HoaDon };
  /** Chỉ định còn chờ khách quyết làm hay không (máy chủ tính). */
  chon_dich_vu?: ChoKhachQuyet | null;
  /** Đã trả, chưa bắt đầu — xếp / đổi phòng sau khi thu (máy chủ tính). */
  xep_phong?: DaTraChoPhong[];
  /** Quầy một hoá đơn (27/09): hoá đơn dịch vụ dựng sẵn ở máy chủ. */
  quay_thu?: QuayThu | null;
  loai_kham?: string | null;
  bac_si?: string | null;
  cho_tu?: string | null;
  /** Tick "Làm trước – thu sau" + dịch vụ đã làm / còn nợ (30/09/2026 tối). */
  lam_truoc?: LamTruocLuot | null;
  /** TIỀN THỪA (hoàn tác 01/10/2026): đã thu cho chỉ định nay đã bỏ / không
   *  làm — máy chủ tính (đã trừ khoản hoàn). */
  tien_thua?: TienThua | null;
  /** Chỉ định ĐÃ XOÁ (chưa hoàn tác) — 06/10/2026: vẫn thấy, gạch ngang. */
  da_bo_chi_dinh?: DaBoChiDinh[];
  /** Máy chủ: lượt đang chờ thu ở quầy dịch vụ (`_xep_hang_cho_thu`). */
  cho_thu?: boolean;
}

/** Một chỉ định đã xoá — câu "ai đã xoá" do máy chủ viết. */
interface DaBoChiDinh {
  so_id: string;
  order_id: string | null;
  nhom_nhan: string;
  ten: string | null;
  lan: number | null;
  gia: number | null;
  cau: string;
  luc: string | null;
  ly_do: string | null;
  da_thu: number;
  tien_thua: number;
}

interface TienThua {
  tong: number;
  dong: {
    order_id: string | null;
    line_id?: string;
    ten: string | null;
    so_tien: number;
    loai: "BO_CHI_DINH" | "KHONG_LAM" | "BO_DICH_VU_KHAM";
    ly_do: string | null;
  }[];
}

/** Một dịch vụ của lượt "Làm trước – thu sau" (máy chủ tính trạng thái + nợ). */
interface DichVuLamTruoc {
  id: string;
  ten: string | null;
  trang_thai: "DA_XONG" | "DANG_LAM" | "CHUA_LAM" | "KHONG_LAM";
  nhan: string;
  con_no: number | null;
}

interface LamTruocLuot extends LamTruoc {
  dich_vu?: DichVuLamTruoc[];
  /** LAM_XONG_THU_TIEN = mọi dịch vụ đã xong, còn nợ — máy chủ đưa lên đầu. */
  nhom?: "LAM_TRUOC" | "LAM_XONG_THU_TIEN";
}

interface DaThu {
  visit_id: string;
  kind: string;
}

export interface ChoXacMinh {
  payment_cycle_id: string;
  visit_id: string;
  kind: string;
  so_tien: number;
  phuong_thuc: string;
  luc: string;
  /** Chia TM + CK của lần chờ (01/10/2026). */
  phan?: PhanThu[];
  anh_ck?: AnhCk[];
}

/** Hình thức chính (có phần chuyển khoản → chuyển khoản). QR đã gộp vào CK. */
export type PhuongThuc = "CASH" | "TRANSFER";

export const TEN_PT: Record<PhuongThuc, string> = {
  CASH: "Tiền mặt",
  TRANSFER: "Chuyển khoản",
};

/** Câu "(Tiền mặt)" / "(Tiền mặt 500.000đ + Chuyển khoản 200.000đ)" cho lời báo. */
function nhanChia(c: KetQuaChia): string {
  return nhanPhan(c.phan.map((p) => ({ ...p })));
}

export type Quay = "dich_vu" | "thuoc" | "ca_hai";

const MODES: Record<Quay, string> = {
  dich_vu: "dich_vu",
  thuoc: "thuoc",
  ca_hai: "dich_vu,thuoc",
};

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

const TONE_DV: Record<DichVuLamTruoc["trang_thai"], ChipTone> = {
  DA_XONG: "success",
  DANG_LAM: "run",
  CHUA_LAM: "neutral",
  KHONG_LAM: "neutral",
};

export default function QuayThuNgan({ quay, ngay }: { quay: Quay; ngay?: string }) {
  // THUỐC VÀ DỊCH VỤ THU RIÊNG HẲN (Tuyền 01/10/2026): mọi lệnh gửi kèm quầy
  // đang đứng — máy chủ từ chối (409 QUAY_KHAC_LOAI) nếu loại tiền không thuộc quầy.
  const quayThu = quay === "ca_hai" ? undefined : quay;
  const [ds, setDs] = useState<Luot[] | null>(null);
  const [daThu, setDaThu] = useState<DaThu[]>([]);
  const [cho, setCho] = useState<ChoXacMinh[]>([]);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dangThu, setDangThu] = useState<string | null>(null);
  const [vatTuDangLuu, setVatTuDangLuu] = useState<Set<string>>(() => new Set());
  // `?luot=` — mở quầy từ nút "Thu ngay" của check-out (khách còn nợ,
  // 01/10/2026): chọn sẵn đúng lượt ấy.
  const thamSo = useSearchParams();
  const [chonVisit, setChonVisit] = useState<string | null>(
    () => thamSo?.get("luot") ?? null,
  );
  // Lượt vừa thu xong — để mời Check-out ngay dưới câu "Đã thu…" (27/09/2026,
  // đợt 3). Nút tự ẩn nếu tài khoản không có quyền đóng lượt.
  // Gắn với ĐÚNG câu báo của lần thu ấy (`cau`): câu báo đổi sang việc khác
  // (chốt dịch vụ, chỉnh đơn…) thì nút tự ẩn, không treo dưới câu của người khác.
  const [vuaThu, setVuaThu] = useState<{
    visitId: string;
    ten: string | null;
    cau: string;
  } | null>(null);
  // Mã lần thu vừa ghi — nút "In phiếu thu" (có phòng làm dịch vụ) ngay dưới
  // câu "Đã thu…" (Tuyền 30/09/2026: in bill cho khách cầm đi theo).
  const [phieuVuaThu, setPhieuVuaThu] = useState<string | null>(null);
  // Lượt vừa CHỐT, THU SAU — nút "In phiếu hướng dẫn phòng" dưới câu báo (chưa
  // có tiền nên không có phiếu thu, nhưng khách vẫn cần giấy đi phòng).
  const [vuaChot, setVuaChot] = useState<{ visitId: string; cau: string } | null>(null);
  // Lần thu vừa ghi (đã thu HOẶC chờ xác minh) — nút "Hoàn tác lần thu" ngay dưới
  // câu báo (Tuyền 01/10/2026: làm lại thao tác sai ngay tại chỗ).
  const [lanVuaGhi, setLanVuaGhi] = useState<{ cycleId: string; soTien: number } | null>(null);

  const doc = useCallback(async () => {
    try {
      // `ngay` (02/10/2026, thanh ngày): xem lại một ngày cũ; không có = hôm nay.
      const duoiNgay = ngay ? `&ngay=${ngay}` : "";
      const r = await fetch(`/api/cashier?modes=${MODES[quay]}${duoiNgay}`, {
        cache: "no-store",
      });
      const d = (await r.json().catch(() => null)) as
        | { items?: Luot[]; paid?: DaThu[]; cho_xac_minh?: ChoXacMinh[]; error?: string }
        | null;
      if (!r.ok) return { loi: d?.error ?? "Không đọc được danh sách chờ thu." };
      return { items: d?.items ?? [], paid: d?.paid ?? [], cho: d?.cho_xac_minh ?? [] };
    } catch {
      return { loi: "Mất kết nối tới máy chủ." };
    }
  }, [quay, ngay]);

  const nhan = useCallback(
    (kq: { items?: Luot[]; paid?: DaThu[]; cho?: ChoXacMinh[]; loi?: string }) => {
      if (kq.loi) {
        setLoi(kq.loi);
        return;
      }
      setLoi(null);
      setDs(kq.items ?? []);
      setDaThu(kq.paid ?? []);
      setCho(kq.cho ?? []);
    },
    [],
  );

  const tai = useCallback(async () => nhan(await doc()), [doc, nhan]);

  // NGHE SỰ KIỆN (28/09/2026): trước đây quầy nạp MỘT lần khi mở. Hệ thống tự
  // xếp phòng (dây H4) ngay sau khi thu — màn vẫn hiện "chưa xếp phòng" với số
  // phiên bản cũ, bấm "Xếp phòng" thì bị báo "vừa được điều phối bởi người khác".
  useNgheBang(
    [
      "service_order",
      "visit",
      "queue_entry",
      "payment",
      "payment_cycle",
      "prescription",
      "luot_vat_tu",
      // Sổ sửa chỉ định: xoá / hoàn tác → dòng "đã xoá" đổi ngay. Phí khám
      // thêm/bỏ cũng tới qua đây (trigger `trg_so_sua_phi_kham` ghi sổ) —
      // `luot_phi_kham` không có trigger báo tin nên nghe thẳng nó là vô ích.
      "so_sua_chi_dinh",
    ],
    () => void tai(),
  );

  useEffect(() => {
    let huy = false;
    void doc().then((kq) => {
      if (!huy) nhan(kq);
    });
    return () => {
      huy = true;
    };
  }, [doc, nhan]);

  /** Gửi một lệnh thu ngân; trả `true` nếu máy chủ nhận VÀ tiền đã tính là thu
   *  (không phải "chờ xác minh"). Luôn tải lại sau đó. */
  const gui = useCallback(
    async (
      khoa: string,
      noiDung: Record<string, unknown>,
      xongCau: string,
      thaoTac?: string,
      anh?: File | null,
    ): Promise<boolean> => {
      setDangThu(khoa);
      setLoi(null);
      setXong(null);
      setVuaThu(null);
      setPhieuVuaThu(null);
      setLanVuaGhi(null);
      let daThuThat = false;
      try {
        // Một THAO TÁC một khoá gửi lại: mất phản hồi rồi bấm lại thì mang đúng
        // khoá cũ, máy chủ trả kết quả lần đầu thay vì thu lần hai.
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (thaoTac) headers["Idempotency-Key"] = khoaThaoTac(thaoTac);
        const r = await fetch("/api/payment", {
          method: "POST",
          headers,
          body: JSON.stringify(noiDung),
        });
        if (r.ok && thaoTac) xongThaoTac(thaoTac);
        const d = (await r.json().catch(() => null)) as
          | { error?: string; message?: string; status?: string; payment_cycle_id?: string | null }
          | null;
        if (!r.ok) {
          setLoi(d?.message ?? d?.error ?? "Không ghi được.");
        } else {
          daThuThat = d?.status !== "PENDING_VERIFICATION";
          if (daThuThat && d?.payment_cycle_id) setPhieuVuaThu(d.payment_cycle_id);
          if (d?.payment_cycle_id && (d.status === "PAID" || d.status === "PENDING_VERIFICATION")) {
            const tien0 = Number((noiDung as { amount?: number }).amount ?? 0);
            setLanVuaGhi({ cycleId: d.payment_cycle_id, soTien: tien0 });
            // Ảnh chuyển khoản chọn lúc thu: tải lên NGAY khi có mã lần thu.
            if (anh) {
              const loiAnh = await taiAnhChuyenKhoan(d.payment_cycle_id, anh);
              if (loiAnh) setLoi(`Đã ghi lần thu, nhưng ảnh chuyển khoản chưa lưu: ${loiAnh}`);
            }
          }
          setXong(
            d?.status === "PENDING_VERIFICATION"
              ? "Đã ghi CHỜ XÁC MINH — chưa tính là đã thu cho tới khi nhập mã giao dịch."
              : xongCau,
          );
        }
        // Hoá đơn đổi (BILL_CHANGED) hay bị từ chối: tải lại để thấy số mới.
        await tai();
      } catch {
        setLoi("Mất kết nối — CHƯA ghi được thao tác này.");
      } finally {
        setDangThu(null);
      }
      return daThuThat;
    },
    [tai],
  );

  const thu = useCallback(
    async (l: Luot, kind: "dich_vu" | "thuoc", hd: HoaDon, chia: KetQuaChia) => {
      const pt: PhuongThuc = chia.coChuyenKhoan ? "TRANSFER" : "CASH";
      const cau = `Đã thu ${tien(hd.tong)} (${nhanChia(chia)}) của ${l.full_name ?? "khách"}.`;
      const ok = await gui(
        `${l.visit_id}:${kind}`,
        {
          visitId: l.visit_id,
          clinicPatientId: l.clinic_patient_id,
          kind,
          quay: quayThu,
          billRevision: hd.revision,
          amount: hd.tong,
          method: pt,
          phan: chia.phan,
        },
        cau,
        dinhDanhThaoTac("thu", l.visit_id, kind, hd.revision, JSON.stringify(chia.phan), String(hd.tong)),
        chia.anh,
      );
      if (ok) setVuaThu({ visitId: l.visit_id, ten: l.full_name, cau });
    },
    [gui, quayThu],
  );

  /** Thu một lệnh: máy chủ chốt lựa chọn dịch vụ + ghi sổ (quầy một hoá đơn). */
  const thuMot = useCallback(
    async (l: Luot, p: LenhThuMot) => {
      const cau =
        p.amount === undefined
          ? `Đã chốt dịch vụ của ${l.full_name ?? "khách"} (không có khoản thu tại quầy).`
          : `Đã thu ${tien(p.tong)} (${nhanPhan(p.phan ?? [])}) của ${l.full_name ?? "khách"}.`;
      const ok = await gui(
        `${l.visit_id}:dich_vu`,
        {
          visitId: l.visit_id,
          clinicPatientId: l.clinic_patient_id,
          kind: "dich_vu",
          quay: quayThu,
          billRevision: p.billRevision,
          amount: p.amount,
          method: p.method,
          chon: p.chon,
          ...(p.phan ? { phan: p.phan } : {}),
        },
        cau,
        dinhDanhThaoTac(l.visit_id, p.khoa),
        p.anh,
      );
      if (ok) setVuaThu({ visitId: l.visit_id, ten: l.full_name, cau });
    },
    [gui, quayThu],
  );

  /** V10 LÀM TRƯỚC, THU SAU (Tuyền 30/09/2026): chốt dịch vụ khách làm, KHÔNG
   *  thu — máy chủ xếp phòng ngay (dây H4), khách đi làm, cuối buổi quay lại
   *  quầy thu. Cùng lệnh xác nhận lựa chọn của ô "Khách chọn dịch vụ". */
  const chotThuSau = useCallback(
    async (l: Luot, chon: NonNullable<LenhThuMot["chon"]>) => {
      const khoa = `${l.visit_id}:dich_vu`;
      const thaoTac = dinhDanhThaoTac(
        "chon-dich-vu",
        l.visit_id,
        String(chon.expected_selection_revision),
        chon.selected_order_ids.join(","),
      );
      setDangThu(khoa);
      setLoi(null);
      setXong(null);
      setVuaThu(null);
      try {
        const r = await fetch("/api/luot-kham", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Idempotency-Key": khoaThaoTac(thaoTac) },
          body: JSON.stringify({ thao_tac: "chon-dich-vu", id: l.visit_id, du_lieu: chon }),
        });
        const d = (await r.json().catch(() => null)) as { error?: string; message?: string } | null;
        if (r.ok) {
          xongThaoTac(thaoTac);
          const cau = `Đã chốt dịch vụ của ${l.full_name ?? "khách"} — khách đi làm trước, thu tiền sau (còn nợ ở quầy).`;
          setXong(cau);
          setVuaChot({ visitId: l.visit_id, cau });
        } else {
          setLoi(d?.message ?? d?.error ?? "Không chốt được dịch vụ.");
        }
        await tai();
      } catch {
        setLoi("Mất kết nối — CHƯA chốt được dịch vụ.");
      } finally {
        setDangThu(null);
      }
    },
    [tai],
  );

  /** "Đã nhận tiền" của lần chờ xác minh — cũng là lúc tiền đã đủ. */
  const xacMinh = useCallback(
    async (l: Luot, kind: "dich_vu" | "thuoc", ma: string) => {
      const cau = `Đã xác minh — khoản này đã thu (${l.full_name ?? "khách"}).`;
      const ok = await gui(
        `${l.visit_id}:${kind}`,
        {
          action: "xac-minh",
          // Nhắm ĐÚNG lần thu đang hiện (review CP2 #1).
          paymentCycleId: cho.find((p) => p.visit_id === l.visit_id && p.kind === kind)
            ?.payment_cycle_id,
          visitId: l.visit_id,
          kind,
          quay: quayThu,
          reference: ma,
        },
        cau,
      );
      if (ok) setVuaThu({ visitId: l.visit_id, ten: l.full_name, cau });
    },
    [gui, cho, quayThu],
  );

  if (loi && ds === null) {
    return (
      <section className="rounded-card border border-line bg-surface p-4 shadow-card">
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      </section>
    );
  }
  if (ds === null) return <p className="text-body text-ink-muted">Đang tải…</p>;

  const daThuCua = (visitId: string, kind: string) =>
    daThu.some((p) => p.visit_id === visitId && p.kind === kind);
  const choCua = (visitId: string, kind: string) =>
    cho.find((p) => p.visit_id === visitId && p.kind === kind);

  const choQuyet = (l: Luot) =>
    Boolean(l.chon_dich_vu?.chi_dinh.some((c) => c.selection_status === "PENDING"));
  const conCho = ds.filter(
    (l) =>
      (quay !== "thuoc" &&
        ((l.services.length > 0 && !daThuCua(l.visit_id, "dich_vu")) ||
          choQuyet(l) ||
          // Đã thu đủ nhưng còn TIỀN THỪA (bỏ chỉ định sau khi thu — Khối 2,
          // 06/10/2026): máy chủ xếp lượt vào hàng chờ xử lý (`ds_cho_thu`);
          // thiếu vế này thì khối "Tiền thừa" không bao giờ hiện ở quầy.
          (l.tien_thua?.tong ?? 0) > 0 ||
          // Máy chủ nói lượt còn khoản chờ thu (vd CHỈ có dòng trả trước liệu
          // trình, 08/10/2026 — không có dịch vụ nào trong `services`).
          Boolean(l.cho_thu))) ||
      (quay !== "dich_vu" && l.drugs.length > 0 && !daThuCua(l.visit_id, "thuoc")),
  );

  // "Lượt đã thu xong" chỉ đếm lượt CÓ khoản của quầy này (thuốc và dịch vụ
  // thu riêng hẳn — lượt chỉ có tiền dịch vụ không phải "đã thu xong" ở quầy thuốc).
  const lienQuan = (l: Luot) =>
    (quay !== "thuoc" && (l.services.length > 0 || choQuyet(l))) ||
    (quay !== "dich_vu" && l.drugs.length > 0);
  const daXong = ds.filter((l) => lienQuan(l) && !conCho.includes(l)).length;

  const dangXem = conCho.find((l) => l.visit_id === chonVisit) ?? conCho[0] ?? null;

  const daThuChoPhong =
    quay === "thuoc"
      ? []
      : ds.filter((l) => !conCho.includes(l) && (l.xep_phong?.length ?? 0) > 0);

  return (
    <section className="space-y-3">
      <p className="text-body font-semibold text-ink">
        {conCho.length} khách đang chờ thu
        {daXong > 0 ? (
          <span className="ml-2 font-normal text-meta text-ink-muted">
            ({daXong} lượt đã thu xong)
          </span>
        ) : null}
      </p>

      {loi ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger"
        >
          {loi}
        </p>
      ) : null}
      {xong ? (
        <div className="space-y-2 rounded-control border border-success bg-success-bg px-3 py-2">
          <p className="text-meta text-success">{xong}</p>
          {/* SAU "ĐÃ NHẬN ĐỦ" (27/09/2026, đợt 3): khách thường về ngay sau
              quầy thu — mời check-out tại chỗ thay vì phải nhớ mở màn Check-out.
              CHỈ tài khoản có quyền đóng lượt thấy nút (NutCheckOut tự ẩn). */}
          {vuaThu && vuaThu.cau === xong && phieuVuaThu ? (
            <NutInPhieu href={`/print/phieu-thu/${phieuVuaThu}?loai=thu`} size="md">
              In phiếu thu (có phòng làm dịch vụ)
            </NutInPhieu>
          ) : null}
          {lanVuaGhi && (vuaThu?.cau === xong || xong.startsWith("Đã ghi CHỜ XÁC MINH")) ? (
            <NutHoanTac
              key={lanVuaGhi.cycleId}
              cycleId={lanVuaGhi.cycleId}
              quay={quayThu}
              soTien={lanVuaGhi.soTien || null}
              onXong={(c) => {
                setXong(c);
                setVuaThu(null);
                setLanVuaGhi(null);
                setPhieuVuaThu(null);
                void tai();
              }}
            />
          ) : null}
          {vuaChot && vuaChot.cau === xong ? (
            <NutInPhieu href={`/print/phieu-thu/${vuaChot.visitId}?loai=huong_dan`} size="md">
              In phiếu hướng dẫn phòng (chưa thu tiền)
            </NutInPhieu>
          ) : null}
          {/* SAU "ĐÃ NHẬN ĐỦ": mời check-out. Thuốc và dịch vụ thu RIÊNG HẲN
              (01/10/2026) — quầy này không thu hộ, không hiện nợ của quầy kia;
              nút Check-out tự nhắc nếu khách còn khoản chưa thu. */}
          {vuaThu && vuaThu.cau === xong ? (
            <NutCheckOut
              key={vuaThu.visitId}
              visitId={vuaThu.visitId}
              ten={vuaThu.ten}
              onXong={() => void tai()}
            />
          ) : null}
        </div>
      ) : null}

      {conCho.length === 0 ? (
        <div className="rounded-card border border-line bg-surface p-6 text-center shadow-card">
          <p className="text-body text-ink">Không có ai đang chờ thu.</p>
          <p className="mt-1 text-meta text-ink-muted">
            Khách hiện ở đây ngay khi bác sĩ chỉ định dịch vụ (tiền thuốc: sau khi
            khám xong).
          </p>
        </div>
      ) : (
        <div className="grid items-start gap-3 lg:grid-cols-[minmax(260px,340px)_minmax(0,1fr)]">
          <ul
            aria-label="Khách chờ thu"
            className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
          >
            {conCho.map((l, i) => {
              const on = l.visit_id === dangXem?.visit_id;
              const soTien =
                quay === "thuoc"
                  ? (l.hoa_don?.thuoc?.tong ?? null)
                  : (l.quay_thu?.tong ?? l.hoa_don?.dich_vu?.tong ?? null);
              const xongHet = l.lam_truoc?.nhom === "LAM_XONG_THU_TIEN";
              // Máy chủ đưa lượt "đã làm xong — thu tiền" lên đầu; màn chỉ kẻ
              // tiêu đề nhóm ở dòng đầu mỗi nhóm.
              const dauNhom =
                xongHet && (i === 0 || conCho[i - 1].lam_truoc?.nhom !== "LAM_XONG_THU_TIEN");
              const hetNhom =
                !xongHet && i > 0 && conCho[i - 1].lam_truoc?.nhom === "LAM_XONG_THU_TIEN";
              return (
                <li key={l.visit_id} className="border-b border-line last:border-b-0">
                  {dauNhom || hetNhom ? (
                    <p className="border-b border-line bg-surface-muted px-3 py-1 text-label font-semibold uppercase text-ink-muted">
                      {dauNhom ? "Đã làm xong — thu tiền" : "Khách khác"}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    aria-current={on ? "true" : undefined}
                    onClick={() => setChonVisit(l.visit_id)}
                    className={`flex w-full items-center gap-2.5 border-l-3 px-2.5 py-2.5 text-left ${
                      on ? "border-l-brand-500 bg-surface-selected" : "border-l-transparent hover:bg-surface-sunken"
                    }`}
                  >
                    <SoLuot dang="tron" checkin={l.so_tiep_don} booking={l.so_booking} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-emph font-semibold text-ink">{l.full_name ?? "—"}</span>
                      <span className="block truncate text-meta text-ink-muted">
                        {[l.loai_kham, l.bac_si].filter(Boolean).join(" · ") || (l.patient_code ?? "")}
                      </span>
                      {l.lam_truoc?.lam_truoc_thu_sau ? (
                        <span className="mt-1 flex min-w-0 flex-col items-start gap-0.5">
                          <Chip tone="info">Làm trước – thu sau</Chip>
                          <span className="block max-w-full truncate text-meta text-ink-muted">
                            {[l.lam_truoc.bat_boi, gio(l.lam_truoc.bat_luc)].filter(Boolean).join(" · ")}
                          </span>
                        </span>
                      ) : null}
                    </span>
                    {soTien != null ? (
                      <span className="shrink-0 text-body font-semibold tabular-nums text-ink">{tien(soTien)}</span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        {(dangXem ? [dangXem] : []).map((l) => (
          <article
            key={l.visit_id}
            className="min-w-0 rounded-card border border-line bg-surface shadow-card"
          >
            <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-3">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-1.5 text-body font-semibold text-ink">
                  {l.full_name ?? "—"}
                  <SoLuot booking={l.so_booking} checkin={l.so_tiep_don} />
                </p>
                <p className="text-meta text-ink-muted">{l.patient_code ?? ""}</p>
                {l.lam_truoc?.lam_truoc_thu_sau ? (
                  <p className="mt-1">
                    <Chip tone="info">{nhanLamTruocThuSau(l.lam_truoc)}</Chip>
                  </p>
                ) : null}
              </div>
              {/* Thu xong, máy chủ xếp theo phòng quầy đã chọn (dây H4): lễ tân mở đây để
                  báo khách phòng nào, hoặc đổi sang phòng vắng hơn. */}
              <NutXemLuot visitId={l.visit_id} nhan="Xem hành trình · đổi phòng" />
            </header>

            {/* Tick dịch vụ khám ngay tại quầy khi người khám chưa tick (28/09/2026)
                — máy chủ khoá khi tiền khám đã thu; tự ẩn với lượt đi thẳng phòng. */}
            {quay !== "thuoc" && !daThuCua(l.visit_id, "dich_vu") ? (
              <ChonDichVuKham visitId={l.visit_id} onDoi={() => void tai()} />
            ) : null}
            {/* Mua thêm vật tư (đầu dò Bio chọn nhanh, tìm theo tên) — vào hoá đơn
                DỊCH VỤ, KHÔNG có ở quầy thuốc (C13, 01/10/2026). */}
            {quay !== "thuoc" && !daThuCua(l.visit_id, "dich_vu") ? (
              <VatTuQuay
                visitId={l.visit_id}
                reloadToken={l.quay_thu?.revision}
                onDoi={tai}
                onDangLuu={(dang) =>
                  setVatTuDangLuu((cu) => {
                    const moi = new Set(cu);
                    if (dang) moi.add(l.visit_id);
                    else moi.delete(l.visit_id);
                    return moi;
                  })
                }
              />
            ) : null}
            {/* LIỆU TRÌNH (08/10/2026): trả trước … buổi / trả hết → dòng vào hoá
                đơn đang thu (máy chủ tính tối đa, tiền). */}
            {quay !== "thuoc" && !daThuCua(l.visit_id, "dich_vu") ? (
              <LieuTrinhQuay visitId={l.visit_id} reloadToken={l.quay_thu?.revision} onDoi={() => void tai()} />
            ) : null}
            {quay !== "thuoc" &&
            l.quay_thu &&
            !daThuCua(l.visit_id, "dich_vu") &&
            !choCua(l.visit_id, "dich_vu") ? (
              <HoaDonMot
                key={`${l.visit_id}:${l.quay_thu.lua_chon.order_ids_seen.join(",")}:${l.quay_thu.lua_chon.revision}`}
                visitId={l.visit_id}
                lamTruoc={l.lam_truoc}
                qt={l.quay_thu}
                dangThu={dangThu === `${l.visit_id}:dich_vu`}
                dangLuuVatTu={vatTuDangLuu.has(l.visit_id)}
                onThu={(p) => void thuMot(l, p)}
                onChotThuSau={(c) => void chotThuSau(l, c)}
                onDoiPhong={() => void tai()}
              />
            ) : (
            <>
            {quay !== "thuoc" && l.chon_dich_vu ? (
              <ChonDichVu
                // Danh sách chỉ định đổi thì dựng lại ô để lấy mặc định mới. KHÔNG
                // gắn revision: mỗi lần tick là một lần lưu (revision tăng) — dựng
                // lại sẽ thu gọn ô giữa lúc lễ tân đang bỏ tick tiếp.
                key={`${l.visit_id}:${l.chon_dich_vu.chi_dinh.map((c) => c.id).join(",")}`}
                visitId={l.visit_id}
                cho={l.chon_dich_vu}
                onXong={async (cau, loiMoi) => {
                  setXong(cau);
                  setLoi(loiMoi);
                  await tai();
                }}
              />
            ) : null}

            {quay !== "thuoc" && l.services.length > 0 ? (
              <NhomThu
                quay="dich_vu"
                tieu_de="Tiền dịch vụ"
                hd={l.hoa_don?.dich_vu}
                daThu={daThuCua(l.visit_id, "dich_vu")}
                cho={choCua(l.visit_id, "dich_vu")}
                dangThu={dangThu === `${l.visit_id}:dich_vu`}
                onThu={(hd, c) => void thu(l, "dich_vu", hd, c)}
                onXacMinh={(ma) => void xacMinh(l, "dich_vu", ma)}
                onDoi={(cau) => {
                  if (cau) setXong(cau);
                  void tai();
                }}
              />
            ) : null}
            </>
            )}

            {quay !== "thuoc" && l.lam_truoc?.dich_vu?.length ? <DichVuLamTruocKhoi ds={l.lam_truoc.dich_vu} /> : null}

            {l.tien_thua && l.tien_thua.tong > 0 ? (
              <TienThuaKhoi tt={l.tien_thua} visitId={l.visit_id} onDoi={() => void tai()} />
            ) : null}

            {quay !== "thuoc" && l.da_bo_chi_dinh?.length ? <DaBoChiDinhKhoi ds={l.da_bo_chi_dinh} /> : null}

            {quay !== "thuoc" ? (
              <XepPhongDaThu
                ds={l.xep_phong ?? []}
                onDoi={() => void tai()}
                visitId={l.visit_id}
              />
            ) : null}

            {/* CHỈNH ĐƠN BÁN trước khi thu (Tuyền 24/09/2026): tích / bỏ tick,
                số lượng, lấy thêm thuốc. Thu rồi (hoặc đang chờ xác minh) thì
                khoá — huỷ phiếu thu trước rồi mới chỉnh. */}
            {quay !== "dich_vu" &&
            l.drugs.length > 0 &&
            !daThuCua(l.visit_id, "thuoc") &&
            !choCua(l.visit_id, "thuoc") ? (
              <ChinhDonQuay
                visitId={l.visit_id}
                onDoi={async (cau, loiMoi) => {
                  setXong(cau);
                  setLoi(loiMoi);
                  await tai();
                }}
              />
            ) : null}

            {quay !== "dich_vu" && l.drugs.length > 0 ? (
              <NhomThu
                quay="thuoc"
                tieu_de="Thuốc đã kê"
                hd={l.hoa_don?.thuoc}
                daThu={daThuCua(l.visit_id, "thuoc")}
                cho={choCua(l.visit_id, "thuoc")}
                dangThu={dangThu === `${l.visit_id}:thuoc`}
                onThu={(hd, c) => void thu(l, "thuoc", hd, c)}
                onXacMinh={(ma) => void xacMinh(l, "thuoc", ma)}
                onDoi={(cau) => {
                  if (cau) setXong(cau);
                  void tai();
                }}
              />
            ) : null}
          </article>
        ))}
        </div>
      )}

      {/* Thu đủ rồi thì lượt rời danh sách chờ thu — nhưng khách chưa vào phòng
          vẫn cần chỗ để xếp / đổi phòng (Tuyền 24/09/2026). */}
      {daThuChoPhong.length > 0 ? (
        <div className="space-y-3">
          <p className="text-body font-semibold text-ink">
            Đã thu — chờ vào phòng ({daThuChoPhong.length})
          </p>
          {daThuChoPhong.map((l) => (
            <article
              key={l.visit_id}
              className="rounded-card border border-line bg-surface shadow-card"
            >
              <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-3">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-1.5 text-body font-semibold text-ink">
                    {l.full_name ?? "—"}
                    <SoLuot booking={l.so_booking} checkin={l.so_tiep_don} />
                  </p>
                  <p className="text-meta text-ink-muted">{l.patient_code ?? ""}</p>
                </div>
                <NutXemLuot visitId={l.visit_id} nhan="Xem hành trình" />
              </header>
              <XepPhongDaThu
                ds={l.xep_phong ?? []}
                onDoi={() => void tai()}
                visitId={l.visit_id}
              />
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

/** TIỀN THỪA (hoàn tác chỉ định đã thu, 01/10/2026): khoản đã thu cho dịch vụ
 *  nay đã bỏ / không làm. Quầy KHÔNG tự trả: hoàn cho khách (Hoàn tiền / Huỷ
 *  phiếu ở tab "Đã thanh toán hôm nay") hoặc trừ vào dịch vụ khác khi thu. Số
 *  tiền máy chủ tính, màn chỉ vẽ. */
function TienThuaKhoi({
  tt,
  visitId,
  onDoi,
}: {
  tt: TienThua;
  visitId: string;
  onDoi: () => void;
}) {
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // HOÀN TIỀN THỪA (06/10/2026, E2b): máy hoàn ĐÚNG số còn thừa (tiền mặt) —
  // không gõ số. Ai có lego Thu tiền dịch vụ; máy chủ kiểm lại.
  const hoan = async () => {
    setDang(true);
    setLoi(null);
    try {
      const r = await fetch("/api/reception/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hanh_dong: "hoan_tien_thua", visit_id: visitId }),
      });
      const d = (await r.json().catch(() => null)) as { ok?: boolean } | null;
      if (!r.ok || !d?.ok) setLoi(loiDocDuoc(d, `Chưa hoàn được (HTTP ${r.status}).`));
      else onDoi();
    } catch {
      setLoi("Mất kết nối — chưa hoàn.");
    } finally {
      setDang(false);
    }
  };
  return (
    <div className="border-b border-line bg-warning-bg px-4 py-3">
      <p className="text-body font-semibold text-warning">
        Tiền thừa {tien(tt.tong)} — cần hoàn cho khách hoặc chuyển sang dịch vụ khác
      </p>
      <ul className="mt-1 divide-y divide-line">
        {tt.dong.map((d) => (
          <li
            key={d.order_id ?? d.line_id ?? d.ten ?? ""}
            className="flex flex-wrap items-center justify-between gap-2 py-1.5"
          >
            <span className="flex min-w-0 flex-wrap items-center gap-2 text-body text-ink">
              {d.ten ?? "—"}
              <Chip tone="warning">
                {d.loai === "BO_CHI_DINH"
                  ? "Đã bỏ chỉ định"
                  : d.loai === "BO_DICH_VU_KHAM"
                    ? "Đã bỏ dịch vụ khám"
                    : "Không làm"}
              </Chip>
              {d.ly_do ? <span className="text-meta text-ink-muted">{d.ly_do}</span> : null}
            </span>
            <span className="shrink-0 text-body tabular-nums text-ink">{tien(d.so_tien)}</span>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="primary" disabled={dang} onClick={() => void hoan()}>
          {dang ? "Đang hoàn…" : `Hoàn tiền thừa ${tien(tt.tong)} (tiền mặt)`}
        </Button>
        {loi ? (
          <span role="alert" className="text-meta text-danger">
            {loi}
          </span>
        ) : null}
      </div>
      <p className="mt-1 text-meta text-ink-muted">
        Máy hoàn đúng số còn thừa của từng dòng. Hoàn chuyển khoản: tab “Đã thanh toán hôm nay”.
        Khách không lấy lại: lúc check-out chọn “Giữ lại” và ghi lý do. Máy không tự trừ tiền
        thừa vào dịch vụ khác — thu dịch vụ mới đủ số, rồi hoàn khoản thừa.
      </p>
    </div>
  );
}

/** Chỉ định đã xoá (06/10/2026 — Tuyền: "không biến mất im lặng"): gạch
 *  ngang, lần mấy, ai xoá + lúc nào, đã thu chưa. Máy chủ viết câu, màn chỉ vẽ. */
function DaBoChiDinhKhoi({ ds }: { ds: DaBoChiDinh[] }) {
  return (
    <div className="border-b border-line px-4 py-3">
      <p className="text-label font-semibold uppercase text-ink-muted">Chỉ định đã xoá</p>
      <ul className="mt-1 divide-y divide-line">
        {ds.map((d) => (
          <li key={d.so_id} className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 py-1.5">
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-body text-ink-faint line-through">{d.ten ?? "—"}</span>
                {d.lan ? <Chip tone="neutral">Lần {d.lan}</Chip> : null}
                <Chip tone="danger">Đã xoá</Chip>
              </span>
              <span className="block text-meta text-ink-muted">
                {d.cau}
                {gio(d.luc) ? ` · ${gio(d.luc)}` : ""}
                {d.ly_do ? ` · Lý do: ${d.ly_do}` : ""}
              </span>
            </span>
            <span className="shrink-0 text-right text-meta tabular-nums text-ink-muted">
              {d.da_thu > 0
                ? `đã thu ${tien(d.da_thu)} → tiền thừa ${tien(d.tien_thua)}`
                : d.gia != null
                  ? `${tien(d.gia)} · không thu`
                  : "không thu"}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-meta text-ink-muted">
        Có vật tư mua thêm đi kèm dịch vụ đã xoá thì kiểm lại ở khối “Mua thêm vật tư” — máy
        không tự bỏ vật tư.
      </p>
    </div>
  );
}

/** Lượt "Làm trước – thu sau": từng dịch vụ Đã làm xong / Đang làm / Chưa làm
 *  + số tiền còn nợ — máy chủ tính, màn chỉ vẽ. */
function DichVuLamTruocKhoi({ ds }: { ds: DichVuLamTruoc[] }) {
  return (
    <div className="border-b border-line px-4 py-3">
      <p className="text-label font-semibold uppercase text-ink-muted">Làm trước – thu sau</p>
      <ul className="mt-2 divide-y divide-line">
        {ds.map((d) => (
          <li key={d.id} className="flex flex-wrap items-center justify-between gap-2 py-1.5">
            <span className="flex min-w-0 flex-wrap items-center gap-2 text-body text-ink">
              {d.ten ?? "—"}
              <Chip tone={TONE_DV[d.trang_thai]}>{d.nhan}</Chip>
            </span>
            <span className="shrink-0 text-body tabular-nums text-ink">
              {d.con_no ? `còn nợ ${tien(d.con_no)}` : <span className="text-ink-faint">—</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Khối thu MỘT khoản — dùng lại ở Nhà thuốc cho lượt Bán lẻ (V8, `pharmacy/BanLeThu`).
export function NhomThu({
  quay,
  tieu_de,
  hd,
  daThu,
  cho,
  dangThu,
  onThu,
  onXacMinh,
  onDoi,
}: {
  /** Loại tiền của khối — gửi kèm lệnh hoàn tác để máy chủ gác quầy (01/10/2026). */
  quay?: "dich_vu" | "thuoc";
  tieu_de: string;
  hd: HoaDon | undefined;
  daThu: boolean;
  cho: ChoXacMinh | undefined;
  dangThu: boolean;
  onThu: (hd: HoaDon, chia: KetQuaChia) => void;
  onXacMinh: (ma: string) => void;
  /** Sau hoàn tác / thêm ảnh: tải lại (kèm câu báo nếu có). */
  onDoi: (cau?: string) => void;
}) {
  const [chia, setChia] = useState<KetQuaChia | null>(null);
  const [ma, setMa] = useState("");
  if (cho) {
    // CHỜ XÁC MINH: bấm "Đã nhận tiền" là xong. Mã giao dịch TUỲ CHỌN (Tuyền
    // 24/09/2026: "không được bắt buộc điền mã mới cho thanh toán xong, open đi").
    return (
      <div className="border-b border-line px-4 py-3 last:border-b-0">
        <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
          {tieu_de}
        </p>
        <p className="mt-2 text-body text-warning">
          {nhanPhan(cho.phan) || tenHinhThuc(cho.phuong_thuc)} · tổng {tien(cho.so_tien)} — CHỜ XÁC
          MINH chuyển khoản, chưa tính là đã thu.
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            value={ma}
            onChange={(e) => setMa(e.target.value)}
            placeholder="Mã giao dịch (không bắt buộc)"
            aria-label="Mã giao dịch ngân hàng (không bắt buộc)"
            className="min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink"
          />
          <button
            type="button"
            disabled={dangThu}
            onClick={() => onXacMinh(ma.trim())}
            className="inline-flex min-h-10 items-center rounded-control border border-brand-500 bg-brand-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            Đã nhận tiền
          </button>
        </div>
        <AnhChuyenKhoan cycleId={cho.payment_cycle_id} ds={cho.anh_ck} onDoi={() => onDoi()} />
        {/* Khách không chuyển / chuyển sai / ghi nhầm hình thức → HOÀN TÁC (lý do
            không bắt buộc), rồi thu lại. Thay "Huỷ lần chờ" bắt gõ lý do. */}
        <div className="mt-2">
          <NutHoanTac cycleId={cho.payment_cycle_id} soTien={cho.so_tien} quay={quay} onXong={onDoi} />
        </div>
      </div>
    );
  }
  return (
    <div className="border-b border-line px-4 py-3 last:border-b-0">
      <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
        {tieu_de}
      </p>
      {hd?.chi_doi_tac_thu ? (
        <p className="mt-2 text-meta text-ink-muted">
          Phòng khám không còn khoản nào — dịch vụ dưới đây là thu hộ đối tác.
        </p>
      ) : daThu ? (
        <p className="mt-2 text-meta text-ink-muted">Không còn khoản nào phải thu.</p>
      ) : !hd ? (
        <p className="mt-2 text-meta text-ink-muted">Đang tính hoá đơn…</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {hd.dong.map((d) => (
            <li key={d.source_id} className="flex flex-wrap items-baseline justify-between gap-x-3">
              <span className="min-w-0 text-body text-ink">
                {d.ten}
                {d.so_luong !== 1 || d.don_vi ? (
                  <span className="text-ink-muted">
                    {" "}
                    × {d.so_luong.toLocaleString("vi-VN")}
                    {d.don_vi ? ` ${d.don_vi}` : ""}
                    {d.don_gia !== null ? ` × ${tien(d.don_gia)}` : ""}
                  </span>
                ) : null}
                {d.ben_thu === "EXTERNAL_PARTNER" ? (
                  <span className="text-meta text-ink-muted"> · đối tác tự thu, không cộng</span>
                ) : null}
              </span>
              <span
                className={
                  d.van_de
                    ? "w-full text-meta text-warning"
                    : "shrink-0 text-body tabular-nums text-ink"
                }
              >
                {d.van_de ?? (d.thanh_tien !== null ? tien(d.thanh_tien) : "—")}
              </span>
            </li>
          ))}
        </ul>
      )}

      {hd && (hd.dong_doi_tac?.length ?? 0) > 0 ? (
        <DongDoiTacThu ds={hd.dong_doi_tac ?? []} />
      ) : null}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <div>
          <p className="text-body font-semibold text-ink">
            Tổng: <span className="tabular-nums">{hd ? tien(hd.tong) : "—"}</span>
          </p>
          {hd && hd.van_de.length > 0 ? (
            // KHÔNG cho bấm thu khi còn dòng chưa thu được (thiếu giá, giá mâu
            // thuẫn, chưa xác định thuốc kho): máy chủ cũng từ chối y như vậy.
            <p className="text-meta text-warning">
              {hd.van_de.length} dòng chưa thu được — xem lý do từng dòng.
            </p>
          ) : null}
        </div>
        {daThu || hd?.chi_doi_tac_thu ? (
          <span className="inline-flex min-h-10 items-center rounded-control border border-success bg-success-bg px-4 text-sm font-semibold text-success">
            {hd?.chi_doi_tac_thu ? "Không còn khoản thu" : "Đã thu"}
          </span>
        ) : (
          <button
            type="button"
            disabled={dangThu || !hd || !hd.thu_duoc || !chia?.hopLe}
            onClick={() => hd && chia && onThu(hd, chia)}
            className="inline-flex min-h-10 items-center rounded-control border border-brand-500 bg-brand-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {dangThu
              ? "Đang ghi…"
              : chia?.coChuyenKhoan
                ? "Ghi · chờ xác minh CK"
                : "Đã nhận đủ tiền mặt"}
          </button>
        )}
      </div>
      {hd && hd.thu_duoc && !daThu && !hd.chi_doi_tac_thu ? (
        <div className="mt-3">
          <ChiaHinhThuc key={hd.revision} tong={hd.tong} onDoi={setChia} />
        </div>
      ) : null}
    </div>
  );
}

/** Dịch vụ khách trả TRỰC TIẾP cho đối tác (Tuyền chốt 27/09/2026): hiện giá
 *  tham khảo + đối tác đã thu hay chưa. Không cộng vào tổng — máy chủ đã tách
 *  (`dong_doi_tac`), màn chỉ đọc. */
function DongDoiTacThu({ ds }: { ds: DongDoiTac[] }) {
  return (
    <div className="mt-2 rounded-control bg-surface-muted px-3 py-2">
      <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
        Thu hộ đối tác — không cộng
      </p>
      <ul className="mt-1 space-y-1">
        {ds.map((d) => (
          <li key={d.source_id} className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="min-w-0 text-body text-ink">
              {d.ten}
              <span className="ml-2">
                {d.doi_tac_da_thu ? (
                  <Chip tone="success">Đã thu hộ cho đối tác {tien(d.doi_tac_da_thu.so_tien)}</Chip>
                ) : (
                  <Chip tone="neutral">Chưa thu hộ cho đối tác</Chip>
                )}
              </span>
            </span>
            <span className="shrink-0 text-meta tabular-nums text-ink-muted">
              {d.thanh_tien !== null ? `tham khảo ${tien(d.thanh_tien)}` : "chưa có giá"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
