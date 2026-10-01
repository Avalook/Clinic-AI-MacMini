"use client";

// DANH SÁCH TIẾP ĐÓN — làm lại theo bản mẫu Tuyền duyệt (27/09/2026, đợt 3).
//
// Mỗi lịch hẹn / lượt hôm nay MỘT DÒNG, chia buổi Sáng / Chiều (/ Tối):
//
//   [#booking][vòng check-in]  TÊN (to, không cắt) + chip loại khách   [chip trạng thái] [nút]
//                              giờ hẹn · loại khám · BS · SĐT
//
// Bản trước (24/09) có hai tab "Chờ check-in / Đã check-in", kéo đổi thứ tự và
// hai cột phải (thông tin người bệnh, điều phối tại quầy). Bản mẫu bỏ cả ba:
// một danh sách, lọc bằng tab có số đếm, mọi việc làm ngay trên dòng.
//
// MÀN CHỈ VẼ. Chia buổi, thứ tự, chip trạng thái ("Trễ 25′", "Đang ở: …",
// "Đã check-in 08:02 · chờ đo", "Đã về 10:12") và nút nào được hiện đều do máy
// chủ tính (`GET /api/v1/reception/danh-sach` → `services/tiep_don_service.py`).
// Ở đây chỉ lọc tại chỗ (tab + ô tìm, `lib/tiep-don.ts`) và tô màu theo `loai`.
//
// SẮP XẾP (29/09/2026, Tuyền): máy chủ xếp CŨ → MỚI theo giờ vào hàng thật
// (giờ check-in; chưa đến thì giờ hẹn). Công tắc "Mới nhất trước" chỉ đảo lại
// để xem — lựa chọn nhớ theo máy quầy (localStorage, bọc try/catch).

import { Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useMemo, useState, useSyncExternalStore, useTransition } from "react";

import { buttonClass } from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ChipChon from "@/components/ui/ChipChon";
import NutCheckIn from "@/components/ui/NutCheckIn";
import PriorityChip from "@/components/ui/PriorityChip";
import SoLuot from "@/components/ui/SoLuot";
import ThanhTab from "@/components/ui/ThanhTab";
import { doctorName } from "@/lib/doctor-name";
import { hrefThemKhach } from "@/lib/lien-ket-lich";
import {
  docHuongXep,
  dongPhu,
  ghiHuongXep,
  HUONG_XEP_MAC_DINH,
  locTiepDon,
  sapXepTiepDon,
  toneTrangThai,
  type DongTiepDon,
  type GoiTiepDon,
  type HuongXep,
  type TabTiepDon,
} from "@/lib/tiep-don";

import { NutLamThem, useLamThem, type GoiLamThem } from "../../_lam-viec/LamThemTaiQuay";
import NutCheckOut from "../../_lam-viec/NutCheckOut";
import NutXemLuot from "../../_lam-viec/NutXemLuot";

/** Một dòng tiếp đón. Check-in đi ĐÚNG đường của bảng "Lịch hẹn hôm nay"
 *  (`PATCH /api/appointments` action=checkin) — hai đường check-in là hai luật
 *  cấp số lệch nhau. Ai được bấm do máy chủ quyết theo khối quyền. */
