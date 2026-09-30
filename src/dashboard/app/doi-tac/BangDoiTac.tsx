"use client";

// Bàn của đối tác: DANH SÁCH KHÁCH, mỗi khách một thẻ, dưới là việc của họ.
//
// Bản đầu liệt kê chỉ định phẳng — mỗi việc một dòng. Tuyền bác đúng: bàn đón
// NGƯỜI, không đón việc. Một khách tới lấy máu có thể mang hai ba chỉ định, và
// danh sách phẳng làm cùng một người hiện ba dòng cách xa nhau, đúng lúc người
// ngồi bàn đang cầm ống nghiệm và cần biết "người này còn gì nữa không".
//
// MỖI VIỆC VẪN MỘT NÚT GỬI RIÊNG, và vẫn KHÔNG có ô "chọn bệnh nhân". Đối tác
// không khai người nhận; họ chỉ nói "đây là kết quả của việc này", còn việc ấy
// thuộc về ai là do máy chủ tra ra. Thiếu ràng buộc đó thì một tài khoản ngoài
// phòng khám gửi được tệp cho bất kỳ ai — chỉ cần đoán đúng một mã.
//
// 17/09/2026 (Tuyền): thêm bước "Chờ tài liệu" giữa lấy mẫu và gửi kết quả, để
// CSKH thấy đối tác đã nhận việc.
//
// 28/09/2026 (Tuyền: "thiết kế như các màn thủ thuật, siêu âm, bác sĩ"): cùng
// khuôn màn phòng — hàng chờ bên trái chia theo bước còn dở, khách đang chọn
// bên phải với từng việc của họ. Bỏ thanh chỉ số và tab lọc: đầu nhóm đã đếm.
//
// 29/09/2026 (Tuyền: "cần một chỗ UP LÊN và XEM LẠI được LỊCH SỬ các lần up"):
// việc đối tác do NHÂN SỰ phòng khám có lego/vị trí Đối tác làm. Thanh chọn NGÀY
// (ngày cũ vẫn tải thêm tệp, vẫn bấm "Đã lấy mẫu" — máy chủ ghi lại, không lỗi);
// mỗi việc hiện đủ lịch sử tệp (tên, giờ, ai tải); ai được máy chủ cho đọc tệp
// (`xem_tep`) thì mở / in / tải được ngay tại đây.
//
// 29/09/2026 (Tuyền): MẪU GỬI ĐỐI TÁC — dịch vụ thu hộ đối tác làm ở phòng của
// phòng khám (Giải phẫu bệnh, Sinh thiết + GPB ở phòng Thủ thuật): phòng bấm Xong
// thì việc lên đây, nhãn "Mẫu gửi đối tác" (máy chủ quyết, cờ `mau_gui_doi_tac`).
//
// 29/09/2026 (Tuyền): NHẬN MẪU LÀ XONG — "khi NHẬN MẪU là coi như XONG VIỆC …
// KHÔNG được hiển thị là việc này chưa xong". Bấm "Nhận mẫu" → nhóm "Đã nhận
// mẫu · xong" (tick xanh). Kết quả tải lên lúc nào cũng được (máy chủ báo chuông
// bác sĩ chính + CSKH) — là mốc tuỳ chọn, không phải điều kiện xong. Lịch sử
// tệp XEM TRƯỚC ngay tại chỗ (ảnh thu nhỏ + hộp xem, PDF/Word trong khung) bằng
// đúng thành phần của trang chỉ định (AnhKetQua + Lightbox + XemTaiLieu).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CircleCheck, FileUp, FlaskConical, Inbox } from "lucide-react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import Lightbox from "@/components/ui/Lightbox";
import ThanhNgay from "@/components/ui/ThanhNgay";
import { ngayNgan } from "@/lib/thanh-ngay";
import { homNayVn } from "@/lib/validation";
import { doCoTep, guiTepCoTienDo } from "../../lib/gui-tep-co-tien-do";
import AnhKetQua, { tepXem } from "../(dashboard)/_lam-viec/AnhKetQua";
import { XemTaiLieu } from "../(dashboard)/_lam-viec/KhungTep";
import { NutKhoiPhucTep, NutXoaTep } from "../(dashboard)/_lam-viec/XoaTep";
import { EmptyWorkspace } from "../(dashboard)/tasks/WorkspacePrimitives";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";

/** DA_NHAN_MAU và DA_GUI_KET_QUA đều là XONG (máy chủ: VIEC_DOI_TAC_XONG). */
type TrangThai = "CHO_LAY_MAU" | "DA_LAY_MAU" | "DA_NHAN_MAU" | "DA_GUI_KET_QUA";
const XONG: ReadonlySet<TrangThai> = new Set<TrangThai>(["DA_NHAN_MAU", "DA_GUI_KET_QUA"]);

