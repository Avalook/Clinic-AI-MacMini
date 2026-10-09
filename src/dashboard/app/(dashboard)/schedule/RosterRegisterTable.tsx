"use client";

// "Đăng ký / xếp ca" — bảng MA TRẬN tương tác, CÙNG form với hai bảng chỉ-đọc:
// form Excel của PK Kim Ngưu, hàng = Tầng → Phòng → Vị trí, cột = ngày × ca.
// Khác ở chỗ:
//   - Click 1 ô → popup: quản lý CHỌN NGƯỜI rồi xếp vào đúng vị trí, đúng
//     ngày, và đúng CA CỦA CỘT vừa bấm (chọn lại ca khác được trong popup).
//   - Ô trống có dấu "+"; ô đã có người hiện tên + ca.
// Ghi qua /api/roster (POST xếp, DELETE gỡ) rồi router.refresh().
//
// MỘT BẢNG CHO CẢ BA VIỆC (Tuyền 06/10/2026 — "cuộn quá nhiều vì 3 khối tách
// lẻ"): khối "Đổi người trong ca" và "Lịch sử thay đổi" đã gộp vào đây.
//   - Thanh công cụ DÍNH đầu bảng: ◀ Tuần ▶ · ô Phiên bản (chỉ khi máy chủ cho
//     xem — trưởng ca / quản lý) · nút Áp dụng tuần · ngăn "Xem các thay đổi".
//   - Popup ô: cạnh mỗi người có [Đổi người] (cùng API `/api/roster/thay-nguoi`
//     khối cũ gọi) bên cạnh thùng rác; cuối popup "Lịch sử ô này".
//   - Chọn một phiên bản → chính bảng này vẽ lịch tại bản ấy, tô màu so với bản
//     ngay trước (token `MAU_THAY_DOI`), CHỈ XEM: không dấu +, popup chỉ đọc.
//   - Mọi thao tác nạp lại ô Phiên bản ngay — không bắt tải lại trang.

