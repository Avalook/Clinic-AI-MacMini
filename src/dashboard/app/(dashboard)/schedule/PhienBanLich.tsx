"use client";

// Lịch sử thay đổi lịch trực — kiểu "lịch sử phiên bản" của Google Docs (Khối 3,
// Tuyền 06/10/2026).
//
// Chọn một phiên bản → thấy đúng bảng lịch lúc đó, ô khác bản ngay trước được tô
// màu: thêm người vào ca (xanh lá), đổi người "BS Thành → BS Hằng" (xanh dương),
// ca bị xoá (đỏ, gạch ngang tại chỗ cũ). Mọi phép tính (phiên bản nào, khác gì)
// do máy chủ làm — `GET /api/v1/roster/phien-ban`; ở đây chỉ trình bày.
//
// AI THẤY: máy chủ quyết (cửa `roster.manage` / `config.clinic.manage` — trưởng
// ca và quản lý). Trang chỉ bày khối này khi máy chủ trả dữ liệu, không hỏi vai.

import { useState } from "react";

import Chip from "../../../components/ui/Chip";
import OChon from "../../../components/ui/OChon";
import { fmtDate, fmtDateTime } from "../../../lib/datetime";
import { doctorName } from "../../../lib/doctor-name";
import {
  SHIFT_LABEL,
  dayShort,
  fmtDayMonth,
  nhanViTri,
  type Station,
} from "../../../lib/roster";
import WorkRosterTable, {
  type DongCaRow,
  type LoaiThayDoi,
  type RosterRow,
} from "../home/WorkRosterTable";

interface SoThayDoi {
  them: number;
  xoa: number;
  doi_nguoi: number;
}

interface MucPhienBan {
  ma: string;
  loai: "GOC" | "AP_DUNG_LAI" | "LEN_BAN" | "THAY_DOI";
  luc: string | null;
  boi_ten: string | null;
  so: SoThayDoi;
}

interface OPhienBan {
  id: string;
  work_date: string;
  shift: string;
  station: string;
  staff_id: string | null;
  staff_name: string | null;
  ten_chuan: string | null;
  vai: string;
  vai_ngan: string;
  thay_doi: LoaiThayDoi | null;
  truoc_ten: string | null;
}

export interface PhienBanTraVe {
  tuan: string | null;
  co_lich_su: boolean;
  da_ap_dung: boolean;
  lich_su_tu: string | null;
  phien_ban: MucPhienBan[];
  dang_xem:
    | (MucPhienBan & {
        moi_nhat: boolean;
        truoc_ma: string | null;
        dong: OPhienBan[];
        da_xoa: OPhienBan[];
      })
    | null;
}

const NHAN_LOAI: Record<MucPhienBan["loai"], string> = {
  GOC: "Lịch gốc (áp dụng tuần)",
  AP_DUNG_LAI: "Áp dụng lại",
  LEN_BAN: "Lịch lúc bắt đầu ghi lịch sử",
  THAY_DOI: "Sửa lịch",
};

function tomTat(so: SoThayDoi): string {
  const phan = [
    so.doi_nguoi ? `đổi người ${so.doi_nguoi}` : "",
    so.xoa ? `xoá ${so.xoa}` : "",
    so.them ? `thêm ${so.them}` : "",
  ].filter(Boolean);
  return phan.join(" · ");
}

function nhanMuc(p: MucPhienBan, moiNhat: boolean): string {
  const tt = p.loai === "THAY_DOI" ? tomTat(p.so) : NHAN_LOAI[p.loai];
  const ai = p.boi_ten ? doctorName(p.boi_ten) || p.boi_ten : "không rõ người sửa";
  return `${fmtDateTime(p.luc)} · ${tt || NHAN_LOAI[p.loai]} · ${ai}${moiNhat ? " (hiện tại)" : ""}`;
}

const tenHien = (o: OPhienBan) =>
  (o.staff_id && doctorName(o.ten_chuan)) || o.staff_name || "";