interface Viec {
  chi_dinh_id: string;
  ten_dich_vu: string;
  chi_dinh_luc: string | null;
  trang_thai: TrangThai;
  lay_mau_luc: string | null;
  cho_tai_lieu_luc: string | null;
  ket_qua_luc: string | null;
  /** Ghi chú đối tác đã ghi (24/09/2026). */
  ghi_chu_lay_mau?: string | null;
  ghi_chu_tai_lieu?: string | null;
  /** Dịch vụ thu hộ đối tác (bên thu của dịch vụ, Bảng giá). */
  doi_tac_thu?: boolean;
  /** Giá tham khảo trong bảng giá phòng khám. */
  gia_tham_khao?: number | null;
  /** Ghi nhận "đã thu hộ cho đối tác" còn hiệu lực — null = chưa thu. */
  da_thu?: DaThu | null;
  /** LỊCH SỬ các lần tải tệp của việc này (29/09/2026) — cũ trước. */
  tep?: TepDaGui[];
  /** Mẫu lấy ở phòng của phòng khám, gửi sang đối tác (29/09/2026). */
  mau_gui_doi_tac?: boolean;
}

interface TepDaGui {
  id: string;
  ten: string | null;
  loai: string | null;
  mime?: string | null;
  so_byte: number;
  luc: string | null;
  /** Ai tải lên (tên nhân sự). */
  boi?: string | null;
  /** Tệp đã bị thu hồi — vẫn hiện trong lịch sử, không mở được. */
  thu_hoi?: boolean;
  /** Tệp đã xoá mềm (V9) — vẫn hiện trong lịch sử kèm lý do, không mở được. */
  da_xoa?: boolean;
  da_xoa_ly_do?: string | null;
  /** Cờ máy chủ: nút Xoá / Đính chính (tệp còn hiệu lực) và Khôi phục. */
  xoa_duoc?: boolean;
  xoa_loai?: string | null;
  xoa_ly_do?: string | null;
  khoi_phuc_duoc?: boolean;
}

const kichThuoc = (b: number) =>
  b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;

interface DaThu {
  id: string;
  so_tien: number;
  hinh_thuc: "CASH" | "TRANSFER";
  ghi_chu: string | null;
  luc: string | null;
  /** Ai ghi nhận. */
  boi?: string | null;
}

const TEN_HINH_THUC: Record<DaThu["hinh_thuc"], string> = {
  CASH: "Tiền mặt",
  TRANSFER: "Chuyển khoản",
};

function tienVnd(n: number): string {
  return `${n.toLocaleString("vi-VN")}đ`;
}

interface Khach {
  clinic_patient_id: string;
  ten_khach: string;
  ma_khach: string;
  cho_tu: string | null;
  viec: Viec[];
}

interface DanhSach {
  khach: Khach[];
  so_viec: number;
  /** Ngày máy chủ đã xem (YYYY-MM-DD) — ngày rác thì máy chủ trả hôm nay. */
  ngay: string;
  hom_nay: boolean;
  /** Máy chủ cho người này MỞ tệp (xem / in / tải) không. */
  xem_tep: boolean;
}

type KetQua = DanhSach | { loi: string };

// Thanh bước (29/09/2026): Lấy mẫu → Nhận mẫu (ĐIỂM XONG) → Có kết quả (tuỳ
// chọn — không phải điều kiện xong, không tô "đang chờ").
const BUOC: { nhan: string; xong: (tt: TrangThai) => boolean; tuyChon?: boolean }[] = [
  { nhan: "Lấy mẫu", xong: (tt) => tt !== "CHO_LAY_MAU" },
  { nhan: "Nhận mẫu · xong", xong: (tt) => XONG.has(tt) },
  { nhan: "Có kết quả (tuỳ chọn)", xong: (tt) => tt === "DA_GUI_KET_QUA", tuyChon: true },
];

const NHAN_TRANG_THAI: Record<TrangThai, { chu: string; tone: "warning" | "info" | "success" }> = {
  CHO_LAY_MAU: { chu: "Chờ lấy mẫu", tone: "warning" },
  DA_LAY_MAU: { chu: "Đã có mẫu · chờ nhận", tone: "info" },
  DA_NHAN_MAU: { chu: "Đã nhận mẫu · xong", tone: "success" },
  DA_GUI_KET_QUA: { chu: "Xong · có kết quả", tone: "success" },
};

function gioPhut(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Ho_Chi_Minh",
    });
  } catch {
    return "—";
  }
}

function gioVn(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function choBaoLau(iso: string | null): string {
  if (!iso) return "";
  const phut = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(phut) || phut < 0) return "";
  if (phut < 60) return `chờ ${phut} phút`;
  const gio = Math.floor(phut / 60);
  if (gio < 24) return `chờ ${gio} giờ`;
  return `chờ ${Math.floor(gio / 24)} ngày`;
}

