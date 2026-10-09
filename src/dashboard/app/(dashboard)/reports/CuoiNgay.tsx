"use client";

// BÁO CÁO CUỐI NGÀY (29/09/2026) — tài chính kiểu KiotViet: Bán hàng / Thu chi.
//
// Mọi con số do máy chủ gom (`GET /api/v1/reports/cuoi-ngay` →
// `bao_cao_cuoi_ngay_service`), cùng sổ và cùng luật cộng trừ với tab Lịch sử
// của quầy thu. Màn chỉ VẼ: chọn khoảng ngày, In (window.print), Xuất Excel
// (CSV UTF-8 BOM do máy chủ dựng).
//
// Theo cơ sở (08/10/2026 — mở Hào Nam): ô chọn "Tất cả cơ sở / từng cơ sở".
// Tất cả → thêm bảng từng cơ sở + dòng Tổng; mọi số (kể cả Tổng) do máy chủ trả.
//
// Cuối ca (08/10/2026): xem MỘT ngày thì chọn được ca Sáng / Chiều / Tối — máy
// chủ cắt mọi số theo khung giờ ca. Khối "Thuốc theo khách": kê vs thực bán.

import { useCallback, useEffect, useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import ThanhNgay from "@/components/ui/ThanhNgay";
import { fmtDayTime } from "@/lib/datetime";
import { todayVn } from "@/lib/roster";
import { congNgay, nhanKhoang, type Khoang } from "@/lib/thanh-ngay";

import ThuocTheoKhach, { type ThuocTheoKhachData } from "./ThuocTheoKhach";

interface OTien {
  thu: number;
  huy: number;
  hoan: number;
  thuc_thu: number;
}

interface BaoCao {
  tu: string;
  den: string;
  /** Đang xem riêng một loại tiền (01/10/2026) — null = cả hai. */
  loai?: "dich_vu" | "thuoc" | null;
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
    nhan_hinh_thuc?: string;
    so_tien: number;
    nguoi: string | null;
    ly_do: string | null;
    cho: boolean;
  }[];
  khach: {
    so_luot_kham: number;
    so_luot_da_thu: number;
    so_khach_da_thu: number;
    /** V8: lượt bán lẻ (khách chỉ mua thuốc) — không tính vào lượt khám. */
    so_luot_ban_le?: number;
    so_luot_khong_chon_dich_vu_kham: number;
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
    /** Nhãn máy chủ dựng — có cả chia TM + CK (01/10/2026). */
    nhan_sang?: string;
    so_tien: number;
    nguoi: string | null;
    ly_do: string | null;
  }[];
  top_dich_vu: { ten: string; so_luong: number; doanh_thu: number }[];
  /** Tiền thừa của các lượt trong khoảng (06/10/2026): đã hoàn / giữ lại / còn
   *  treo (chưa hoàn, chưa giữ lại). Báo cáo quầy thuốc: null. */
  tien_thua?: {
    da_hoan: number;
    giu_lai: number;
    con_treo: number;
    so_luot_con_treo: number;
  } | null;
  /** Khách còn nợ (01/10/2026): khoản ghi nợ lúc check-out còn CHƯA THU — tính
   *  tới hiện tại, không theo khoảng ngày. */
  khach_con_no?: {
    so_khach: number;
    so_luot: number;
    so_tien: number;
    bi_cat?: boolean;
    ds?: {
      id: string;
      khach: string | null;
      ma_bn: string | null;
      so_tien: number;
      ly_do: string;
      nguoi_ghi: string | null;
      luc: string;
    }[];
  };
  theo_ngay: (OTien & { ngay: string; so_phieu: number })[];
  /** Ca đang xem (08/10/2026) — null = cả ngày. Khung giờ do máy chủ tính. */
  ca?: { ma: string; ten: string; tu: string; den: string } | null;
  /** Thuốc kê vs thực bán theo khách — báo cáo dịch vụ: null. */
  thuoc_theo_khach?: ThuocTheoKhachData | null;
  /** Cơ sở đang xem (08/10/2026) — null = tất cả. */
  co_so?: string | null;
  ten_co_so?: string | null;
  /** Chỉ có khi xem tất cả: từng cơ sở, tiền cộng lại = `tong`. */
  theo_co_so?: {
    location_id: string | null;
    ten: string;
    tong: OTien & { so_phieu_thu: number };
    khach: { so_luot_kham: number };
  }[];
}

const TEN_PT: Record<string, string> = { CASH: "Tiền mặt", TRANSFER: "Chuyển khoản", QR: "Chuyển khoản" };
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

