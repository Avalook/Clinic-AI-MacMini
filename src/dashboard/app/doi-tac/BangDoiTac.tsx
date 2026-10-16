"use client";

// BÀN CỦA ĐỐI TÁC — "Việc của đối tác".
//
// CÙNG KHUÔN, CÙNG THÀNH PHẦN với phòng dịch vụ `/phong/[ma]` (Tuyền 16/10/2026:
// "bê form sang, sao để mỗi chỗ một kiểu, sửa khó hơn"): đầu trang (tiêu đề +
// dòng đếm, thanh ngày, ô tìm `OTimKhach`), cột trái là thẻ khách
// `TheKhachHangCho` theo nhóm, khung phải là thẻ dịch vụ `TheDichVu` + ô tệp
// `KhungTep` + khối `KhoiViecDoiTac` — đúng những thứ Phòng đối tác dùng. Sửa
// một chỗ là cả hai đổi. KHÔNG vẽ thẻ riêng ở đây.
//
// Bàn đón NGƯỜI, không đón việc: một khách lấy máu có thể mang hai ba chỉ định,
// mỗi chỉ định một thẻ dịch vụ bên phải. Không có ô "chọn bệnh nhân": đối tác chỉ
// nói "đây là kết quả của việc này", việc ấy của ai do máy chủ tra — thiếu ràng
// buộc đó thì tài khoản ngoài phòng khám gửi được tệp cho bất kỳ ai.
//
// Ba nhóm: Chờ làm → Đã nhận mẫu · chờ kết quả → Có kết quả. NHẬN MẪU LÀ XONG
// (Tuyền 29/09/2026); kết quả tải / điền phiếu lúc nào cũng được rồi [Trả kết
// quả]. Ngày cũ vẫn tải thêm tệp / Nhận mẫu / Trả kết quả được (máy chủ ghi giờ
// thật). Nút nào hiện là cờ máy chủ; mọi lệnh đi `/api/doi-tac/*`.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Inbox } from "lucide-react";

import Chip from "@/components/ui/Chip";
import OTimKhach from "@/components/ui/OTimKhach";
import ThanhNgay from "@/components/ui/ThanhNgay";
import ThongBaoHoanTac, { type ThongBao } from "@/components/ui/ThongBaoHoanTac";
import { tienVn } from "@/lib/phieu-kham";
import { ngayNgan } from "@/lib/thanh-ngay";
import { khopTimKhach } from "@/lib/tim-khach-phong";
import { homNayVn } from "@/lib/validation";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";
import { gioVn, soPhutTu } from "../(dashboard)/_lam-viec/api";
import KhungTep, { type TepDoiTac } from "../(dashboard)/_lam-viec/KhungTep";
import {
  KhoiViecDoiTac,
  guiLenhDoiTac,
  hoanTacDoiTac,
  XONG_DOI_TAC as XONG,
  type TrangThaiDoiTac as TrangThai,
  type ViecDoiTacChung,
} from "../(dashboard)/_lam-viec/KhoiDoiTac";
import TheDichVu from "../(dashboard)/_lam-viec/TheDichVu";
import TheKhachHangCho, { NhomHangCho } from "../(dashboard)/_lam-viec/TheKhachHangCho";
import { EmptyWorkspace } from "../(dashboard)/tasks/WorkspacePrimitives";

interface Viec extends ViecDoiTacChung {
  chi_dinh_luc: string | null;
  lay_mau_luc: string | null;
  ma_kiotviet?: string | null;
  /** LỊCH SỬ các lần tải tệp của việc này — cũ trước. */
  tep?: TepDoiTac[];
  /** Mẫu lấy ở phòng của phòng khám, gửi sang đối tác (29/09/2026). */
  mau_gui_doi_tac?: boolean;
}

interface Khach {
  clinic_patient_id: string;
  ten_khach: string;
  ma_khach: string;
  /** Số check-in / số booking của lượt mới nhất (thẻ khách chung với phòng). */
  so_tiep_don?: number | null;
  so_booking?: number | null;
  cho_tu: string | null;
  viec: Viec[];
}

interface DanhSach {
  khach: Khach[];
  /** Ngày máy chủ đã xem (YYYY-MM-DD) — ngày rác thì máy chủ trả hôm nay. */
  ngay: string;
  hom_nay: boolean;
  /** Máy chủ cho người này MỞ tệp (xem / in / tải) không. */
  xem_tep: boolean;
}

type KetQua = DanhSach | { loi: string };

