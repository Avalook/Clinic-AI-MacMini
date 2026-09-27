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

import { Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

import { buttonClass } from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import NutCheckIn from "@/components/ui/NutCheckIn";
import PriorityChip from "@/components/ui/PriorityChip";
import SoLuot from "@/components/ui/SoLuot";
import ThanhTab from "@/components/ui/ThanhTab";
import { doctorName } from "@/lib/doctor-name";
import {
  dongPhu,
  locTiepDon,
  toneTrangThai,
  type DongTiepDon,
  type GoiTiepDon,
  type TabTiepDon,
} from "@/lib/tiep-don";

import NutCheckOut from "../../_lam-viec/NutCheckOut";
import NutXemLuot from "../../_lam-viec/NutXemLuot";

/** Một dòng tiếp đón. Check-in đi ĐÚNG đường của bảng "Lịch hẹn hôm nay"
 *  (`PATCH /api/appointments` action=checkin) — hai đường check-in là hai luật
 *  cấp số lệch nhau. Ai được bấm do máy chủ quyết theo khối quyền. */
function DongKhach({ d }: { d: DongTiepDon }) {
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
      {loi ? (
        <p className="col-span-full rounded-control bg-danger-bg px-2 py-1 text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </li>
  );
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
  const buoi = useMemo(() => locTiepDon(goi.buoi, tab, tim), [goi.buoi, tab, tim]);

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
        {themKhachDuoc ? (
          <Link href="/patients/new" className={buttonClass("primary", "lg")}>
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
                  <DongKhach key={d.appointment_id} d={d} />
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
