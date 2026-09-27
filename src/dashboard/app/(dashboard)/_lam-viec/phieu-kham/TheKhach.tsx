// THẺ KHÁCH + THẺ SINH HIỆU — Y HỆT bản giao diện mẫu (Tuyền chốt 27/09/2026).
//
// Bản mẫu `dauPhieu` (M/app.js:79-120, M/style.css:345-379): avatar tròn 56 hai chữ
// cái (nam tông info — ngoại lệ ghi ở globals.css), tên 22px HOA + chip loại khám,
// "Nữ • 42 tuổi (1984)", ba viên (Mã khách · SĐT · Khám), ô Cơ sở góc phải, bốn ô
// có icon (Địa chỉ · Bác sĩ · Kênh đặt · Người giới thiệu). Thẻ sinh hiệu: lưới ô
// nhãn + giá trị KÈM ĐƠN VỊ, đầu thẻ "Đo lúc · người đo · chỉ xem".
//
// Dữ liệu do máy chủ dựng (`doc_dau_phieu`: the_khach, the_sinh_hieu) — ở đây chỉ vẽ.
// Không có ô nào sửa được: hồ sơ sửa ở màn khách, sinh hiệu sửa ở Đo sinh hiệu.

import type { ReactNode } from "react";
import {
  CalendarDays,
  IdCard,
  MapPin,
  Megaphone,
  Phone,
  UserRound,
  Users,
} from "lucide-react";

import type { DauPhieu } from "@/lib/phieu-kham";
import SoLuot from "@/components/ui/SoLuot";

/** "2026-09-25" → "25/09/2026". */
function ngayVn(iso: string | number | null | undefined): string | null {
  if (typeof iso !== "string") return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** "0914378212" → "0914 378 212" (đọc qua điện thoại dễ hơn). */
function sdtDoc(sdt: string | number | null | undefined): string | null {
  if (sdt === null || sdt === undefined || sdt === "") return null;
  const s = String(sdt).replace(/\s+/g, "");
  return /^\d{10}$/.test(s) ? `${s.slice(0, 4)} ${s.slice(4, 7)} ${s.slice(7)}` : String(sdt);
}

/** Hai chữ cái: chữ đầu của HỌ + chữ đầu của TÊN ("Nguyễn Thị Mẫu" → "NM"). */
function chuDau(ten: string): string {
  const tu = ten.trim().split(/\s+/).filter(Boolean);
  if (tu.length === 0) return "?";
  return `${tu[0][0]}${tu.length > 1 ? tu[tu.length - 1][0] : ""}`.toUpperCase();
}

function gioDo(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: "Asia/Ho_Chi_Minh",
      });
}

function Vien({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex h-7 items-center gap-1.5 rounded-control bg-surface-muted px-2.5 text-meta text-ink">
      <span aria-hidden className="shrink-0 text-ink-faint">
        {icon}
      </span>
      {children}
    </span>
  );
}

function OThongTin({ icon, nhan, gia_tri }: { icon: ReactNode; nhan: string; gia_tri: string | null }) {
  return (
    <div className="flex items-start gap-2.5 rounded-control px-2.5 py-2 ring-1 ring-inset ring-hairline sm:px-3 sm:py-2.5">
      <span
        aria-hidden
        className="hidden size-7 shrink-0 place-items-center rounded-control bg-surface-muted text-ink-muted sm:grid"
      >
        {icon}
      </span>
      <div className="min-w-0">
        <span className="block text-label font-semibold uppercase tracking-wide text-ink-muted">{nhan}</span>
        <span className={`mt-0.5 block font-medium ${gia_tri ? "text-ink" : "text-ink-faint"}`}>
          {gia_tri || "—"}
        </span>
      </div>
    </div>
  );
}