function DongKhach({
  d,
  lamThem,
  napLamThem,
}: {
  d: DongTiepDon;
  /** Nút "+ dịch vụ" (làm thêm tại quầy, 01/10/2026) — một lần đọc cho cả bảng. */
  lamThem: GoiLamThem | null;
  napLamThem: () => void;
}) {
  const router = useRouter();
  const [dang, startTransition] = useTransition();
  const [gui, setGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function checkIn() {
    if (gui) return;
    setLoi(null);
    setGui(true);
    try {
      const res = await fetch("/api/appointments", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: d.appointment_id, action: "checkin" }),
      });
      if (!res.ok) {
        const b = (await res.json().catch(() => null)) as { error?: string } | null;
        setLoi(b?.error ?? `Không check-in được (HTTP ${res.status})`);
        return;
      }
      startTransition(() => router.refresh());
    } catch {
      setLoi("Mất kết nối — chưa check-in được, bấm lại.");
    } finally {
      setGui(false);
    }
  }

  const ban = gui || dang;
  const phu = dongPhu([
    d.gio_hen,
    d.loai_kham,
    d.bac_si ? doctorName(d.bac_si) : null,
    d.sdt,
  ]);

  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3 last:border-b-0 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
      <SoLuot dang="tron" bookingTruoc booking={d.so_booking} checkin={d.so_tiep_don} />
      <div className="min-w-0">
        {/* TÊN KHÔNG CẮT: tên dài xuống dòng (bản mẫu "Nguyễn Thị Phương Mai
            Anh") — lễ tân đọc tên để gọi khách. */}
        <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 break-words text-title font-semibold text-ink">
          <span>{d.ten ?? "Chưa rõ tên"}</span>
          {d.loai_khach ? <Chip tone="info">{d.loai_khach}</Chip> : null}
          {d.uu_tien ? (
            <span title={d.uu_tien_ly_do ?? "Khách ưu tiên"}>
              <PriorityChip priority="P0" />
            </span>
          ) : null}
        </p>
        {phu ? <p className="mt-0.5 text-meta text-ink-muted">{phu}</p> : null}
      </div>
      {/* Điện thoại (dưới sm): trạng thái + nút xuống dòng dưới tên, Check-in
          kéo rộng hết dòng. */}
      <div className="col-span-2 flex flex-wrap items-center gap-2 sm:col-span-1 sm:justify-end">
        <Chip
          tone={toneTrangThai(d.trang_thai.loai)}
          title={d.trang_thai.nhan}
          className="max-w-full overflow-hidden text-ellipsis"
        >
          {d.trang_thai.nhan}
        </Chip>
        {d.check_in_duoc ? (
          <div className="flex-1 sm:min-w-28 sm:flex-none">
            <NutCheckIn size="lg" fullWidth disabled={ban} onChon={() => checkIn()}>
              {ban ? "Đang check-in…" : "Check-in"}
            </NutCheckIn>
          </div>
        ) : null}
        {d.visit_id ? <NutXemLuot visitId={d.visit_id} nhan="Xem" variant="secondary" /> : null}
        {/* Check-out ngay trên dòng (cùng lệnh với màn Check-out, máy chủ
            quyết); nút tự ẩn khi tài khoản không có quyền đóng lượt. */}
        {d.check_out_duoc && d.visit_id ? (
          <NutCheckOut
            key={d.visit_id}
            visitId={d.visit_id}
            ten={d.ten}
            onXong={() => startTransition(() => router.refresh())}
          />
        ) : null}
      </div>
      {/* "+ Nước tiểu"… ngay sau check-in: tick là chỉ định luôn, không cần
          bác sĩ (Tuyền 01/10/2026). Danh sách nút do quản lý quản. */}
      {d.visit_id ? (
        <NutLamThem
          goi={lamThem}
          visitId={d.visit_id}
          napLai={napLamThem}
          className="col-span-full sm:col-start-2"
        />
      ) : null}
      {loi ? (
        <p className="col-span-full rounded-control bg-danger-bg px-2 py-1 text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </li>
  );
}

/** Kho nhớ không phát tin đổi (chỉ màn này ghi) — không cần theo dõi. */
function khongTheoDoi(): () => void {
  return () => {};
}

