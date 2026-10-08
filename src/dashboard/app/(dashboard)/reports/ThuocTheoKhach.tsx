"use client";

// THUỐC THEO KHÁCH (08/10/2026) — bác sĩ KÊ vs quầy THỰC BÁN, một khách một dòng;
// bấm khách → khung phải hiện từng thuốc (kê · thực bán · chênh · đơn giá · tiền).
// Mọi con số do máy chủ tính (`bao_cao_thuoc_service`); màn chỉ vẽ.

import { useState } from "react";

import Chip from "@/components/ui/Chip";
import StatCard, { StatRow } from "@/components/ui/StatCard";

export interface DongThuoc {
  id: string;
  ten: string;
  ten_bac_si: string | null;
  nguon: string | null;
  don_vi: string | null;
  so_ke: number | null;
  so_ban: number;
  so_tra: number;
  thuc_ban: number;
  chenh: number | null;
  don_gia: number | null;
  thanh_tien: number;
  da_giao: number;
  trang_thai: "da_ban" | "khong_lay" | "chua_thu";
  lech: boolean;
}

export interface ThuocTheoKhachData {
  tong: { so_khach: number; so_khach_lech: number; so_dong_lech: number; tien: number };
  khach: {
    visit_id: string;
    khach: string | null;
    ma_bn: string | null;
    ban_le: boolean;
    bac_si: string | null;
    luc: string | null;
    nguoi_thu: string[];
    so_dong: number;
    so_lech: number;
    tien: number;
    dong: DongThuoc[];
  }[];
  tieu_hao: {
    ten: string;
    don_vi: string | null;
    so_ke: number;
    thuc_ban: number;
    so_tra: number;
    tien: number;
  }[];
}

const TRANG_THAI: Record<DongThuoc["trang_thai"], { nhan: string; tone: "success" | "neutral" | "warning" }> = {
  da_ban: { nhan: "Đã bán", tone: "success" },
  khong_lay: { nhan: "Khách không lấy", tone: "neutral" },
  chua_thu: { nhan: "Chưa thu", tone: "warning" },
};

const TH = "px-3 py-2 font-medium";
const TD = "px-3 py-2 text-ink";
const SO = "px-3 py-2 text-right tabular-nums text-ink";

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

function sl(n: number | null): string {
  return n == null ? "—" : n.toLocaleString("vi-VN");
}

function chenh(n: number | null): string {
  if (n == null) return "—";
  if (n > 0) return `+${sl(n)}`;
  if (n < 0) return `−${sl(-n)}`;
  return "0";
}

function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
}

