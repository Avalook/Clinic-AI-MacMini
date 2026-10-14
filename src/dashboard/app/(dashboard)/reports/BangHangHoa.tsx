// Bảng "Báo cáo cuối ngày về hàng hóa" — bố cục y khuôn KiotViet mà quầy thuốc
// gửi (EndOfDayProduct, 08/10/2026): Mã hàng · Tên hàng · SL bán · Doanh thu ·
// SL trả · Giá trị trả · Doanh thu thuần; dòng đầu "SL mặt hàng". Số do máy chủ
// gom (`gom_hang_hoa`); bảng chỉ vẽ.
//
// G6 (14/10/2026): bảng THUỐC có khối `kho` (máy chủ thêm khi `co_ton`) → thêm cột
// tồn kho ĐÚNG THỨ TỰ khách chốt: Mã hàng · Tên hàng · Tồn đầu · Nhập trong ca ·
// SL bán · SL trả · Tồn cuối ca · Kiểm kê · Lệch · Đã thu chưa giao · Doanh thu ·
// GT trả · Doanh thu thuần. Trong khuôn này "SL bán" là số GIAO tận tay và "SL trả"
// là số thuốc trả về kệ (theo sổ kho); Doanh thu vẫn theo tiền thu — cột "Đã thu
// chưa giao" giải thích chỗ khác nhau. Mỗi (thuốc, đơn vị lô) một dòng nhỏ.

/** Một (thuốc, đơn vị lô) của khối tồn kho — số lượng theo SỔ KHO, máy chủ tính. */
export interface TonDonVi {
  don_vi: string;
  ton_dau: number;
  nhap: number;
  sl_ban: number;
  sl_tra: number;
  khac: number;
  ton_cuoi: number;
  /** null = chưa kiểm cuối ca (không suy ra). */
  kiem_ke: number | null;
  lech: number | null;
  da_thu_chua_giao: number;
}

export interface HangHoa {
  /** Máy chủ bật khi dòng thuốc có khối `kho` → vẽ khuôn có cột tồn. */
  co_ton?: boolean;
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
    kho?: { theo_don_vi: TonDonVi[]; giao_chua_gan_lo: number | null };
    sl_ban: number;
    doanh_thu: number;
    sl_tra: number;
    gia_tri_tra: number;
    doanh_thu_thuan: number;
  }[];
}

const TH = "px-3 py-3 font-semibold whitespace-nowrap";
const SO = "px-3 py-3 text-right tabular-nums";

// Kiểu số của KiotViet: 6,800,000 (dấu phẩy ngăn nghìn).
const so = (n: number) => n.toLocaleString("en-US");

const sk = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** Một ô nhiều đơn vị: mỗi đơn vị một dòng nhỏ, cùng thứ tự ở mọi cột. */
function OTon({ ds, lay, dau }: { ds: TonDonVi[]; lay: (t: TonDonVi) => number | null; dau?: boolean }) {
  if (ds.length === 0) return <>—</>;
  return (
    <>
      {ds.map((t) => {
        const v = lay(t);
        return (
          <span key={t.don_vi} className="block whitespace-nowrap">
            {v === null ? "—" : `${dau && v > 0 ? "+" : ""}${sk(v)}`}
            {ds.length > 1 ? <span className="text-meta text-ink-soft"> {t.don_vi}</span> : null}
          </span>
        );
      })}
    </>
  );
}

