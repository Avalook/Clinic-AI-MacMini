// "BÁO CÁO CUỐI NGÀY VỀ HÀNG HÓA" (08/10/2026) — bố cục y khuôn KiotViet mà quầy
// thuốc gửi (Mã hàng · Tên hàng · SL bán · Doanh thu · SL trả · Giá trị trả ·
// Doanh thu thuần; dòng đầu "SL mặt hàng"). Số do máy chủ gom (`gom_hang_hoa`).

import { buttonClass } from "@/components/ui/Button";

export interface HangHoa {
  tong: {
    so_mat_hang: number;
    sl_ban: number;
    doanh_thu: number;
    sl_tra: number;
    gia_tri_tra: number;
    doanh_thu_thuan: number;
  };
  dong: {
    ma: string | null;
    ten: string;
    don_vi: string | null;
    sl_ban: number;
    doanh_thu: number;
    sl_tra: number;
    gia_tri_tra: number;
    doanh_thu_thuan: number;
  }[];
}

const TH = "px-3 py-2 font-medium";
const SO = "px-3 py-2 text-right tabular-nums";

const so = (n: number) => n.toLocaleString("vi-VN");

export default function BangHangHoa({ hh, xuat }: { hh: HangHoa; xuat: string }) {
  const t = hh.tong;
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
        <table className="w-full border-collapse text-body">
          <thead>
            <tr className="border-b border-line bg-brand-50 text-left text-meta text-ink">
              <th className={TH}>Mã hàng</th>
              <th className={TH}>Tên hàng</th>
              <th className={`${TH} text-right`}>SL bán</th>
              <th className={`${TH} text-right`}>Doanh thu</th>
              <th className={`${TH} text-right`}>SL trả</th>
              <th className={`${TH} text-right`}>Giá trị trả</th>
              <th className={`${TH} text-right`}>Doanh thu thuần</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-line bg-warning-bg font-semibold text-ink">
              <td className="px-3 py-2" colSpan={2}>
                SL mặt hàng: {t.so_mat_hang}
              </td>
              <td className={SO}>{so(t.sl_ban)}</td>
              <td className={SO}>{so(t.doanh_thu)}</td>
              <td className={SO}>{so(t.sl_tra)}</td>
              <td className={SO}>{so(t.gia_tri_tra)}</td>
              <td className={`${SO} text-brand-700`}>{so(t.doanh_thu_thuan)}</td>
            </tr>
            {hh.dong.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-4 text-center text-ink-muted">
                  Chưa bán mặt hàng nào.
                </td>
              </tr>
            ) : (
              hh.dong.map((m) => (
                <tr key={`${m.ma ?? ""}-${m.ten}`} className="border-b border-surface-sunken text-ink last:border-b-0">
                  <td className="px-3 py-2 whitespace-nowrap text-brand-700">{m.ma ?? "—"}</td>
                  <td className="px-3 py-2 min-w-44">
                    {m.ten}
                    {m.don_vi ? <span className="text-ink-muted"> ({m.don_vi})</span> : null}
                  </td>
                  <td className={SO}>{so(m.sl_ban)}</td>
                  <td className={SO}>{so(m.doanh_thu)}</td>
                  <td className={SO}>{so(m.sl_tra)}</td>
                  <td className={SO}>{so(m.gia_tri_tra)}</td>
                  <td className={SO}>{so(m.doanh_thu_thuan)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <a href={xuat} className={buttonClass("secondary", "sm")}>
          Xuất Excel (mẫu KiotViet)
        </a>
        <span className="text-meta text-ink-muted">
          Tồn đầu / tồn cuối chưa có: quầy bán chưa trừ kho nên số tồn máy chưa đúng.
        </span>
      </div>
    </div>
  );
}