export default function QueueBoard({
  goi,
  themKhachDuoc,
}: {
  goi: GoiTiepDon;
  /** Được mở trang Thêm khách hàng không — trang gọi `moDuocMan("/patients/new")`,
   *  cùng luật cửa của trang đích. */
  themKhachDuoc: boolean;
}) {
  const [tab, setTab] = useState<TabTiepDon>("tat_ca");
  const [tim, setTim] = useState("");
  // Bảng được vẽ hai bản (máy tính / điện thoại): hai nhóm ô chọn cùng `name`
  // thì trình duyệt chỉ cho MỘT ô được chọn trên cả hai — bản kia trống. Mỗi
  // bản một tên riêng.
  const tenNhomXep = `huong-xep-tiep-don-${useId()}`;
  // Lựa chọn đã nhớ đọc qua useSyncExternalStore (cùng cách `NganGap`): máy
  // chủ vẽ mặc định, trình duyệt vẽ lựa chọn đã nhớ — không lệch HTML, không
  // setState trong effect. Lần bấm trong phiên thắng cái đã nhớ.
  const daNho = useSyncExternalStore(khongTheoDoi, docHuongXep, () => HUONG_XEP_MAC_DINH);
  const [bam, setBam] = useState<HuongXep | null>(null);
  const huong = bam ?? daNho;
  function doiHuong(h: HuongXep) {
    setBam(h);
    ghiHuongXep(h);
  }
  const buoi = useMemo(
    () => locTiepDon(sapXepTiepDon(goi.buoi, huong), tab, tim),
    [goi.buoi, huong, tab, tim],
  );
  // Mọi lượt đã check-in hôm nay — một lần đọc nút "+ dịch vụ" cho cả bảng.
  const cacLuot = useMemo(
    () =>
      goi.buoi.flatMap((b) => b.dong.map((d) => d.visit_id)).filter((v): v is string => Boolean(v)),
    [goi.buoi],
  );
  const { goi: lamThem, napLai: napLamThem } = useLamThem("tiep_don", cacLuot);

  return (
    <section aria-label="Danh sách tiếp đón" className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <ThanhTab
          nhan="Lọc danh sách tiếp đón"
          muc={[
            { ma: "tat_ca", nhan: "Tất cả", dem: goi.dem.tat_ca },
            { ma: "chua_den", nhan: "Chưa đến", dem: goi.dem.chua_den },
            { ma: "da_den", nhan: "Đã check-in", dem: goi.dem.da_den },
          ]}
          chon={tab}
          onChon={setTab}
        />
        <label className="flex min-h-10 min-w-48 flex-1 items-center gap-2 rounded-control border border-line bg-surface px-3 text-ink-muted focus-within:border-brand-500">
          <Search size={15} aria-hidden />
          <span className="sr-only">Tìm tên, SĐT, mã khách</span>
          <input
            type="search"
            value={tim}
            onChange={(e) => setTim(e.target.value)}
            placeholder="Tìm tên, SĐT, mã khách"
            className="min-w-0 flex-1 bg-transparent text-body text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
        <div role="radiogroup" aria-label="Sắp xếp theo giờ vào hàng" className="flex items-center gap-1.5">
          <span className="text-meta text-ink-muted">Sắp xếp:</span>
          <ChipChon
            kieu="mot"
            ten={tenNhomXep}
            chon={huong === "cu_truoc"}
            onDoi={() => doiHuong("cu_truoc")}
          >
            Cũ nhất trước
          </ChipChon>
          <ChipChon
            kieu="mot"
            ten={tenNhomXep}
            chon={huong === "moi_truoc"}
            onDoi={() => doiHuong("moi_truoc")}
          >
            Mới nhất trước
          </ChipChon>
        </div>
        {themKhachDuoc ? (
          <Link href={hrefThemKhach()} className={buttonClass("primary", "lg")}>
            + Thêm khách hàng
          </Link>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
        {buoi.length === 0 ? (
          <p className="px-4 py-10 text-center text-body text-ink-muted">
            {tim.trim()
              ? "Không có khách nào khớp từ khoá."
              : goi.dem.tat_ca === 0
                ? "Hôm nay chưa có lịch hẹn nào."
                : tab === "chua_den"
                  ? "Khách hẹn hôm nay đã check-in hết."
                  : "Chưa có khách nào check-in."}
          </p>
        ) : (
          buoi.map((b) => (
            <div key={b.ma}>
              <h3 className="border-b border-line bg-surface-muted px-4 py-2 text-label font-semibold uppercase tracking-wide text-ink-muted">
                {b.nhan}
              </h3>
              <ul>
                {b.dong.map((d) => (
                  <DongKhach
                    key={d.appointment_id}
                    d={d}
                    lamThem={lamThem}
                    napLamThem={napLamThem}
                  />
                ))}
              </ul>
            </div>
          ))
        )}
      </div>
      {goi.bi_cat ? (
        <p className="text-meta text-warning">
          Danh sách đã cắt ở 500 lịch hôm nay — có thể thiếu khách, báo kỹ thuật.
        </p>
      ) : null}
    </section>
  );
}
