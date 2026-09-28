"use client";

// BÀN KHÁM — màn của bác sĩ và thư ký đi kèm (Tuyền chốt 16/09/2026).
//
// BỐ CỤC GIỮ ĐÚNG màn Tuyền đã chọn ("đây là view tôi muốn làm", Bàn khám bác sĩ
// cũ): hàng chờ hẹp bên trái, bệnh án rộng ở giữa, chỉ định bên phải.
//
// NGUỒN DỮ LIỆU ĐỔI SANG MỘT ĐƯỜNG: hàng chờ phòng (`queue_entry`), phiên khám
// (`consultation`), chỉ định (`service_order`). Màn cũ đọc thẻ việc và chỉ định
// ghi vào `payload` của thẻ — một đường thứ ba song song mà trên final cloud có
// 0 chỉ định thật.
//
// CHECK-IN / CHECK-OUT CỦA PHÒNG = hai nút: "Bắt đầu khám" ở TRÊN và "Hoàn tất"
// ở CUỐI hồ sơ (Tuyền chốt 23/09/2026: *"chỉ cần nút hoàn tất là khám xong
// rồi… bỏ luôn nút khám xong ở trên đi, chỉ cần nút bắt đầu khám"*). Không còn
// nút Ký, và Hoàn tất KHÔNG khoá hồ sơ ("không khoá, sửa thoải mái"). Khám xong mà còn chỉ định
// chưa làm thì khách tự sang hàng chờ phòng làm chỉ định — máy chủ quyết.