import Link from "next/link";
import { Fragment, useEffect, useId, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { X, Trash2, ChevronLeft, ChevronRight } from "lucide-react";
import Button, { buttonClass } from "../../../components/ui/Button";
import NganGap from "../../../components/ui/NganGap";
import OChon from "../../../components/ui/OChon";
import ONhap from "../../../components/ui/ONhap";
import ApDungTuan from "./ApDungTuan";
import ChonNhanVien from "./ChonNhanVien";
import {
  ChuThichMau,
  DanhSachThayDoi,
  nhanMuc,
  taiPhienBan,
  tenHien,
  type OPhienBan,
  type PhienBanTraVe,
} from "./PhienBanLich";
import { fmtDate, fmtDateTime } from "../../../lib/datetime";
import { doctorName } from "../../../lib/doctor-name";
import {
  SHIFTS,
  shiftWeek,
  SHIFT_LABEL,
  VI_TRI_LICH_KHAM,
  cotCuaTuan,
  nhanViTri,
  demBacSiTruc,
  type CotLich,
  type Station,
  dayShort,
  fmtDayMonth,
  type Shift,
} from "../../../lib/roster";
import {
  RosterGridHead,
  RosterViTriRows,
  SO_COT_TRAI,
  nenO,
  type ThongTinO,
} from "../RosterGrid";
import Chip from "../../../components/ui/Chip";
import { vaiKemTen } from "../../../lib/doctor-name";
import {
  MAU_THAY_DOI,
  nenThayDoi,
  type DongCaRow,
  type LoaiThayDoi,
} from "../home/WorkRosterTable";
import { loiDocDuoc } from "../../../lib/loi-doc-duoc";

/** Vết "Hà đứng tới 10:30 → B từ 10:30" của lần đổi người trong ca (29/09). */
export interface VetThayNguoi {
  roster_id: string | null;
  nguoi_cu_ten: string;
  nguoi_moi_ten: string;
  gio: string;
  boi_ten: string | null;
}

export interface NguoiChon {
  id: string;
  name: string;
}

export interface RegisterRow {
  id: string;
  work_date: string;
  station: string;
  shift: Shift;
  staff_id: string | null;
  staff_name: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reject_reason: string | null;
  /** Vai ngắn do máy chủ trả (27/09/2026 đợt 3, A9) — chip cạnh tên. */
  vai_ngan?: string | null;
  /** Chỉ khi đang xem một phiên bản: ô khác bản ngay trước thế nào. */
  thay_doi?: LoaiThayDoi | null;
  truoc_ten?: string | null;
}

/** Một người có thể xếp được, kèm chức danh để lọc theo phạm vi trạm. */
export interface StaffOpt {
  id: string;
  name: string;
  /** `staff.primary_department` — khoá của ma trận `vai_duoc_vao_tram`. */
  vai: string;
  /** `staff.full_name` nguyên văn — ô tìm khớp cả chữ đang lưu. */
  hoTen?: string | null;
  /** `staff.short_name` — tên gọi ở phòng khám, hiện kèm khi khác tên. */
  tenNgan?: string | null;
}

// KHÔNG CÒN "CHỜ DUYỆT" (Quang 09/08/2026: *"cần gì phải duyệt với không
// duyệt, chỉ có quản lý toàn quyền mà"*).
//
// Bảng này giờ CHỈ quản lý thấy, và backend đã ghi thẳng APPROVED cho quản lý
// (config_service.py: `"APPROVED" if is_admin else "PENDING"`). Nên mọi ô ở đây
// vốn đã là ca chính thức — dán thêm nhãn "Đã duyệt" lên từng dòng là bày ra
// một quy trình không tồn tại, và bắt người đọc phân biệt hai trạng thái mà
// thực tế chỉ có một.
//
// Ca REJECTED cũ vẫn còn trong database (từ thời có luồng duyệt) nên vẫn phải
// vẽ khác đi — gạch ngang, mờ — chứ không lẫn vào ca đang có hiệu lực.
const STATUS_BADGE: Record<RegisterRow["status"], { cls: string; label: string }> = {
  PENDING: { cls: "bg-brand-50 text-brand-800", label: "Đã xếp" },
  APPROVED: { cls: "bg-brand-50 text-brand-800", label: "Đã xếp" },
  REJECTED: { cls: "bg-surface-sunken text-ink-faint", label: "Đã gỡ" },
};

const NHAN_SR: Record<LoaiThayDoi, string> = {
  THEM: "Mới thêm:",
  XOA: "Đã xoá:",
  DOI_NGUOI: "Đổi sang:",
};

function cellKey(date: string, station: string) {
  return `${date}|${station}`;
}

export default function RosterRegisterTable({
  stations,
  weekStart,
  dates,
  rows,
  dong = [],
  myStaffId,
  myStaffName,
  staff = [],
  tramTheoVai = {},
  isApprover = false,
  xepDuoc = true,
  daApDung = false,
  phienBan = null,
  doiNguoi = false,
  homNay,
  vet = [],
  nhanSuDoi = [],
}: {
  /** Danh mục vị trí từ database — xem `viTriTuDb`. */
  stations: readonly Station[];
  weekStart: string;
  dates: string[];
  rows: RegisterRow[];
  /** Ô đen / khối NGHỈ của tuần (bảng `vi_tri_dong_ca`). */
  dong?: DongCaRow[];
  /** staff_id người đang đăng nhập; null = chưa chọn danh tính (không đăng ký được). */
  myStaffId: string | null;
  /** Tên người đăng nhập — hiện ngay cho ca vừa đăng ký (optimistic). */
  myStaffName?: string;
  /** Danh sách nhân viên để quản lý chọn xếp vào ô. */
  staff?: StaffOpt[];
  /** Chức danh → những mã trạm được xếp vào (bảng `vai_duoc_vao_tram`). */
  tramTheoVai?: Record<string, string[]>;
  /** Quản lý hệ thống: được chọn NGƯỜI để xếp, và gỡ được ca của bất kỳ ai. */
  isApprover?: boolean;
  /** Người xếp lịch (`roster.manage` / `config.clinic.manage`) — ô +, thùng rác, Áp dụng tuần.
   *  Sai = người chỉ có quyền đổi người trong ca: bảng chỉ còn [Đổi người]. */
  xepDuoc?: boolean;
  daApDung?: boolean;
  /** Lịch sử phiên bản của tuần; `null` = máy chủ không cho xem (không bày ô
   *  Phiên bản, không "Lịch sử ô này"). */
  phienBan?: PhienBanTraVe | null;
  /** Máy chủ cho ĐỔI NGƯỜI trong ca (`lich-tuan` → `doi_nguoi`). */
  doiNguoi?: boolean;
  /** Hôm nay theo máy chủ (giờ VN) — ca đã qua không đổi người được. */
  homNay?: string;
  vet?: VetThayNguoi[];
  /** Người vào thay được (không gồm tài khoản đối tác). */
  nhanSuDoi?: NguoiChon[];
}) {
  const router = useRouter();
  const STATION_LABEL = nhanViTri(stations);
  const dialogTitleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState<{
    date: string;
    station: string;
    shift: Shift;
  } | null>(null);
  const [shift, setShift] = useState<Shift>("FULL");
  const [pickedId, setPickedId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [, startTransition] = useTransition();

  // ── Phiên bản (Khối 3) ──────────────────────────────────────────────────
  // `pb` = gói phiên bản mới nhất máy chủ trả (hoặc gói của bản đang xem);
  // `xemMa` = mã bản đang xem; null = HIỆN TẠI (bảng sửa được).
  const [pb, setPb] = useState<PhienBanTraVe | null>(phienBan);
  const [xemMa, setXemMa] = useState<string | null>(null);
  const [pbDangTai, setPbDangTai] = useState(false);
  const [pbLoi, setPbLoi] = useState<string | null>(null);
  const coPhienBan = pb !== null;

  /** Nạp lại bản MỚI NHẤT sau mỗi thao tác — ô Phiên bản và "Lịch sử ô này"
   *  có ngay lần sửa vừa rồi. Đang xem bản cũ thì giữ nguyên chỗ đang xem. */
  async function napLaiPhienBan() {
    if (!coPhienBan || xemMa !== null) return;
    const kq = await taiPhienBan(weekStart);
    if (typeof kq !== "string") setPb(kq);
  }

  async function chonBan(ma: string | null) {
    setPbLoi(null);
    setOpen(null);
    setPbDangTai(true);
    const kq = await taiPhienBan(weekStart, ma);
    setPbDangTai(false);
    if (typeof kq === "string") {
      setPbLoi(kq);
      return;
    }
    setPb(kq);
    setXemMa(ma && kq.dang_xem ? kq.dang_xem.ma : null);
  }

  // ── Đổi người trong ca (gộp từ khối riêng 29/09) ────────────────────────
  // Ghi đè tạm người đứng theo id dòng — bảng đổi tên NGAY khi máy chủ nhận,
  // không chờ router.refresh(). Chỉ áp khi dòng máy chủ CÒN người cũ: máy chủ
  // đã đổi (sang người mới, hay người khác ở tab khác) thì máy chủ thắng.
  const [doiTen, setDoiTen] = useState<
    Record<string, { cu: string | null; staff_id: string; staff_name: string }>
  >({});
  const [doiDangMo, setDoiDangMo] = useState<string | null>(null);
  const [nguoiMoi, setNguoiMoi] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [doiBusy, setDoiBusy] = useState(false);
  const [baoXong, setBaoXong] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const containDialogFocus = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(null);
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", containDialogFocus);
    return () => {
      document.removeEventListener("keydown", containDialogFocus);
      previouslyFocused?.focus();
    };
  }, [open]);

  // OPTIMISTIC UI — cập nhật ngay khi bấm (khỏi chờ refetch cả trang cho mượt).
  //   overrides: ghi đè trạng thái theo id ("REMOVED" = ẩn ca).
  //   optimistic: ca vừa xếp, chưa kịp về từ server.
  // Khi data server mới phản ánh đúng thay đổi → tự bỏ override/optimistic tương ứng.
  const [overrides, setOverrides] = useState<
    Record<string, "APPROVED" | "REJECTED" | "REMOVED">
  >({});
  const [optimistic, setOptimistic] = useState<RegisterRow[]>([]);

  const refresh = () => startTransition(() => router.refresh());

  const apDoiTen = (r: RegisterRow): RegisterRow => {
    const d = doiTen[r.id];
    return d && r.staff_id === d.cu
      ? { ...r, staff_id: d.staff_id, staff_name: d.staff_name }
      : r;
  };

  // Danh sách hiệu lực = data server + áp optimistic (TÍNH KHI RENDER, không dùng
  // effect): ẩn ca REMOVED, đổi trạng thái theo override, thêm ca vừa xếp nếu
  // server chưa trả về (dedupe theo người+ngày+trạm để không trùng sau khi refetch).
  const effRows: RegisterRow[] = [
    ...rows
      .filter((r) => overrides[r.id] !== "REMOVED")
      .map((r) =>
        apDoiTen(
          overrides[r.id]
            ? { ...r, status: overrides[r.id] as RegisterRow["status"] }
            : r,
        ),
      ),
    // Ca vừa xếp rồi GỠ ngay (28/09/2026): phải ẩn cả ở đây. Trước chỉ ẩn dòng
    // của máy chủ — gỡ xong, tải lại, máy chủ không còn dòng ấy nên dòng tạm
    // hiện lại: người vừa gỡ vẫn "Đã xếp", biến khỏi danh sách chọn, bấm gỡ lần
    // nữa thì máy chủ báo "Không tìm thấy ca trực".
    // Ca vừa xếp rồi ĐỔI NGƯỜI (06/10/2026, Tuyền bấm trên staging): máy chủ
    // sửa ĐÚNG dòng ấy (cùng id) sang người mới, nên so người+ngày+trạm không
    // còn khớp và dòng tạm mang tên người cũ hiện lại như ô có hai người. Máy
    // chủ đã có dòng cùng id thì dòng tạm hết việc, bỏ luôn.
    ...optimistic.filter(
      (o) =>
        overrides[o.id] !== "REMOVED" &&
        !rows.some(
          (r) =>
            r.id === o.id ||
            (r.staff_id === o.staff_id &&
              r.work_date === o.work_date &&
              r.station === o.station),
        ),
    ).map(apDoiTen),
  ];

  // ĐANG XEM MỘT PHIÊN BẢN: bảng vẽ lịch tại bản ấy (kể cả ca đã xoá, gạch
  // ngang tại chỗ cũ) thay cho lịch hiện tại — chỉ xem.
  const dx = xemMa !== null ? (pb?.dang_xem ?? null) : null;
  const chiXem = dx !== null;
  const oSangDong = (o: OPhienBan): RegisterRow => ({
    id: o.id,
    work_date: o.work_date,
    station: o.station,
    shift: o.shift as Shift,
    staff_id: o.staff_id,
    staff_name: tenHien(o),
    status: "APPROVED",
    reject_reason: null,
    vai_ngan: o.vai_ngan,
    thay_doi: o.thay_doi,
    truoc_ten: o.truoc_ten ? doctorName(o.truoc_ten) || o.truoc_ten : null,
  });
  const rowsBan: RegisterRow[] = dx ? [...dx.dong, ...dx.da_xoa].map(oSangDong) : [];

  // HIỆN TẠI CŨNG TÔ MÀU (Tuyền thử staging 06/10): bảng vẫn sửa được, nhưng ô
  // khác bản LIỀN TRƯỚC tô y như khi xem phiên bản. Phần khác do MÁY CHỦ tính
  // (`dang_xem` của gói phiên bản mới nhất — nạp lại sau mỗi thao tác); ở đây
  // chỉ gắn nhãn vào dòng cùng id và vẽ ca vừa xoá thành "bóng" chỉ xem.
  const banMoiNhat = !chiXem && pb?.dang_xem?.moi_nhat ? pb.dang_xem : null;
  const nhanMoiNhat = new Map(
    (banMoiNhat?.dong ?? [])
      .filter((o) => o.thay_doi)
      .map((o) => [o.id, o] as const),
  );
  const rowsHienTai: RegisterRow[] = effRows.map((r) => {
    const o = nhanMoiNhat.get(r.id);
    // Chỉ gắn khi dòng sống còn đúng người máy chủ so — lệch (vừa sửa, chưa nạp
    // lại phiên bản) thì thôi tô, không tô sai.
    return o && r.status === "APPROVED" && r.staff_id === o.staff_id
      ? {
          ...r,
          thay_doi: o.thay_doi,
          truoc_ten: o.truoc_ten ? doctorName(o.truoc_ten) || o.truoc_ten : null,
        }
      : r;
  });
  const bong: RegisterRow[] = (banMoiNhat?.da_xoa ?? []).map(oSangDong);
  const rowsBang = chiXem ? rowsBan : [...rowsHienTai, ...bong];
  /** Dòng "bóng": ca đã xoá — chỉ để xem, không phải người đang đứng ca. */
  const laBong = (r: RegisterRow) => r.thay_doi === "XOA";

  // byCell[date|station] = các ca ở ô đó (mọi người, mọi trạng thái).
  const byCell = new Map<string, RegisterRow[]>();
  for (const r of rowsBang) {
    const k = cellKey(r.work_date, r.station);
    const list = byCell.get(k) ?? [];
    list.push(r);
    byCell.set(k, list);
  }

  // Một ô = vị trí × ngày × CA. Người trực CẢ NGÀY thuộc về mọi ca của ngày
  // ấy — không tính họ vào thì bảng nói ca Tối trống trong khi có người đứng.
  const cuaCa = (list: RegisterRow[], ca: Shift) =>
    list.filter((r) => r.shift === ca || r.shift === "FULL");
  const openCellRows = open
    ? cuaCa(byCell.get(cellKey(open.date, open.station)) ?? [], open.shift)
    : [];
  // "Đã đăng ký" chỉ tính ca ĐANG hiệu lực (Đã xếp) của mình. Ca bị gỡ không
  // tính → cho phép xếp lại ô đó.
  const myHere = openCellRows.find(
    (r) => r.staff_id === myStaffId && r.status !== "REJECTED" && !laBong(r),
  );

  // AI ĐƯỢC XẾP VÀO Ô NÀY — lọc bằng ĐÚNG ma trận mà backend dùng để từ chối
  // (`vai_duoc_vao_tram`, xem RosterService._kiem_pham_vi_tram). Hỏi hai nguồn
  // là sớm muộn popup mời một người mà lúc lưu mới báo lỗi.
  //
  // Chức danh CHƯA KHAI dòng nào → cho qua, y như backend: phòng khám mới cài
  // đặt chưa có ma trận, chặn hết ở đây là màn xếp lịch chết câm ngày đầu.
  const daCoTrongO = new Set(
    openCellRows
      .filter((r) => r.status !== "REJECTED" && !laBong(r))
      .map((r) => r.staff_id),
  );
  const nhanVienHopLe = open
    ? staff.filter((s) => {
        if (daCoTrongO.has(s.id)) return false;
        const tram = tramTheoVai[s.vai];
        return !tram || tram.length === 0 || tram.includes(open.station);
      })
    : [];

  function moO(date: string, station: string, ca: Shift) {
    setError(null);
    // Chọn sẵn ĐÚNG ca của cột vừa bấm. Bản cũ luôn chọn sẵn "Cả ngày" vì bảng
    // cũ không có cột theo ca — giữ vậy thì bấm vào cột Tối rồi lưu là xếp
    // người ấy vào cả Sáng lẫn Chiều mà không ai để ý.
    setShift(ca);
    setPickedId("");
    setDoiDangMo(null);
    setBaoXong(null);
    setOpen({ date, station, shift: ca });
  }

  function moDoiNguoi(id: string) {
    setError(null);
    setBaoXong(null);
    setNguoiMoi("");
    setLyDo("");
    setDoiDangMo(id);
  }

  /** ĐỔI NGƯỜI TRONG CA — đúng lệnh khối "Đổi người trong ca" cũ gửi
   *  (`POST /api/roster/thay-nguoi`). Máy chủ giữ mọi luật: ai được đổi, ca đã
   *  qua không đổi, người mới có ngay quyền vị trí, lịch hẹn rơi ra ngoài. */
  async function doiNguoiTrongCa(r: RegisterRow) {
    if (!nguoiMoi) {
      setError("Chọn người vào thay.");
      return;
    }
    if (r.id.startsWith("temp-")) {
      setError("Ca này chưa lưu xong. Bấm làm mới rồi đổi lại.");
      refresh();
      return;
    }
    setError(null);
    setDoiBusy(true);
    const res = await fetch("/api/roster/thay-nguoi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: r.id, staff_id: nguoiMoi, ly_do: lyDo.trim() || null }),
    });
    const kq = (await res.json().catch(() => ({}))) as {
      nguoi_moi_ten?: string;
      so_lich_cho_xep?: number;
    };
    setDoiBusy(false);
    if (!res.ok) {
      setError(loiDocDuoc(kq, "Chưa đổi được người — thử lại."));
      return;
    }
    const tenMoi =
      nhanSuDoi.find((n) => n.id === nguoiMoi)?.name ??
      (kq.nguoi_moi_ten ? doctorName(kq.nguoi_moi_ten) || kq.nguoi_moi_ten : "người mới");
    setDoiTen((cu) => ({
      ...cu,
      [r.id]: { cu: r.staff_id, staff_id: nguoiMoi, staff_name: tenMoi },
    }));
    // Dòng vừa xếp trong phiên này (optimistic, đã mang id thật) cũng đổi tên.
    setOptimistic((opt) =>
      opt.map((o) => (o.id === r.id ? { ...o, staff_id: nguoiMoi, staff_name: tenMoi } : o)),
    );
    const choXep = kq.so_lich_cho_xep ?? 0;
    setBaoXong(
      `${r.staff_name || "Người cũ"} → ${tenMoi}: đã đổi, quyền áp dụng ngay.` +
        (choXep > 0 ? ` ${choXep} lịch hẹn của người cũ chuyển sang "Lịch chờ xếp bác sĩ".` : ""),
    );
    setDoiDangMo(null);
    void napLaiPhienBan();
    refresh();
  }

  /** Quản lý xếp NGƯỜI ĐƯỢC CHỌN; vai khác tự đăng ký chính mình. */
  async function xepCa() {
    if (!open) return;
    const { date, station } = open;
    const picked = isApprover ? staff.find((s) => s.id === pickedId) : null;
    if (isApprover && !picked) {
      setError("Chọn nhân viên trước đã.");
      return;
    }
    setError(null);
    setBusy(true);
    const tempId = `temp-${date}-${station}-${picked?.id ?? myStaffId}-${shift}`;
    setOptimistic((opt) => [
      ...opt,
      {
        id: tempId,
        work_date: date,
        station,
        shift,
        staff_id: picked?.id ?? myStaffId,
        staff_name: picked?.name ?? myStaffName ?? "Tôi",
        // Quản lý xếp → backend ghi thẳng APPROVED. Vẽ optimistic là PENDING thì
        // ô nhấp nháy đổi nhãn khi server trả về.
        status: isApprover ? "APPROVED" : "PENDING",
        reject_reason: null,
      },
    ]);
    const res = await fetch("/api/roster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        week_start: weekStart,
        work_date: date,
        station,
        shift,
        staff_id: picked?.id ?? null,
        staff_name: picked?.name ?? null,
        // Người xếp sau nằm ở hàng con dưới. Không gửi thì mọi dòng cùng sort=0
        // và thứ tự hai hàng đảo qua đảo lại giữa các lần tải trang.
        sort: openCellRows.filter((r) => !laBong(r)).length,
      }),
    });
    setBusy(false);
    const than = await res.json().catch(() => ({}));
    if (!res.ok) {
      setOptimistic((opt) => opt.filter((o) => o.id !== tempId));
      setError(loiDocDuoc(than, "Lỗi khi xếp ca."));
      return;
    }
    // ĐỔI ID TẠM SANG ID THẬT NGAY KHI SERVER TRẢ VỀ.
    //
    // Bản trước để nguyên dòng optimistic mang `temp-…` rồi chỉ gọi refresh().
    // Nhưng popup CỐ Ý ở lại mở, nên người xếp xong thấy ngay dòng vừa thêm —
    // và dòng ấy vẫn là dòng tạm. Bấm thùng rác trên nó gửi
    // `DELETE /roster/shifts/temp-2026-08-22-LICH_KHAM-…` xuống máy chủ; đường
    // ấy khai tham số là UUID nên trả 422, và màn hình chỉ nói "Lỗi khi gỡ ca."
    //
    // Đo trên prod 14/08/2026: id thật gỡ được (200), id tạm 422 ba lần liên
    // tiếp — Tuyền bấm lại ba lần vì không có gì nói cho biết vì sao.
    //
    // Không xoá hẳn dòng tạm ở đây: refresh() là một vòng mạng nữa, và trong
    // lúc chờ thì ô vừa xếp trống trở lại rồi mới hiện — nhấp nháy đúng vào
    // khoảnh khắc người ta đang nhìn nó.
    const idThat = typeof than?.id === "string" ? than.id : null;
    setOptimistic((opt) =>
      idThat
        ? opt.map((o) => (o.id === tempId ? { ...o, id: idThat } : o))
        : opt.filter((o) => o.id !== tempId),
    );
    // GIỮ POPUP MỞ. Mỗi ngày có tới hai người mỗi trạm; đóng lại sau người thứ
    // nhất là bắt quản lý bấm vào đúng ô ấy thêm một lần nữa.
    setPickedId("");
    void napLaiPhienBan();
    refresh();
  }

  async function remove(id: string) {
    setError(null);
    // CHỐT CUỐI: không bao giờ gửi một id tạm xuống máy chủ. Trên lý thuyết
    // xepCa() đã đổi nó sang id thật rồi, nhưng nếu vòng mạng ấy hỏng thì dòng
    // tạm vẫn còn — và khi đó câu trả lời đúng là "làm mới rồi thử lại", không
    // phải một mã 422 khó hiểu.
    if (id.startsWith("temp-")) {
      setError("Ca này chưa lưu xong. Bấm làm mới rồi gỡ lại.");
      refresh();
      return;
    }
    // ĐO TRƯỚC KHI CẮT. Gỡ một ca khám KHÔNG huỷ lịch hẹn (CONTEXT v1.0),
    // nhưng những lịch rơi RA NGOÀI phần ca còn lại sẽ mất bác sĩ và vào hàng
    // "Lịch chờ xếp bác sĩ" — việc cho người khác, nên hỏi lại trước. Hộp
    // cũng dạy luôn đường đổi ca không sinh việc: thêm ca mới trước.
    const uom = await fetch("/api/roster", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, dry_run: true }),
    });
    const doDac = (await uom.json().catch(() => null)) as {
      so_lich_cho_xep?: number;
      gio?: string[];
    } | null;
    const soChoXep = doDac?.so_lich_cho_xep ?? 0;
    if (uom.ok && soChoXep > 0) {
      const dsGio = (doDac?.gio ?? []).join(", ");
      const dongY = window.confirm(
        `Ca này đang gánh ${soChoXep} lịch hẹn (${dsGio}).\n` +
          `Gỡ ca KHÔNG huỷ lịch — các lịch ấy sẽ mất bác sĩ và chuyển sang ` +
          `"Lịch chờ xếp bác sĩ" để xếp bác sĩ khác hoặc gọi khách đổi giờ.\n\n` +
          `Nếu chị định ĐỔI ca (vd sáng → cả ngày): bấm Huỷ ở hộp này, THÊM ca mới ` +
          `trước rồi mới gỡ ca cũ — lịch nằm trong khung còn phủ sẽ giữ nguyên bác sĩ.\n\n` +
          `Gỡ ca và chuyển ${soChoXep} lịch sang chờ xếp bác sĩ?`,
      );
      if (!dongY) return;
    }
    setOverrides((ov) => ({ ...ov, [id]: "REMOVED" }));
    const res = await fetch("/api/roster", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    // 404 = ca đã không còn trên máy chủ (vừa gỡ ở tab khác / bấm hai lần):
    // đúng điều người bấm muốn — coi là gỡ xong, không báo lỗi.
    if (!res.ok && res.status !== 404) {
      setOverrides((ov) => {
        const n = { ...ov };
        delete n[id];
        return n;
      });
      setError(loiDocDuoc(await res.json().catch(() => ({})), "Lỗi khi gỡ ca."));
      return;
    }
    setOptimistic((opt) => opt.filter((o) => o.id !== id));
    void napLaiPhienBan();
    refresh();
  }

  const cot = cotCuaTuan(weekStart, rowsBang);

  const dongO = new Map(
    dong.map((d) => [`${d.station}|${d.work_date}|${d.shift}`, d.ly_do] as const),
  );
  const thongTin = (st: Station, c: CotLich): ThongTinO => ({
    dong: dongO.get(`${st.key}|${c.date}|${c.shift}`) ?? null,
    // Gộp dọc CHỈ theo người đang có hiệu lực — một ca đã gỡ không được làm hai
    // ô dính nhau vì còn lưu tên cũ.
    // Kèm loại thay đổi khi xem phiên bản: ô đổi không gộp với ô không đổi.
    khoa: cuaCa(byCell.get(cellKey(c.date, st.key)) ?? [], c.shift)
      .filter((r) => r.status !== "REJECTED")
      .map((r) => `${r.staff_id ?? r.staff_name}~${r.thay_doi ?? ""}~${r.truoc_ten ?? ""}`)
      .sort()
      .join("|"),
  });

  const oCuaBang = (st: Station, date: string, ca: Shift, rowSpan = 1) => {
    const station = st.key;
    const list = cuaCa(byCell.get(cellKey(date, station)) ?? [], ca);
    const nen = nenThayDoi(list.map((r) => ({ loai: r.thay_doi ?? null }))) || nenO(st);
    return (
      <td rowSpan={rowSpan} className={`border border-line-strong ${nen} p-0`}>
        <button
          type="button"
          onClick={() => moO(date, station, ca)}
          aria-label={`${STATION_LABEL[station] ?? station} · ${dayShort(date)} ${fmtDayMonth(date)} · ${SHIFT_LABEL[ca]}`}
          className="flex h-full min-h-8 w-full flex-col gap-0.5 px-1.5 py-1 text-center transition-colors hover:bg-brand-50"
        >
          {list.length === 0 ? (
            // Xem phiên bản: không có dấu + (chỉ xem).
            chiXem ? null : <span className="text-brand-200">+</span>
          ) : (
            list.map((r) => {
              const b = STATUS_BADGE[r.status];
              const vai = vaiKemTen(r.staff_name, r.vai_ngan);
              const loai = r.thay_doi ?? null;
              if (chiXem || loai) {
                // Cùng cách vẽ với bảng xem phiên bản cũ: không chỉ bằng màu —
                // "+" = thêm, gạch ngang = xoá, "cũ → mới" = đổi người.
                return (
                  <span
                    key={`${r.id}-${loai ?? ""}`}
                    className="flex items-center justify-center gap-1 whitespace-nowrap leading-snug text-ink"
                  >
                    {loai === "DOI_NGUOI" && r.truoc_ten ? (
                      <>
                        <span className="text-ink-muted line-through">{r.truoc_ten}</span>
                        <span aria-hidden="true">→</span>
                      </>
                    ) : null}
                    {loai === "THEM" ? <span aria-hidden="true">+</span> : null}
                    {loai ? <span className="sr-only">{NHAN_SR[loai]}</span> : null}
                    <span className={loai ? MAU_THAY_DOI[loai].chu : undefined}>
                      {r.staff_name}
                    </span>
                    {vai && loai !== "XOA" ? <Chip>{vai}</Chip> : null}
                  </span>
                );
              }
              return (
                <span
                  key={r.id}
                  className={
                    "block whitespace-nowrap rounded px-1 leading-snug " +
                    b.cls +
                    (r.status === "REJECTED" ? " line-through" : "") +
                    (r.staff_id === myStaffId ? " ring-1 ring-brand-600/40" : "")
                  }
                  title={`${b.label}${r.reject_reason ? " — " + r.reject_reason : ""}${
                    r.shift === "FULL" ? " · trực cả ngày" : ""
                  }`}
                >
                  {r.staff_name}
                  {vai ? <Chip className="ml-1">{vai}</Chip> : null}
                </span>
              );
            })
          )}
        </button>
      </td>
    );
  };

  const soCaDaXep = effRows.filter((r) => r.status === "APPROVED").length;
  const nhatKy = pb?.nhat_ky ?? [];
  const vetTheoDong = new Map<string, VetThayNguoi[]>();
  for (const v of vet) {
    if (v.roster_id) vetTheoDong.set(v.roster_id, [...(vetTheoDong.get(v.roster_id) ?? []), v]);
  }
  // Lịch sử của ĐÚNG ô đang mở — cùng luật "người trực cả ngày thuộc mọi ca"
  // với chính ô ấy trên bảng (`cuaCa`).
  const lichSuO = open
    ? nhatKy.filter(
        (n) =>
          n.work_date === open.date &&
          n.station === open.station &&
          (n.shift === open.shift || n.shift === "FULL"),
      )
    : [];

  return (
    <>
      {/* THANH CÔNG CỤ DÍNH (06/10/2026) — dính dưới thanh đầu trang (`top-12`
          = cao GlobalHeader) suốt lúc cuộn qua bảng. */}
      <div className="sticky top-12 z-20 -mx-4 space-y-2 border-b border-line bg-surface px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1">
            <Link
              href={`/schedule?week=${shiftWeek(weekStart, -1)}`}
              aria-label="Tuần trước"
              className={buttonClass("secondary", "sm")}
            >
              <ChevronLeft className="size-4" aria-hidden="true" />
            </Link>
            <span className="whitespace-nowrap px-1 text-body font-medium text-ink">
              Tuần {fmtDayMonth(dates[0])} – {fmtDayMonth(dates[dates.length - 1])}
            </span>
            <Link
              href={`/schedule?week=${shiftWeek(weekStart, 1)}`}
              aria-label="Tuần sau"
              className={buttonClass("secondary", "sm")}
            >
              <ChevronRight className="size-4" aria-hidden="true" />
            </Link>
          </span>
          {pb?.co_lich_su ? (
            <label className="flex w-full min-w-0 items-center gap-2 sm:w-auto">
              <span className="shrink-0 text-meta text-ink-muted">Phiên bản</span>
              <OChon
                value={xemMa ?? ""}
                disabled={pbDangTai}
                onChange={(e) => void chonBan(e.target.value || null)}
                className="min-w-0 flex-1 sm:max-w-md sm:flex-none"
              >
                <option value="">Hiện tại — sửa được</option>
                {pb.phien_ban.map((p, i) => (
                  <option key={p.ma} value={p.ma}>
                    {nhanMuc(p, i === 0)}
                  </option>
                ))}
              </OChon>
              {pbDangTai ? <span className="text-meta text-ink-muted">Đang tải…</span> : null}
            </label>
          ) : pb ? (
            <span className="text-meta text-ink-muted">
              {pb.da_ap_dung
                ? `Phiên bản: tuần chưa có lịch sử${pb.lich_su_tu ? ` (chỉ ghi từ ${fmtDate(pb.lich_su_tu)})` : ""}`
                : "Phiên bản: có từ lúc bấm “Áp dụng tuần”"}
            </span>
          ) : null}
          {/* Chú thích màu cạnh ô Phiên bản — ô tô màu = khác bản LIỀN TRƯỚC
              (bản hiện tại cũng tô, 06/10). */}
          {pb?.co_lich_su ? (
            <span
              className="flex flex-wrap items-center gap-1.5 text-meta text-ink-muted"
              title="Ô tô màu = khác bản liền trước"
            >
              <span>So với bản trước:</span>
              <ChuThichMau />
            </span>
          ) : null}
          {xepDuoc && !chiXem ? (
            <span className="ml-auto">
              <ApDungTuan
                gon
                weekStart={weekStart}
                daApDung={daApDung}
                laQuanLy={xepDuoc}
                soCa={soCaDaXep}
                onXong={() => void napLaiPhienBan()}
              />
            </span>
          ) : null}
        </div>
        {dx ? (
          <div className="flex flex-wrap items-center gap-2 rounded-control bg-surface-sunken px-3 py-1.5 text-meta text-ink">
            <span>
              Đang xem bản <b>{fmtDateTime(dx.luc)}</b> · chỉ xem
              {dx.truoc_ma === null ? " · bản đầu tiên, không có bản trước để so" : " · tô màu so với bản ngay trước"}
            </span>
            <Button size="sm" variant="soft" className="ml-auto" onClick={() => void chonBan(null)}>
              Về hiện tại
            </Button>
          </div>
        ) : null}
        {pbLoi ? (
          <p className="rounded-control bg-danger-bg px-3 py-1.5 text-meta text-danger">{pbLoi}</p>
        ) : null}
      </div>

      {nhatKy.length > 0 ? (
        <NganGap tieuDe={`Xem các thay đổi của tuần (${nhatKy.length})`}>
          <div className="max-h-72 overflow-y-auto rounded-control border border-line p-2">
            <DanhSachThayDoi
              nhatKy={nhatKy}
              nhan={STATION_LABEL}
              dangXemMa={xemMa}
              onXemBan={(ma) => void chonBan(ma)}
            />
          </div>
        </NganGap>
      ) : null}

      <div className="max-h-[88vh] min-h-[180px] max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
        <table className="w-full min-w-max border-collapse text-xs">
          <RosterGridHead cot={cot} minWidth={112} />
          <tbody>
            <RosterViTriRows
              stations={stations}
              cot={cot}
              thongTin={thongTin}
              veO={(st, c, rs) => oCuaBang(st, c.date, c.shift, rs)}
            />
          </tbody>
        </table>
      </div>

      {/* BÁC SĨ NHẬN LỊCH KHÁM — đứng NGOÀI bảng Excel, có chủ ý.
          06/10/2026 Tuyền: bỏ cho gọn — đặt lịch đếm MỌI người có tên trong
          lịch trực (capacity_service), nên xếp bác sĩ ở phòng là đủ; dòng này
          trên prod chưa từng có ai. CHỈ hiện khi tuần có người ở đây (máy tự
          thêm khi chọn bác sĩ cho lịch hẹn tuần chưa áp dụng —
          booking_service), để không có ca trực bị giấu mà không gỡ được. */}
      {rowsBang.some((r) => r.station === VI_TRI_LICH_KHAM.key) ? (
      <div className="mt-4 max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
        <table className="w-full min-w-max border-collapse text-xs">
          <RosterGridHead cot={cot} minWidth={112} />
          <tbody>
            <tr className="align-middle">
              <td
                colSpan={SO_COT_TRAI}
                className="sticky left-0 z-10 border border-line-strong bg-surface px-2 py-2 font-semibold text-ink"
                title={STATION_LABEL.LICH_KHAM}
              >
                Bác sĩ nhận lịch khám
                <span className="block text-meta font-normal text-ink-muted">
                  Không có trong Excel · lưới đặt lịch đọc dòng này
                </span>
              </td>
              {cot.map((c) => (
                <Fragment key={`lk-${c.date}-${c.shift}`}>
                  {oCuaBang(VI_TRI_LICH_KHAM, c.date, c.shift)}
                </Fragment>
              ))}
            </tr>
            <tr>
              <td
                colSpan={SO_COT_TRAI}
                className="sticky left-0 z-10 border border-line-strong bg-surface px-2 py-1 text-meta text-ink-muted"
              >
                Số bác sĩ nhận lịch
              </td>
              {cot.map((c) => {
                const n = demBacSiTruc(
                  rowsBang.filter((r) => r.status !== "REJECTED" && r.thay_doi !== "XOA"),
                  c.date,
                  c.shift,
                );
                return (
                  <td
                    key={`sobs-${c.date}-${c.shift}`}
                    className="border border-line-strong px-2 py-1 text-center font-semibold text-brand-700"
                  >
                    {n > 0 ? n : <span className="text-ink-faint">—</span>}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
      ) : null}

      {/* Modal "nảy ra" khi click 1 ô */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 p-4"
          onClick={() => setOpen(null)}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={dialogTitleId}
            className="max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto rounded-card border border-line bg-surface p-4 shadow-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-2">
              <h3 id={dialogTitleId} className="text-sm font-semibold text-ink">
                {chiXem ? "Xem ca" : isApprover ? "Xếp ca" : "Đăng ký ca"} · {dayShort(open.date)}{" "}
                {fmtDayMonth(open.date)}
                <span className="block text-xs font-normal text-ink-muted">
                  {STATION_LABEL[open.station] ?? open.station}
                </span>
              </h3>
              <button
                type="button"
                onClick={() => setOpen(null)}
                aria-label="Đóng"
                autoFocus
                className="rounded-md p-1 text-ink-faint hover:bg-surface-sunken"
              >
                <X size={16} />
              </button>
            </div>

            {/* Ai đang ở ô này (để thấy lịch của người khác trước khi xếp thêm). */}
            {openCellRows.length > 0 && (
              <div className="mb-3 rounded-lg border border-surface-sunken bg-surface-muted p-2">
                <p className="mb-1 text-xs font-medium text-ink-muted">
                  {chiXem ? "Ô này ở phiên bản đang xem" : "Đang xếp ở ô này"}
                </p>
                <ul className="space-y-1">
                  {openCellRows.map((r) => {
                    const b = STATUS_BADGE[r.status];
                    const loai = r.thay_doi ?? null;
                    // Quản lý gỡ được ca của BẤT KỲ AI — đúng luật của
                    // RosterService.remove. Người thường chỉ gỡ ca của mình.
                    const bongXoa = loai === "XOA";
                    const goDuoc =
                      !chiXem &&
                      !bongXoa &&
                      xepDuoc &&
                      (isApprover || r.staff_id === myStaffId);
                    // Đổi người: máy chủ cho (`doi_nguoi`), ca đang hiệu lực, hôm
                    // nay trở đi — y như khối cũ chỉ bày ca từ hôm nay (máy chủ
                    // cũng chặn ca đã qua).
                    const doiDuoc =
                      !chiXem &&
                      !bongXoa &&
                      doiNguoi &&
                      r.status !== "REJECTED" &&
                      (!homNay || r.work_date >= homNay);
                    const vetDong = chiXem || bongXoa ? [] : (vetTheoDong.get(r.id) ?? []);
                    return (
                      <li key={`${r.id}-${loai ?? ""}`} className="text-xs text-ink-soft">
                        <div className="flex items-center justify-between gap-2">
                          <span className="min-w-0">
                            {loai === "DOI_NGUOI" && r.truoc_ten ? (
                              <span className="text-ink-muted line-through">
                                {r.truoc_ten}{" "}
                              </span>
                            ) : null}
                            {loai === "DOI_NGUOI" && r.truoc_ten ? "→ " : null}
                            <span
                              className={
                                loai ? MAU_THAY_DOI[loai].chu : "font-medium text-ink"
                              }
                            >
                              {r.staff_name}
                            </span>
                            {r.shift !== "FULL" && (
                              <span className="text-ink-faint">
                                {" "}
                                ({SHIFT_LABEL[r.shift]})
                              </span>
                            )}
                            {chiXem || bongXoa ? null : (
                              <span
                                className={"ml-1.5 rounded px-1.5 py-0.5 font-medium " + b.cls}
                              >
                                {b.label}
                              </span>
                            )}
                            {loai ? (
                              <Chip
                                className="ml-1.5"
                                tone={
                                  loai === "THEM" ? "success" : loai === "XOA" ? "danger" : "info"
                                }
                              >
                                {loai === "THEM"
                                  ? "Mới thêm"
                                  : loai === "XOA"
                                    ? chiXem
                                      ? "Xoá"
                                      : "Vừa xoá · chỉ xem"
                                    : "Vừa đổi người"}
                              </Chip>
                            ) : null}
                            {r.status === "REJECTED" && r.reject_reason && (
                              <span className="block text-danger">
                                Lý do: {r.reject_reason}
                              </span>
                            )}
                            {vetDong.map((v, i) => (
                              <span key={i} className="block text-meta text-ink-muted">
                                {v.nguoi_cu_ten} đứng tới {v.gio} → {v.nguoi_moi_ten} từ {v.gio}
                                {v.boi_ten ? ` · ${v.boi_ten} đổi` : ""}
                              </span>
                            ))}
                          </span>
                          <span className="flex shrink-0 items-center gap-1">
                            {doiDuoc && doiDangMo !== r.id ? (
                              <Button size="sm" onClick={() => moDoiNguoi(r.id)}>
                                Đổi người
                              </Button>
                            ) : null}
                            {goDuoc && (
                              <button
                                type="button"
                                onClick={() => remove(r.id)}
                                aria-label={`Gỡ ${r.staff_name} khỏi ca này`}
                                className="shrink-0 rounded p-1 text-ink-faint hover:bg-danger-bg hover:text-danger disabled:opacity-50"
                              >
                                <Trash2 size={14} />
                              </button>
                            )}
                          </span>
                        </div>
                        {doiDangMo === r.id ? (
                          <div className="mt-2 space-y-2 rounded-control bg-surface-sunken p-2">
                            <label className="block text-meta text-ink-muted">
                              Người vào thay
                              <OChon
                                value={nguoiMoi}
                                onChange={(e) => {
                                  setNguoiMoi(e.target.value);
                                  setError(null);
                                }}
                                className="mt-1 w-full"
                              >
                                <option value="">— Chọn người —</option>
                                {nhanSuDoi
                                  .filter((n) => n.id !== r.staff_id)
                                  .map((n) => (
                                    <option key={n.id} value={n.id}>
                                      {n.name}
                                    </option>
                                  ))}
                              </OChon>
                            </label>
                            <label className="block text-meta text-ink-muted">
                              Lý do (không bắt buộc)
                              <ONhap
                                value={lyDo}
                                onChange={(e) => setLyDo(e.target.value)}
                                maxLength={500}
                                placeholder="VD: có việc đột xuất phải về"
                                className="mt-1 w-full"
                              />
                            </label>
                            <div className="flex gap-2">
                              <Button
                                variant="primary"
                                size="sm"
                                disabled={doiBusy || !nguoiMoi}
                                onClick={() => void doiNguoiTrongCa(r)}
                              >
                                {doiBusy ? "Đang đổi…" : "Đổi người"}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={doiBusy}
                                onClick={() => setDoiDangMo(null)}
                              >
                                Thôi
                              </Button>
                            </div>
                          </div>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {error && (
              <p className="mb-2 rounded bg-danger-bg px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}
            {baoXong && (
              <p className="mb-2 rounded-control bg-status-in-progress-bg px-3 py-2 text-sm text-status-in-progress">
                {baoXong}
              </p>
            )}

            {/* QUẢN LÝ: chọn người + chọn ca rồi xếp.

                Khối này TỪNG KHÔNG TỒN TẠI. Sau khi bỏ trang /schedule/edit
                (09/08), popup chỉ hiện đúng câu "Chưa có ai đăng ký ô này" cho
                quản lý — tức là dấu "+" mở ra một ngõ cụt và cả phòng khám không
                còn đường nào xếp lịch trực. */}
            {chiXem ? (
              <p className="rounded-control bg-surface-sunken px-3 py-2 text-sm text-ink-muted">
                Đang xem phiên bản cũ — chỉ xem. Bấm <b>Về hiện tại</b> trên thanh công cụ để sửa.
              </p>
            ) : !xepDuoc ? null : isApprover ? (
              <div className="space-y-2">
                <div>
                  {/* Ô tìm + nhóm theo vai (09/10/2026). `key` theo ô: mở ô
                      khác là ô tìm và nhóm đang mở về trạng thái đầu. */}
                  <ChonNhanVien
                    key={cellKey(open.date, open.station)}
                    nhanVien={nhanVienHopLe}
                    daChon={pickedId}
                    onChon={(id) => {
                      setPickedId(id);
                      setError(null);
                    }}
                  />
                  {nhanVienHopLe.length === 0 && (
                    <p className="mt-1 text-xs text-ink-faint">
                      Không còn ai được xếp vào vị trí này. Phạm vi vị trí theo
                      chức danh nằm ở bảng “Ai được vào vị trí nào”.
                    </p>
                  )}
                </div>
                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <label
                      htmlFor={`${dialogTitleId}-ca`}
                      className="mb-1 block text-xs font-medium text-ink-muted"
                    >
                      Ca
                    </label>
                    <select
                      id={`${dialogTitleId}-ca`}
                      className="w-full rounded-control border border-line bg-surface px-3 py-2 text-sm focus:border-brand-600 focus:outline-none"
                      value={shift}
                      onChange={(e) => setShift(e.target.value as Shift)}
                    >
                      {SHIFTS.map((s) => (
                        <option key={s} value={s}>
                          {SHIFT_LABEL[s]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={xepCa}
                    disabled={busy || !pickedId}
                    className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface hover:bg-brand-700 disabled:opacity-50"
                  >
                    Xếp vào
                  </button>
                </div>
                <p className="text-xs text-ink-faint">
                  Xếp xong ca vào thẳng lịch chính thức. Popup vẫn mở để xếp tiếp
                  người thứ hai của ô này.
                </p>
              </div>
            ) : myStaffId == null ? (
              <p className="rounded-control bg-warning-bg px-3 py-2 text-sm text-warning">
                Chưa chọn danh tính nhân viên — không thể tự đăng ký ca.
              </p>
            ) : myHere ? (
              <p className="rounded-control bg-status-in-progress-bg px-3 py-2 text-sm text-status-in-progress">
                Bạn đã đăng ký ô này.
              </p>
            ) : (
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <label
                    htmlFor={`${dialogTitleId}-ca-toi`}
                    className="mb-1 block text-xs font-medium text-ink-muted"
                  >
                    Ca
                  </label>
                  <select
                    id={`${dialogTitleId}-ca-toi`}
                    className="w-full rounded-control border border-line bg-surface px-3 py-2 text-sm focus:border-brand-600 focus:outline-none"
                    value={shift}
                    onChange={(e) => setShift(e.target.value as Shift)}
                  >
                    {SHIFTS.map((s) => (
                      <option key={s} value={s}>
                        {SHIFT_LABEL[s]}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  onClick={xepCa}
                  disabled={busy}
                  className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface hover:bg-brand-700 disabled:opacity-50"
                >
                  Đăng ký
                </button>
              </div>
            )}

            {/* LỊCH SỬ Ô NÀY — các lần thêm / xoá / đổi người ở đúng ô (ngày ×
                vị trí × ca), ai và lúc nào; cùng nguồn với ô Phiên bản. */}
            {pb ? (
              <div className="mt-4 border-t border-line pt-3">
                <p className="mb-1.5 text-xs font-medium text-ink-muted">Lịch sử ô này</p>
                {!pb.co_lich_su ? (
                  <p className="text-meta text-ink-muted">
                    Tuần chưa có lịch sử — lịch gốc được chốt khi bấm “Áp dụng tuần”, mọi lần sửa
                    sau đó được ghi lại.
                  </p>
                ) : lichSuO.length === 0 ? (
                  <p className="text-meta text-ink-muted">Ô này chưa đổi gì kể từ lịch gốc.</p>
                ) : (
                  <DanhSachThayDoi
                    nhatKy={lichSuO}
                    nhan={STATION_LABEL}
                    boO
                    dangXemMa={xemMa}
                  />
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}
