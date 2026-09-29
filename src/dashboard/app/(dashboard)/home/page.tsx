// Trang chủ — ĐỒNG BỘ cho mọi vai trò. Giữ ĐÚNG 4 khối:
//  1. Lời chào (chức danh + tên) + ngày hôm nay
//  2. 3 ô số: Việc đang chờ làm · BN mới đăng ký hôm nay · Lịch chờ xác nhận
//  3. Ca trực hôm nay của bạn (từ work_roster)
//
// (Khối "2 mục" Lịch hẹn/Lịch làm việc + "Lối tắt" cũ đã bỏ/ẩn theo yêu cầu —
//  comment "Lối tắt" giữ ở cuối file để dùng lại nếu cần.)
//
// LÁT 3 (22/08/2026) — HAI ĐỔI LỚN, cùng một lý do "đông người không giật":
//
//  * MỘT vòng gói thay 6 vòng PostgREST + 3 endpoint rời. Trước đây mỗi lần
//    mở trang đi: 3 truy vấn đếm + roster tuần + ca trực + (Lễ tân) bảng
//    trạng thái (kèm truy vấn `staff` phụ và một ĐƯỜNG LÙI hai truy vấn khi
//    select join lỗi) + 3 lời gọi FastAPI. Nay tất cả là MỘT
//    `GET /api/v1/home/bang-dieu-khien` — xem man_trang_chu_service.py.
//
//  * SUSPENSE: lời chào + khung trang hiện NGAY, dữ liệu rót vào sau. Trước
//    đây server đợi đủ mọi truy vấn mới trả byte đầu tiên — bấm nút sidebar
//    lúc hệ đang đông là màn hình đứng trắng vài giây, người trực đọc thành
//    "web treo/quá tải" dù mạng không sao. Khung hiện tức thì nói điều
//    ngược lại: hệ sống, dữ liệu đang tới.

import { Suspense, cache } from "react";
import OSoXuHuong from "@/components/ui/OSoXuHuong";
import { buttonClass } from "@/components/ui/Button";
import CotTongQuan, { type CanXuLyRow, type TaiBacSiRow } from "./CotTongQuan";
import {
  getVaiChinh,
  getVaiHomNay,
  getQuyenCuaToi,
  getViTriHomNay,
  getActiveStaff,
} from "../../../lib/clinic-session";
import {
  type ClinicRole,
  canCheckin,
  isNurseRole,
  legoChoHien,
  vaoDuocMan,
} from "../../../lib/roles";
import Link from "next/link";
import { TEN_NHOM, hrefTheoViTri, mucPhong, nhomTheoViTri } from "../nav-items";
import type { ActiveStaff } from "../../../lib/clinic-session";
import { fmtDate } from "../../../lib/datetime";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { QUYEN_GHI_CHAM_SOC, coMotQuyen } from "../../../lib/quyen-cua-toi";
import { doctorName } from "../../../lib/doctor-name";
import {
  currentWeekStartVn,
  todayVn,
  viTriTuDb,
  weekDates,
  weekStartOf,
} from "../../../lib/roster";
import WeekNav from "../WeekNav";
import WeeklyAppointmentsTable, { type WeekApptRow } from "./WeeklyAppointmentsTable";
import { dungLichHenTuan } from "./lich-hen-ngay";
import WorkRosterTable, { type DongCaRow, type RosterRow } from "./WorkRosterTable";
import VisitStatusBoard, { type VisitStatusRow } from "./VisitStatusBoard";
import type { HanhTrinhGon } from "../../../lib/hanh-trinh-khach";
import VisitStatusRealtime from "./VisitStatusRealtime";

export const dynamic = "force-dynamic";

/** Shape of GET /api/v1/visits/progress — flags only, never the note itself. */
interface VisitProgressRow {
  appointment_id: string | null;
  visit_id: string | null;
  vitals_recorded: boolean;
  has_clinical_record: boolean;
  has_prescription: boolean;
  paid_kinds: string[];
  /** Giờ hai mốc giữa của thanh tiến trình (không có trên bảng `visit`). */
  exam_started_at?: string | null;
  paid_at?: string | null;
  /** Lễ tân đã Check-out — khách xong buổi (29/09/2026). */
  closed_at?: string | null;
  /** Mốc khám xong thật (`visit.exam_completed_at`). */
  kham_xong_luc?: string | null;
}