import {
  CheckCircle2,
  ClipboardPlus,
  FlaskConical,
  HeartPulse,
  Search,
  Stethoscope,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import PriorityChip from "@/components/ui/PriorityChip";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import ThanhTab from "@/components/ui/ThanhTab";

import LuotKhamTruoc, { type LuotTruoc } from "../doctor/board/LuotKhamTruoc";
import ServiceFormEngine from "../tasks/ServiceFormEngine";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import type { DoctorApptRow } from "../tasks/DoctorApptRow";
import type { NutBanKham } from "@/lib/roles";
import {
  type ClinicalCompletionGate,
  type ClinicalCompletionMode,
} from "@/lib/clinical-completion";
import {
  docBang,
  guiThaoTac,
  soPhutTu,
  gioVn,
  type DongHangCho,
  type Phong,
  type PhongHomNay,
} from "../_lam-viec/api";
import KhungTep from "../_lam-viec/KhungTep";
import XemPhieuKetQua from "../_lam-viec/XemPhieuKetQua";
import DoiPhong from "../_lam-viec/DoiPhong";
import { TomTatLuotContext } from "../_lam-viec/phieu-kham/TomTatLuot";
import XemLuot from "../_lam-viec/XemLuot";
import PhieuKhamLuot from "../_lam-viec/phieu-kham/PhieuKhamLuot";
import BanTuVan from "./BanTuVan";
import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import ChoBacSiQuyet from "./ChoBacSiQuyet";
import ThaiKy from "./ThaiKy";
import SoLuot from "@/components/ui/SoLuot";
import { useNgheBang } from "../dung-nghe-bang";

// ── Dữ liệu của bảng lượt khám (chỉ những trường màn này dùng) ─────────────
interface SinhHieu {
  tam_thu: number | null;
  tam_truong: number | null;
  mach: number | null;
  nhiet_do: number | null;
  nhip_tho: number | null;
  spo2: number | null;
  can_nang: number | null;
  chieu_cao: number | null;
  bmi: number | null;
  muc_do_dau: number | null;
  luc: string | null;
  nguoi_do: string | null;
}
interface ChiDinh {
  id: string;
  phien_id: string;
  ma_dich_vu: string;
  ten_dich_vu: string;
  node: string;
  trang_thai: string;
  phong: string | null;
  version: number;
  nguoi_ghi: string | null;
  ket_qua: string | null;
  /** Có phiếu kết quả đã hoàn tất để mở đọc (chỉ đọc; mở là tự ghi đã xem). */
  co_phieu?: boolean;
  da_xem_ket_qua_luc?: string | null;
  ly_do_khong_lam: string | null;
  /** Lần làm gần nhất ở phòng (23/09/2026): giờ phòng bấm Bắt đầu / xong. */
  lam_bat_dau_luc?: string | null;
  lam_xong_luc?: string | null;
  lam_trang_thai?: "IN_PROGRESS" | "COMPLETED" | "INTERRUPTED" | null;
  lam_phong?: string | null;
  phong_id?: string | null;
  routing_revision?: number | null;
  doi_phong_duoc?: boolean;
  /** Việc gửi đối tác làm — không có phòng nào của phòng khám để xếp. */
  doi_tac?: boolean;
  trang_thai_doi_tac?: "CHO_LAY_MAU" | "DA_LAY_MAU" | "CHO_TAI_LIEU" | "DA_GUI_KET_QUA" | null;
  /** Khách trả TRỰC TIẾP cho đối tác (27/09/2026): đối tác đã thu chưa. */
  doi_tac_thu_tien?: "DA_THU" | "CHUA_THU" | null;
}
interface Luot {
  visit_id: string;
  sinh_hieu: SinhHieu | null;
  chi_dinh: ChiDinh[];
}
interface DichVu {
  ma: string;
  ten: string;
  node: string;
}
interface Bang {
  luot: Luot[];
  dich_vu: DichVu[];
}

const LA_PHONG_KHAM = (p: Phong) => p.nodes.some((n) => n.startsWith("KHAM-"));

/** PHIẾU KHÁM v5 (Tuyền 23/09/2026 tối: "form sửa theo như này đi… làm luôn").
 *  Bật: lượt khám dùng bảy phiếu v5 — tự lưu, chỉ định C/F có giá, kết quả điền
 *  tại chỗ, đơn thuốc mục E. Đường cũ (phiếu chuyên khoa `ServiceFormEngine` +
 *  bệnh án `ClinicalRecordForm` có nút Lưu) để OFF, KHÔNG xoá, tới khi Tuyền
 *  bấm thật xong. Lượt CŨ (xem lại) vẫn đọc bằng đường cũ. */
const PHIEU_V5 = true;
/** Bàn TƯ VẤN dùng MỘT ô chữ tự do (Tuyền 24/09/2026) thay cho phiếu khám v5 —
 *  nội dung sang mục "Dữ liệu mang sang" của bác sĩ chính. `false` = về phiếu
 *  v5 như trước (OFF, không xoá). */
const TU_VAN_O_TU_DO = true;
/** Hỏi lại "Hoàn tất lượt khám này…? [Hoàn tất] [Thôi]" trước khi gửi. OFF
 *  (Tuyền 24/09/2026: "khi ấn hoàn tất là ok rồi chứ đừng bắt ấn thêm lần nữa")
 *  — hồ sơ không khoá, bấm nhầm vẫn sửa tiếp được. Giữ code, chưa xoá. */
const HOI_LAI_KHI_HOAN_TAT = false;

function initials(name: string | null): string {
  if (!name) return "BN";
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function tone(d: DongHangCho): { tone: StatusTone; nhan: string } {
  switch (d.trang_thai) {
    case "serving":
      return { tone: "in_progress", nhan: "Đang khám" };
    case "called":
      return { tone: "called", nhan: "Đã gọi vào" };
    case "waiting":
      return { tone: "ready", nhan: "Chờ khám" };
    case "blocked":
      return { tone: "blocked", nhan: "Đang ở bước khác" };
    default:
      return { tone: "completed", nhan: "Đã khám xong" };
  }
}

const TEN_TRANG_THAI_CHI_DINH: Record<string, string> = {
  draft: "Nháp — chờ bác sĩ duyệt",
  authorized: "Đã duyệt — chờ xếp phòng",
  assigned: "Chờ ở phòng",
  in_progress: "Đang làm",
  performed: "Đã làm",
  not_performed: "Không làm được",
};

/** Việc đối tác: nói trạng thái bên đối tác, không nói "chờ xếp phòng". */
const TEN_TRANG_THAI_DOI_TAC: Record<string, string> = {
  CHO_LAY_MAU: "Đã gửi đối tác",
  DA_LAY_MAU: "Đối tác đã lấy mẫu",
  CHO_TAI_LIEU: "Đối tác đang làm",
  DA_GUI_KET_QUA: "Đối tác đã gửi kết quả",
};

type Khung = "benh-an" | "chi-dinh";

/** Khách của bác sĩ chính đang ở bước TƯ VẤN — bác sĩ chính chỉ xem (24/09). */
interface SapToi {
  visit_id: string;
  ten: string;
  ma_bn: string | null;
  so_tiep_don: number | null;
  so_booking?: number | null;
  dang_o: string;
}

export default function BanKham({
  phongMa,
  nut,
  staffId = null,
  cheDo = "kham",
}: {
  /** room_id (hoặc mã phòng cũ) trên đường dẫn. Rỗng = khách của tôi. */
  phongMa: string | null;
  /** Nút nào HIỆN — theo LEGO của tài khoản (`nutBanKham`, lib/roles.ts), không
   *  theo vai (đợt 3, 27/09/2026). Lệnh vẫn hỏi quyền ở máy chủ. */
  nut: NutBanKham;
  staffId?: string | null;
  /** "tu_van" = Bàn khám TƯ VẤN (dây H1/H3, 24/09/2026): CÙNG màn, đọc hàng tư
   *  vấn chung, nút "Bắt đầu tư vấn" / "Xong tư vấn". Không chép màn thứ hai. */
  cheDo?: "kham" | "tu_van";
}) {
  const tuVan = cheDo === "tu_van";
  // "Bác sĩ" = có quyền Hoàn tất khám; có Khám mà thiếu Hoàn tất = làm như thư
  // ký (chờ bác sĩ hoàn tất). Không còn hỏi vai (Tuyền 26/09: "chỉ cần lego").
  const laBacSi = nut.hoanTat;
  const laThuKy = nut.kham && !nut.hoanTat;
  const choBam = tuVan ? nut.tuVan : nut.kham;
  const [sapToi, setSapToi] = useState<SapToi[]>([]);

  const router = useRouter();
  const [phongs, setPhongs] = useState<PhongHomNay | null>(null);
  const [hang, setHang] = useState<DongHangCho[] | null>(null);
  const [bang, setBang] = useState<Bang | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [chonId, setChonId] = useState<string | null>(null);
  const [lanNap, setLanNap] = useState(0);

  // Phòng khám của người này hôm nay (theo lịch), để biết hàng chờ nào là của họ.
  useEffect(() => {
    let huy = false;
    void docBang<PhongHomNay>("phong-hom-nay").then((kq) => {
      if (huy) return;
      if (kq.ok) setPhongs(kq.data);
      else setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, []);

  const phongKham = useMemo(
    () => (phongs?.tat_ca_phong ?? []).filter(LA_PHONG_KHAM),
    [phongs],
  );
  const maPhong = phongMa;
  // `room_id` là định danh; mã phòng cũ vẫn khớp để link đã lưu không gãy.
  const phong =
    phongKham.find((p) => p.id === maPhong || p.code === maPhong) ?? null;

  useEffect(() => {
    if (phongs === null) return;
    let huy = false;
    const nap = async () => {
      const [h, b] = await Promise.all([
        docBang<{ hang_cho: DongHangCho[]; sap_toi?: SapToi[] }>(
          "hang-cho",
          tuVan ? { tu_van: "true" } : phong ? { phong: phong.id } : {},
        ),
        docBang<Bang>(null),
      ]);
      if (huy) return;
      if (!h.ok) setLoi(h.loi);
      else {
        setLoi(null);
        setHang(h.data.hang_cho.filter((d) => d.loai === (tuVan ? "TU_VAN" : "KHAM")));
        setSapToi(tuVan ? [] : (h.data.sap_toi ?? []));
      }
      if (b.ok) setBang(b.data);
    };
    void nap();
    // Làm mới đều: người khác (điều dưỡng đo xong, thư ký bấm) đổi hàng chờ.
    // SỰ KIỆN THAY NHỊP HỎI (27/09/2026): nghe tin bảng đổi qua dòng SSE chung
    // (`useNgheBang`) → nạp lại NGAY; nhịp hỏi giãn còn 60 giây làm lưới an toàn.
    const t = setInterval(() => void nap(), 60000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [phongs, phong, lanNap, tuVan]);

  const napLai = useCallback(() => setLanNap((n) => n + 1), []);
  useNgheBang(
    ["queue_entry", "consultation", "visit", "encounter_flow", "service_order", "form_instance", "tep_ket_qua", "vital_measurement"],
    napLai,
  );

  const hienRa = useMemo(() => {
    const kim = query.trim().toLocaleLowerCase("vi");
    const ds = hang ?? [];
    if (!kim) return ds;
    return ds.filter((d) =>
      [d.ten, d.ma_bn, String(d.so_thu_tu)].some((v) =>
        v?.toLocaleLowerCase("vi").includes(kim),
      ),
    );
  }, [hang, query]);

  const dangKham = hienRa.filter((d) => d.trang_thai === "serving");
  const dangCho = hienRa.filter(
    (d) => d.trang_thai === "waiting" || d.trang_thai === "called",
  );
  // "Kết quả cần đọc" = khách quay lại đọc kết quả (vòng REVIEW) — tách khỏi
  // hàng khám lần đầu để bác sĩ thấy ngay ai đã có kết quả (batch pilot 18/09).
  const canDoc = dangCho.filter((d) => d.vong === "REVIEW");
  const choKham = dangCho.filter((d) => d.vong !== "REVIEW");
  const buocKhac = hienRa.filter((d) => d.trang_thai === "blocked");
  // Hàng chờ trả MỖI PHIÊN KHÁM một dòng: khách có kết quả mới có một dòng
  // phiên đầu (đã xong) VÀ một dòng phiên đọc kết quả. Lượt còn phiên mở thì
  // chưa "khám xong" — không xếp vào nhóm đó; dòng đọc kết quả ghi giờ khám
  // phiên đầu (smoke 18/09: Thu hiện ở cả hai nhóm).
  const luotConMo = new Set(
    hienRa.filter((d) => d.trang_thai !== "done").map((d) => d.visit_id),
  );
  const daKhamLuc: Record<string, string | null> = {};
  for (const d of hienRa) {
    if (d.trang_thai === "done" && d.vong !== "REVIEW") daKhamLuc[d.visit_id] = d.xong_luc;
  }
  // Lượt đã đọc kết quả xong có HAI dòng "xong" (phiên đầu + phiên đọc):
  // chỉ giữ dòng xong muộn nhất cho mỗi lượt.
  const cuoiCung: Record<string, DongHangCho> = {};
  for (const d of hienRa) {
    if (d.trang_thai !== "done" || luotConMo.has(d.visit_id)) continue;
    const cu = cuoiCung[d.visit_id];
    if (!cu || (d.xong_luc ?? "") > (cu.xong_luc ?? "")) cuoiCung[d.visit_id] = d;
  }
  const daXong = hienRa.filter((d) => cuoiCung[d.visit_id] === d);
  // Thư ký: phân "chờ bác sĩ hoàn tất" với "đã hoàn tất" — thấy ngay lượt nào
  // mình đã nhập mà bác sĩ chưa hoàn tất (không còn bước ký riêng, 23/09/2026).
  const choKy = daXong.filter((d) => !d.da_ky);
  const daKy = daXong.filter((d) => d.da_ky);
  const macDinh = dangKham[0] ?? canDoc[0] ?? choKham[0] ?? buocKhac[0] ?? null;
  const chon = hienRa.find((d) => d.id === chonId) ?? macDinh;
  const luot = bang?.luot.find((l) => l.visit_id === chon?.visit_id) ?? null;

  // VÙNG LÀM VIỆC khi không đủ chỗ cho 3 cột (< 1536px): Bệnh án và Chỉ định &
  // kết quả thành hai tab. Ba cột tối thiểu 220 + 480 + 320 = 1052px, trong khi
  // laptop 1280 cạnh thanh bên chỉ còn ~925px → trước đây cả trang kéo ngang
  // (smoke 18/09). Khách quay lại đọc kết quả thì mở sẵn tab kết quả; bác sĩ
  // đổi tab thì giữ lựa chọn cho tới khi chọn khách khác. Cả hai khung vẫn
  // nằm trong cây (chỉ ẩn) — chữ đang gõ trong bệnh án không mất khi đổi tab.
  const [khungChon, setKhungChon] = useState<{ id: string; khung: Khung } | null>(null);
  const khungMacDinh: Khung =
    chon?.vong === "REVIEW" && chon.trang_thai !== "done" ? "chi-dinh" : "benh-an";
  const khung = khungChon && khungChon.id === chon?.id ? khungChon.khung : khungMacDinh;
  // HÀNG CHỜ GẬP khi đang mở phiếu v5 của bác sĩ chính (Tuyền 27/09/2026 — "y hệt
  // bản giao diện mẫu"): bản mẫu không có cột danh sách, phiếu chiếm trọn chiều
  // rộng. Dưới 1536px cột ~250px của danh sách bóp phiếu còn ~350px (tên khách vỡ
  // từng chữ). Mở lại bằng nút "Hàng chờ" ở thanh công việc; chọn khách là gập.
  const [moHang, setMoHang] = useState(false);
  const chonKhach = useCallback((id: string) => {
    setMoHang(false);
    setChonId(id);
    // Màn xếp chồng (< 1280): danh sách ở TRÊN vùng làm việc — tự cuộn tới.
    if (window.innerWidth < 1280) {
      requestAnimationFrame(() =>
        document.getElementById("vung-lam-viec")?.scrollIntoView({ block: "start" }),
      );
    }
  }, []);
  // [Bắt đầu …] ngay ở dòng hàng chờ (27/09 — bản mẫu tư vấn): cùng lệnh
  // `nhan-kham` với nút trong hồ sơ; xong thì mở hồ sơ khách đó.
  const [dangBatDau, setDangBatDau] = useState<string | null>(null);
  const batDauTuHang = useCallback(
    async (d: DongHangCho) => {
      setDangBatDau(d.id);
      setLoi(null);
      const kq = await guiThaoTac("nhan-kham", d.ref_id);
      setDangBatDau(null);
      if (!kq.ok) {
        setLoi(kq.loi);
        return;
      }
      chonKhach(d.id);
      napLai();
    },
    [chonKhach, napLai],
  );
  const nutBatDau =
    laBacSi || laThuKy || tuVan
      ? { nhan: tuVan ? "Bắt đầu tư vấn" : "Bắt đầu khám", dangGui: dangBatDau, onBam: batDauTuHang }
      : undefined;
  const gapHang = PHIEU_V5 && !tuVan && Boolean(chon) && !moHang;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {tuVan ? (
          <p className="text-sm text-ink-muted">
            Hàng tư vấn chung — bác sĩ tư vấn nào rảnh thì nhận. Đo sinh hiệu trước,
            nhưng khách chưa đo vẫn nhận được.
          </p>
        ) : (
        <>
        <label className="text-sm font-semibold text-ink" htmlFor="chon-phong">
          Phòng
        </label>
        <select
          id="chon-phong"
          value={phong?.id ?? ""}
          onChange={(e) => {
            setChonId(null);
            router.push(
              e.target.value
                ? `/ban-kham/${encodeURIComponent(e.target.value)}`
                : "/ban-kham",
            );
          }}
          className="min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink"
        >
          <option value="">Khách của tôi (mọi phòng)</option>
          {phongKham.map((p) => (
            <option key={p.id} value={p.id}>
              {p.ten}
              {phongs?.phong_cua_toi.some((m) => m.id === p.id) ? " · hôm nay" : ""}
            </option>
          ))}
        </select>
        </>
        )}
        {loi ? (
          <p role="alert" className="text-sm text-danger">
            {loi}
          </p>
        ) : null}
      </div>

      {!tuVan && nut.kham ? (
        <ChoBacSiQuyet lanNap={lanNap} onDaQuyet={napLai} />
      ) : null}

      {tuVan ? (
        <StatRow>
          <StatCard label="Chờ tư vấn" value={choKham.length} tone="brand" />
          <StatCard label="Chưa đo sinh hiệu" value={buocKhac.length} tone="warning" />
          <StatCard label="Đang tư vấn" value={dangKham.length} tone="neutral" />
          <StatCard label="Đã chuyển bác sĩ chính" value={daXong.length} tone="neutral" />
        </StatRow>
      ) : (
        <StatRow>
          <StatCard label="Chờ khám" value={choKham.length} tone="brand" />
          <StatCard label="Kết quả cần đọc" value={canDoc.length} tone="warning" />
          <StatCard label="Đang khám" value={dangKham.length} tone="neutral" />
          <StatCard label="Sắp tới" value={sapToi.length} tone="neutral" />
          <StatCard label="Đang ở bước khác" value={buocKhac.length} tone="warning" />
          <StatCard label="Đã khám xong" value={daXong.length} tone="neutral" />
        </StatRow>
      )}

      {/* Hai cột (hàng chờ · phiếu khám) từ khi bỏ cột "Chỉ định & kết quả"
          (23/09 khuya). Bật lại đường cũ (PHIEU_V5 = false) thì trả cột thứ ba:
          minmax 320px, 1fr. */}
      <div
        className={`grid items-start gap-4 2xl:grid-cols-[minmax(220px,0.55fr)_minmax(0,2.9fr)] ${
          gapHang ? "" : "xl:grid-cols-[auto_minmax(0,1fr)]"
        }`}
      >
        <aside
          aria-label="Hàng chờ khám"
          className={`min-w-0 overflow-hidden rounded-card bg-surface shadow-card xl:w-64 2xl:block 2xl:w-auto ${
            gapHang ? "hidden" : ""
          }`}
        >
          <div className="px-3 py-3">
            <label className="flex items-center gap-2 rounded-control bg-surface-muted px-3 py-2 text-ink-muted">
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Tìm khách</span>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Tìm tên, mã, số check-in"
                className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
              />
            </label>
          </div>
          {hang === null ? (
            <p className="px-3 pb-3 text-xs text-ink-muted">Đang tải hàng chờ…</p>
          ) : (
            <div className="max-h-[720px] overflow-y-auto">
              {tuVan ? (
                <>
                  <Nhom ten="Đang tư vấn" chinh chuDang="đang tư vấn" ds={dangKham} chon={chon?.id ?? null} onChon={chonKhach} trong="Chưa có ai đang tư vấn." />
                  <Nhom ten="Chờ tư vấn" chinh ds={choKham} chon={chon?.id ?? null} onChon={chonKhach} trong="Không có khách đang chờ." batDau={nutBatDau} />
                  <Nhom ten="Chưa đo sinh hiệu" ghiChu="vẫn nhận được" ds={buocKhac} chon={chon?.id ?? null} onChon={chonKhach} />
                  <Nhom ten="Đã chuyển bác sĩ chính hôm nay" gap ds={daXong} chon={chon?.id ?? null} onChon={chonKhach} />
                </>
              ) : (
              <>
              <Nhom ten={laThuKy ? "Đang hỗ trợ" : "Đang khám"} chinh ds={dangKham} chon={chon?.id ?? null} onChon={chonKhach} trong="Chưa có ai đang khám." />
              <Nhom ten="Kết quả cần đọc" ds={canDoc} chon={chon?.id ?? null} onChon={chonKhach} daKhamLuc={daKhamLuc} />
              <Nhom ten="Chờ khám" chinh ds={choKham} chon={chon?.id ?? null} onChon={chonKhach} trong="Không có khách đang chờ." batDau={nutBatDau} />
              <NhomSapToi ds={sapToi} />
              <Nhom ten="Đang ở bước khác" ds={buocKhac} chon={chon?.id ?? null} onChon={chonKhach} />
              {laThuKy ? (
                <>
                  <Nhom ten="Chờ bác sĩ hoàn tất" ds={choKy} chon={chon?.id ?? null} onChon={chonKhach} />
                  <Nhom ten="Đã hoàn tất hôm nay" gap ds={daKy} chon={chon?.id ?? null} onChon={chonKhach} />
                </>
              ) : (
                <Nhom ten="Đã khám xong hôm nay" gap ds={daXong} chon={chon?.id ?? null} onChon={chonKhach} />
              )}
              </>
              )}
            </div>
          )}
        </aside>

        {/* ≥ 1536: `contents` → Bệnh án và Chỉ định & kết quả là cột 2 và 3.
            Dưới đó: một cột, chọn bằng tab. */}
        <div id="vung-lam-viec" className="grid min-w-0 scroll-mt-4 gap-3 2xl:contents">
          {/* Tab "Chỉ định & kết quả" + cột chỉ định OFF (Tuyền 23/09 khuya: "xoá đi,
              chỉ định ở trong form khám rồi mà"). Phiếu v5 có mục C/F (chỉ định),
              kết quả + tệp ngay dưới mục C. */}
          {!PHIEU_V5 ? (
          <ThanhTab
            nhan="Vùng làm việc"
            className="2xl:hidden"
            muc={[
              { ma: "benh-an", nhan: "Bệnh án" },
              { ma: "chi-dinh", nhan: "Chỉ định & kết quả", nhac: khungMacDinh === "chi-dinh" },
            ]}
            chon={khung}
            onChon={(k) => chon && setKhungChon({ id: chon.id, khung: k })}
          />
          ) : null}
          <div
            className={`min-w-0 ${PHIEU_V5 || khung === "benh-an" ? "" : "hidden"} 2xl:block`}
          >
            <HoSo
              onHangCho={
                PHIEU_V5 && !tuVan && chon ? () => setMoHang((x) => !x) : undefined
              }
              hangMo={!gapHang}
              soCho={choKham.length + canDoc.length}
              dong={chon}
              daKhamLuc={chon ? (daKhamLuc[chon.visit_id] ?? null) : null}
              luot={luot}
              choBam={choBam}
              laBacSi={laBacSi}
              staffId={staffId}
              onDaBam={napLai}
              tuVan={tuVan}
            />
          </div>
          {!PHIEU_V5 ? (
          <div className={`min-w-0 ${khung === "chi-dinh" && !tuVan ? "" : "hidden"} ${tuVan ? "" : "2xl:block"}`}>
            <ChiDinhPanel
              dong={chon}
              luot={luot}
              dichVu={bang?.dich_vu ?? []}
              laBacSi={laBacSi}
              laThuKy={laThuKy}
              onDaGui={napLai}
            />
          </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** "Sắp tới — đang ở tư vấn": bác sĩ chính THẤY trước, chưa gọi được (24/09).
 *  Chỉ xem — khách vào "Chờ khám" khi bác sĩ tư vấn bấm Xong. */
function NhomSapToi({ ds }: { ds: SapToi[] }) {
  if (ds.length === 0) return null;
  return (
    <section>
      <h3 className="border-y border-line bg-surface-muted px-3 py-2 text-xs font-semibold text-ink-soft">
        Sắp tới — đang ở tư vấn ({ds.length})
      </h3>
      <ul>
        {ds.map((d) => (
          <li key={d.visit_id} className="flex items-center gap-2.5 px-2.5 py-2.5 text-xs">
            <SoLuot dang="tron" checkin={d.so_tiep_don} booking={d.so_booking} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-emph font-semibold text-ink">{d.ten}</span>
              <span className="block truncate text-ink-muted">
                {d.ma_bn ?? ""} · {d.dang_o}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Nhom({
  ten,
  ds,
  chon,
  onChon,
  trong,
  daKhamLuc,
  chinh = false,
  gap = false,
  ghiChu,
  batDau,
  chuDang = "đang khám",
}: {
  ten: string;
  ds: DongHangCho[];
  chon: string | null;
  onChon: (id: string) => void;
  trong?: string;
  /** visit_id → giờ xong phiên khám đầu (chỉ nhóm "Kết quả cần đọc"). */
  daKhamLuc?: Record<string, string | null>;
  /** Nhóm chính (Đang · Chờ): số đếm nền brand. */
  chinh?: boolean;
  /** Nhóm gập sẵn (đã xong hôm nay) — bấm tiêu đề để mở. */
  gap?: boolean;
  /** Chữ nhỏ bên phải tiêu đề ("vẫn nhận được"). */
  ghiChu?: string;
  /** Nút [Bắt đầu …] NGAY Ở DÒNG khách (Tuyền 27/09 — bản mẫu tư vấn, làm nhỏ). */
  batDau?: { nhan: string; dangGui: string | null; onBam: (d: DongHangCho) => void };
  /** "đang tư vấn" ở bàn tư vấn. */
  chuDang?: string;
}) {
  const [mo, setMo] = useState(!gap);
  if (ds.length === 0 && !trong) return null;
  const tieuDe = (
    <>
      <span>
        {ten}
        <span
          className={`ml-1.5 inline-grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-meta tabular-nums ${
            chinh ? "bg-brand-600 text-white" : "bg-surface-sunken text-ink-soft"
          }`}
        >
          {ds.length}
        </span>
      </span>
      {ghiChu ? <span className="font-normal text-ink-faint">{ghiChu}</span> : null}
      {gap ? <span aria-hidden="true">{mo ? "▾" : "▸"}</span> : null}
    </>
  );
  const kieuTieuDe =
    "flex w-full items-center justify-between gap-2 border-y border-line bg-surface-muted px-3 py-2 text-left text-xs font-semibold text-ink-soft";
  return (
    <section>
      {gap ? (
        <button type="button" aria-expanded={mo} onClick={() => setMo((m) => !m)} className={kieuTieuDe}>
          {tieuDe}
        </button>
      ) : (
        <h3 className={kieuTieuDe}>{tieuDe}</h3>
      )}
      {!mo ? null : ds.length === 0 ? (
        <p className="px-3 py-3 text-xs text-ink-faint">{trong}</p>
      ) : (
        ds.map((d) => {
          const dangChon = d.id === chon;
          return (
            <div
              key={d.id}
              className={`border-b border-l-3 border-b-line ${
                dangChon
                  ? "border-l-brand-500 bg-surface-selected"
                  : "border-l-transparent bg-surface hover:bg-surface-sunken"
              }`}
            >
              <button
                type="button"
                onClick={() => onChon(d.id)}
                aria-current={dangChon ? "true" : undefined}
                className="flex w-full items-center gap-2.5 px-2.5 py-2.5 text-left"
              >
                <SoLuot dang="tron" checkin={d.so_tiep_don ?? d.so_thu_tu} booking={d.so_booking} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-emph font-semibold text-ink" title={d.ten}>
                      {d.ten}
                    </span>
                    {d.uu_tien ? (
                      <span title={d.uu_tien_ly_do ?? undefined}>
                        <PriorityChip priority="P0" />
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-ink-muted">
                    <span className="truncate">
                      {d.dich_vu_kham ?? "Chưa gán dịch vụ"}
                      {d.bac_si ? ` · ${d.bac_si}` : ""}
                    </span>
                    {d.trang_thai === "done" ? (
                      <span className="text-success">xong {gioVn(d.xong_luc)}</span>
                    ) : d.trang_thai === "serving" ? (
                      <span className="font-semibold text-brand-700">{chuDang} {soPhutTu(d.bat_dau_luc)}</span>
                    ) : (
                      <span>chờ {soPhutTu(d.vao_hang_luc)}</span>
                    )}
                    {d.vong === "REVIEW" ? (
                      <span className="text-warning">
                        {d.trang_thai === "done"
                          ? "đã đọc kết quả"
                          : `đã khám${daKhamLuc?.[d.visit_id] ? ` ${gioVn(daKhamLuc[d.visit_id])}` : ""} · có kết quả mới`}
                      </span>
                    ) : null}
                  </span>
                </span>
              </button>
              {batDau ? (
                <div className="flex justify-end px-2.5 pb-2 -mt-1">
                  <Button
                    size="sm"
                    variant="soft"
                    disabled={batDau.dangGui !== null}
                    onClick={() => batDau.onBam(d)}
                  >
                    {batDau.dangGui === d.id ? "Đang ghi…" : batDau.nhan}
                  </Button>
                </div>
              ) : null}
            </div>
          );
        })
      )}
    </section>
  );
}

function HoSo({
  dong,
  daKhamLuc,
  luot,
  choBam,
  laBacSi,
  staffId,
  onDaBam,
  tuVan = false,
  onHangCho,
  hangMo = true,
  soCho = 0,
}: {
  /** Mở / gập cột hàng chờ (phiếu v5 bác sĩ chính — 27/09/2026). */
  onHangCho?: () => void;
  hangMo?: boolean;
  soCho?: number;
  dong: DongHangCho | null;
  daKhamLuc: string | null;
  luot: Luot | null;
  choBam: boolean;
  laBacSi: boolean;
  staffId: string | null;
  onDaBam: () => void;
  /** Bàn khám tư vấn: Bắt đầu / Xong tư vấn thay cho Bắt đầu khám / Hoàn tất. */
  tuVan?: boolean;
}) {
  const [xemLai, setXemLai] = useState<{ id: string; luot: LuotTruoc } | null>(null);
  const dangXem = xemLai && xemLai.id === dong?.id ? xemLai.luot : null;
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<{ id: string; cau: string } | null>(null);
  const [xemLuot, setXemLuot] = useState<string | null>(null);
  // Trạng thái phiếu (đã lưu hết chưa) GẮN VỚI KHÁCH đang mở, không xoá bằng
  // effect: bấm thật 24/09 — effect của phiếu con chạy TRƯỚC effect của màn
  // này, nên "xoá khi đổi khách" đè mất báo "sẵn sàng" đầu tiên của phiếu và
  // [Xong tư vấn] / [Hoàn tất] kẹt ở "Đang kiểm tra trạng thái bệnh án" mãi.
  const [gateTheoKhach, setGateTheoKhach] = useState<{
    id: string;
    gate: ClinicalCompletionGate;
  } | null>(null);
  const completionGate =
    gateTheoKhach && gateTheoKhach.id === dong?.id ? gateTheoKhach.gate : null;
  const khachId = dong?.id ?? null;
  const baoGate = useCallback(
    (g: ClinicalCompletionGate) => {
      if (khachId) setGateTheoKhach({ id: khachId, gate: g });
    },
    [khachId],
  );
  // Hỏi lại trước khi Hoàn tất — dải xác nhận tại chỗ, theo đúng khách đang mở.
  const [hoiHoanTat, setHoiHoanTat] = useState<string | null>(null);
  // Thẻ khách (phiếu v5 / bàn tư vấn) đã hiện chưa — hiện rồi thì tóm tắt lượt
  // vẽ TRONG thẻ, bỏ ô riêng phía trên (Tuyền 27/09 tối).
  const [coTheKhach, setCoTheKhach] = useState(false);

  const conChiDinhDangLam =
    luot?.chi_dinh.some((c) =>
      ["authorized", "assigned", "in_progress"].includes(c.trang_thai),
    ) ?? false;

  const completionMode: ClinicalCompletionMode =
    conChiDinhDangLam ? "HANDOFF" : "TERMINAL";

  if (!dong) {
    return (
      <section
        aria-label="Hồ sơ khám bệnh"
        className="grid min-h-96 place-items-center rounded-card bg-surface p-8 text-center shadow-card"
      >
        <div>
          <Stethoscope className="mx-auto size-8 text-brand-500" aria-hidden="true" />
          <p className="mt-3 font-medium text-ink">Chọn một khách trong hàng chờ</p>
          <p className="mt-1 text-sm text-ink-muted">
            Khách vào hàng chờ khám sau khi điều dưỡng đo sinh hiệu xong.
          </p>
        </div>
      </section>
    );
  }

  const gui = async (thaoTac: "nhan-kham" | "kham-xong" | "xong-tu-van") => {
    setDangGui(true);
    setLoi(null);
    // Gọi khách: theo CHỖ CHỜ; bắt đầu/khám xong: theo PHIÊN KHÁM.
    const kq = await guiThaoTac(thaoTac, dong.ref_id);
    setDangGui(false);
    setHoiHoanTat(null);
    if (!kq.ok) setLoi({ id: dong.id, cau: kq.loi });
    else onDaBam();
  };

  const bam = async (thaoTac: "nhan-kham" | "kham-xong" | "xong-tu-van") => {
    if (thaoTac === "kham-xong" || thaoTac === "xong-tu-van") {
      if (thaoTac === "kham-xong" && completionMode === "TERMINAL" && !laBacSi) {
        setLoi({
          id: dong.id,
          cau: "Chờ bác sĩ hoàn tất lượt khám.",
        });
        return;
      }

      // Phiếu còn chữ chưa lưu thì đợi — cả Hoàn tất lẫn Xong tư vấn.
      if (!completionGate) {
        setLoi({
          id: dong.id,
          cau: "Đang kiểm tra trạng thái bệnh án. Thử lại sau một chút.",
        });
        return;
      }

      if (!completionGate.ok) {
        // Còn chữ chưa lưu (đợt 3, 27/09/2026 — góp ý B9): KHÔNG bắt người
        // dùng đợi "Đã lưu" rồi bấm lại — lưu nốt ngay, xong mới gửi. Lưu
        // không được thì không gửi và nói lý do ngay dưới nút.
        if (completionGate.code === "UNSAVED_CHANGES" && completionGate.luuNot) {
          setDangGui(true);
          setLoi(null);
          const daLuu = await completionGate.luuNot();
          setDangGui(false);
          if (!daLuu) {
            setLoi({
              id: dong.id,
              cau:
                "Nội dung vừa gõ CHƯA lưu được nên chưa Hoàn tất. Xem dòng trạng thái lưu, bấm [Thử lại] rồi bấm lại.",
            });
            return;
          }
        } else {
          setLoi({
            id: dong.id,
            cau: completionGate.message ?? "Hồ sơ chưa sẵn sàng để Hoàn tất.",
          });
          return;
        }
      }

      if (thaoTac === "kham-xong" && HOI_LAI_KHI_HOAN_TAT) {
        setLoi(null);
        setHoiHoanTat(dong.id);
        return;
      }
    }
    await gui(thaoTac);
  };
  const t = tone(dong);
  const sh = luot?.sinh_hieu ?? null;
  const loiHienTai = loi?.id === dong.id ? loi.cau : null;
  // PHIẾU KHÁM BÁC SĨ CHÍNH theo bản giao diện mẫu (Tuyền 27/09/2026): thẻ khách +
  // thẻ sinh hiệu nằm TRONG phiếu, Hoàn tất ở chân cột phải — Bàn khám chỉ giữ
  // một thanh công việc gọn (trạng thái · số thứ tự · giờ · Bắt đầu khám).
  const laPhieuMoi = PHIEU_V5 && dong.loai === "KHAM" && !dangXem && Boolean(dong.form_code);
  // BÀN TƯ VẤN theo bản giao diện mẫu (27/09/2026, mục 8): thẻ khách + sinh hiệu
  // dùng chung với phiếu bác sĩ chính, [Xong tư vấn] ở thanh dính đáy.
  const laTuVanMoi = TU_VAN_O_TU_DO && dong.loai === "TU_VAN" && !dangXem;
  const gon = laPhieuMoi || laTuVanMoi;
  const nutHoanTat =
    choBam && dong.trang_thai === "serving" ? (
      <div className="flex flex-col gap-2">
        <Button
          type="button"
          size="lg"
          variant="primary"
          disabled={dangGui}
          onClick={() => void bam(tuVan ? "xong-tu-van" : "kham-xong")}
          className={laPhieuMoi ? "lg:w-full" : tuVan ? "w-full sm:w-auto" : ""}
        >
          <CheckCircle2 className="size-4" aria-hidden="true" />
          {dangGui ? "Đang ghi…" : tuVan ? "Xong tư vấn — chuyển bác sĩ chính" : "Hoàn tất"}
        </Button>
        {!tuVan && !laBacSi && completionMode === "TERMINAL" ? (
          <p className="text-meta text-ink-muted">Chờ bác sĩ hoàn tất lượt khám.</p>
        ) : null}
        {hoiHoanTat === dong.id ? (
          <XacNhanTaiCho
            cau={
              completionMode === "HANDOFF"
                ? `Hoàn tất lượt khám này cho ${dong.ten}? Khách còn chỉ định sẽ sang hàng chờ phòng dịch vụ. Phiếu vẫn sửa được sau.`
                : `Hoàn tất khám cho ${dong.ten}? Phiếu vẫn sửa được sau.`
            }
            nhanDongY="Hoàn tất"
            dangGui={dangGui}
            onDongY={() => void gui("kham-xong")}
            onThoi={() => setHoiHoanTat(null)}
          />
        ) : null}
        {loiHienTai ? (
          <p role="alert" className="text-meta text-danger">
            {loiHienTai}
          </p>
        ) : null}
      </div>
    ) : dong.da_ky ? (
      <span className="text-center text-meta text-ink-muted">
        <Chip tone="success">Đã hoàn tất{dong.ky_luc ? ` ${gioVn(dong.ky_luc)}` : ""}</Chip>
        <br />
        vẫn sửa được
      </span>
    ) : null;

  const hanhDong = choBam ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {dong.trang_thai === "waiting" ||
            dong.trang_thai === "called" ||
            (tuVan && dong.trang_thai === "blocked") ? (
              <button
                type="button"
                disabled={dangGui}
                onClick={() => void bam("nhan-kham")}
                className="inline-flex min-h-11 items-center gap-2 rounded-control bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                <Stethoscope className="size-4" aria-hidden="true" />
                {dangGui ? "Đang ghi…" : tuVan ? "Bắt đầu tư vấn" : "Bắt đầu khám"}
              </button>
            ) : null}
            {tuVan && dong.trang_thai === "blocked" ? (
              <p className="text-xs text-warning">
                Khách chưa đo sinh hiệu — vẫn nhận tư vấn được.
              </p>
            ) : null}
            {!tuVan && dong.trang_thai === "blocked" ? (
              <p className="text-xs text-warning">
                Khách đang ở một bước khác (đang làm dịch vụ) — chưa gọi vào được.
              </p>
            ) : null}
            {loiHienTai && dong.trang_thai !== "serving" ? (
              <p role="alert" className="text-xs text-danger">
                {loiHienTai}
              </p>
            ) : null}
          </div>
        ) : null;
  // Tóm tắt lượt vẽ trong thẻ khách: trạng thái · thời gian · nút. Loại khám và
  // số booking/check-in đã có sẵn trên thẻ, không lặp.
  const tomTatGon = gon ? (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip tone={t.tone} label={t.nhan} size="md" />
        {dong.vong === "REVIEW" && dong.trang_thai !== "done" ? (
          <StatusChip
            tone="blocked"
            label={`Đã khám${daKhamLuc ? ` ${gioVn(daKhamLuc)}` : ""} · có kết quả mới cần đọc`}
            size="md"
          />
        ) : null}
        <span className="text-meta text-ink-muted">
          {dong.trang_thai === "serving" ? "Đã khám" : "Đã chờ"}{" "}
          <b className="text-ink">
            {(dong.trang_thai === "serving" ? soPhutTu(dong.bat_dau_luc) : soPhutTu(dong.vao_hang_luc)) || "—"}
          </b>
          {" · "}Từ lúc check-in <b className="text-ink">{soPhutTu(dong.checkin_luc) || "—"}</b>
        </span>
        <span className="ml-auto flex flex-wrap gap-1">
          {onHangCho ? (
            <Button size="sm" variant="ghost" aria-expanded={hangMo} onClick={onHangCho}>
              ☰ {hangMo ? "Ẩn hàng chờ" : `Hàng chờ (${soCho})`}
            </Button>
          ) : null}
          <Button size="sm" variant="ghost" onClick={() => setXemLuot(dong.visit_id)}>
            Xem lại cả lượt
          </Button>
        </span>
      </div>
      {xemLuot ? <XemLuot visitId={xemLuot} onDong={() => setXemLuot(null)} /> : null}
      {hanhDong}
    </div>
  ) : null;

  return (
    <section
      aria-label="Hồ sơ khám bệnh"
      className={
        gon ? "min-w-0 space-y-3" : "min-w-0 overflow-hidden rounded-card bg-surface shadow-card"
      }
    >
      {gon && coTheKhach ? null : (
      <header
        className={
          gon ? "rounded-card border border-hairline bg-surface px-4 py-3" : "px-4 py-3"
        }
      >
        <div className="flex flex-wrap items-center gap-3">
          {gon ? null : (
            <span className="grid size-11 place-items-center rounded-full border border-line bg-surface-sunken text-sm font-semibold text-ink-soft">
              {initials(dong.ten)}
            </span>
          )}
          <div className="min-w-44 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              {gon ? null : (
                <h2 className="text-base font-semibold text-ink">{dong.ten}</h2>
              )}
              <StatusChip tone={t.tone} label={t.nhan} size="md" />
              {dong.vong === "REVIEW" && dong.trang_thai !== "done" ? (
                <StatusChip
                  tone="blocked"
                  label={`Đã khám${daKhamLuc ? ` ${gioVn(daKhamLuc)}` : ""} · có kết quả mới cần đọc`}
                  size="md"
                />
              ) : null}
            </div>
            <p className="text-xs text-ink-muted">
              {dong.ma_bn} · {dong.bac_si ?? "Chưa có bác sĩ"}
            </p>
            <div className="mt-1 -ml-3 flex flex-wrap gap-1">
              {onHangCho ? (
                <Button size="sm" variant="ghost" aria-expanded={hangMo} onClick={onHangCho}>
                  ☰ {hangMo ? "Ẩn hàng chờ" : `Hàng chờ (${soCho})`}
                </Button>
              ) : null}
              <Button size="sm" variant="ghost" onClick={() => setXemLuot(dong.visit_id)}>
                Xem lại cả lượt
              </Button>
            </div>
            {xemLuot ? <XemLuot visitId={xemLuot} onDong={() => setXemLuot(null)} /> : null}
          </div>
          <dl className="grid grid-cols-4 divide-x divide-line text-xs">
            <Truong
              nhan="Booking · Check-in"
              gia={`${dong.so_booking != null ? `#${dong.so_booking}` : "—"} · ${dong.so_tiep_don ?? dong.so_thu_tu}`}
            />
            <Truong
              nhan={dong.trang_thai === "serving" ? "Đã khám" : "Đã chờ"}
              gia={
                dong.trang_thai === "serving"
                  ? soPhutTu(dong.bat_dau_luc) || "—"
                  : soPhutTu(dong.vao_hang_luc) || "—"
              }
            />
            <Truong
              nhan="Từ lúc check-in"
              gia={soPhutTu(dong.checkin_luc) || "—"}
            />
            <Truong nhan="Loại khám" gia={dong.dich_vu_kham ?? "Chưa gán dịch vụ"} />
          </dl>
        </div>

        {/* CHECK-IN / CHECK-OUT PHÒNG.

            BỎ [GỌI VÀO KHÁM] (Tuyền chốt 23/09/2026): `Gọi vào → Bắt đầu` là
            hai bước cho một việc. `nhan-kham` vốn đã dời con trỏ "khách đang ở
            đâu" (`_cap_nhat_vi_tri` trong `start_consultation`), nên bỏ nút
            không để state nào mắc lại.

            `called_at` trong database giữ nguyên — lượt cũ còn đọc được giờ
            gọi; chỉ thôi ghi mới từ màn này. */}
        {hanhDong}

        {gon ? null : (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-control border border-line bg-surface-muted px-3 py-2 text-xs text-ink-soft">
          <HeartPulse className="size-4 shrink-0 text-brand-600" aria-hidden="true" />
          {sh ? (
            <>
              <span>
                HA <b>{sh.tam_thu ?? "—"}/{sh.tam_truong ?? "—"}</b>
              </span>
              <span>Mạch <b>{sh.mach ?? "—"}</b></span>
              <span>Nhiệt <b>{sh.nhiet_do ?? "—"}</b></span>
              <span>Nhịp thở <b>{sh.nhip_tho ?? "—"}</b></span>
              <span>SpO₂ <b>{sh.spo2 ?? "—"}</b></span>
              <span>Cân <b>{sh.can_nang ?? "—"}</b></span>
              <span>Cao <b>{sh.chieu_cao ?? "—"}</b></span>
              <span>BMI <b>{sh.bmi ?? "—"}</b></span>
              {sh.muc_do_dau !== null ? <span>Đau <b>{sh.muc_do_dau}</b></span> : null}
              <span className="text-ink-muted">
                · {sh.nguoi_do ?? "?"} đo lúc {gioVn(sh.luc)}
              </span>
            </>
          ) : (
            <span>Chưa có sinh hiệu.</span>
          )}
        </div>
        )}
        {dong.da_ky ? (
          <p className="mt-2 text-xs font-medium text-ink-soft">
            Hồ sơ đã hoàn tất{dong.nguoi_ky ? ` · ${dong.nguoi_ky}` : ""}
            {dong.ky_luc ? ` · ${gioVn(dong.ky_luc)}` : ""} — phiếu chỉ xem.
          </p>
        ) : null}
      </header>
      )}

      <TomTatLuotContext.Provider value={gon ? { noiDung: tomTatGon, baoHien: setCoTheKhach } : null}>
      <div className={gon ? "space-y-3" : "p-3 pt-0"}>
        <LuotKhamTruoc
          clinicPatientId={dong.clinic_patient_id}
          visitIdHienTai={dong.visit_id}
          dangXem={dangXem}
          onXem={(l) => setXemLai(l ? { id: dong.id, luot: l } : null)}
        />
        {dangXem ? (
          <div className="mt-2">
            <ServiceFormEngine
              key={dangXem.visit_id}
              visitId={dangXem.visit_id}
              serviceCode={dangXem.service_code}
              readOnly
            />
          </div>
        ) : laTuVanMoi ? (
          // Ô chữ tư vấn + mục B của CHÍNH phiếu khám lượt (Tuyền 24/09: "cho cả 2
          // bác sĩ đều thêm sửa xoá được, hồ sơ là open") sau công tắc "Thông tin
          // cơ bản" (25/09, mặc định đóng) + thanh dính đáy [Xong tư vấn] (27/09).
          <BanTuVan
            key={dong.ref_id}
            visitId={dong.visit_id}
            consultationId={dong.ref_id}
            clinicPatientId={dong.clinic_patient_id}
            coPhieu={PHIEU_V5 && Boolean(dong.form_code)}
            choGhi={choBam}
            onTrangThai={baoGate}
            datChiDinh={async (codes, batBuoc) => {
              const kq = await guiThaoTac("chi-dinh", dong.ref_id, {
                service_codes: codes,
                bat_buoc_codes: batBuoc,
              });
              return kq.ok ? { ok: true } : { ok: false, loi: kq.loi };
            }}
            onDaDat={onDaBam}
            nutXong={nutHoanTat}
          />
        ) : PHIEU_V5 && (dong.loai === "KHAM" || dong.loai === "TU_VAN") ? (
          // Bàn khám tư vấn ghi vào CHÍNH phiếu khám của lượt (Tuyền chốt
          // 24/09) — bác sĩ chính mở ra thấy ngay phần tư vấn đã điền.
          <>
            <PhieuKhamLuot
              key={dong.visit_id}
              visitId={dong.visit_id}
              clinicPatientId={dong.clinic_patient_id}
              choGhi={choBam}
              datChiDinh={async (codes, batBuoc) => {
                const kq = await guiThaoTac("chi-dinh", dong.ref_id, {
                  service_codes: codes,
                  bat_buoc_codes: batBuoc,
                });
                return kq.ok ? { ok: true } : { ok: false, loi: kq.loi };
              }}
              onDaDat={onDaBam}
              onTrangThai={baoGate}
              chanRay={laPhieuMoi ? nutHoanTat : undefined}
            />
            {dong.form_code === "SK" ? (
              <ThaiKy
                key={`tk-${dong.clinic_patient_id}`}
                clinicPatientId={dong.clinic_patient_id}
                visitId={dong.visit_id}
              />
            ) : null}
          </>
        ) : !dong.form_code ? (
          <p className="rounded-control border border-dashed border-warning bg-warning-bg px-3 py-6 text-center text-xs text-warning">
            Dịch vụ “{dong.dich_vu_kham ?? "chưa gán"}” chưa gắn phiếu khám nào.
            Vào Cấu trúc phòng khám để gán, hoặc chọn đúng loại khám khi đặt lịch.
          </p>
        ) : (
          <>
            <ServiceFormEngine
              key={dong.visit_id}
              visitId={dong.visit_id}
              serviceCode={dong.form_code}
              // Hoàn tất KHÔNG khoá (Tuyền chốt 23/09/2026): khách đã khám xong
              // vẫn sửa được. Chỉ lượt CŨ đã từng ký mới chỉ-xem.
              readOnly={!choBam || Boolean(dong.da_ky)}
            />
            {/* Sản khoa: thai kỳ CHÍNH THỨC (bảng `pregnancy`) — chỉ bác sĩ ghi. */}
            {dong.form_code === "SK" ? (
              <ThaiKy
                key={`tk-${dong.clinic_patient_id}`}
                clinicPatientId={dong.clinic_patient_id}
                visitId={dong.visit_id}
              />
            ) : null}
          </>
        )}
        {/* BỆNH ÁN · CHẨN ĐOÁN · ĐƠN THUỐC (demo 17/09/2026). Thư ký nhập, màn
            bác sĩ tự tải lại khi bên kia lưu (sự kiện realtime), bác sĩ duyệt
            đơn rồi bấm Hoàn tất ở cuối hồ sơ — trạng thái truyền vào là
            COMPLETED để form KHÔNG bày nút "Kết thúc khám" của đường cũ. */}
        {!PHIEU_V5 && dong.loai === "KHAM" && dong.appointment_id && !dangXem ? (
          <details open className="mt-3 rounded-card border border-line">
            <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-ink">
              Bệnh án · Chẩn đoán · Đơn thuốc · Lời dặn
            </summary>
            <ClinicalRecordForm
              key={dong.appointment_id}
              appt={
                {
                  id: dong.appointment_id,
                  slot_start: dong.checkin_luc ?? dong.vao_hang_luc ?? "",
                  status: "COMPLETED",
                  queue_number: String(dong.so_thu_tu),
                  patient: {
                    clinic_patient_id: dong.clinic_patient_id,
                    patient_code: dong.ma_bn,
                    full_name: dong.ten,
                    date_of_birth: null,
                    phone_primary: null,
                    phone_secondary: null,
                    gender: null,
                    ethnicity: null,
                    nationality: null,
                    occupation: null,
                    patient_objection: null,
                    address: null,
                    guardian_name: null,
                  },
                  service: dong.dich_vu_kham
                    ? { name: dong.dich_vu_kham, form_code: dong.form_code }
                    : null,
                } as unknown as DoctorApptRow
              }
              staffId={staffId}
              onClose={() => {}}
              canSign={laBacSi}
              // Hoàn tất KHÔNG khoá (Tuyền chốt 23/09/2026): khách đã khám xong
              // vẫn sửa được. Chỉ lượt CŨ đã từng ký mới chỉ-xem.
              readOnly={!choBam || Boolean(dong.da_ky)}
              completionMode={completionMode}
              onCompletionGateChange={baoGate}
            />
          </details>
        ) : null}
        {/* HOÀN TẤT — nút duy nhất để khép phiên khám, đặt CUỐI hồ sơ: điền
            xong bệnh án và chỉ định rồi mới bấm (Tuyền chốt 23/09/2026). Phiên
            cuối thì khép lượt khám; còn chỉ định thì khách sang phòng. Không
            khoá hồ sơ — bệnh án vẫn sửa được sau khi hoàn tất. */}
        {!gon && nutHoanTat ? (
          <div className="mt-3 border-t border-line pt-3">{nutHoanTat}</div>
        ) : null}
      </div>
      </TomTatLuotContext.Provider>
    </section>
  );
}

function Truong({ nhan, gia }: { nhan: string; gia: string }) {
  return (
    <div className="max-w-36 px-3 first:pl-0">
      <dt className="text-ink-faint">{nhan}</dt>
      <dd className="mt-0.5 truncate font-medium text-ink" title={gia}>
        {gia}
      </dd>
    </div>
  );
}

function ChiDinhPanel({
  dong,
  luot,
  dichVu,
  laBacSi,
  laThuKy,
  onDaGui,
}: {
  dong: DongHangCho | null;
  luot: Luot | null;
  dichVu: DichVu[];
  laBacSi: boolean;
  laThuKy: boolean;
  onDaGui: () => void;
}) {
  const [go, setGo] = useState("");
  const [chon, setChon] = useState<{ id: string; ma: string[] }>({ id: "", ma: [] });
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [moKetQua, setMoKetQua] = useState<string | null>(null);
  const [moPhieu, setMoPhieu] = useState<string | null>(null);

  const dsChon = chon.id === dong?.id ? chon.ma : [];
  const dangKham = dong?.trang_thai === "serving";
  const chiDinh = (luot?.chi_dinh ?? []).filter((c) => c.trang_thai !== "cancelled");
  const nhap = chiDinh.filter((c) => c.trang_thai === "draft");

  if (!dong) {
    return (
      <section className="rounded-card bg-surface-muted p-3.5 text-xs text-ink-muted shadow-card">
        Chọn khách để xem và ghi chỉ định.
      </section>
    );
  }

  const them = (ma: string) => {
    if (!ma || dsChon.includes(ma)) return;
    setChon({ id: dong.id, ma: [...dsChon, ma] });
    setGo("");
  };

  const gui = async () => {
    if (dsChon.length === 0 && !(laBacSi && nhap.length > 0)) return;
    setDangGui(true);
    setLoi(null);
    // Lát CD-01: một lệnh cho cả bác sĩ lẫn thư ký y khoa — chỉ định là chỉ
    // định luôn, không có bước duyệt (Tuyền, tin số 149).
    //
    // Đường cũ chỉ còn dùng cho các bản NHÁP có từ trước: chúng vẫn nằm trong
    // database và chỉ bác sĩ mới dọn được. Khi không còn bản nháp nào, đường ấy
    // bị xoá.
    const kq =
      dsChon.length > 0
        ? await guiThaoTac("chi-dinh", dong.ref_id, { service_codes: dsChon })
        : await guiThaoTac("duyet-chi-dinh", dong.ref_id, {
            service_codes: [],
            draft_order_ids: nhap.map((c) => c.id),
            expected_versions: Object.fromEntries(nhap.map((c) => [c.id, c.version])),
          });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setChon({ id: dong.id, ma: [] });
    onDaGui();
  };

  return (
    <section
      aria-label="Chỉ định và kết quả"
      className="min-w-0 rounded-card bg-surface-muted p-3.5 shadow-card"
    >
      <div className="flex items-center gap-2">
        <FlaskConical className="size-4 text-specialty-service" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-ink">Chỉ định & kết quả</h3>
      </div>

      {chiDinh.length === 0 ? (
        <p className="mt-3 text-xs text-ink-muted">Lượt khám này chưa có chỉ định.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {chiDinh.map((c) => (
            <li key={c.id} className="rounded-control border border-line bg-surface px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <p className="min-w-0 text-sm font-medium text-ink">{c.ten_dich_vu}</p>
                <span
                  className={`shrink-0 rounded-chip px-2 py-0.5 text-label font-semibold ${
                    c.trang_thai === "draft"
                      ? "bg-warning-bg text-warning"
                      : c.trang_thai === "performed"
                        ? "bg-success-bg text-success"
                        : "bg-brand-50 text-brand-700"
                  }`}
                >
                  {c.doi_tac && c.trang_thai !== "draft" && c.trang_thai_doi_tac
                    ? TEN_TRANG_THAI_DOI_TAC[c.trang_thai_doi_tac]
                    : TEN_TRANG_THAI_CHI_DINH[c.trang_thai] ?? c.trang_thai}
                </span>
              </div>
              <p className="mt-0.5 text-label text-ink-muted">
                {c.lam_phong ?? c.phong ?? ""}
                {c.lam_bat_dau_luc ? ` · bắt đầu ${gioVn(c.lam_bat_dau_luc)}` : ""}
                {c.lam_xong_luc
                  ? ` · ${c.lam_trang_thai === "INTERRUPTED" ? "dừng" : "xong"} ${gioVn(c.lam_xong_luc)}`
                  : c.lam_trang_thai === "IN_PROGRESS"
                    ? " · đang làm"
                    : ""}
                {c.ly_do_khong_lam ? ` · ${c.ly_do_khong_lam}` : ""}
                {c.doi_tac_thu_tien === "DA_THU"
                  ? " · Đối tác đã thu"
                  : c.doi_tac_thu_tien === "CHUA_THU"
                    ? " · Khách trả đối tác — chưa thu"
                    : ""}
              </p>
              {c.ket_qua ? (
                <p className="mt-1 whitespace-pre-line text-xs text-ink">{c.ket_qua}</p>
              ) : null}
              {/* PHÒNG LÀM ĐƯỢC + SỐ NGƯỜI CHỜ ngay lúc chỉ định (luồng chuẩn
                  bước 7). Chưa làm / chưa đối tác thì mới bày. */}
              {!c.doi_tac && !["draft", "performed", "not_performed", "cancelled", "in_progress"].includes(c.trang_thai) ? (
                <DoiPhong
                  orderId={c.id}
                  phongHienTaiId={c.phong_id ?? null}
                  routingRevision={c.routing_revision ?? null}
                  choDoi={Boolean(c.doi_phong_duoc)}
                  onDaDoi={onDaGui}
                />
              ) : null}
              {c.trang_thai === "performed" || c.trang_thai === "in_progress" ? (
                <button
                  type="button"
                  onClick={() => setMoKetQua(moKetQua === c.id ? null : c.id)}
                  className="mt-1 text-label font-semibold text-brand-700 hover:underline"
                >
                  {moKetQua === c.id ? "Ẩn tệp kết quả" : "Xem tệp kết quả"}
                </button>
              ) : null}
              {c.co_phieu ? (
                <button
                  type="button"
                  onClick={() => setMoPhieu(moPhieu === c.id ? null : c.id)}
                  className="mt-1 ml-3 text-label font-semibold text-brand-700 hover:underline"
                >
                  {moPhieu === c.id
                    ? "Ẩn phiếu kết quả"
                    : c.da_xem_ket_qua_luc
                      ? "Xem phiếu kết quả"
                      : "Xem phiếu kết quả (mới)"}
                </button>
              ) : null}
              {moPhieu === c.id ? (
                <div className="mt-2">
                  <XemPhieuKetQua serviceOrderId={c.id} />
                </div>
              ) : null}
              {moKetQua === c.id ? (
                <div className="mt-2">
                  <KhungTep
                    clinicPatientId={dong.clinic_patient_id}
                    serviceOrderId={c.id}
                    choTaiLen={false}
                    tieuDe="Tệp kết quả"
                  />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {(laBacSi || laThuKy) && dong.trang_thai !== "done" ? (
        <div className="mt-4 border-t border-line pt-3">
          {!dangKham ? (
            <p className="text-xs text-ink-muted">
              Bấm “Bắt đầu khám” trước khi ghi chỉ định.
            </p>
          ) : (
            <>
              <label className="text-xs font-semibold text-ink" htmlFor="go-dich-vu">
                Chỉ định thêm
              </label>
              <input
                id="go-dich-vu"
                list="danh-muc-chi-dinh"
                value={go}
                onChange={(e) => {
                  const v = e.target.value;
                  const dv = dichVu.find((d) => d.ten === v || d.ma === v);
                  if (dv) them(dv.ma);
                  else setGo(v);
                }}
                placeholder="Gõ tên siêu âm, xét nghiệm, thủ thuật…"
                className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
              />
              <datalist id="danh-muc-chi-dinh">
                {dichVu.map((d) => (
                  <option key={d.ma} value={d.ten} />
                ))}
              </datalist>
              {dsChon.length > 0 ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {dsChon.map((ma) => (
                    <li key={ma}>
                      <button
                        type="button"
                        onClick={() =>
                          setChon({ id: dong.id, ma: dsChon.filter((x) => x !== ma) })
                        }
                        className="rounded-chip bg-brand-50 px-2 py-1 text-label font-semibold text-brand-700"
                        title="Bấm để bỏ"
                      >
                        {dichVu.find((d) => d.ma === ma)?.ten ?? ma} ✕
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
              <button
                type="button"
                disabled={dangGui || (dsChon.length === 0 && !(laBacSi && nhap.length > 0))}
                onClick={() => void gui()}
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-control border border-brand-600 px-3 py-2.5 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50"
              >
                <ClipboardPlus className="size-4" aria-hidden="true" />
                {dangGui
                  ? "Đang ghi…"
                  : dsChon.length > 0
                    ? `Xác nhận ${dsChon.length} chỉ định`
                    : nhap.length > 0
                      ? `Duyệt ${nhap.length} chỉ định nháp (bản cũ)`
                      : "Chọn dịch vụ ở ô trên để chỉ định"}
              </button>
              <p className="mt-1 text-label text-ink-muted">
                Xác nhận xong khách tự vào hàng chờ phòng làm dịch vụ.
              </p>
              {loi ? (
                <p role="alert" className="mt-2 text-xs text-danger">
                  {loi}
                </p>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
