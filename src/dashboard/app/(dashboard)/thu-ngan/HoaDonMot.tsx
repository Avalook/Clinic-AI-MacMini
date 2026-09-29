"use client";

// QUẦY THU — MỘT HOÁ ĐƠN CHO MỘT KHÁCH (27/09/2026, đợt 3 — bản mẫu
// `ban-mau-tam/quay-thu.html` Tuyền duyệt).
//
// Trước: hai khối rời — "Khách chọn dịch vụ" (chốt) rồi mới tới "Tiền dịch vụ"
// (thu) — hai lần bấm cho một việc, và giữa hai lần hoá đơn có thể đổi. Nay mỗi
// dịch vụ đúng MỘT dòng có ô tick; bấm [Thu] = MÁY CHỦ chốt lựa chọn + ghi sổ
// trong CÙNG một giao dịch (`chon` của POST /api/v1/payments).
//
// Hoá đơn (`quay_thu`) do máy chủ dựng (`quay_thu_service.dung_hoa_don_quay`).
// Tổng hiển thị = cộng giá các dòng đang tick — CHỈ để đối chiếu: máy chủ tự tính
// lại theo lựa chọn gửi lên, lệch là từ chối (BILL_CHANGED), không ghi số màn gửi.
// Đối tác tự thu nằm nhóm riêng, không cộng.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

export interface PhongChon {
  id: string;
  ten: string;
  dang_cho: number;
  vang_nhat?: boolean;
}

export interface DongQuay {
  id: string;
  loai: "kham" | "chi_dinh" | "phu_thu";
  ten: string | null;
  gia: number | null;
  van_de: string | null;
  chon: boolean;
  sua_duoc: boolean;
  trong_lua_chon: boolean;
  bat_buoc?: boolean;
  mang_sang?: boolean;
  doi_tac_lam?: boolean;
  doi_tac_da_thu?: boolean | null;
  phong_chon_duoc?: PhongChon[];
  phong_du_kien_id?: string | null;
  can_xep_phong?: boolean;
}

export interface QuayThu {
  tong: number;
  revision: string | null;
  thu_duoc: boolean;
  van_de: string[];
  chi_doi_tac_thu: boolean;
  phong_kham: DongQuay[];
  doi_tac: DongQuay[];
  so_sanh: {
    so_chi_dinh: number;
    so_lam: number;
    so_bo: number;
    tien_bo: number;
    dong: { id: string; ten: string | null; khach: "lam" | "khong" | "doi_tac"; tien: number | null }[];
    /** BÁC SĨ chỉ định (null = chưa có bác sĩ) — không bao giờ trợ lý. */
    bac_si: string | null;
    /** Người bấm chỉ định hộ, khi không phải chính bác sĩ ấy. */
    nguoi_bam?: string | null;
    lan: number | null;
    luc: string | null;
  };
  lua_chon: { revision: number; order_ids_seen: string[] };
}

export type PhuongThuc = "CASH" | "TRANSFER" | "QR";
const TEN_PT: Record<PhuongThuc, string> = { CASH: "Tiền mặt", TRANSFER: "Chuyển khoản", QR: "QR" };

export interface LenhThuMot {
  amount: number | undefined;
  billRevision: string | undefined;
  method: PhuongThuc;
  chon:
    | { order_ids_seen: string[]; selected_order_ids: string[]; expected_selection_revision: number }
    | undefined;
  khoa: string;
  tong: number;
}

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
}