/** Toàn bộ dữ liệu Trang chủ, một lượt — hình do man_trang_chu_service quyết. */
interface GoiTrangChu {
  so_lieu: {
    viec_dang_cho: number;
    khach_moi_hom_nay: number;
    lich_can_xu_ly: number;
  };
  roster: (RosterRow & { ten_staff?: string | null })[];
  /** Ô đen / khối NGHỈ của tuần lịch (bảng `vi_tri_dong_ca`). */
  dong_ca?: DongCaRow[];
  truc_ca: { work_date: string; staff_id: string; staff_name: string | null }[];
  trang_thai_kham: VisitStatusRow[];
  /** Hành trình khách dạng gọn theo lượt (29/09/2026) — máy chủ quyết. */
  hanh_trinh_gon?: Record<string, HanhTrinhGon>;
  tuan_hen: WeekApptRow[];
  tien_trinh: VisitProgressRow[];
  /** 7 ngày, cũ → mới (27/09/2026). Chỉ hai ô có lịch sử thật. */
  xu_huong?: {
    ngay: string[];
    viec_dang_cho: number[];
    khach_moi_hom_nay: number[];
  };
  tai_bac_si?: TaiBacSiRow[];
  can_xu_ly?: CanXuLyRow[];
}


// LỜI CHÀO KHÔNG ĐƯỢC LẶP CHỨC DANH.
//
// Quang 09/08/2026: *"chỉ là xin chào CSKH Diệu Hoa thôi"*. Bản trước ghép
// `GREET_LABEL[role]` vào trước `full_name`, mà `full_name` trên prod đã mang
// sẵn chức danh ("CSKH · Diệu Hoa") — ra "Xin chào CSKH CSKH · Diệu Hoa". Hàm
// cắt tiền tố cũ chỉ biết "BS/ĐD/TL", không biết dấu chấm giữa.
//
// `doctorName` là chỗ đã giải đúng chuyện này cho mọi màn khác — dùng lại nó.
function greet(role: ClinicRole | null, staff: ActiveStaff | null): string {
  if (!role || !staff) return "Trang chủ";
  const goc = staff.full_name ?? staff.short_name;
  const ten = doctorName(goc);
  if (!ten) return "Trang chủ";
  // CHÀO THEO TÊN, KHÔNG THEO VAI (Tuyền 28/09/2026: tài khoản mang tên người,
  // "không có kiểu điều dưỡng hay lễ tân nữa" — việc của họ là các node trên
  // thanh bên theo kỹ năng). Tên đã mang chức danh (BS …) thì giữ nguyên.
  return `Xin chào ${ten}`;
}

/** Một ô ma đứng chỗ trong lúc dữ liệu đang rót — cùng khung với thẻ thật. */
function OMa({ cao }: { cao: string }) {
  return (
    <div
      aria-hidden
      className={`${cao} animate-pulse rounded-card border border-line bg-surface-sunken`}
    />
  );
}