/** Giờ + ngày một lần ("15:30 16/10") — không in lặp giờ hai lần. */
function ngayGio(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

/** Mốc gần nhất của việc — mẩu cuối của dòng "mã · giá · mốc" trên thẻ. */
function mocViec(v: Viec): string {
  switch (v.trang_thai) {
    case "DA_GUI_KET_QUA":
      return v.cho_tai_lieu_luc
        ? `Đã nhận mẫu ${ngayGio(v.cho_tai_lieu_luc)} · có kết quả ${ngayGio(v.ket_qua_luc)}`
        : `Có kết quả ${ngayGio(v.ket_qua_luc)}`;
    case "DA_NHAN_MAU":
      return `Đã nhận mẫu ${ngayGio(v.cho_tai_lieu_luc)}`;
    case "DA_LAY_MAU":
      return `Phòng khám gửi mẫu lúc ${ngayGio(v.lay_mau_luc)}`;
    default:
      return `Phòng khám gửi lúc ${ngayGio(v.chi_dinh_luc)}`;
  }
}

// Đọc danh sách — KHÔNG đụng state: lần tải đầu chạy trong effect và phải bỏ
// kết quả nếu người dùng đã rời màn, còn lần tải lại sau khi bấm thì luôn nhận.
async function docDanhSach(ngay: string): Promise<KetQua> {
  try {
    const r = await fetch(`/api/doi-tac?ngay=${encodeURIComponent(ngay)}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | (Partial<DanhSach> & { error?: string; message?: string })
      | null;
    if (!r.ok) return { loi: d?.message ?? d?.error ?? "Không đọc được danh sách khách." };
    return {
      khach: d?.khach ?? [],
      ngay: d?.ngay ?? ngay,
      hom_nay: d?.hom_nay ?? true,
      xem_tep: d?.xem_tep ?? false,
    };
  } catch {
    return { loi: "Mất kết nối tới máy chủ." };
  }
}

// Nhóm cột trái theo BƯỚC CHƯA XONG sớm nhất của khách. Chưa nhận mẫu là MỘT
// nhóm "Chờ làm" — mẫu điều dưỡng đã lấy cũng chờ đối tác nhận.
const NHOM: { ma: TrangThai; ten: string }[] = [
  { ma: "CHO_LAY_MAU", ten: "Chờ làm" },
  { ma: "DA_NHAN_MAU", ten: "Đã nhận mẫu · chờ kết quả" },
  { ma: "DA_GUI_KET_QUA", ten: "Có kết quả" },
];
const THU_TU: Record<TrangThai, number> = {
  CHO_LAY_MAU: 0,
  DA_LAY_MAU: 0,
  DA_NHAN_MAU: 2,
  DA_GUI_KET_QUA: 3,
};
/** Khách đứng ở nhóm của việc CHƯA XONG sớm nhất; xong hết → nhóm xong. */
function buocCua(k: Khach): TrangThai {
  const tt = k.viec.reduce<TrangThai>(
    (m, v) => (THU_TU[v.trang_thai] < THU_TU[m] ? v.trang_thai : m),
    "DA_GUI_KET_QUA",
  );
  return tt === "DA_LAY_MAU" ? "CHO_LAY_MAU" : tt;
}

/** Giờ bên phải thẻ khách: đang chờ → đã chờ bao lâu; xong → giờ mốc cuối. */
function gioThe(k: Khach, xong: boolean): string {
  if (!xong) return soPhutTu(k.cho_tu);
  const moc = k.viec
    .map((v) => v.ket_qua_luc ?? v.cho_tai_lieu_luc)
    .filter((x): x is string => Boolean(x))
    .sort();
  return moc.length > 0 ? gioVn(moc[moc.length - 1]) : "";
}

const chuThuong = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

export default function BangDoiTac() {
  const [ds, setDs] = useState<Khach[] | null>(null);
  const [homNay] = useState(homNayVn);
  const [ngay, setNgay] = useState(homNay);
  const [xemNgay, setXemNgay] = useState<{ ngay: string; homNay: boolean; xemTep: boolean }>({
    ngay: homNay,
    homNay: true,
    xemTep: false,
  });
  const [dangDoi, setDangDoi] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangLam, setDangLam] = useState<string | null>(null);
  const [chonId, setChonId] = useState<string | null>(null);
  const [tim, setTim] = useState("");
  // Thông báo kèm Hoàn tác như phòng dịch vụ (16/10/2026: dòng xanh cố định
  // trên đầu giữ nguyên câu "Đã nhận mẫu…" sau khi bấm bước khác).
  const [thongBao, setThongBao] = useState<ThongBao | null>(null);
  const dongThongBao = useCallback(() => setThongBao(null), []);

  const nhan = useCallback((kq: KetQua) => {
    if ("loi" in kq) {
      setLoi(kq.loi);
      return;
    }
    setLoi(null);
    setDs(kq.khach);
    setXemNgay({ ngay: kq.ngay, homNay: kq.hom_nay, xemTep: kq.xem_tep });
  }, []);

  const tai = useCallback(async () => {
    nhan(await docDanhSach(ngay));
  }, [nhan, ngay]);

  useEffect(() => {
    let huy = false;
    const doc = () =>
      void docDanhSach(ngay).then((kq) => {
        if (huy) return;
        nhan(kq);
        setDangDoi(false);
      });
    doc();
    // Phòng khám chỉ định liên tục — không bắt đối tác tải lại trang. Tab ẩn
    // thì huỷ hẳn nhịp; hiện lại thì đọc một lần ngay.
    const goNhip = nhipKhiHien(doc, 20000);
    return () => {
      huy = true;
      goNhip();
    };
  }, [nhan, ngay]);

  const theoNhom = useMemo(
    () => NHOM.map((n) => ({ ...n, khach: (ds ?? []).filter((k) => buocCua(k) === n.ma) })),
    [ds],
  );

  const nhanMau = useCallback(
    async (v: Viec, k: Khach, ghiChu: string) => {
      setDangLam(v.chi_dinh_id);
      setLoi(null);
      const kq = await guiLenhDoiTac("/api/doi-tac/cho-tai-lieu", {
        chi_dinh_id: v.chi_dinh_id,
        ghi_chu: ghiChu.trim() || undefined,
      });
      if (kq.loi) setLoi(kq.loi);
      else
        setThongBao({
          cau: `Đã nhận mẫu ${v.ten_dich_vu} — ${k.ten_khach}`,
          goi: hoanTacDoiTac("huy-nhan-mau", v.chi_dinh_id),
        });
      await tai();
      setDangLam(null);
    },
    [tai],
  );

  if (loi && ds === null) {
    return (
      <p role="alert" className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-body text-danger">
        {loi}
      </p>
    );
  }
  if (ds === null) {
    return <p className="text-body text-ink-muted">Đang tải…</p>;
  }

  // Mặc định chọn khách đầu tiên còn việc dở; khách vừa chọn biến mất (bị huỷ)
  // thì rơi về mặc định — không để khung phải trỏ vào khoảng không.
  const macDinh = theoNhom.find((n) => !XONG.has(n.ma) && n.khach.length > 0)?.khach[0];
  const chon = ds.find((k) => k.clinic_patient_id === chonId) ?? macDinh ?? null;
  const conDo = theoNhom[0].khach.length;
  // Ô tìm chỉ lọc HIỂN THỊ cột trái (như phòng) — khách đang mở, số đếm giữ nguyên.
  const khop = (k: Khach) =>
    khopTimKhach(tim, { ten: k.ten_khach, ma: k.ma_khach, so: [k.so_tiep_don, k.so_booking] });
  const khongKhop = tim !== "" && ds.length > 0 && !ds.some(khop);

  return (
    <div className="grid gap-4">
      <ThongBaoHoanTac thongBao={thongBao} onDong={dongThongBao} onHoanTacXong={() => void tai()} />
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-title font-semibold text-ink">Việc của đối tác</h1>
        {/* Cùng kiểu dòng đếm của phòng — số KHÁCH mỗi nhóm cột trái. */}
        <p className="text-body tabular-nums text-ink-muted">
          {theoNhom.map((n) => `${n.khach.length} ${chuThuong(n.ten)}`).join(" · ")}
        </p>
        {loi ? (
          <p role="alert" className="text-body text-danger">
            {loi}
          </p>
        ) : null}
      </header>

      <ThanhNgay
        motNgay
        nhan="Xem việc theo ngày"
        khoang={{ tu: ngay, den: ngay }}
        homNay={homNay}
        soNgaySau={0}
        dangTai={dangDoi}
        onChon={(k) => {
          const moi = k?.den ?? homNay;
          if (moi === ngay) return;
          setDangDoi(true);
          setChonId(null);
          setNgay(moi);
        }}
      />
      {!xemNgay.homNay ? (
        <p className="rounded-control border border-warning bg-warning-bg px-3 py-2 text-body text-warning">
          Đang xem ngày {ngayNgan(xemNgay.ngay)} — vẫn tải tệp, Nhận mẫu, Trả kết quả được; hệ
          thống ghi giờ thật lúc bấm.
        </p>
      ) : null}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(15rem,0.6fr)_minmax(0,1.8fr)]">
        <aside aria-label="Hàng chờ của đối tác" className="space-y-3">
          <OTimKhach value={tim} onChange={setTim} nhan="Tìm khách của đối tác" />
          {khongKhop ? (
            <p className="text-body text-ink-muted">Không có khách nào khớp “{tim}”.</p>
          ) : null}
          {ds.length === 0 ? (
            <p className="rounded-card border border-line bg-surface p-4 text-sm text-ink-muted">
              {xemNgay.homNay
                ? "Chưa có khách nào được gửi sang."
                : "Ngày này không có việc đối tác nào."}
            </p>
          ) : (
            <div className="space-y-3">
              {theoNhom.map((n) => {
                const hien = n.khach.filter(khop);
                if (hien.length === 0) return null;
                const xong = XONG.has(n.ma);
                return (
                  <NhomHangCho key={n.ma} ten={n.ten} so={hien.length}>
                    {hien.map((k) => (
                      <TheKhachHangCho
                        key={k.clinic_patient_id}
                        so={k.so_tiep_don ?? null}
                        ten={k.ten_khach}
                        soBooking={k.so_booking ?? null}
                        phu={`${k.viec.length} chỉ định`}
                        gio={gioThe(k, xong)}
                        dangChon={chon?.clinic_patient_id === k.clinic_patient_id}
                        mo={xong}
                        onChon={() => {
                          setChonId(k.clinic_patient_id);
                          // Màn hẹp: khung khách nằm DƯỚI danh sách — tự cuộn tới.
                          if (window.innerWidth < 1024) {
                            requestAnimationFrame(() =>
                              document
                                .getElementById("khung-khach-doi-tac")
                                ?.scrollIntoView({ block: "start" }),
                            );
                          }
                        }}
                      />
                    ))}
                  </NhomHangCho>
                );
              })}
            </div>
          )}
        </aside>

        {chon ? (
          <div id="khung-khach-doi-tac" className="min-w-0 space-y-4">
            {[...chon.viec]
              .sort((x, y) => THU_TU[x.trang_thai] - THU_TU[y.trang_thai])
              .map((v) => (
                <TheDichVu
                  key={v.chi_dinh_id}
                  nhan={`${v.ten_dich_vu} — ${chon.ten_khach}`}
                  so={chon.so_tiep_don ?? null}
                  ten={v.ten_dich_vu}
                  moc={[v.ma_kiotviet ?? null, tienVn(v.gia_tham_khao), mocViec(v)]}
                  khach={chon.ten_khach}
                  maKhach={chon.ma_khach}
                  duoiKhach={
                    v.mau_gui_doi_tac ? (
                      <Chip tone="info" className="mt-1" title="Mẫu lấy ở phòng của phòng khám, gửi sang đối tác">
                        Mẫu gửi đối tác
                      </Chip>
                    ) : null
                  }
                  // In phiếu cần mở được tệp — vai đối tác bên ngoài không có.
                  inHref={xemNgay.xemTep ? `/print/ket-qua/${v.chi_dinh_id}` : null}
                >
                  <KhungTep
                    clinicPatientId={chon.clinic_patient_id}
                    serviceOrderId={v.chi_dinh_id}
                    tieuDe="Ảnh · video · phiếu kết quả"
                    cuaDoiTac={{ tep: v.tep ?? [], xemTep: xemNgay.xemTep }}
                    onDaTaiLen={() => void tai()}
                  />
                  <KhoiViecDoiTac
                    viec={v}
                    nhanMau={{
                      nhan: "Nhận mẫu",
                      dangGui: dangLam === v.chi_dinh_id,
                      onBam: (g) => void nhanMau(v, chon, g),
                    }}
                    ketQua
                    duongPhieu="/api/doi-tac/phieu"
                    onDoi={() => void tai()}
                    onBao={setThongBao}
                  />
                </TheDichVu>
              ))}
          </div>
        ) : (
          <section className="rounded-card bg-surface p-4 shadow-card">
            <EmptyWorkspace
              title={conDo === 0 ? "Không có việc nào đang chờ" : "Chọn một khách trong hàng chờ"}
              detail="Phòng khám chỉ định xét nghiệm / chụp chiếu gửi sang thì khách hiện ở đây."
              icon={<Inbox className="size-7" />}
            />
          </section>
        )}
      </div>
    </div>
  );
}