export default function HoaDonMot({
  qt,
  dangThu,
  onThu,
  onDoiPhong,
}: {
  qt: QuayThu;
  dangThu: boolean;
  /** Cha gửi POST /api/payment (khoá gửi lại, báo kết quả, tải lại). */
  onThu: (p: LenhThuMot) => void;
  onDoiPhong: () => void;
}) {
  const macDinh = new Set(
    [...qt.phong_kham, ...qt.doi_tac].filter((d) => d.trong_lua_chon && d.chon).map((d) => d.id),
  );
  const [chon, setChon] = useState<Set<string>>(macDinh);
  const [pt, setPt] = useState<PhuongThuc>("CASH");
  const [loiPhong, setLoiPhong] = useState<string | null>(null);

  const dangChon = (d: DongQuay) => (d.trong_lua_chon ? chon.has(d.id) : d.chon);
  const doi = [...macDinh].some((id) => !chon.has(id)) || [...chon].some((id) => !macDinh.has(id));
  const tong = doi
    ? qt.phong_kham.filter(dangChon).reduce((s, d) => s + (d.gia ?? 0), 0)
    : qt.tong;
  const thieuGia = qt.phong_kham.some((d) => dangChon(d) && d.gia == null);
  const chiChot = tong === 0;
  const chanThu = thieuGia || (!doi && !qt.thu_duoc && !chiChot);

  const doiTick = (id: string) =>
    setChon((c) => {
      const m = new Set(c);
      if (m.has(id)) m.delete(id);
      else m.add(id);
      return m;
    });

  const datPhong = async (orderId: string, roomId: string) => {
    setLoiPhong(null);
    const r = await fetch("/api/luot-kham", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thao_tac: "phong-du-kien", id: orderId, du_lieu: { room_id: roomId || null } }),
    });
    if (!r.ok) {
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      setLoiPhong(d?.message ?? d?.error ?? "Không ghi được phòng.");
      return;
    }
    onDoiPhong();
  };

  const bam = () => {
    const seen = qt.lua_chon.order_ids_seen;
    const selected = seen.filter((id) => chon.has(id));
    onThu({
      amount: chiChot ? undefined : tong,
      billRevision: doi ? undefined : (qt.revision ?? undefined),
      method: pt,
      chon: seen.length
        ? { order_ids_seen: seen, selected_order_ids: selected, expected_selection_revision: qt.lua_chon.revision }
        : undefined,
      khoa: ["thu-mot", qt.revision, String(qt.lua_chon.revision), selected.join(","), pt, String(tong)].join("|"),
      tong,
    });
  };

  const ss = qt.so_sanh;

  return (
    <div className="space-y-3 px-4 py-3">
      <DanhSach tieuDe="Phòng khám thu" ds={qt.phong_kham} dangChon={dangChon} doiTick={doiTick} datPhong={datPhong} />
      {qt.doi_tac.length > 0 ? (
        <DanhSach
          tieuDe="Thu hộ đối tác · không cộng"
          ds={qt.doi_tac}
          dangChon={dangChon}
          doiTick={doiTick}
          datPhong={datPhong}
          doiTac
        />
      ) : null}
      {loiPhong ? (
        <p role="alert" className="text-meta text-danger">
          {loiPhong}
        </p>
      ) : null}

      {ss.so_chi_dinh > 0 ? (
        <details className="rounded-control border border-line">
          <summary className="cursor-pointer px-3 py-2 text-meta text-ink-soft">
            So với bác sĩ chỉ định — BS chỉ định {ss.so_chi_dinh} · khách làm {ss.so_lam}
            {ss.so_bo > 0 ? ` · bỏ ${ss.so_bo} (−${tien(ss.tien_bo)})` : ""}
          </summary>
          <table className="w-full text-meta">
            <thead className="text-ink-muted">
              <tr>
                <th className="px-3 py-1 text-left font-medium">Dịch vụ</th>
                <th className="px-3 py-1 text-left font-medium">Khách</th>
                <th className="px-3 py-1 text-right font-medium">Tiền</th>
              </tr>
            </thead>
            <tbody>
              {ss.dong.map((d) => (
                <tr key={d.id} className="border-t border-line">
                  <td className="px-3 py-1">{d.ten}</td>
                  <td className="px-3 py-1">
                    {d.khach === "lam" ? "làm" : d.khach === "doi_tac" ? "trả đối tác" : "không làm"}
                  </td>
                  <td className="px-3 py-1 text-right tabular-nums">{d.tien != null ? tien(d.tien) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {ss.bac_si || ss.nguoi_bam ? (
            <p className="px-3 py-1.5 text-meta text-ink-muted">
              {ss.bac_si ?? "Chưa có bác sĩ"}
              {ss.nguoi_bam ? ` · ${ss.nguoi_bam} bấm` : ""}
              {ss.lan ? ` · chỉ định lần ${ss.lan}` : ""}
              {ss.luc ? ` lúc ${gio(ss.luc)}` : ""}
            </p>
          ) : null}
        </details>
      ) : null}

      {qt.van_de.length > 0 && !doi ? (
        <ul className="space-y-0.5 text-meta text-warning">
          {qt.van_de.map((v) => (
            <li key={v}>{v}</li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <div role="radiogroup" aria-label="Hình thức thu" className="flex gap-1">
          {(Object.keys(TEN_PT) as PhuongThuc[]).map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={pt === k}
              onClick={() => setPt(k)}
              className={`h-8 rounded-control px-3 text-meta font-medium ${
                pt === k ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"
              }`}
            >
              {TEN_PT[k]}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-emph font-semibold tabular-nums text-ink">{tien(tong)}</span>
          <Button variant="primary" size="lg" disabled={dangThu || chanThu} onClick={bam}>
            {dangThu ? "Đang ghi…" : chiChot ? "Chốt dịch vụ" : "Thu"}
          </Button>
        </div>
      </div>
      {thieuGia ? <p className="text-meta text-danger">Có dịch vụ chưa có giá — chưa thu được.</p> : null}
    </div>
  );
}

function DanhSach({
  tieuDe,
  ds,
  dangChon,
  doiTick,
  datPhong,
  doiTac = false,
}: {
  tieuDe: string;
  ds: DongQuay[];
  dangChon: (d: DongQuay) => boolean;
  doiTick: (id: string) => void;
  datPhong: (orderId: string, roomId: string) => Promise<void>;
  doiTac?: boolean;
}) {
  if (ds.length === 0) return null;
  return (
    <section>
      <h4 className="mb-1 text-label font-semibold uppercase text-ink-muted">{tieuDe}</h4>
      <ul className="divide-y divide-line rounded-control border border-line">
        {ds.map((d) => {
          const co = dangChon(d);
          return (
            <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
              <label className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                <input
                  type="checkbox"
                  checked={co}
                  disabled={!d.sua_duoc}
                  onChange={() => doiTick(d.id)}
                  className="size-4 accent-brand-600"
                />
                <span className={`min-w-0 truncate text-body ${co ? "text-ink" : "text-ink-faint line-through"}`}>
                  {d.ten ?? "—"}
                </span>
                {!co ? <span className="text-meta text-ink-muted">khách không làm</span> : null}
                {d.bat_buoc ? <Chip tone="warning">Bắt buộc</Chip> : null}
                {d.mang_sang ? <Chip tone="neutral">Mang sang</Chip> : null}
                {doiTac ? (
                  <Chip tone={d.doi_tac_da_thu ? "success" : "neutral"}>
                    {d.doi_tac_da_thu ? "đã thu hộ cho đối tác" : "chưa thu hộ cho đối tác"}
                  </Chip>
                ) : null}
              </label>
              <span className={`tabular-nums text-body ${doiTac || !co ? "text-ink-muted" : "text-ink"}`}>
                {d.gia != null ? tien(d.gia) : "chưa có giá"}
              </span>
              {co && d.can_xep_phong && d.phong_chon_duoc?.length ? (
                <select
                  aria-label={`Phòng làm ${d.ten ?? ""}`}
                  value={d.phong_du_kien_id ?? ""}
                  onChange={(e) => void datPhong(d.id, e.target.value)}
                  className="w-full rounded-control border border-line bg-surface px-2 py-1 text-meta text-ink-soft"
                >
                  <option value="">{doiTac ? "Lấy mẫu: tự xếp phòng vắng nhất" : "Tự xếp phòng vắng nhất"}</option>
                  {d.phong_chon_duoc.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.ten} · {p.dang_cho} đang chờ{p.vang_nhat ? " — vắng nhất" : ""}
                    </option>
                  ))}
                </select>
              ) : null}
              {d.van_de && co ? <p className="w-full text-meta text-warning">{d.van_de}</p> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