/** Khung chờ của phần dữ liệu — hiện tức thì trong lúc gói đang về. */
function KhungTai({ isReception }: { isReception: boolean }) {
  return (
    <>
      <section
        aria-label="Đang tải số liệu"
        className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-3"
      >
        <OMa cao="h-20" />
        <OMa cao="h-20" />
        <OMa cao="h-20" />
      </section>
      {isReception && <OMa cao="h-40" />}
      <OMa cao="h-72" />
      <OMa cao="h-56" />
    </>
  );
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ weekAppt?: string; weekRoster?: string }>;
}) {
  // TRANG CHỦ THEO VIỆC HÔM NAY (Tuyền 16/09/2026): Minh Thư — tài khoản Điều
  // dưỡng — hôm nay đứng Lễ tân thì trang chủ là trang chủ Lễ tân (check-in),
  // không phải "Điền sinh hiệu". Không có ca thì vai chính = vai tài khoản.
  const role = await getVaiChinh();
  const viTriDo = await getViTriHomNay();
  const viTriHomNay = viTriDo?.vi_tri ?? [];
  const phong = viTriDo?.phong ?? {};
  // "Điền sinh hiệu" là việc của vị trí ĐO CHỈ SỐ, không phải của mọi điều
  // dưỡng: hôm 16/09 Hải Yến đứng Lấy mẫu, Vân Anh đứng ĐD Sàn chậu mà trang chủ
  // vẫn mời cả hai đo sinh hiệu. Không có ca → theo vai như trước.
  const choDoSinhHieu =
    viTriHomNay.length > 0
      ? hrefTheoViTri(viTriHomNay).includes("/do-sinh-hieu")
      : isNurseRole(role);
  // Việc hôm nay đi theo VỊ TRÍ, nhưng màn thuộc lego đang tắt thì không bày
  // (cùng phép lọc với thanh bên ngày có ca — kiểm toán 27/09/2026).
  const quyenHomNay = await getQuyenCuaToi();
  const viecHomNay = nhomTheoViTri(viTriHomNay, role, phong).map((g) => ({
    ten: TEN_NHOM[g.nhom],
    muc: g.hrefs
      .filter((h) => legoChoHien(quyenHomNay, h))
      .map((h) => mucPhong(h, phong))
      .filter((n): n is NonNullable<typeof n> => n !== undefined)
      .map((n) => ({ href: n.href, label: n.label })),
  }));
  const staff = await getActiveStaff();
  // CHECK-IN KHÔNG CÒN Ở TRANG CHỦ (Tuyền chốt 18/09/2026): cả ô check-in của
  // Quản lý lẫn cột check-in của Lễ tân chuyển sang Tiếp đón khách
  // (/reception/queue) — một việc, một chỗ. Bảng lịch ở đây chỉ để xem.
  const isReception = role === "RECEPTION"; // bảng trạng thái buổi khám: chỉ Lễ tân

  // 2 bảng có tuần ĐỘC LẬP: weekAppt cho Lịch hẹn khám, weekRoster cho Lịch làm
  // việc — bấm nút bảng nào CHỈ đổi tuần bảng đó (không kéo theo bảng kia).
  const { weekAppt: rawWeekAppt, weekRoster: rawWeekRoster } = await searchParams;
  // Hai tham số này lấy thẳng từ thanh địa chỉ. Ngày không đọc được thì rơi về
  // tuần hiện tại — TRANG CHỦ PHẢI MỞ ĐƯỢC. Trước đây `weekStartOf` ném
  // RangeError trên chuỗi rác, và server component ném thì cả trang rơi vào
  // error.tsx: một link hỏng là màn hình đầu ngày của cả phòng khám không vào được.
  const weekAppt =
    (rawWeekAppt ? weekStartOf(rawWeekAppt) : null) ?? currentWeekStartVn();
  const weekRoster =
    (rawWeekRoster ? weekStartOf(rawWeekRoster) : null) ?? currentWeekStartVn();

  const homeTitle = isReception ? "Tổng quan tiếp nhận" : greet(role, staff);
  // Phụ đề của Lễ tân từng là một câu mô tả màn hình ("Theo dõi lịch hẹn, tình
  // trạng buổi khám và lịch trực trong cùng một không gian") — Tuyền bỏ
  // 16/09/2026. Nó tả lại thứ người ta đang nhìn thấy, trong khi NGÀY HÔM NAY
  // mới là thứ quầy cần đọc ngay.
  const homeSubtitle = `Hôm nay · ${fmtDate(new Date())}`;

  return (
    <div className="mx-auto max-w-[1540px] space-y-5">
      {/* (Lịch sử) LỜI CHÀO VÀ BA Ô SỐ TỪNG NẰM CÙNG MỘT HÀNG — nay tách: xem
          khối ngay dưới.

          Trước đây chúng là hai thẻ chồng nhau, và thẻ lời chào để trống hết
          nửa bên phải — một khoảng trắng bằng cả ba ô số nằm ngay đầu trang mà
          không mang thông tin gì.

          Trên màn hẹp thì vẫn xuống dòng: ba con số quan trọng hơn việc chúng
          nằm cạnh lời chào.

          Từ Lát 3, phần LỜI CHÀO đứng ngoài Suspense — nó chỉ cần phiên, hiện
          tức thì; ba ô số thuộc phần dữ liệu nên rót vào sau. */}
      {/* LỜI CHÀO KHÔNG ĐÓNG KHUNG, BA Ô SỐ CÓ XU HƯỚNG BÊN DƯỚI (Tuyền chốt
          Trang chủ 27/09/2026: "bảng A + thống kê B"). Lời chào đứng trần như
          tiêu đề trang; ba ô số kiểu Stripe — con số lớn, chênh so với hôm
          qua, đường 7 ngày. Lời chào ngoài Suspense (chỉ cần phiên, hiện tức
          thì); ô số thuộc phần dữ liệu nên rót vào sau. */}
      <header>
        <p className="text-meta text-ink-muted">{homeSubtitle}</p>
        <h1 className="mt-0.5 text-hero font-semibold text-ink">{homeTitle}</h1>
      </header>

      <Suspense
        fallback={
          <section
            aria-label="Đang tải số liệu"
            className="grid grid-cols-1 gap-3 sm:grid-cols-3"
          >
            <OMa cao="h-28" />
            <OMa cao="h-28" />
            <OMa cao="h-28" />
          </section>
        }
      >
        <BaOSo
          weekAppt={weekAppt}
          weekRoster={weekRoster}
          isReception={isReception}
        />
      </Suspense>

      {/* VIỆC CỦA BẠN HÔM NAY — đúng các màn của vị trí trong lịch, bấm là vào. */}
      {viecHomNay.length > 0 ? (
        <section
          aria-label="Việc của bạn hôm nay"
          className="rounded-card border border-line bg-surface px-4 py-3 shadow-card sm:px-5"
        >
          <h2 className="text-sm font-semibold text-ink">Việc của bạn hôm nay</h2>
          <div className="mt-2 flex flex-col gap-2">
            {viecHomNay.map((g) => (
              <div key={g.ten} className="flex flex-wrap items-center gap-2">
                <span className="min-w-24 text-label font-semibold uppercase tracking-wider text-brand-700">
                  {g.ten}
                </span>
                {g.muc.map((m) => (
                  <Link
                    key={m.href}
                    href={m.href}
                    className="inline-flex min-h-10 items-center rounded-control border border-brand-500 px-3 text-sm font-semibold text-brand-700 hover:bg-brand-50"
                  >
                    {m.label}
                  </Link>
                ))}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <Suspense fallback={<KhungTai isReception={isReception} />}>
        <KhoiDuLieu
          choDoSinhHieu={choDoSinhHieu}
          role={role}
          isReception={isReception}
          weekAppt={weekAppt}
          weekRoster={weekRoster}
        />
      </Suspense>
    </div>
  );
}

// MỘT lời gọi gói cho CẢ trang, nhớ trong phạm vi MỘT lượt dựng.
//
// Hai island Suspense (ba ô số + phần thân) cùng đọc gói này — không khử trùng
// lặp thì thành HAI lời gọi backend giống hệt nhau, tức là tự tay nhân đôi cái
// mình vừa gộp. Dùng `cache()` của React chứ KHÔNG dùng Map module-scope: Map
// theo khoá tuần sẽ CHIA SẺ promise giữa hai người dùng khác nhau đang render
// cùng lúc với cùng cặp tuần — cookie của người gọi trước quyết định dữ liệu
// người gọi sau nhìn thấy (bảng Lễ tân, ô Quản lý). `cache()` tự scope theo
// TỪNG lượt render nên không có đường rò ấy.
const goiTrangChu = cache(
  (weekAppt: string, weekRoster: string): Promise<GoiTrangChu | null> =>
    fetchFromBackend<GoiTrangChu>(
      `/api/v1/home/bang-dieu-khien?week_appt=${weekAppt}&week_roster=${weekRoster}`,
    ),
);

/** Ba ô số trên đầu trang — island nhỏ, rót vào cạnh lời chào. */
async function BaOSo({
  weekAppt,
  weekRoster,
  isReception,
}: {
  weekAppt: string;
  weekRoster: string;
  isReception: boolean;
}) {
  const goi = await goiTrangChu(weekAppt, weekRoster);
  // Ô SỐ BẤM ĐƯỢC, CÓ ICON (ảnh Tuyền 16/09/2026). Chỉ gắn đường dẫn khi vai
  // mở được trang đích — một ô trông bấm được mà dẫn tới 403 tệ hơn ô chữ.
  // Cùng luật cửa trang (`vaoDuocMan` — lego của tài khoản, 27/09/2026): ô
  // trỏ tới màn thuộc lego đang tắt thì thành ô chữ, không dẫn vào ngõ cụt.
  const [vaiHomNay, quyen] = await Promise.all([getVaiHomNay(), getQuyenCuaToi()]);
  const toi = (href: string) =>
    vaoDuocMan(href, vaiHomNay, quyen) ? href : undefined;
  // BA Ô SỐ CỦA LỄ TÂN KHÁC CỦA CSKH (16/09/2026).
  //
  // Hai ô "Việc đang chờ làm" và "Lịch cần xử lý" đếm việc CHĂM SÓC KHÁCH và
  // cùng dẫn tới /customers — màn Tuyền vừa bỏ khỏi thanh bên của quầy vì
  // thừa. Để nguyên thì quầy nhìn hai con số của bộ phận khác, bấm vào không
  // đi đâu được. Thay bằng đúng hai câu hỏi của quầy sáng nay: còn ai chưa
  // đến, và đã đón được bao nhiêu người.
  //
  // Đếm trên CHÍNH danh sách lịch tuần mà bảng bên dưới đang vẽ (`tuan_hen`),
  // không hỏi thêm một lời gọi nữa — và vì cùng một nguồn nên con số trên đầu
  // không bao giờ cãi nhau với bảng ngay dưới nó.
  const homNay = todayVn();
  const henHomNay = (goi?.tuan_hen ?? []).filter(
    (a) => a.slot_start.slice(0, 10) === homNay,
  );
  const xh = goi?.xu_huong;
  const cards: {
    nhan: string;
    so: number;
    xuHuong?: number[];
    tangLaTot?: boolean;
    href?: string;
    phu?: string;
  }[] = isReception
    ? [
        {
          nhan: "Chờ check-in hôm nay",
          so: henHomNay.filter((a) =>
            ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"].includes(a.status),
          ).length,
          phu: "lịch hẹn chưa đến quầy",
        },
        {
          nhan: "Đã check-in hôm nay",
          so: henHomNay.filter((a) => a.status === "CHECKED_IN").length,
          href: toi("/reception/queue"),
          phu: "đang trong phòng khám",
        },
        {
          nhan: "BN mới đăng ký hôm nay",
          so: goi?.so_lieu.khach_moi_hom_nay ?? 0,
          xuHuong: xh?.khach_moi_hom_nay,
          href: toi("/patient-list"),
        },
      ]
    : [
        {
          // Việc tồn tăng là tin XẤU — chữ chênh lệch đổi màu theo đó.
          nhan: "Việc đang chờ làm",
          so: goi?.so_lieu.viec_dang_cho ?? 0,
          xuHuong: xh?.viec_dang_cho,
          tangLaTot: false,
          href: toi("/customers"),
        },
        {
          nhan: "Khách mới đăng ký hôm nay",
          so: goi?.so_lieu.khach_moi_hom_nay ?? 0,
          xuHuong: xh?.khach_moi_hom_nay,
          href: toi("/patient-list"),
        },
        {
          // Thay "Lịch chờ xác nhận" (luôn 0 từ khi đặt xong là xác nhận): số
          // khách đang có khung báo — vượt sức chứa, cần xác nhận/nhắc lịch, kết
          // quả chờ gửi, lịch bị gỡ bác sĩ. Ảnh chụp, không có lịch sử → không
          // vẽ đường xu hướng giả.
          nhan: "Lịch cần xử lý",
          so: goi?.so_lieu.lich_can_xu_ly ?? 0,
          href: toi("/customers"),
          phu: "khách có khung báo ở Quản lý khách hàng",
        },
      ];
  return (
    <section
      aria-label={isReception ? "Tổng quan tiếp nhận" : "Tổng quan ca làm việc"}
      className="grid grid-cols-1 gap-3 sm:grid-cols-3"
    >
      {cards.map((c) => (
        <OSoXuHuong
          key={c.nhan}
          nhan={c.nhan}
          so={c.so}
          xuHuong={c.xuHuong}
          tangLaTot={c.tangLaTot}
          href={c.href}
          phu={c.phu}
        />
      ))}
    </section>
  );
}

/** Phần thân dữ liệu của trang — mọi bảng, sau MỘT lời gọi gói. */
async function KhoiDuLieu({
  role,
  isReception,
  choDoSinhHieu,
  weekAppt,
  weekRoster,
}: {
  role: ClinicRole | null;
  isReception: boolean;
  choDoSinhHieu: boolean;
  weekAppt: string;
  weekRoster: string;
}) {
  const rosterDates = weekDates(weekRoster);

  // Danh mục vị trí từ database (C4) — cùng lời gọi layout đã làm (cache theo
  // lượt dựng trang), không thêm vòng mạng.
  const [goi, viTri, vaiHomNay, quyen] = await Promise.all([
    goiTrangChu(weekAppt, weekRoster),
    getViTriHomNay(),
    getVaiHomNay(),
    getQuyenCuaToi(),
  ]);
  // Dòng "Cần xử lý" chỉ là link khi tài khoản mở được màn đích (cùng luật cửa
  // trang với ô số — lego tắt thì thành dòng chữ).
  const toi = (href: string) =>
    vaoDuocMan(href, vaiHomNay, quyen) ? href : undefined;
  // Backend im thì các bảng cùng rỗng — phải NÓI RA. Một trang chủ trống trơn
  // trông y hệt "hôm nay chưa có gì", và người trực sẽ tin nó (cùng luật với
  // goiLoi ở màn Quản lý khách hàng, Lát 2).
  const goiLoi = goi === null;

  // Bảng trạng thái buổi khám: join đã làm THẲNG trong SQL của backend, nên
  // đường-lùi-hai-truy-vấn cũ (sinh ra vì select join PostgREST từng lỗi cột)
  // không còn đất sống — cột sai giờ là CI đỏ ở test service, không đợi prod.
  //
  // Lịch bị HỦY / KHÔNG ĐẾN sau khi đã check-in vẫn còn visit (OPEN/IN_PROGRESS)
  // → bảng hiển thị "Đang khám" mãi + đếm sai. Lọc bỏ các lượt mà appointment
  // đã CANCELLED/NO_SHOW (KHÔNG xóa visit — giữ data lâm sàng nếu đã nhập; chỉ
  // ẩn khỏi bảng theo dõi buổi khám).
  const visitStatusRows = (goi?.trang_thai_kham ?? []).filter((v) => {
    const s = v.appointment?.status ?? null;
    return s !== "CANCELLED" && s !== "NO_SHOW";
  });

  // Tiến trình mỗi lượt khám (đã đo sinh hiệu chưa, đã thu những khâu nào) từ
  // FastAPI — ROLE-02: backend trả về CỜ, không trả nội dung bệnh án, nên Lễ
  // tân/Thu ngân không cần (và không có) quyền đọc bệnh án.
  const progress = goi?.tien_trinh ?? [];
  const progressByVisit = new Map(
    progress.filter((p) => p.visit_id).map((p) => [p.visit_id as string, p]),
  );

  // Mốc "Đã thanh toán": đã thu ĐỦ mọi khâu PHẢI thu của lượt khám = DỊCH VỤ
  // (luôn có, vì có dịch vụ khám) + THUỐC nếu lượt có đơn thuốc.
  if (isReception && visitStatusRows.length) {
    for (const v of visitStatusRows) {
      const p = progressByVisit.get(v.visit_id);
      const kinds = new Set(p?.paid_kinds ?? []);
      v.paid = kinds.has("dich_vu") && (!p?.has_prescription || kinds.has("thuoc"));
      // Giờ hai mốc giữa của thanh tiến trình. Chúng không nằm trên bảng
      // `visit`, nên lấy từ chính khối tiến trình của gói.
      v.exam_started_at = p?.exam_started_at ?? null;
      v.paid_at = p?.paid_at ?? null;
      v.closed_at = p?.closed_at ?? null;
      v.kham_xong_luc = p?.kham_xong_luc ?? null;
      // Hành trình khách dạng gọn (29/09/2026) — thay thanh 4 mốc.
      v.hanh_trinh = goi?.hanh_trinh_gon?.[v.visit_id] ?? null;
    }
  }

  // TÊN TRONG BẢNG LỊCH LÀM VIỆC LẤY TỪ `staff`, KHÔNG PHẢI CHUỖI EXCEL.
  //
  // Màn /schedule đã làm bước này từ trước; trang chủ thì không, nên cùng một
  // bảng ở hai nơi hiện hai cách viết tên — và ở đây còn tệ hơn: cột "Số BS"
  // đếm theo staff_id nên nó nói 4 trong khi ô bên cạnh bày 5 cái tên (08/08:
  // "Bác sĩ · BSNT. Lê Thiệu Quyết" và "BS QUYẾT" là MỘT người).
  //
  // Backend join sẵn `ten_staff` (staff.full_name); phép CẮT CHỨC DANH vẫn là
  // việc của `doctorName` phía frontend — luật ấy sống một chỗ, không chép
  // sang Python thành bản thứ hai (đúng cách dongBoTenTrucNhat từng làm,
  // chỉ bớt được truy vấn `staff` phụ).
  const rosterRows: RosterRow[] = (goi?.roster ?? []).map((r) => {
    const ten = r.ten_staff ? doctorName(r.ten_staff) : "";
    return { ...r, staff_name: (r.staff_id && ten) || r.staff_name };
  });

  const { apptDays, dutyByDate } = dungLichHenTuan(goi, weekAppt);

  return (
    <>
      {goiLoi && (
        <div
          role="alert"
          className="rounded-card border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          Không đọc được dữ liệu trang chủ — backend không trả lời. Các bảng
          bên dưới đang trống vì thế, không phải vì hôm nay không có gì.
        </div>
      )}

      {/* Trạng thái BN buổi khám hôm nay — CHỈ Lễ tân, READ-ONLY (theo visit.status).
          Thanh tiến trình kiểu Grab + tự cập nhật liên tục (realtime visit). */}
      {isReception && (
        <section aria-label="Trạng thái buổi khám hôm nay" className="rounded-card border border-line bg-surface p-3 shadow-card sm:p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-ink">
              Trạng thái BN buổi khám hôm nay
            </h2>
            <VisitStatusRealtime />
          </div>
          <VisitStatusBoard rows={visitStatusRows} />
        </section>
      )}

      {/* Lịch hẹn khám — nút tuần RIÊNG (weekAppt), KHÔNG đụng Lịch làm việc. */}
      {/* BẢNG LỊCH + CỘT TỔNG QUAN (27/09/2026): máy rộng thì cột phải đứng
          cạnh bảng; màn hẹp thì xuống dưới bảng. */}
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <section aria-label="Lịch hẹn khám" className="min-w-0 rounded-card border border-line bg-surface p-3 shadow-card sm:p-4">
        {/* KHU ĐIỀU KHIỂN MỘT KHỐI (Tuyền 27/09/2026: "tối giản thông minh"):
            tên bảng · ‹ tuần › · nút sang Tiếp đón trên một hàng, dải ngày
            ngay dưới (bảng tự vẽ). Nút Check-in hạ xuống nút phụ — việc
            check-in ở màn Tiếp đón, đây chỉ là lối tắt. */}
        <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-2">
          <h2 className="text-emph font-semibold text-ink">Lịch hẹn khám</h2>
          <WeekNav
            gon
            week={weekAppt}
            basePath="/home"
            param="weekAppt"
            others={{ weekRoster }}
          />
          {canCheckin(role) && (
            <Link
              href="/reception/queue"
              className={`ml-auto ${buttonClass("secondary", "sm")}`}
            >
              Check-in ở Tiếp đón
            </Link>
          )}
        </div>
        <WeeklyAppointmentsTable
          days={apptDays}
          role={role}
          dutyByDate={dutyByDate}
          choDoSinhHieu={choDoSinhHieu}
          // ⋯ "Đổi lịch" (popover tại dòng) theo LEGO Quản lý lịch hẹn; bấm tên
          // khách: đã check-in → Hành trình khách, chưa → hồ sơ khách (29/09/2026,
          // bỏ ngăn "Hành chính & Sinh hiệu").
          duocDoiLich={quyen === null ? undefined : quyen.includes("booking.manage")}
          // ⋯ "Gọi / ghi chăm sóc" làm TẠI CHỖ; "Mở hồ sơ khách" → Danh sách
          // bệnh nhân `?chon=` — hỏi đúng luật cửa của trang đích (29/09/2026).
          duocGhiChamSoc={coMotQuyen(quyen, QUYEN_GHI_CHAM_SOC)}
          duocXemHoSo={vaoDuocMan("/patient-list", vaiHomNay, quyen)}
          moHoSoKhach={vaoDuocMan("/customers", vaiHomNay, quyen)}
          // Chip T2…CN + "Cả tuần", giữ trên `?ngay=` (27/09/2026, đợt 3 —
          // "check đặt lịch cần hiển thị theo ngày"). Mặc định hôm nay khi
          // đang xem tuần này.
          chonNgay
          // Không bày dòng "+ Thêm khách hàng" (Tuyền 28/09/2026, chọn a).
          choThemKhach={false}
        />
      </section>
      <CotTongQuan
        taiBacSi={goi?.tai_bac_si ?? []}
        canXuLy={goi?.can_xu_ly ?? []}
        hrefCanXuLy={{
          khach_tre: toi("/reception/queue"),
          chua_xep_bac_si: toi("/appointments/cho-xep-bac-si"),
          viec_qua_han: toi("/viec-can-xu-ly"),
        }}
      />
      </div>

      {/* Lịch làm việc — nút tuần RIÊNG (weekRoster), KHÔNG đụng Lịch hẹn khám. */}
      <section aria-label="Lịch làm việc" className="rounded-card border border-line bg-surface p-3 shadow-card sm:p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">Lịch làm việc</h2>
          <WeekNav
            week={weekRoster}
            basePath="/home"
            param="weekRoster"
            others={{ weekAppt }}
          />
        </div>
        <WorkRosterTable
          stations={viTriTuDb(viTri?.danh_muc)}
          dates={rosterDates}
          rows={rosterRows}
          dong={goi?.dong_ca ?? []}
        />
      </section>

      {/*
        ===== TẠM ẨN: "Lối tắt" cũ (giữ lại để dùng sau, đừng xoá) =====
        Lối tắt = các mục nav vai trò được phép, dạng nút lớn:

        const actions = NAV.filter(n => n.href !== "/home" && canSeeNav(role, n.href));
        <section>
          <h2>Lối tắt</h2>
          <div className="grid grid-cols-2 ... lg:grid-cols-4">
            {actions.map(({ href, label, icon: Icon }) => (
              <Link href={href} ...><Icon/> {label}</Link>
            ))}
          </div>
        </section>
        (cần import lại: NAV từ "../nav-items", canSeeNav từ "../../../lib/roles")
      */}
    </>
  );
}