export default function ThuocTheoKhach({ data }: { data: ThuocTheoKhachData }) {
  const [chon, setChon] = useState<string | null>(null);
  const dangXem = data.khach.find((k) => k.visit_id === chon) ?? data.khach[0] ?? null;

  return (
    <div className="space-y-3">
      <StatRow>
        <StatCard label="Khách có thuốc" value={data.tong.so_khach} />
        <StatCard
          label={`Khách lệch kê / bán (${data.tong.so_dong_lech} dòng)`}
          value={data.tong.so_khach_lech}
          tone={data.tong.so_khach_lech > 0 ? "warning" : "neutral"}
        />
        <StatCard label="Tiền thuốc thực bán" value={tien(data.tong.tien)} tone="brand" />
      </StatRow>

      {data.khach.length === 0 ? (
        <p className="text-meta text-ink-muted">Không có khách nào có đơn thuốc trong khoảng này.</p>
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(240px,0.8fr)_minmax(0,1.6fr)]">
          <ul className="divide-y divide-surface-sunken overflow-hidden rounded-card border border-line bg-surface shadow-card print:hidden">
            {data.khach.map((k) => {
              const dang = dangXem?.visit_id === k.visit_id;
              return (
                <li key={k.visit_id}>
                  <button
                    type="button"
                    onClick={() => setChon(k.visit_id)}
                    aria-pressed={dang}
                    className={`flex min-h-11 w-full items-center gap-2 px-3 py-2 text-left ${
                      dang ? "bg-brand-50" : "hover:bg-surface-muted"
                    }`}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-body font-medium text-ink">{k.khach ?? "—"}</span>
                      <span className="block truncate text-meta text-ink-muted">
                        {[k.ma_bn, gio(k.luc), `${k.so_dong} thuốc`].filter(Boolean).join(" · ")}
                      </span>
                    </span>
                    {k.so_lech ? <Chip tone="warning">Lệch {k.so_lech}</Chip> : null}
                    <span className="shrink-0 text-body tabular-nums text-ink">{tien(k.tien)}</span>
                  </button>
                </li>
              );
            })}
          </ul>

          {dangXem ? (
            <section className="space-y-2 rounded-card border border-line bg-surface p-3 shadow-card">
              <div>
                <h4 className="text-body font-semibold text-ink">
                  {dangXem.khach ?? "—"}
                  {dangXem.ma_bn ? <span className="ml-1.5 text-meta text-ink-muted">{dangXem.ma_bn}</span> : null}
                </h4>
                <p className="text-meta text-ink-muted">
                  {[
                    dangXem.ban_le ? "Bán lẻ" : dangXem.bac_si ? `Bác sĩ kê: ${dangXem.bac_si}` : null,
                    dangXem.nguoi_thu.length ? `Thu: ${dangXem.nguoi_thu.join(", ")}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-body">
                  <thead>
                    <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
                      <th className={TH}>Thuốc</th>
                      <th className={`${TH} text-right`}>Kê</th>
                      <th className={`${TH} text-right`}>Thực bán</th>
                      <th className={`${TH} text-right`}>Chênh</th>
                      <th className={`${TH} text-right`}>Đơn giá</th>
                      <th className={`${TH} text-right`}>Thành tiền</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dangXem.dong.map((d) => (
                      <tr key={d.id} className="border-b border-surface-sunken last:border-b-0">
                        <td className={`${TD} min-w-44`}>
                          {d.ten}
                          {d.don_vi ? <span className="ml-1 text-meta text-ink-muted">({d.don_vi})</span> : null}
                          <span className="mt-0.5 flex flex-wrap gap-1">
                            <Chip tone={TRANG_THAI[d.trang_thai].tone}>{TRANG_THAI[d.trang_thai].nhan}</Chip>
                            {d.nguon === "QUAY" ? <Chip tone="info">Quầy thêm</Chip> : null}
                            {d.so_tra ? <Chip tone="warning">Khách trả {sl(d.so_tra)}</Chip> : null}
                          </span>
                          {d.ten_bac_si ? (
                            <span className="block text-meta text-ink-muted">Bác sĩ ghi: {d.ten_bac_si}</span>
                          ) : null}
                        </td>
                        <td className={SO}>{sl(d.so_ke)}</td>
                        <td className={SO}>{sl(d.thuc_ban)}</td>
                        <td className={`${SO} ${d.chenh ? "font-semibold text-warning" : ""}`}>{chenh(d.chenh)}</td>
                        <td className={SO}>{d.don_gia != null ? tien(d.don_gia) : "—"}</td>
                        <td className={`${SO} font-semibold`}>{tien(d.thanh_tien)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-line font-semibold">
                      <td className={TD} colSpan={5}>
                        Tổng
                      </td>
                      <td className={SO}>{tien(dangXem.tien)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              <p className="text-meta text-ink-muted">
                Kê = số bác sĩ ghi (quầy sửa số thì vẫn giữ số gốc) · Thực bán = đã thu trừ khách trả · Chênh = thực
                bán − kê.
              </p>
            </section>
          ) : null}
        </div>
      )}

      {data.tieu_hao.length > 0 ? (
        <div className="space-y-2">
          <h4 className="text-body font-semibold text-ink">Tiêu hao thuốc — đã bán ra</h4>
          <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
            <table className="w-full border-collapse text-body">
              <thead>
                <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
                  <th className={TH}>Thuốc</th>
                  <th className={`${TH} text-right`}>Kê</th>
                  <th className={`${TH} text-right`}>Thực bán</th>
                  <th className={`${TH} text-right`}>Khách trả</th>
                  <th className={`${TH} text-right`}>Tiền</th>
                </tr>
              </thead>
              <tbody>
                {data.tieu_hao.map((t) => (
                  <tr key={t.ten} className="border-b border-surface-sunken last:border-b-0">
                    <td className={TD}>
                      {t.ten}
                      {t.don_vi ? <span className="ml-1 text-meta text-ink-muted">({t.don_vi})</span> : null}
                    </td>
                    <td className={SO}>{sl(t.so_ke)}</td>
                    <td className={`${SO} font-semibold`}>{sl(t.thuc_ban)}</td>
                    <td className={SO}>{t.so_tra ? sl(t.so_tra) : "—"}</td>
                    <td className={SO}>{tien(t.tien)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