// Đọc danh sách — KHÔNG đụng state. Tách ra để chỗ gọi tự quyết định có nhận kết
// quả hay không: lần tải đầu chạy trong effect và phải bỏ kết quả nếu người dùng
// đã rời màn, còn lần tải lại sau khi gửi thì luôn nhận.
async function docDanhSach(ngay: string): Promise<KetQua> {
  try {
    const r = await fetch(`/api/doi-tac?ngay=${encodeURIComponent(ngay)}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | (Partial<DanhSach> & { error?: string; message?: string })
      | null;
    if (!r.ok) return { loi: d?.message ?? d?.error ?? "Không đọc được danh sách khách." };
    return {
      khach: d?.khach ?? [],
      so_viec: d?.so_viec ?? 0,
      ngay: d?.ngay ?? ngay,
      hom_nay: d?.hom_nay ?? true,
      xem_tep: d?.xem_tep ?? false,
    };
  } catch {
    return { loi: "Mất kết nối tới máy chủ." };
  }
}

async function bamViec(
  duong: string,
  id: string,
  ghiChu: string,
  them: Record<string, unknown> = {},
): Promise<string | null> {
  try {
    const r = await fetch(duong, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chi_dinh_id: id, ghi_chu: ghiChu.trim() || undefined, ...them }),
    });
    if (r.ok) return null;
    const d = (await r.json().catch(() => null)) as { error?: string; message?: string } | null;
    return d?.message ?? d?.error ?? "Không ghi được.";
  } catch {
    return "Mất kết nối — CHƯA ghi được.";
  }
}

// HÀNG CHỜ BÊN TRÁI chia theo BƯỚC ĐẦU TIÊN còn dở của khách (Tuyền 28/09/2026:
// "thiết kế như các màn thủ thuật, siêu âm, bác sĩ") — cùng khuôn HangChoCot.
// Hai nhóm cuối là XONG (Tuyền 29/09/2026: nhận mẫu là xong việc).
const NHOM: { ma: TrangThai; ten: string }[] = [
  { ma: "CHO_LAY_MAU", ten: "Chờ lấy mẫu" },
  { ma: "DA_LAY_MAU", ten: "Có mẫu · chờ nhận" },
  { ma: "DA_NHAN_MAU", ten: "Đã nhận mẫu · xong" },
  { ma: "DA_GUI_KET_QUA", ten: "Xong · có kết quả" },
];
const THU_TU: Record<TrangThai, number> = {
  CHO_LAY_MAU: 0,
  DA_LAY_MAU: 1,
  DA_NHAN_MAU: 2,
  DA_GUI_KET_QUA: 3,
};
/** Khách đứng ở nhóm của việc CHƯA XONG sớm nhất; xong hết → nhóm xong. */
function buocCua(k: Khach): TrangThai {
  return k.viec.reduce<TrangThai>(
    (m, v) => (THU_TU[v.trang_thai] < THU_TU[m] ? v.trang_thai : m),
    "DA_GUI_KET_QUA",
  );
}

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
  const [tienDo, setTienDo] = useState<{ id: string; pt: number; ten: string } | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [chonId, setChonId] = useState<string | null>(null);

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
    // Phòng khám chỉ định liên tục — không bắt đối tác tải lại trang.
    // Tab ẩn thì huỷ hẳn nhịp; hiện lại thì đọc một lần ngay (30/09/2026).
    const goNhip = nhipKhiHien(doc, 20000);
    return () => {
      huy = true;
      goNhip();
    };
  }, [nhan, ngay]);

  const dem = useMemo(() => {
    const c: Record<TrangThai, number> = {
      CHO_LAY_MAU: 0,
      DA_LAY_MAU: 0,
      DA_NHAN_MAU: 0,
      DA_GUI_KET_QUA: 0,
    };
    for (const k of ds ?? []) for (const v of k.viec) c[v.trang_thai] += 1;
    return c;
  }, [ds]);

  const lamViec = useCallback(
    async (
      duong: string,
      v: Viec,
      k: Khach,
      bao: string,
      ghiChu = "",
      them: Record<string, unknown> = {},
    ): Promise<boolean> => {
      setDangLam(v.chi_dinh_id);
      setLoi(null);
      setXong(null);
      const l = await bamViec(duong, v.chi_dinh_id, ghiChu, them);
      if (l) setLoi(l);
      else setXong(`${bao} — ${v.ten_dich_vu} của ${k.ten_khach}.`);
      await tai();
      setDangLam(null);
      return l === null;
    },
    [tai],
  );

  const gui = useCallback(
    async (v: Viec, k: Khach, tep: File) => {
      setDangLam(v.chi_dinh_id);
      setLoi(null);
      setXong(null);
      setTienDo({ id: v.chi_dinh_id, pt: 0, ten: `${tep.name} · ${doCoTep(tep.size)}` });
      try {
        const fd = new FormData();
        fd.append("chi_dinh_id", v.chi_dinh_id);
        fd.append("file", tep);
        const r = await guiTepCoTienDo("/api/doi-tac", fd, (pt) =>
          setTienDo((t) => (t ? { ...t, pt } : t)),
        );
        if (!r.ok) {
          const d = r.data as { error?: string; message?: string } | null;
          setLoi(d?.message ?? d?.error ?? "Gửi không được.");
          return;
        }
        setXong(`Đã gửi tài liệu ${v.ten_dich_vu} của ${k.ten_khach}.`);
        await tai();
      } catch {
        setLoi("Mất kết nối — tệp CHƯA được gửi.");
      } finally {
        setTienDo(null);
        setDangLam(null);
      }
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

  const theoNhom = NHOM.map((n) => ({
    ...n,
    khach: ds.filter((k) => buocCua(k) === n.ma),
  }));
  // Mặc định chọn khách đầu tiên còn việc dở; khách vừa chọn biến mất (xong,
  // bị huỷ) thì rơi về mặc định — không để khung phải trỏ vào khoảng không.
  const macDinh = theoNhom.find((n) => !XONG.has(n.ma) && n.khach.length > 0)?.khach[0];
  const chon = ds.find((k) => k.clinic_patient_id === chonId) ?? macDinh ?? null;
  const conDo = dem.CHO_LAY_MAU + dem.DA_LAY_MAU;

  return (
    <div className="grid gap-4">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-title font-semibold text-ink">Việc của đối tác</h1>
        <p className="text-body text-ink-muted">
          {xemNgay.homNay ? "Hôm nay" : `Ngày ${ngayNgan(xemNgay.ngay)}`} · {dem.CHO_LAY_MAU} chờ lấy
          mẫu · {dem.DA_LAY_MAU} chờ nhận mẫu · {dem.DA_NHAN_MAU} đã nhận mẫu ·{" "}
          {dem.DA_GUI_KET_QUA} có kết quả
        </p>
      </header>

      {/* NGÀY CŨ (29/09/2026): việc có hoạt động ngày ấy — chỉ định, lấy mẫu,
          nhận mẫu, gửi tệp. Vẫn tải thêm tệp / bấm "Đã lấy mẫu" được. */}
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

      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {xong ? (
        <p role="status" className="rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">
          {xong}
        </p>
      ) : null}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(15rem,0.6fr)_minmax(0,1.8fr)]">
        <aside aria-label="Hàng chờ của đối tác" className="space-y-3">
          {ds.length === 0 ? (
            <p className="rounded-card border border-line bg-surface p-4 text-sm text-ink-muted">
              {xemNgay.homNay
                ? "Chưa có khách nào được gửi sang."
                : "Ngày này không có việc đối tác nào."}
            </p>
          ) : (
            theoNhom.map((n) =>
              n.khach.length === 0 ? null : (
                <section key={n.ma}>
                  <h3 className="mb-1 px-1 text-label font-semibold uppercase tracking-wide text-ink-muted">
                    {n.ten} ({n.khach.length})
                  </h3>
                  <ul className="space-y-1">
                    {n.khach.map((k) => {
                      const dangChon = chon?.clinic_patient_id === k.clinic_patient_id;
                      const conViec = k.viec.filter((v) => !XONG.has(v.trang_thai)).length;
                      return (
                        <li key={k.clinic_patient_id}>
                          <button
                            type="button"
                            aria-pressed={dangChon}
                            onClick={() => {
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
                            className={`flex w-full items-start gap-2 rounded-control border px-2.5 py-2 text-left transition-colors ${
                              dangChon
                                ? "border-brand-500 bg-brand-50"
                                : "border-line bg-surface hover:bg-surface-muted"
                            } ${XONG.has(n.ma) ? "opacity-70" : ""}`}
                          >
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-body font-medium text-ink">
                                {k.ten_khach}
                              </span>
                              <span className="block text-meta text-ink-muted">
                                {k.ma_khach}
                                {conViec > 0 ? ` · ${conViec} việc` : ""}
                              </span>
                            </span>
                            {XONG.has(n.ma) ? (
                              <CircleCheck className="size-4 shrink-0 text-success" aria-label="Xong" />
                            ) : (
                              <span className="shrink-0 text-meta tabular-nums text-ink-muted">
                                {choBaoLau(k.cho_tu)}
                              </span>
                            )}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ),
            )
          )}
        </aside>

        {chon ? (
          <section
            id="khung-khach-doi-tac"
            aria-label={`Việc của ${chon.ten_khach}`}
            className="min-w-0 space-y-3 rounded-card bg-surface p-4 shadow-card"
          >
            <header className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
                  Khách đang chọn
                </p>
                <h2 className="text-title font-semibold text-ink">{chon.ten_khach}</h2>
                <p className="text-meta tabular-nums text-ink-muted">
                  Mã {chon.ma_khach}
                  {chon.cho_tu ? ` · gửi sang ${gioVn(chon.cho_tu)}` : ""}
                  {choBaoLau(chon.cho_tu) ? ` · ${choBaoLau(chon.cho_tu)}` : ""}
                </p>
              </div>
              <Chip tone={XONG.has(buocCua(chon)) ? "success" : "warning"}>
                {NHOM.find((n) => n.ma === buocCua(chon))?.ten}
              </Chip>
            </header>
            <ul className="divide-y divide-line rounded-control border border-line">
              {[...chon.viec]
                .sort((x, y) => THU_TU[x.trang_thai] - THU_TU[y.trang_thai])
                .map((v) => (
                  <MotViec
                    key={v.chi_dinh_id}
                    viec={v}
                    xemTep={xemNgay.xemTep}
                    dangLam={dangLam === v.chi_dinh_id}
                    tienDo={tienDo?.id === v.chi_dinh_id ? tienDo : null}
                    onLayMau={(g) =>
                      void lamViec("/api/doi-tac/da-lay-mau", v, chon, "Đã ghi lấy mẫu", g)
                    }
                    onChoTaiLieu={(g) =>
                      void lamViec(
                        "/api/doi-tac/cho-tai-lieu",
                        v,
                        chon,
                        "Đã nhận mẫu — việc đối tác XONG (kết quả tải lên lúc nào cũng được)",
                        g,
                      )
                    }
                    onGui={(tep) => void gui(v, chon, tep)}
                    onDoiTep={() => void tai()}
                    onDaThu={(soTien, hinhThuc, g) =>
                      lamViec("/api/doi-tac/da-thu-tien", v, chon, "Đã ghi nhận thu hộ cho đối tác", g, {
                        so_tien: soTien,
                        hinh_thuc: hinhThuc,
                      })
                    }
                    onHuyThu={(lyDo) =>
                      lamViec("/api/doi-tac/huy-da-thu", v, chon, "Đã huỷ ghi nhận thu hộ", "", {
                        ly_do: lyDo,
                      })
                    }
                  />
                ))}
            </ul>
          </section>
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

function MotViec({
  viec,
  xemTep,
  dangLam,
  tienDo,
  onLayMau,
  onChoTaiLieu,
  onGui,
  onDaThu,
  onHuyThu,
  onDoiTep,
}: {
  viec: Viec;
  /** Máy chủ cho mở tệp (xem / in / tải) — vai PARTNER bên ngoài: không. */
  xemTep: boolean;
  dangLam: boolean;
  tienDo: { pt: number; ten: string } | null;
  onLayMau: (ghiChu: string) => void;
  onChoTaiLieu: (ghiChu: string) => void;
  onGui: (tep: File) => void;
  onDaThu: (soTien: string, hinhThuc: DaThu["hinh_thuc"], ghiChu: string) => Promise<boolean>;
  onHuyThu: (lyDo: string) => Promise<boolean>;
  /** Vừa xoá / khôi phục một tệp (V9) — tải lại danh sách. */
  onDoiTep: () => void;
}) {
  const oTep = useRef<HTMLInputElement>(null);
  // Ghi chú đi kèm "Đã lấy mẫu" / "Nhận mẫu" (24/09/2026).
  const [ghiChu, setGhiChu] = useState("");
  // Hộp xem tệp (Lightbox) — mở ở tệp thứ `i` (29/09/2026).
  const [mo, setMo] = useState<{ i: number; luoi: boolean } | null>(null);
  const tt = viec.trang_thai;
  const xong = XONG.has(tt);
  const nhanTt = NHAN_TRANG_THAI[tt];
  // Tệp còn hiệu lực, xem trước được — cùng đường đọc tệp chung của trang chỉ định.
  const tepCon = (viec.tep ?? []).filter((t) => !t.thu_hoi && !t.da_xoa);
  const xem = tepCon.map((t) =>
    tepXem({ id: t.id, ten: t.ten, loai_tep: t.loai ?? "TAI_LIEU", mime: t.mime }),
  );
  const mocGanNhat =
    tt === "DA_GUI_KET_QUA"
      ? viec.cho_tai_lieu_luc
        ? `Đã nhận mẫu ${gioPhut(viec.cho_tai_lieu_luc)} · có kết quả ${gioVn(viec.ket_qua_luc)}`
        : `Có kết quả ${gioVn(viec.ket_qua_luc)}`
      : tt === "DA_NHAN_MAU"
        ? `Đã nhận mẫu ${gioPhut(viec.cho_tai_lieu_luc)} · ${gioVn(viec.cho_tai_lieu_luc)}`
        : tt === "DA_LAY_MAU"
          ? viec.mau_gui_doi_tac
            ? `Phòng khám gửi mẫu lúc ${gioVn(viec.lay_mau_luc)}`
            : `Có mẫu lúc ${gioVn(viec.lay_mau_luc)}`
          : `Phòng khám gửi lúc ${gioVn(viec.chi_dinh_luc)}`;

  return (
    <li className="space-y-2.5 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-body font-medium text-ink">{viec.ten_dich_vu}</p>
          {viec.mau_gui_doi_tac ? (
            <Chip tone="info" title="Mẫu lấy ở phòng của phòng khám, gửi sang đối tác">
              Mẫu gửi đối tác
            </Chip>
          ) : null}
          <p className="text-meta text-ink-muted">{mocGanNhat}</p>
        </div>
        <Chip tone={nhanTt.tone}>
          {xong ? <CircleCheck className="size-3.5" aria-hidden="true" /> : null}
          {tt === "DA_NHAN_MAU" ? `Đã nhận mẫu ${gioPhut(viec.cho_tai_lieu_luc)}` : nhanTt.chu}
        </Chip>
      </div>

      <ol className="grid grid-cols-3 gap-1" aria-label="Tiến độ việc">
        {BUOC.map((b) => {
          const daXong = b.xong(tt);
          // Bước đang làm = bước đầu tiên chưa xong, trừ bước tuỳ chọn.
          const dangO = !daXong && !b.tuyChon && BUOC.find((x) => !x.xong(tt)) === b;
          return (
            <li key={b.nhan} className="min-w-0">
              <span
                className={`block h-1.5 rounded-full ${
                  daXong ? "bg-success" : dangO ? "bg-brand-500" : "bg-line"
                }`}
              />
              <span
                className={`mt-1 block truncate text-label ${
                  dangO || (daXong && !b.tuyChon) ? "font-semibold text-ink" : "text-ink-faint"
                }`}
              >
                {b.nhan}
              </span>
            </li>
          );
        })}
      </ol>

      {tienDo ? (
        <div className="space-y-1" role="status">
          <div className="h-1.5 overflow-hidden rounded-full bg-line">
            <div className="h-full bg-brand-500 transition-all" style={{ width: `${tienDo.pt}%` }} />
          </div>
          <p className="truncate text-label text-ink-muted">
            {tienDo.pt >= 100 ? "Đang cất tài liệu…" : `Đang gửi ${tienDo.pt}%`} · {tienDo.ten}
          </p>
        </div>
      ) : null}

      {/* LỊCH SỬ CÁC LẦN TẢI (29/09/2026): tên, giờ, ai tải — cũ trước. XEM
          TRƯỚC ngay tại chỗ khi máy chủ cho (`xem_tep`): ảnh thu nhỏ, bấm mở hộp
          xem (phóng to, chuyển tệp, Mở / In, Tải về) — cùng AnhKetQua + Lightbox
          của trang chỉ định. Tệp thu hồi chỉ còn dòng ghi. */}
      {viec.tep && viec.tep.length > 0 ? (
        <div className="space-y-1.5">
          <p className="text-label font-semibold uppercase tracking-wider text-ink-faint">
            Lịch sử tải tệp ({viec.tep.length})
          </p>
          {xemTep && xem.length > 0 ? (
            <AnhKetQua tep={xem} onMo={(i, luoi) => setMo({ i, luoi: Boolean(luoi) })} />
          ) : null}
          <ol className="space-y-1">
            {viec.tep.map((t) => (
              <li
                key={t.id}
                className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 rounded-control bg-surface-muted px-3 py-1.5 text-meta"
              >
                <span
                  className={`min-w-0 truncate ${t.thu_hoi || t.da_xoa ? "text-ink-faint line-through" : "text-ink"}`}
                >
                  {t.ten ?? "Tệp kết quả"}
                </span>
                <span className="text-ink-muted">
                  {[
                    t.loai,
                    kichThuoc(t.so_byte),
                    t.luc ? gioVn(t.luc) : null,
                    t.boi ?? null,
                    t.thu_hoi ? "đã thu hồi" : null,
                    t.da_xoa ? `đã xoá${t.da_xoa_ly_do ? ` — ${t.da_xoa_ly_do}` : ""}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
                {t.da_xoa && t.khoi_phuc_duoc ? (
                  <NutKhoiPhucTep tepId={t.id} nhan="Khôi phục" onXong={onDoiTep} />
                ) : null}
                {!t.thu_hoi && !t.da_xoa ? (
                  <NutXoaTep
                    tepId={t.id}
                    ten={t.ten}
                    co={{ xoa_duoc: t.xoa_duoc, xoa_loai: t.xoa_loai, xoa_ly_do: t.xoa_ly_do }}
                    onDaXoa={onDoiTep}
                  />
                ) : null}
                {xemTep && !t.thu_hoi && !t.da_xoa ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setMo({ i: Math.max(0, tepCon.findIndex((x) => x.id === t.id)), luoi: false })
                    }
                  >
                    Xem
                  </Button>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      {mo && xem.length > 0 ? (
        <Lightbox
          tieuDe={viec.ten_dich_vu}
          tep={xem}
          batDau={mo.i}
          luoiBanDau={mo.luoi}
          veTaiLieu={(x) => {
            const goc = tepCon.find((t) => t.id === x.id);
            return goc ? (
              <XemTaiLieu tep={{ id: goc.id, mime: goc.mime ?? "", ten_hien_thi: goc.ten }} />
            ) : null;
          }}
          veThaoTac={(x) => {
            const goc = tepCon.find((t) => t.id === x.id);
            return goc ? (
              <NutXoaTep
                tepId={goc.id}
                ten={goc.ten}
                co={{ xoa_duoc: goc.xoa_duoc, xoa_loai: goc.xoa_loai, xoa_ly_do: goc.xoa_ly_do }}
                nenToi
                onDaXoa={() => {
                  setMo(null);
                  onDoiTep();
                }}
              />
            ) : null;
          }}
          onDong={() => setMo(null)}
        />
      ) : null}

      {viec.ghi_chu_lay_mau || viec.ghi_chu_tai_lieu ? (
        <div className="space-y-0.5 text-meta text-ink-soft">
          {viec.ghi_chu_lay_mau ? (
            <p className="whitespace-pre-wrap">Ghi chú lấy mẫu: {viec.ghi_chu_lay_mau}</p>
          ) : null}
          {viec.ghi_chu_tai_lieu ? (
            <p className="whitespace-pre-wrap">Ghi chú nhận mẫu: {viec.ghi_chu_tai_lieu}</p>
          ) : null}
        </div>
      ) : null}

      {viec.doi_tac_thu ? (
        <ThuTienKhach viec={viec} dangLam={dangLam} onDaThu={onDaThu} onHuyThu={onHuyThu} />
      ) : null}

      {tt === "CHO_LAY_MAU" || tt === "DA_LAY_MAU" ? (
        <label className="block">
          <span className="text-label font-semibold text-ink-muted">
            Ghi chú (tuỳ chọn)
          </span>
          <textarea
            value={ghiChu}
            onChange={(e) => setGhiChu(e.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="VD: lấy mẫu lúc 10h, mẫu đủ; hẹn trả kết quả sau 3 ngày…"
            className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink"
          />
        </label>
      ) : null}

      <div className="flex flex-wrap justify-end gap-2">
        {tt === "CHO_LAY_MAU" ? (
          <button
            type="button"
            disabled={dangLam}
            onClick={() => onLayMau(ghiChu)}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            <FlaskConical className="size-4" aria-hidden="true" />
            {dangLam ? "Đang ghi…" : "Đã lấy mẫu"}
          </button>
        ) : null}
        {tt === "DA_LAY_MAU" ? (
          <button
            type="button"
            disabled={dangLam}
            onClick={() => onChoTaiLieu(ghiChu)}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            <CircleCheck className="size-4" aria-hidden="true" />
            {dangLam ? "Đang ghi…" : "Nhận mẫu"}
          </button>
        ) : null}
        <input
          ref={oTep}
          type="file"
          accept="image/*,video/mp4,video/quicktime,video/webm,application/pdf,.docx,.xlsx"
          className="hidden"
          onChange={(e) => {
            const t = e.target.files?.[0];
            // Xoá giá trị NGAY: chọn lại đúng tệp vừa gửi hỏng phải bắn được
            // sự kiện change lần nữa, không thì nút im lặng không làm gì.
            e.target.value = "";
            if (t) onGui(t);
          }}
        />
        {/* Tải tài liệu MỌI LÚC (Tuyền 28/09/2026): các nút bước chỉ ghi sự
            kiện — đối tác bận chưa bấm "Đã lấy mẫu" vẫn gửi được kết quả. */}
        <button
            type="button"
            disabled={dangLam}
            onClick={() => oTep.current?.click()}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-control border border-brand-500 px-4 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
          >
            <FileUp className="size-4" aria-hidden="true" />
            {dangLam && tienDo ? "Đang gửi…" : tt === "DA_GUI_KET_QUA" ? "Gửi thêm kết quả" : "Tải kết quả lên"}
          </button>
      </div>
    </li>
  );
}

/** THU HỘ ĐỐI TÁC (Tuyền chốt 27/09/2026, Q1; đổi tên 29/09/2026): người ở vị
 *  trí Đối tác ghi nhận đã thu hộ (số tiền mặc định = giá tham khảo, hình thức,
 *  ghi chú) và huỷ có lý do. Máy chủ kiểm số tiền / hình thức / lý do. */
function ThuTienKhach({
  viec,
  dangLam,
  onDaThu,
  onHuyThu,
}: {
  viec: Viec;
  dangLam: boolean;
  onDaThu: (soTien: string, hinhThuc: DaThu["hinh_thuc"], ghiChu: string) => Promise<boolean>;
  onHuyThu: (lyDo: string) => Promise<boolean>;
}) {
  const [mo, setMo] = useState<"thu" | "huy" | null>(null);
  const [soTien, setSoTien] = useState(
    viec.gia_tham_khao != null ? String(viec.gia_tham_khao) : "",
  );
  const [hinhThuc, setHinhThuc] = useState<DaThu["hinh_thuc"]>("CASH");
  const [ghiChu, setGhiChu] = useState("");
  const [lyDo, setLyDo] = useState("");
  const da = viec.da_thu;

  return (
    <div className="space-y-2 rounded-control bg-surface-muted px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-meta text-ink-muted">
          Thu hộ đối tác
          {viec.gia_tham_khao != null ? ` · tham khảo ${tienVnd(viec.gia_tham_khao)}` : ""}
        </p>
        {da ? (
          <Chip tone="success">
            Đã thu hộ {tienVnd(da.so_tien)} · {TEN_HINH_THUC[da.hinh_thuc]}
          </Chip>
        ) : (
          <Chip tone="warning">Chưa thu hộ</Chip>
        )}
      </div>
      {da?.ghi_chu ? <p className="whitespace-pre-wrap text-meta text-ink-soft">Ghi chú: {da.ghi_chu}</p> : null}
      {da?.luc ? (
        <p className="text-label text-ink-faint">
          Ghi lúc {gioVn(da.luc)}
          {da.boi ? ` · ${da.boi}` : ""}
        </p>
      ) : null}

      {mo === "thu" && !da ? (
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="block">
            <span className="text-label font-semibold text-ink-muted">Số tiền (đồng)</span>
            <input
              value={soTien}
              onChange={(e) => setSoTien(e.target.value)}
              inputMode="numeric"
              className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body tabular-nums text-ink"
            />
          </label>
          <label className="block">
            <span className="text-label font-semibold text-ink-muted">Hình thức</span>
            <select
              value={hinhThuc}
              onChange={(e) => setHinhThuc(e.target.value as DaThu["hinh_thuc"])}
              className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
            >
              <option value="CASH">Tiền mặt</option>
              <option value="TRANSFER">Chuyển khoản</option>
            </select>
          </label>
          <label className="block sm:col-span-2">
            <span className="text-label font-semibold text-ink-muted">Ghi chú (tuỳ chọn)</span>
            <input
              value={ghiChu}
              onChange={(e) => setGhiChu(e.target.value)}
              maxLength={2000}
              className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
            />
          </label>
        </div>
      ) : null}

      {mo === "huy" && da ? (
        <label className="block">
          <span className="text-label font-semibold text-ink-muted">Lý do huỷ ghi nhận</span>
          <input
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            maxLength={2000}
            placeholder="VD: ghi nhầm số tiền"
            className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
          />
        </label>
      ) : null}

      <div className="flex flex-wrap justify-end gap-2">
        {mo === null && !da ? (
          <Button variant="soft" size="lg" disabled={dangLam} onClick={() => setMo("thu")}>
            Đã thu hộ cho đối tác
          </Button>
        ) : null}
        {mo === null && da ? (
          <Button variant="ghost" size="lg" disabled={dangLam} onClick={() => setMo("huy")}>
            Huỷ ghi nhận
          </Button>
        ) : null}
        {mo === "thu" && !da ? (
          <>
            <Button variant="ghost" size="lg" disabled={dangLam} onClick={() => setMo(null)}>
              Thôi
            </Button>
            <Button
              variant="primary"
              size="lg"
              disabled={dangLam || !soTien.trim()}
              onClick={() =>
                void onDaThu(soTien, hinhThuc, ghiChu).then((ok) => {
                  if (ok) setMo(null);
                })
              }
            >
              {dangLam ? "Đang ghi…" : "Ghi nhận đã thu hộ"}
            </Button>
          </>
        ) : null}
        {mo === "huy" && da ? (
          <>
            <Button variant="ghost" size="lg" disabled={dangLam} onClick={() => setMo(null)}>
              Thôi
            </Button>
            <Button
              variant="danger"
              size="lg"
              disabled={dangLam || lyDo.trim().length < 3}
              onClick={() =>
                void onHuyThu(lyDo).then((ok) => {
                  if (ok) {
                    setMo(null);
                    setLyDo("");
                  }
                })
              }
            >
              {dangLam ? "Đang ghi…" : "Huỷ ghi nhận"}
            </Button>
          </>
        ) : null}
      </div>
    </div>
  );
}
