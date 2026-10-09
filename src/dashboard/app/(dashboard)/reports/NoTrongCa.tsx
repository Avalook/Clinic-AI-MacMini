// NỢ TRONG CA (09/10/2026) — báo cáo cuối ca: khoản ghi nợ mới, thu lại, huỷ
// trong khung giờ ca, kèm tên khách. Số và danh sách do máy chủ gom
// (`cong_no_service.doc_no_trong_khung`); màn chỉ vẽ.

export interface DongNo {
  id: string;
  khach: string | null;
  ma_bn: string | null;
  so_tien: number;
  trang_thai: string;
  ly_do: string | null;
  nguoi: string | null;
  luc: string | null;
}

export interface NhomNo {
  so: number;
  so_tien: number;
  ds: DongNo[];
}

export type NoTrongCaData = Record<"ghi_moi" | "thu_lai" | "huy", NhomNo>;

const NHOM: ["ghi_moi" | "thu_lai" | "huy", string][] = [
  ["ghi_moi", "Ghi nợ mới"],
  ["thu_lai", "Thu lại nợ"],
  ["huy", "Huỷ ghi nợ"],
];

const TRANG_THAI: Record<string, string> = {
  CHUA_THU: "còn nợ",
  DA_THU: "đã thu",
  HUY: "đã huỷ",
};

const TH = "px-3 py-2 font-medium";
const TD = "px-3 py-2 text-ink";

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function NoTrongCa({ no }: { no: NoTrongCaData }) {
  const dong = NHOM.flatMap(([ma, ten]) => no[ma].ds.map((d) => ({ ...d, nhom: ten, ma })));
  return (
    <div className="space-y-2">
      <p className="text-meta text-ink-muted">
        {NHOM.map(([ma, ten]) => `${ten}: ${no[ma].so} — ${tien(no[ma].so_tien)}`).join(" · ")}
      </p>
      {dong.length === 0 ? (
        <p className="text-meta text-ink-muted">Không có khoản nợ nào ghi, thu hay huỷ trong ca.</p>
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
          <table className="w-full border-collapse text-body">
            <thead>
              <tr className="border-b border-line bg-surface-muted text-left text-meta text-ink-muted">
                <th className={TH}>Lúc</th>
                <th className={TH}>Việc</th>
                <th className={TH}>Khách</th>
                <th className={TH}>Lý do</th>
                <th className={`${TH} text-right`}>Số tiền</th>
              </tr>
            </thead>
            <tbody>
              {dong.map((d) => (
                <tr key={`${d.ma}-${d.id}`} className="border-b border-surface-sunken last:border-b-0">
                  <td className={`${TD} whitespace-nowrap`}>{gio(d.luc)}</td>
                  <td className={TD}>
                    {d.nhom}
                    {d.ma === "ghi_moi" && TRANG_THAI[d.trang_thai] ? (
                      <span className="block text-meta text-ink-muted">{TRANG_THAI[d.trang_thai]}</span>
                    ) : null}
                  </td>
                  <td className={TD}>
                    {d.khach ?? "—"}
                    {d.ma_bn ? <span className="block text-meta text-ink-muted">{d.ma_bn}</span> : null}
                  </td>
                  <td className={`${TD} min-w-40`}>
                    {d.ly_do ?? "—"}
                    {d.nguoi ? <span className="block text-meta text-ink-muted">{d.nguoi}</span> : null}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink">{tien(d.so_tien)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