function BangCoSo({ bc }: { bc: BaoCao }) {
  const t = bc.tong;
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
            <th className={TH}>Cơ sở</th>
            <th className={`${TH} text-right`}>Lượt khám</th>
            <th className={`${TH} text-right`}>Phiếu thu</th>
            <th className={`${TH} text-right`}>Thu gốc</th>
            <th className={`${TH} text-right`}>Huỷ phiếu</th>
            <th className={`${TH} text-right`}>Hoàn</th>
            <th className={`${TH} text-right`}>Thực thu</th>
          </tr>
        </thead>
        <tbody>
          {(bc.theo_co_so ?? []).map((o) => (
            <tr key={o.location_id ?? "chua-ro"} className="border-b border-surface-sunken">
              <td className={`${TD} whitespace-nowrap`}>{o.ten}</td>
              <td className={SO}>{o.khach.so_luot_kham}</td>
              <td className={SO}>{o.tong.so_phieu_thu}</td>
              <td className={SO}>{tien(o.tong.thu)}</td>
              <td className={SO}>{am(o.tong.huy)}</td>
              <td className={SO}>{am(o.tong.hoan)}</td>
              <td className={`${SO} font-semibold`}>{tien(o.tong.thuc_thu)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-line bg-surface-muted font-semibold">
            <td className={TD}>Tổng</td>
            <td className={SO}>{bc.khach.so_luot_kham}</td>
            <td className={SO}>{t.so_phieu_thu}</td>
            <td className={SO}>{tien(t.thu)}</td>
            <td className={SO}>{am(t.huy)}</td>
            <td className={SO}>{am(t.hoan)}</td>
            <td className={SO}>{tien(t.thuc_thu)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

export default function CuoiNgay({ coSo = [] }: { coSo?: CoSo[] }) {
  const [homNay] = useState(todayVn);
  const [khoang, setKhoang] = useState<Khoang>({ tu: homNay, den: homNay });
  const [bc, setBc] = useState<BaoCao | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);
  // Thuốc và dịch vụ thu RIÊNG HẲN (Tuyền 01/10/2026): mỗi quầy một ngăn kéo —
  // chọn "Dịch vụ" / "Thuốc" để mọi bảng chỉ cộng đúng loại tiền ấy.
  const [loai, setLoai] = useState<"" | "dich_vu" | "thuoc">("");
  // "" = Tất cả cơ sở (mặc định).
  const [coSoChon, setCoSoChon] = useState("");
  // "" = cả ngày. Chỉ gửi khi xem một ngày (máy chủ cũng bỏ ca nếu nhiều ngày).
  const [ca, setCa] = useState<"" | "SANG" | "CHIEU" | "TOI">("");
  const motNgay = khoang.tu === khoang.den;

  const chuoi = new URLSearchParams({
    tu: khoang.tu,
    den: khoang.den,
    ...(loai ? { loai } : {}),
    ...(coSoChon ? { co_so: coSoChon } : {}),
    ...(ca && motNgay ? { ca } : {}),
  }).toString();

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
        <div role="tablist" aria-label="Loại tiền" className="flex gap-1">
          {(
            [
              ["", "Tất cả"],
              ["dich_vu", "Dịch vụ"],
              ["thuoc", "Thuốc"],
            ] as const
          ).map(([ma, nhan]) => (
            <button
              key={ma}
              type="button"
              role="tab"
              aria-selected={loai === ma}
              onClick={() => setLoai(ma)}
              className={`min-h-10 whitespace-nowrap rounded-control px-3 text-sm font-medium ${
                loai === ma ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"
              }`}
            >
              {nhan}
            </button>
          ))}
        </div>
        {motNgay ? (
          <div role="tablist" aria-label="Ca" className="flex gap-1">
            {(
              [
                ["", "Cả ngày"],
                ["SANG", "Ca sáng"],
                ["CHIEU", "Ca chiều"],
                ["TOI", "Ca tối"],
              ] as const
            ).map(([ma, nhan]) => (
              <button
                key={ma}
                type="button"
                role="tab"
                aria-selected={ca === ma}
                onClick={() => setCa(ma)}
                className={`min-h-10 whitespace-nowrap rounded-control px-3 text-sm font-medium ${
                  ca === ma ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"
                }`}
              >
                {nhan}
              </button>
            ))}
          </div>
        ) : null}
        <ChonCoSoO coSo={coSo} dangChon={coSoChon} onChon={setCoSoChon} />
        <div className="flex gap-2">
          <Button type="button" size="sm" onClick={() => window.print()} disabled={!bc}>
            In
          </Button>
          <a href={`/api/reports/cuoi-ngay?xuat=csv&${chuoi}`} className={buttonClass("secondary", "sm")}>
            Xuất Excel (tổng hợp)
          </a>
        </div>
      </div>

      <p className="text-meta text-ink-muted">
        Báo cáo cuối ngày · {bc?.co_so ? `${bc.ten_co_so ?? "Không có cơ sở này"} · ` : ""}
        {bc ? nhanKhoang({ tu: bc.tu, den: bc.den }) : nhanKhoang(khoang)}
        {bc?.ca ? ` · ${bc.ca.ten} ${bc.ca.tu}–${bc.ca.den}` : ""} · giờ Việt Nam · chỉ đọc
        {bc?.ca ? " · tiền thừa và khách còn nợ vẫn tính cả ngày" : ""}
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
          {/* Hai ngăn kéo riêng: tiền dịch vụ và tiền thuốc không cộng lẫn khi đối soát. */}
          {!bc.loai ? (
            <StatRow>
              {bc.theo_loai.map((o) => (
                <StatCard key={o.ma} label={`Thực thu ${TEN_LOAI[o.ma]?.toLowerCase() ?? o.ten}`} value={tien(o.thuc_thu)} />
              ))}
            </StatRow>
          ) : null}
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
            {bc.khach_con_no ? (
              <StatCard
                label={`Khách còn nợ: ${bc.khach_con_no.so_khach}`}
                value={tien(bc.khach_con_no.so_tien)}
                tone={bc.khach_con_no.so_khach > 0 ? "warning" : "neutral"}
              />
            ) : null}
          </StatRow>
          {bc.tien_thua ? (
            <StatRow>
              <StatCard label="Tiền thừa đã hoàn" value={tien(bc.tien_thua.da_hoan)} />
              <StatCard label="Tiền thừa giữ lại" value={tien(bc.tien_thua.giu_lai)} />
              <StatCard
                label={`Tiền thừa còn treo: ${bc.tien_thua.so_luot_con_treo} lượt`}
                value={tien(bc.tien_thua.con_treo)}
                tone={bc.tien_thua.con_treo > 0 ? "warning" : "neutral"}
              />
            </StatRow>
          ) : null}
          {bc.khach.so_luot_ban_le ? (
            <p className="text-meta text-ink-muted">
              Lượt bán lẻ thuốc (khách chỉ mua thuốc): {bc.khach.so_luot_ban_le} — không tính vào
              lượt khám; tiền thuốc đã cộng ở trên.
            </p>
          ) : null}
          {t.hoan_cho ? (
            <p className="text-meta text-ink-muted">
              Hoàn còn chờ chuyển: {tien(t.hoan_cho)} — chưa trừ vào thực thu.
            </p>
          ) : null}

          {(bc.theo_co_so ?? []).length > 1 ? (
            <Khoi title="Theo cơ sở">
              <BangCoSo bc={bc} />
            </Khoi>
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

          <p className="text-meta text-ink-muted print:hidden">
            Bảng mặt hàng đã bán theo mẫu KiotViet:{" "}
            <a href="/reports?tab=hang-hoa" className="font-medium text-brand-700 underline">
              tab Hàng hoá
            </a>
            .
          </p>

          {bc.thuoc_theo_khach ? (
            <Khoi title="Thuốc theo khách — bác sĩ kê vs thực bán">
              <ThuocTheoKhach data={bc.thuoc_theo_khach} />
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
                          {o.loai === "huy" ? "Hoàn tác lần thu (huỷ phiếu)" : "Hoàn tiền"}
                          {o.cho ? <span className="ml-1 text-meta text-warning">chờ chuyển</span> : null}
                          <span className="block text-meta text-ink-muted">
                            {[TEN_LOAI[o.loai_tien ?? ""], o.nhan_hinh_thuc || TEN_PT[o.hinh_thuc ?? ""]]
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
                          {TEN_PT[o.tu ?? ""] ?? "Không rõ"} → {o.nhan_sang || (TEN_PT[o.sang] ?? o.sang)}
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

          {bc.khach_con_no ? (
            <Khoi
              title={`Khách còn nợ: ${bc.khach_con_no.so_khach} — ${tien(bc.khach_con_no.so_tien)}`}
            >
              {(bc.khach_con_no.ds ?? []).length === 0 ? (
                <p className="text-meta text-ink-muted">Không còn khoản ghi nợ nào chưa thu.</p>
              ) : (
                <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
                  <table className="w-full border-collapse text-body">
                    <thead>
                      <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
                        <th className={TH}>Ghi lúc</th>
                        <th className={TH}>Khách</th>
                        <th className={TH}>Lý do</th>
                        <th className={TH}>Người ghi</th>
                        <th className={`${TH} text-right`}>Số tiền</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(bc.khach_con_no.ds ?? []).map((o) => (
                        <tr key={o.id} className="border-b border-surface-sunken last:border-b-0">
                          <td className={`${TD} whitespace-nowrap`}>{fmtDayTime(o.luc)}</td>
                          <td className={TD}>
                            {o.khach ?? "—"}
                            {o.ma_bn ? <span className="text-ink-muted"> · {o.ma_bn}</span> : null}
                          </td>
                          <td className={TD}>{o.ly_do}</td>
                          <td className={TD}>{o.nguoi_ghi ?? "—"}</td>
                          <td className={SO}>{tien(o.so_tien)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {bc.khach_con_no.bi_cat ? (
                <p className="text-meta text-ink-muted">
                  Danh sách chỉ hiện các khoản mới nhất — tổng ở trên là đủ.
                </p>
              ) : null}
              <p className="text-meta text-ink-muted">
                Thu nợ ở quầy thu ngân như thu thường — lượt hết nợ thì tự rời danh sách này.
              </p>
            </Khoi>
          ) : null}

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