export default function PhienBanLich({
  banDau,
  stations,
  dates,
  dong = [],
}: {
  banDau: PhienBanTraVe;
  stations: readonly Station[];
  dates: string[];
  dong?: DongCaRow[];
}) {
  const [duLieu, setDuLieu] = useState<PhienBanTraVe>(banDau);
  const [dangTai, setDangTai] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const nhan = nhanViTri(stations);

  async function chon(ma: string) {
    if (!duLieu.tuan) return;
    setDangTai(true);
    setLoi(null);
    try {
      const q = new URLSearchParams({ phien_ban: duLieu.tuan, ban: ma });
      const res = await fetch(`/api/roster?${q}`, { cache: "no-store" });
      if (!res.ok) {
        setLoi(`Không đọc được phiên bản (lỗi ${res.status}).`);
        return;
      }
      setDuLieu((await res.json()) as PhienBanTraVe);
    } catch {
      setLoi("Mất kết nối — thử chọn lại.");
    } finally {
      setDangTai(false);
    }
  }

  if (!duLieu.co_lich_su || !duLieu.dang_xem) {
    return (
      <p className="rounded-control bg-surface-sunken px-3 py-2 text-body text-ink-muted">
        {duLieu.da_ap_dung
          ? "Tuần này chưa có lịch sử thay đổi."
          : "Tuần chưa áp dụng — lịch gốc được chốt khi bấm “Áp dụng tuần”, mọi lần sửa sau đó thành một phiên bản."}
        {duLieu.lich_su_tu
          ? ` Lịch sử chỉ ghi từ ngày ${fmtDate(duLieu.lich_su_tu)}; chưa có lịch sử trước ngày đó.`
          : ""}
      </p>
    );
  }

  const dx = duLieu.dang_xem;
  const cu = duLieu.phien_ban[duLieu.phien_ban.length - 1];
  const rows: RosterRow[] = [...dx.dong, ...dx.da_xoa].map((o) => ({
    work_date: o.work_date,
    station: o.station,
    staff_id: o.staff_id,
    staff_name: tenHien(o),
    shift: o.shift,
    vai: o.vai,
    vai_ngan: o.vai_ngan,
    thay_doi: o.thay_doi,
    truoc_ten: o.truoc_ten ? doctorName(o.truoc_ten) || o.truoc_ten : null,
  }));
  const khac = [...dx.dong.filter((o) => o.thay_doi), ...dx.da_xoa];

  return (
    <div className="space-y-3">
      <label className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
        <span className="text-meta text-ink-muted">Phiên bản</span>
        <OChon
          value={dx.ma}
          disabled={dangTai}
          onChange={(e) => void chon(e.target.value)}
          className="w-full sm:w-auto sm:min-w-96"
        >
          {duLieu.phien_ban.map((p, i) => (
            <option key={p.ma} value={p.ma}>
              {nhanMuc(p, i === 0)}
            </option>
          ))}
        </OChon>
        {dangTai ? <span className="text-meta text-ink-muted">Đang tải…</span> : null}
      </label>

      {cu?.loai === "LEN_BAN" && duLieu.lich_su_tu ? (
        <p className="text-meta text-ink-muted">
          Chưa có lịch sử trước ngày {fmtDate(duLieu.lich_su_tu)} — phiên bản cũ nhất là lịch
          của tuần lúc bắt đầu ghi.
        </p>
      ) : null}
      {loi ? (
        <p className="rounded-control bg-danger-bg px-3 py-2 text-body text-danger">{loi}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 text-meta text-ink-muted">
        <span>So với bản ngay trước:</span>
        <Chip tone="success">+ Thêm người vào ca</Chip>
        <Chip tone="info">Đổi người: cũ → mới</Chip>
        <Chip tone="danger">Ca bị xoá</Chip>
      </div>

      <WorkRosterTable stations={stations} dates={dates} rows={rows} dong={dong} />

      {dx.truoc_ma === null ? (
        <p className="text-meta text-ink-muted">
          Đây là phiên bản đầu tiên của tuần — không có bản trước để so.
        </p>
      ) : khac.length === 0 ? (
        <p className="text-meta text-ink-muted">Phiên bản này không đổi ô nào so với bản trước.</p>
      ) : (
        <ul className="space-y-1 text-body text-ink">
          {khac.map((o) => (
            <li key={`${o.id}-${o.thay_doi}`} className="flex flex-wrap items-center gap-2">
              <Chip
                tone={
                  o.thay_doi === "THEM" ? "success" : o.thay_doi === "XOA" ? "danger" : "info"
                }
              >
                {o.thay_doi === "THEM" ? "Thêm" : o.thay_doi === "XOA" ? "Xoá" : "Đổi người"}
              </Chip>
              <span className="text-ink-muted">
                {dayShort(o.work_date)} {fmtDayMonth(o.work_date)} ·{" "}
                {SHIFT_LABEL[o.shift as keyof typeof SHIFT_LABEL] ?? o.shift} ·{" "}
                {nhan[o.station] ?? o.station}
              </span>
              <span>
                {o.thay_doi === "DOI_NGUOI" && o.truoc_ten
                  ? `${doctorName(o.truoc_ten) || o.truoc_ten} → ${tenHien(o)}`
                  : tenHien(o)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
