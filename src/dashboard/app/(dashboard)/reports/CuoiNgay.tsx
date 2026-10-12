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
// chủ tính khoản thu theo ca; các khoản tồn được ghi rõ phạm vi riêng.

import { useCallback, useEffect, useRef, useState } from "react";

import Button from "@/components/ui/Button";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";

import { INPUT } from "../form-ui";
import TomTatCuoiNgay from "./TomTatCuoiNgay";
import { todayVn } from "@/lib/roster";
import { congNgay, nhanKhoang, type Khoang } from "@/lib/thanh-ngay";

import type { ThuocTheoKhachData } from "./ThuocTheoKhach";

interface OTien {
  thu: number;
  huy: number;
  hoan: number;
  thuc_thu: number;
}

interface BaoCao {
  tai_chinh?: import("./TomTatCuoiNgay").TaiChinh;
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

export default function CuoiNgay({ coSo = [], dayDu = false, access, ngay }: { ngay?: string; coSo?: CoSo[]; dayDu?: boolean; access?: import("./access").ReportAccess }) {
  const [homNay] = useState(todayVn);
  const [khoang, setKhoang] = useState<Khoang>({ tu: ngay ?? homNay, den: ngay ?? homNay });
  const [bc, setBc] = useState<BaoCao | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);
  const lanTai = useRef(0);
  const [chuoiDaTai, setChuoiDaTai] = useState<string | null>(null);
  // Thuốc và dịch vụ thu RIÊNG HẲN (Tuyền 01/10/2026): mỗi quầy một ngăn kéo —
  // chọn "Dịch vụ" / "Thuốc" để mọi bảng chỉ cộng đúng loại tiền ấy.
  const [loai, setLoai] = useState<"" | "dich_vu" | "thuoc">("");
  // "" = Tất cả cơ sở (mặc định).
  const [coSoChon, setCoSoChon] = useState(() => access && !access.legacy && !access.quan_ly ? access.co_so_ids[0] ?? "" : coSo.find(o => o.name === "Hào Nam")?.id ?? "");
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
    const lan = ++lanTai.current;
    setDangTai(true);
    setLoi(null);
    setBc(null);
    try {
      const r = await fetch(`/api/reports/cuoi-ngay?${chuoi}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      });
      const d = (await r.json().catch(() => null)) as
        | (BaoCao & { message?: string; error?: string })
        | null;
      if (lan !== lanTai.current) return;
      if (!r.ok || !d || !d.tong) {
        setLoi(d?.message ?? d?.error ?? "Không đọc được báo cáo cuối ngày.");
      } else {
        setBc(d);
        setChuoiDaTai(chuoi);
      }
    } catch {
      if (lan === lanTai.current) setLoi("Không kết nối được báo cáo. Vui lòng thử tải lại.");
    } finally {
      if (lan === lanTai.current) setDangTai(false);
    }
  }, [chuoi]);

  useEffect(() => {
    const compteur = lanTai;
    const h = setTimeout(() => void tai(), 0);
    return () => { clearTimeout(h); ++compteur.current; };
  }, [tai]);

  const nhanLoai = bc?.loai === "thuoc" ? "Thuốc / vật tư" : bc?.loai === "dich_vu" ? "Dịch vụ" : "Tất cả";
  const pret = !!bc && !dangTai && !loi && chuoiDaTai === chuoi;
  const inBaoCao = () => {
    if (!bc || !pret) return;
    const noiDung = document.querySelector('[aria-label="Tóm tắt báo cáo cuối ngày"]');
    if (!noiDung) return;
    const frame = document.createElement("iframe");
    frame.style.position = "fixed"; frame.style.width = "0"; frame.style.height = "0";
    frame.style.border = "0"; document.body.appendChild(frame);
    const doc = frame.contentDocument;
    if (!doc || !frame.contentWindow) { frame.remove(); return; }
    const style = doc.createElement("style");
    style.textContent = "body{font:14px system-ui;padding:24px;color:#102a43}h1{font-size:20px}h3{background:#f5f8fb;padding:12px}dl{margin:0}dl>div{display:flex;justify-content:space-between;border-bottom:1px solid #e5e9f0;padding:12px}dd{margin:0}p{font-size:12px}";
    doc.head.appendChild(style);
    const titre = doc.createElement("h1"); titre.textContent = "Báo cáo cuối ngày";
    const meta = doc.createElement("p");
    meta.textContent = `${nhanKhoang({ tu: bc.tu, den: bc.den })} · ${bc.ten_co_so ?? "Tất cả cơ sở"} · ${bc.ca?.ten ?? "Cả ngày"} · ${nhanLoai}`;
    doc.body.append(titre, meta, noiDung.cloneNode(true));
    frame.contentWindow.focus();
    frame.contentWindow.print();
    setTimeout(() => frame.remove(), 60000);
  };
  const xuat = () => {
    if (!bc || !pret) return;
    const rows = [
      ["Báo cáo cuối ngày", nhanKhoang({ tu: bc.tu, den: bc.den })],
      ["Cơ sở", bc.ten_co_so ?? "Tất cả cơ sở"],
      ["Ca", bc.ca ? `${bc.ca.ten} ${bc.ca.tu}–${bc.ca.den}` : "Cả ngày"],
      ["Loại", nhanLoai],
      ["Mục", "Giá trị"],
      ["Tổng thu", bc.tong.thuc_thu],
      ["Dịch vụ", bc.theo_loai.find(o => o.ma === "dich_vu")?.thuc_thu ?? ""],
      ["Thuốc / vật tư", bc.theo_loai.find(o => o.ma === "thuoc")?.thuc_thu ?? ""],
      ...bc.theo_hinh_thuc.map(o => [o.ten, o.thuc_thu]),
      ...(dayDu && bc.tai_chinh ? [
        ["Doanh thu", bc.tai_chinh.doanh_thu],
        ["Hoàn tiền mặt", bc.tai_chinh.hoan_tien_mat],
        ["Hoàn chuyển khoản", bc.tai_chinh.hoan_chuyen_khoan],
        ["Nợ chưa thu trong kỳ", bc.tai_chinh.no_chua_thu ?? "Chưa có dữ liệu"],
        ["Giảm giá", bc.tai_chinh.giam_gia ?? "Chưa có dữ liệu"],
        ["Doanh thu thuần", bc.tai_chinh.doanh_thu_thuan],
      ] : []),
      ["Phiếu thu", bc.tong.so_phieu_thu],
    ];
    const csv = "\uFEFF" + rows.map(row => row.map(v => {
      const s = String(v);
      return '"' + (typeof v === "string" && (/^\s*[=+@-]/.test(s) || /^[\t\r\n]/.test(s)) ? "'" + s : s).replaceAll('"', '""') + '"';
    }).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url; a.download = `bao-cao-cuoi-ngay-${bc.tu}-${bc.den}.csv`;
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <section className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <ChonCoSoO coSo={coSo} dangChon={coSoChon} onChon={setCoSoChon} />
      </div>
      <div className="print:hidden">
      <div className="flex flex-wrap items-end gap-3 py-3">
        <label className="w-full space-y-1 text-meta text-ink-muted sm:w-auto">
          Chọn nhanh
          <select className={INPUT} defaultValue="" onChange={(e) => {
            const n = Number(e.target.value);
            if (e.target.value === "") return;
            setKhoang(n === 1 ? { tu: congNgay(homNay, -1), den: congNgay(homNay, -1) }
              : { tu: congNgay(homNay, -n), den: homNay });
            e.target.value = "";
          }}>
            <option value="">Chọn khoảng ngày</option>
            <option value="0">Hôm nay</option>
            <option value="1">Hôm qua</option>
            <option value="6">7 ngày gần nhất</option>
            <option value="29">30 ngày gần nhất</option>
          </select>
        </label>
        <div className="grid w-full grid-cols-2 gap-3 sm:w-auto">
          <label className="space-y-1 text-meta text-ink-muted">
            Từ ngày
            <input type="date" max={homNay} className={INPUT} value={khoang.tu}
              onChange={(e) => { if (e.target.value) setKhoang({ ...khoang, tu: e.target.value }); }} />
          </label>
          <label className="space-y-1 text-meta text-ink-muted">
            Đến ngày
            <input type="date" max={homNay} className={INPUT} value={khoang.den}
              onChange={(e) => { if (e.target.value) setKhoang({ ...khoang, den: e.target.value }); }} />
          </label>
        </div>
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
      </div>
      </div>
      <div className="flex flex-wrap gap-2 print:hidden">
        <Button type="button" size="lg" onClick={inBaoCao} disabled={!pret}>In</Button>
        <Button type="button" size="lg" onClick={xuat} disabled={!pret}>Xuất Excel</Button>
      </div>



      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}

      <TomTatCuoiNgay dayDu={dayDu} data={dangTai || loi || chuoiDaTai !== chuoi ? null : bc} dangTai={dangTai || (!loi && chuoiDaTai !== chuoi)} />


    </section>
  );
}