export function TheKhach({ dau, loaiKham }: { dau: DauPhieu; loaiKham?: string | null }) {
  const hc = dau.hanh_chinh;
  const ten = String(hc["patient.name"] ?? "");
  const gioi = (hc["patient.gender"] as string | null) ?? null;
  const namSinh = typeof hc["patient.birth_year"] === "number" ? hc["patient.birth_year"] : null;
  const ngayKham = (hc["encounter.date"] as string | null) ?? null;
  const namKham = ngayKham ? Number(ngayKham.slice(0, 4)) : new Date().getFullYear();
  const tuoi = namSinh ? namKham - namSinh : null;
  const tk = dau.the_khach;
  const loai = tk?.loai_kham || loaiKham || null;
  const nam = gioi === "Nam";
  const icon = "size-4";

  return (
    <section aria-label="Thông tin khách" className="rounded-card border border-hairline bg-surface p-4 sm:p-5">
      <div className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-4 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
        <div
          aria-hidden
          className={`grid size-11 place-items-center rounded-full text-emph font-semibold tracking-wide ring-1 ring-inset sm:size-14 sm:text-title ${
            nam ? "bg-info-bg text-info ring-info-ring" : "bg-brand-50 text-brand-700 ring-brand-100"
          }`}
        >
          {chuDau(ten)}
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-title font-semibold uppercase text-ink sm:text-hero">{ten || "—"}</h2>
            {loai ? (
              <span className="inline-flex items-center rounded-chip bg-brand-50 px-2 py-0.5 text-meta font-medium text-brand-700">
                {loai}
              </span>
            ) : null}
            <SoLuot booking={tk?.so_booking} checkin={tk?.so_tiep_don} />
          </div>
          <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-emph text-ink">
            {gioi ? <b className="font-semibold">{gioi}</b> : null}
            {gioi && tuoi !== null ? <span className="text-ink-faint">•</span> : null}
            {tuoi !== null ? <b className="font-semibold">{tuoi} tuổi</b> : null}
            {namSinh ? <span className="text-ink-muted">({namSinh})</span> : null}
          </p>
          <div className="mt-2.5 flex flex-wrap gap-1.5 sm:gap-2">
            <Vien icon={<IdCard className={icon} />}>
              <span className="text-ink-muted">Mã khách</span>
              <b className="font-semibold">{hc["patient.code"] ?? "—"}</b>
            </Vien>
            {sdtDoc(hc["patient.phone"]) ? (
              <Vien icon={<Phone className={icon} />}>
                <b className="font-semibold tabular-nums">{sdtDoc(hc["patient.phone"])}</b>
              </Vien>
            ) : null}
            {ngayVn(ngayKham) ? (
              <Vien icon={<CalendarDays className={icon} />}>
                <span className="text-ink-muted">Khám</span>
                <b className="font-semibold tabular-nums">{ngayVn(ngayKham)}</b>
              </Vien>
            ) : null}
          </div>
        </div>
        <div className="col-span-2 flex items-baseline gap-2 rounded-control bg-surface-muted px-3 py-2 sm:col-span-1 sm:flex-col sm:items-end sm:gap-0.5 sm:text-right">
          <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">Cơ sở</span>
          <b className="font-semibold text-ink">{tk?.co_so || String(hc["patient.location"] ?? "—")}</b>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-1.5 border-t border-hairline pt-4 sm:gap-2 xl:grid-cols-4">
        <OThongTin icon={<MapPin className={icon} />} nhan="Địa chỉ" gia_tri={(hc["patient.address"] as string | null) ?? null} />
        <OThongTin icon={<UserRound className={icon} />} nhan="Bác sĩ" gia_tri={tk?.bac_si ?? null} />
        <OThongTin icon={<Megaphone className={icon} />} nhan="Kênh đặt" gia_tri={tk?.kenh_dat ?? null} />
        <OThongTin
          icon={<Users className={icon} />}
          nhan="Người giới thiệu"
          gia_tri={(hc["patient.referrer"] as string | null) ?? null}
        />
      </div>
    </section>
  );
}

export function TheSinhHieu({ dau }: { dau: DauPhieu }) {
  const o = dau.the_sinh_hieu ?? [];
  const meta = dau.sinh_hieu_luc
    ? `Đo lúc ${gioDo(dau.sinh_hieu_luc)}${dau.sinh_hieu_nguon ? ` (${dau.sinh_hieu_nguon})` : ""}${dau.sinh_hieu_nguoi ? ` · ${dau.sinh_hieu_nguoi}` : ""} · chỉ xem (sửa ở Đo sinh hiệu)`
    : "Chưa đo sinh hiệu · sửa ở Đo sinh hiệu";
  return (
    <section aria-label="Sinh hiệu" className="rounded-card border border-hairline bg-surface px-4 py-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">Sinh hiệu</span>
        <span className="text-meta text-ink-muted">{meta}</span>
      </div>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 xl:grid-cols-7">
        {o.map((x) => (
          <div key={x.khoa} className="rounded-control bg-surface-muted p-2">
            <span className="text-meta text-ink-muted">{x.nhan}</span>
            <b className={`block text-emph font-semibold tabular-nums ${x.gia_tri ? "text-ink" : "text-ink-faint"}`}>
              {x.gia_tri ?? "—"}
            </b>
          </div>
        ))}
      </div>
    </section>
  );
}
