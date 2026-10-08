// Bảng "Báo cáo cuối ngày về hàng hóa" — bố cục y khuôn KiotViet mà quầy thuốc
// gửi (EndOfDayProduct, 08/10/2026): Mã hàng · Tên hàng · SL bán · Doanh thu ·
// SL trả · Giá trị trả · Doanh thu thuần; dòng đầu "SL mặt hàng". Số do máy chủ
// gom (`gom_hang_hoa`); bảng chỉ vẽ.

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

const TH = "px-3 py-3 font-semibold";
const SO = "px-3 py-3 text-right tabular-nums";

// Kiểu số của KiotViet: 6,800,000 (dấu phẩy ngăn nghìn).
const so = (n: number) => n.toLocaleString("en-US");

export default function BangHangHoa({ hh }: { hh: HangHoa }) {
  const t = hh.tong;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="bg-info-bg text-left text-ink">
            <th className={TH}>Mã hàng</th>
            <th className={TH}>Tên hàng</th>
            <th className={`${TH} text-right`}>SL Bán</th>
            <th className={`${TH} text-right`}>Doanh thu</th>
            <th className={`${TH} text-right`}>SL Trả</th>
            <th className={`${TH} text-right`}>GT trả</th>
            <th className={`${TH} text-right`}>Doanh thu thuần</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-line bg-warning-bg font-semibold text-ink">
            <td className="px-3 py-3 whitespace-nowrap" colSpan={2}>
              SL Mặt hàng: {t.so_mat_hang}
            </td>
            <td className={SO}>{so(t.sl_ban)}</td>
            <td className={SO}>{so(t.doanh_thu)}</td>
            <td className={SO}>{so(t.sl_tra)}</td>
            <td className={SO}>{so(t.gia_tri_tra)}</td>
            <td className={`${SO} text-info`}>{so(t.doanh_thu_thuan)}</td>
          </tr>
          {hh.dong.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-3 py-6 text-center text-ink-muted">
                Không có mặt hàng nào được bán.
              </td>
            </tr>
          ) : (
            hh.dong.map((m) => (
              <tr key={`${m.ma ?? ""}-${m.ten}`} className="border-b border-line text-ink break-inside-avoid">
                <td className="px-3 py-3 whitespace-nowrap font-semibold text-info">{m.ma ?? "—"}</td>
                <td className="px-3 py-3 min-w-44">
                  {m.ten}
                  {m.don_vi ? ` (${m.don_vi})` : ""}
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
  );
}
