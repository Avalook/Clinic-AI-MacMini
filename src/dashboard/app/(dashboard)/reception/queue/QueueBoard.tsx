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
// Từ 09/10/2026 tab + ô tìm nằm ở THANH TRÊN CÙNG trang (`ThanhLocTiepDon`, lọc
// cả bảng Lịch hẹn) — bảng này đọc `tab`/`tim` qua `useLocTiepDon`.
//
// SẮP XẾP (29/09/2026, Tuyền): máy chủ xếp CŨ → MỚI theo giờ vào hàng thật
// (giờ check-in; chưa đến thì giờ hẹn). Công tắc "Mới nhất trước" chỉ đảo lại
// để xem — lựa chọn nhớ theo máy quầy (localStorage, bọc try/catch).

import { useRouter } from "next/navigation";
import { useId, useMemo, useState, useSyncExternalStore, useTransition } from "react";

import Chip from "@/components/ui/Chip";
import ChipChon from "@/components/ui/ChipChon";
import NutCheckIn from "@/components/ui/NutCheckIn";
import PriorityChip from "@/components/ui/PriorityChip";
import SoLuot from "@/components/ui/SoLuot";
import { doctorName } from "@/lib/doctor-name";
import {
  docHuongXep,
  dongPhu,
  ghiHuongXep,
  HUONG_XEP_MAC_DINH,
  LOC_MAC_DINH,
  locTiepDon,
  sapXepTiepDon,
  toneTrangThai,
  type DongTiepDon,
  type GoiTiepDon,
  type HuongXep,
} from "@/lib/tiep-don";
import { useLocTiepDon } from "@/lib/loc-tiep-don-context";

import { nhanLieuTrinhLuot } from "@/lib/lieu-trinh-cskh";

import { useChipLieuTrinh } from "../../_lam-viec/dung-chip-lieu-trinh";
import { NutLamThem, useLamThem, type GoiLamThem } from "../../_lam-viec/LamThemTaiQuay";
import NutCheckOut from "../../_lam-viec/NutCheckOut";
import { lenhHoanTac } from "../../_lam-viec/hoan-tac";
import NutHoanTac, { type KetQuaHoanTac } from "@/components/ui/NutHoanTac";
import NutXemLuot from "../../_lam-viec/NutXemLuot";

/** HOÀN TÁC CHECK-IN (09/10/2026) — cùng lệnh nút "Hoàn tác" của bảng Lịch hẹn
 *  (`PATCH /api/appointments` action=undo_checkin). Máy chủ từ chối khi khách đã
 *  có việc thật sau check-in; câu từ chối hiện nguyên văn. */
async function hoanTacCheckIn(appointmentId: string): Promise<KetQuaHoanTac> {
  try {
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: appointmentId, action: "undo_checkin" }),
    });
    if (res.ok) return { ok: true };
    const b = (await res.json().catch(() => null)) as { error?: string } | null;
    return { ok: false, loi: b?.error ?? `Không hoàn tác được (HTTP ${res.status})` };
  } catch {
    return { ok: false, loi: "Mất kết nối — chưa hoàn tác được, bấm lại." };
  }
}

/** Một dòng tiếp đón. Check-in đi ĐÚNG đường của bảng "Lịch hẹn hôm nay"
 *  (`PATCH /api/appointments` action=checkin) — hai đường check-in là hai luật
 *  cấp số lệch nhau. Ai được bấm do máy chủ quyết theo khối quyền. */
function DongKhach({
  d,
  lamThem,
  napLamThem,
  lieuTrinh = null,
}: {
  /** "Liệu trình Ghế điện: còn 3 buổi đã trả" (08/10/2026) — máy chủ đếm. */
  lieuTrinh?: string | null;
  d: DongTiepDon;
  /** Nút "+ dịch vụ" (làm thêm tại quầy, 01/10/2026) — một lần đọc cho cả bảng. */
  lamThem: GoiLamThem | null;
  napLamThem: () => void;
}) {
  const router = useRouter();
  const [dang, startTransition] = useTransition();
  const [gui, setGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [xemLyDo, setXemLyDo] = useState(false);

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
        {lieuTrinh ? (
          <p className="mt-0.5 break-words text-meta font-medium text-brand-700">{lieuTrinh}</p>
        ) : null}
        {d.ghi_chu ? (
          <p className="mt-0.5 break-words text-meta text-ink-soft">Ghi chú: {d.ghi_chu}</p>
        ) : null}
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
        {/* HOÀN TÁC CHECK-IN (09/10/2026): check-in nhầm → về "Chưa đến". Máy
            chủ chỉ cho khi khách chưa có việc thật nào sau check-in; không cho
            thì nút xám, bấm hiện vì sao (không gửi lệnh). */}
        {d.hoan_tac_duoc ? (
          <NutHoanTac
            goi={() => hoanTacCheckIn(d.appointment_id)}
            moTa="Check-in nhầm — đưa khách về Chưa đến"
            onXong={() => startTransition(() => router.refresh())}
          />
        ) : d.ly_do_khong_hoan_tac ? (
          <button
            type="button"
            aria-expanded={xemLyDo}
            onClick={() => setXemLyDo((x) => !x)}
            title={d.ly_do_khong_hoan_tac}
            className="rounded-control px-2 py-1 text-label font-medium text-ink-faint hover:bg-surface-muted"
          >
            Hoàn tác
          </button>
        ) : null}
        {/* HOÀN TÁC check-out (01/10/2026): "Đã về" nhầm → mở lại lượt. */}
        {d.mo_lai_duoc && d.visit_id ? (
          <NutHoanTac
            goi={lenhHoanTac("mo-lai-luot", d.visit_id)}
            tieuDe="Mở lại lượt khám?"
            moTa="Check-out nhầm — mở lại lượt, khách về lại các hàng chờ còn dở"
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
      {xemLyDo && d.ly_do_khong_hoan_tac ? (
        <p role="status" className="col-span-full rounded-control bg-warning-bg px-2 py-1 text-meta text-warning">
          {d.ly_do_khong_hoan_tac}
        </p>
      ) : null}
    </li>
  );
}

/** Kho nhớ không phát tin đổi (chỉ màn này ghi) — không cần theo dõi. */
function khongTheoDoi(): () => void {
  return () => {};
}

export default function QueueBoard({ goi }: { goi: GoiTiepDon }) {
  // Tab + ô tìm của thanh lọc trên cùng trang (`ManTiepDon` → context).
  const { tab, tim } = useLocTiepDon() ?? LOC_MAC_DINH;
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
  // Chip liệu trình — một lần đọc cho cả bảng (không gọi từng dòng).
  const chipLt = useChipLieuTrinh(cacLuot);

  return (
    <section aria-label="Danh sách tiếp đón" className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-emph font-semibold text-ink">Danh sách tiếp đón hôm nay</h2>
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
                    lieuTrinh={nhanLieuTrinhLuot(chipLt, d.visit_id ?? null)}
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