function BangCoTon({ hh }: { hh: HangHoa }) {
  const t = hh.tong;
  const kho = (m: HangHoa["dong"][number]) => m.kho?.theo_don_vi ?? [];
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="bg-info-bg text-left text-ink">
            <th className={`${TH} hidden sm:table-cell`}>Mã hàng</th>
            <th className={TH}>Tên hàng</th>
            <th className={`${TH} text-right`}>Tồn đầu</th>
            <th className={`${TH} text-right`}>Nhập trong ca</th>
            <th className={`${TH} text-right`}>SL bán</th>
            <th className={`${TH} text-right`}>SL trả</th>
            <th className={`${TH} text-right`}>Tồn cuối ca</th>
            <th className={`${TH} text-right`}>Kiểm kê</th>
            <th className={`${TH} text-right`}>Lệch</th>
            <th className={`${TH} text-right`}>Đã thu chưa giao</th>
            <th className={`${TH} text-right`}>Doanh thu</th>
            <th className={`${TH} text-right`}>GT trả</th>
            <th className={`${TH} text-right`}>Doanh thu thuần</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-line bg-warning-bg font-semibold text-ink">
            <td className="hidden px-3 py-3 whitespace-nowrap sm:table-cell">SL Mặt hàng: {t.so_mat_hang}</td>
            <td className="px-3 py-3 whitespace-nowrap">
              <span className="sm:hidden">SL Mặt hàng: {t.so_mat_hang}</span>
            </td>
            <td className={SO} colSpan={7} />
            <td className={SO} />
            <td className={SO}>{so(t.doanh_thu)}</td>
            <td className={SO}>{so(t.gia_tri_tra)}</td>
            <td className={`${SO} text-info`}>{so(t.doanh_thu_thuan)}</td>
          </tr>
          {hh.dong.length === 0 ? (
            <tr>
              <td colSpan={13} className="px-3 py-6 text-center text-ink-muted">
                Không có mặt hàng nào.
              </td>
            </tr>
          ) : (
            hh.dong.map((m) => {
              const ds = kho(m);
              return (
                <tr key={`${m.ma ?? ""}-${m.ten}`} className="border-b border-line align-top text-ink break-inside-avoid">
                  <td className="hidden px-3 py-3 whitespace-nowrap text-meta font-semibold text-info sm:table-cell">
                    {m.ma ?? "—"}
                  </td>
                  <td className="px-3 py-3 min-w-44">
                    {m.ten}
                    {m.don_vi ? ` (${m.don_vi})` : ""}
                    {m.ma ? <span className="block text-meta text-info sm:hidden">{m.ma}</span> : null}
                    {m.kho?.giao_chua_gan_lo ? (
                      <span className="block text-meta text-ink-muted">
                        Đã giao chưa gắn lô: {sk(m.kho.giao_chua_gan_lo)} — cộng mọi lượt, mọi ngày, cho tới khi
                        gắn lô ở Kho thuốc; không phải lệch đếm
                      </span>
                    ) : null}
                  </td>
                  <td className={SO}><OTon ds={ds} lay={(x) => x.ton_dau} /></td>
                  <td className={SO}><OTon ds={ds} lay={(x) => x.nhap} /></td>
                  <td className={SO}>
                    {ds.length ? <OTon ds={ds} lay={(x) => x.sl_ban} /> : so(m.sl_ban)}
                  </td>
                  <td className={SO}>
                    {ds.length ? <OTon ds={ds} lay={(x) => x.sl_tra} /> : so(m.sl_tra)}
                  </td>
                  <td className={SO}>
                    <OTon ds={ds} lay={(x) => x.ton_cuoi} />
                    {ds.some((x) => x.khac !== 0) ? (
                      <span className="block text-meta text-ink-soft">gồm ±điều chỉnh/huỷ</span>
                    ) : null}
                  </td>
                  <td className={SO}><OTon ds={ds} lay={(x) => x.kiem_ke} /></td>
                  <td className={`${SO} ${ds.some((x) => x.lech) ? "font-semibold text-danger" : ""}`}>
                    <OTon ds={ds} lay={(x) => x.lech} dau />
                  </td>
                  <td className={SO}><OTon ds={ds} lay={(x) => x.da_thu_chua_giao} /></td>
                  <td className={SO}>{so(m.doanh_thu)}</td>
                  <td className={SO}>{so(m.gia_tri_tra)}</td>
                  <td className={SO}>{so(m.doanh_thu_thuan)}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function BangHangHoa({ hh }: { hh: HangHoa }) {
  if (hh.co_ton) return <BangCoTon hh={hh} />;
  const t = hh.tong;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="bg-info-bg text-left text-ink">
            {/* Điện thoại: mã xuống dưới tên hàng, để tên + số không bị đẩy khỏi màn. */}
            <th className={`${TH} hidden sm:table-cell`}>Mã hàng</th>
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
            <td className="hidden px-3 py-3 whitespace-nowrap sm:table-cell">SL Mặt hàng: {t.so_mat_hang}</td>
            <td className="px-3 py-3 whitespace-nowrap">
              <span className="sm:hidden">SL Mặt hàng: {t.so_mat_hang}</span>
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
                <td className="hidden px-3 py-3 whitespace-nowrap text-meta font-semibold text-info sm:table-cell">
                  {m.ma ?? "—"}
                </td>
                <td className="px-3 py-3 min-w-44">
                  {m.ten}
                  {m.don_vi ? ` (${m.don_vi})` : ""}
                  {m.ma ? <span className="block text-meta text-info sm:hidden">{m.ma}</span> : null}
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
