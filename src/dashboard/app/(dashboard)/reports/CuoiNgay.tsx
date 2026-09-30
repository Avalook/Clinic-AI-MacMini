"use client";

// BÁO CÁO CUỐI NGÀY (29/09/2026) — tài chính kiểu KiotViet: Bán hàng / Thu chi.
//
// Mọi con số do máy chủ gom (`GET /api/v1/reports/cuoi-ngay` →
// `bao_cao_cuoi_ngay_service`), cùng sổ và cùng luật cộng trừ với tab Lịch sử
// của quầy thu. Màn chỉ VẼ: chọn khoảng ngày, In (window.print), Xuất Excel
// (CSV UTF-8 BOM do máy chủ dựng).

import { useCallback, useEffect, useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import ThanhNgay from "@/components/ui/ThanhNgay";
import { todayVn } from "@/lib/roster";
import { congNgay, nhanKhoang, type Khoang } from "@/lib/thanh-ngay";

interface OTien {
  thu: number;
  huy: number;
  hoan: number;
  thuc_thu: number;
}

interface BaoCao {
  tu: string;
  den: string;
  tong: OTien & {
    hoan_cho: number;
    so_phieu_thu: number;
    so_phieu_huy: number;
    so_phieu_hoan: number;
  };
  theo_hinh_thuc: (OTien & { ma: string; ten: string })[];
  theo_loai: (OTien & { ma: string; ten: string })[];
  theo_nguoi_thu: (OTien & { ten: string; so_phieu: number })[];
  hoan_huy: {
    loai: "hoan" | "huy";
    id: string;
    luc: string | null;
    khach: string | null;
    ma_bn: string | null;
    loai_tien: string | null;
    hinh_thuc: string | null;
    so_tien: number;
    nguoi: string | null;
    ly_do: string | null;
    cho: boolean;
  }[];
  khach: {
    so_luot_kham: number;
    so_luot_khong_chon_dich_vu_kham: number;
    so_luot_da_thu: number;
    so_khach_da_thu: number;
  };
  doi_tac: {
    tong: number;
    dong: {
      id: string;
      luc: string | null;
      khach: string | null;
      dich_vu: string | null;
      so_tien: number;
      hinh_thuc: string | null;
    }[];
  };
  /** V7: các lần đổi TM/CK/QR ghi trong khoảng — KHÔNG phải huỷ. */
  doi_hinh_thuc?: {
    id: string;
    luc: string | null;
    khach: string | null;
    ma_bn: string | null;
    loai_tien: string | null;
    tu: string | null;
    sang: string;
    so_tien: number;
    nguoi: string | null;
    ly_do: string | null;
  }[];
  top_dich_vu: { ten: string; so_luong: number; doanh_thu: number }[];
  theo_ngay: (OTien & { ngay: string; so_phieu: number })[];
}

const TEN_PT: Record<string, string> = { CASH: "Tiền mặt", TRANSFER: "Chuyển khoản", QR: "QR" };
const TEN_LOAI: Record<string, string> = { dich_vu: "Dịch vụ", thuoc: "Thuốc" };

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

function am(n: number): string {
  return n ? `−${tien(n)}` : tien(0);
}

function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

const TH = "px-3 py-2 font-medium";
const TD = "px-3 py-2 text-ink";
const SO = "px-3 py-2 text-right tabular-nums text-ink";

function BangTien({
  tieuDe,
  dong,
}: {
  tieuDe: string;
  dong: (OTien & { ten: string; so_phieu?: number })[];
}) {
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
            <th className={TH}>{tieuDe}</th>
            <th className={`${TH} text-right`}>Thu gốc</th>
            <th className={`${TH} text-right`}>Huỷ phiếu</th>
            <th className={`${TH} text-right`}>Hoàn</th>
            <th className={`${TH} text-right`}>Thực thu</th>
          </tr>
        </thead>
        <tbody>
          {dong.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-3 py-4 text-center text-ink-muted">
                Chưa có khoản thu.
              </td>
            </tr>
          ) : (
            dong.map((o) => (
              <tr key={o.ten} className="border-b border-surface-sunken last:border-b-0">
                <td className={TD}>
                  {o.ten}
                  {o.so_phieu != null ? (
                    <span className="ml-1.5 text-meta text-ink-muted">{o.so_phieu} phiếu</span>
                  ) : null}
                </td>
                <td className={SO}>{tien(o.thu)}</td>
                <td className={SO}>{am(o.huy)}</td>
                <td className={SO}>{am(o.hoan)}</td>
                <td className={`${SO} font-semibold`}>{tien(o.thuc_thu)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function Khoi({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2 break-inside-avoid">
      <h3 className="text-body font-semibold text-ink">{title}</h3>
      {children}
    </section>
  );
}

export default function CuoiNgay() {
  const [homNay] = useState(todayVn);
  const [khoang, setKhoang] = useState<Khoang>({ tu: homNay, den: homNay });
  const [bc, setBc] = useState<BaoCao | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);

  const chuoi = new URLSearchParams({ tu: khoang.tu, den: khoang.den }).toString();

  const tai = useCallback(async () => {
    setDangTai(true);
    setLoi(null);
    const r = await fetch(`/api/reports/cuoi-ngay?${chuoi}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | (BaoCao & { message?: string; error?: string })
      | null;
    if (!r.ok || !d || !d.tong) setLoi(d?.message ?? d?.error ?? "Không đọc được báo cáo cuối ngày.");
    else setBc(d);
    setDangTai(false);
  }, [chuoi]);

  useEffect(() => {
    const h = setTimeout(() => void tai(), 0);
    return () => clearTimeout(h);
  }, [tai]);

  const t = bc?.tong;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2 print:hidden">
        <ThanhNgay
          nhan="Khoảng ngày báo cáo"
          khoang={khoang}
          homNay={homNay}
          soNgaySau={0}
          dangTai={dangTai}
          // "Tất cả" → tối đa 92 ngày gần nhất (máy chủ cũng chặn ở 92).
          onChon={(k) => setKhoang(k ?? { tu: congNgay(homNay, -92), den: homNay })}
          className="min-w-0 flex-1"
        />
        <div className="flex gap-2">
          <Button type="button" size="sm" onClick={() => window.print()} disabled={!bc}>
            In
          </Button>
          <a href={`/api/reports/cuoi-ngay?xuat=csv&${chuoi}`} className={buttonClass("secondary", "sm")}>
            Xuất Excel
          </a>
        </div>
      </div>

      <p className="text-meta text-ink-muted">
        Báo cáo cuối ngày · {bc ? nhanKhoang({ tu: bc.tu, den: bc.den }) : nhanKhoang(khoang)} · giờ
        Việt Nam · chỉ đọc
      </p>

      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}

      {bc && t ? (
        <>
          <StatRow>
            <StatCard label="Thực thu" value={tien(t.thuc_thu)} tone="brand" />
            <StatCard label="Thu gốc" value={tien(t.thu)} />
            <StatCard label={`Huỷ phiếu (${t.so_phieu_huy})`} value={am(t.huy)} tone="warning" />
            <StatCard label={`Hoàn tiền (${t.so_phieu_hoan})`} value={am(t.hoan)} tone="warning" />
          </StatRow>
          <StatRow>
            <StatCard label="Lượt khám mới" value={bc.khach.so_luot_kham} />
            <StatCard
              label="Lượt chưa chọn DV khám"
              value={bc.khach.so_luot_khong_chon_dich_vu_kham}
              tone="warning"
            />
            <StatCard label="Lượt đã thu" value={bc.khach.so_luot_da_thu} />
            <StatCard label="Khách đã thu" value={bc.khach.so_khach_da_thu} />
            <StatCard label="Phiếu thu" value={t.so_phieu_thu} />
          </StatRow>
          {t.hoan_cho ? (
            <p className="text-meta text-ink-muted">
              Hoàn còn chờ chuyển: {tien(t.hoan_cho)} — chưa trừ vào thực thu.
            </p>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            <Khoi title="Theo hình thức">
              <BangTien tieuDe="Hình thức" dong={bc.theo_hinh_thuc} />
            </Khoi>
            <Khoi title="Dịch vụ · Thuốc / vật tư">
              <BangTien tieuDe="Loại" dong={bc.theo_loai} />
            </Khoi>
          </div>

          <Khoi title="Theo người thu">
            <BangTien tieuDe="Người thu" dong={bc.theo_nguoi_thu} />
          </Khoi>

          {bc.theo_ngay.length > 0 ? (
            <Khoi title="Theo ngày">
              <BangTien
                tieuDe="Ngày"
                dong={bc.theo_ngay.map((o) => ({ ...o, ten: o.ngay }))}
              />
            </Khoi>
          ) : null}

          <Khoi title="Top dịch vụ theo doanh thu">
            <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
              <table className="w-full border-collapse text-body">
                <thead>
                  <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
                    <th className={TH}>Dịch vụ</th>
                    <th className={`${TH} text-right`}>Số lượng</th>
                    <th className={`${TH} text-right`}>Doanh thu gộp</th>
                  </tr>
                </thead>
                <tbody>
                  {bc.top_dich_vu.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-3 py-4 text-center text-ink-muted">
                        Chưa có dịch vụ đã thu.
                      </td>
                    </tr>
                  ) : (
                    bc.top_dich_vu.map((o) => (
                      <tr key={o.ten} className="border-b border-surface-sunken last:border-b-0">
                        <td className={TD}>{o.ten}</td>
                        <td className={SO}>{o.so_luong.toLocaleString("vi-VN")}</td>
                        <td className={SO}>{tien(o.doanh_thu)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <p className="text-meta text-ink-muted">
              Doanh thu gộp của phiếu còn hiệu lực, chưa trừ hoàn từng dòng.
            </p>
          </Khoi>

          <Khoi title="Hoàn tiền & phiếu huỷ">
            <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
              <table className="w-full border-collapse text-body">
                <thead>
                  <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
                    <th className={TH}>Lúc</th>
                    <th className={TH}>Loại</th>
                    <th className={TH}>Khách</th>
                    <th className={TH}>Người</th>
                    <th className={TH}>Lý do</th>
                    <th className={`${TH} text-right`}>Số tiền</th>
                  </tr>
                </thead>
                <tbody>
                  {bc.hoan_huy.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-3 py-4 text-center text-ink-muted">
                        Không có hoàn / huỷ.
                      </td>
                    </tr>
                  ) : (
                    bc.hoan_huy.map((o) => (
                      <tr key={`${o.loai}-${o.id}`} className="border-b border-surface-sunken last:border-b-0">
                        <td className={`${TD} whitespace-nowrap`}>{gio(o.luc)}</td>
                        <td className={TD}>
                          {o.loai === "huy" ? "Huỷ phiếu" : "Hoàn"}
                          {o.cho ? <span className="ml-1 text-meta text-warning">chờ chuyển</span> : null}
                          <span className="block text-meta text-ink-muted">
                            {[TEN_LOAI[o.loai_tien ?? ""], TEN_PT[o.hinh_thuc ?? ""]]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </td>
                        <td className={TD}>
                          {o.khach ?? "—"}
                          {o.ma_bn ? <span className="block text-meta text-ink-muted">{o.ma_bn}</span> : null}
                        </td>
                        <td className={TD}>{o.nguoi ?? "—"}</td>
                        <td className={`${TD} min-w-40`}>{o.ly_do ?? "—"}</td>
                        <td className={SO}>{am(o.so_tien)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Khoi>

          <Khoi title="Đổi hình thức — không phải huỷ">
            {(bc.doi_hinh_thuc ?? []).length === 0 ? (
              <p className="text-meta text-ink-muted">Không có lần đổi hình thức nào.</p>
            ) : (
              <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
                <table className="w-full border-collapse text-body">
                  <thead>
                    <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
                      <th className={TH}>Lúc</th>
                      <th className={TH}>Khách</th>
                      <th className={TH}>Từ → sang</th>
                      <th className={TH}>Người đổi</th>
                      <th className={TH}>Lý do</th>
                      <th className={`${TH} text-right`}>Số tiền</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(bc.doi_hinh_thuc ?? []).map((o) => (
                      <tr key={o.id} className="border-b border-surface-sunken last:border-b-0">
                        <td className={`${TD} whitespace-nowrap`}>{gio(o.luc)}</td>
                        <td className={TD}>
                          {o.khach ?? "—"}
                          <span className="block text-meta text-ink-muted">
                            {[o.ma_bn, TEN_LOAI[o.loai_tien ?? ""]].filter(Boolean).join(" · ")}
                          </span>
                        </td>
                        <td className={TD}>
                          {TEN_PT[o.tu ?? ""] ?? "Không rõ"} → {TEN_PT[o.sang] ?? o.sang}
                        </td>
                        <td className={TD}>{o.nguoi ?? "—"}</td>
                        <td className={`${TD} min-w-40`}>{o.ly_do ?? "—"}</td>
                        <td className={SO}>{tien(o.so_tien)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="text-meta text-ink-muted">
              Bảng &quot;Theo hình thức&quot; đã tính theo hình thức sau khi đổi.
            </p>
          </Khoi>

          <Khoi title={`Đối tác thu hộ — tham khảo, không cộng (${tien(bc.doi_tac.tong)})`}>
            {bc.doi_tac.dong.length === 0 ? (
              <p className="text-meta text-ink-muted">Không có khoản khách trả thẳng đối tác.</p>
            ) : (
              <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
                <table className="w-full border-collapse text-body">
                  <thead>
                    <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
                      <th className={TH}>Lúc</th>
                      <th className={TH}>Dịch vụ</th>
                      <th className={TH}>Khách</th>
                      <th className={TH}>Hình thức</th>
                      <th className={`${TH} text-right`}>Số tiền</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bc.doi_tac.dong.map((o) => (
                      <tr key={o.id} className="border-b border-surface-sunken last:border-b-0">
                        <td className={`${TD} whitespace-nowrap`}>{gio(o.luc)}</td>
                        <td className={TD}>{o.dich_vu ?? "—"}</td>
                        <td className={TD}>{o.khach ?? "—"}</td>
                        <td className={TD}>{TEN_PT[o.hinh_thuc ?? ""] ?? "—"}</td>
                        <td className={`${SO} text-ink-muted`}>{tien(o.so_tien)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Khoi>
        </>
      ) : null}
    </section>
  );
}
