// Lịch làm việc — góc nhìn THEO NGƯỜI (27/09/2026 đợt 3, A9).
//
// Phòng khám: "Cần lịch trực + tên nhân sự kèm vai trò của mỗi người". Bảng
// theo vị trí trả lời "chỗ này ai đứng"; nhân viên hỏi câu ngược lại — "tuần
// này tôi đứng đâu, cô A đứng đâu". Mỗi người một hàng: tên · vai · từng ngày
// trong tuần các vị trí + ca. Cùng dữ liệu ca ĐÃ DUYỆT với bảng theo vị trí.
//
// Bảng vận hành rộng (DESIGN.md §7): giữ dạng bảng, cuộn ngang trong thẻ, cột
// tên dính trái — ở 375px chỉ cột tên dính, bảy cột ngày trôi dưới nó.

import {
  dayShort,
  fmtDayMonth,
  gomTheoNguoi,
  nhanViTri,
  type DongLichNguoi,
  type Station,
} from "../../../lib/roster";

const O = "border-b border-hairline px-2 py-2 align-top";

export default function LichTheoNguoi({
  stations,
  dates,
  rows,
}: {
  stations: readonly Station[];
  dates: string[];
  rows: readonly DongLichNguoi[];
}) {
  const nguoi = gomTheoNguoi(rows, nhanViTri(stations));
  if (nguoi.length === 0) {
    return (
      <p className="rounded-card border border-line bg-surface p-4 text-body text-ink-muted">
        Tuần này chưa có ca nào được duyệt.
      </p>
    );
  }
  return (
    <div className="max-h-[88vh] max-w-full overflow-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full min-w-max border-collapse text-body">
        <thead>
          <tr className="bg-surface-muted text-left text-label font-semibold uppercase text-ink-muted">
            <th className={`${O} sticky left-0 z-20 w-40 min-w-40 bg-surface-muted sm:w-56 sm:min-w-56`}>
              Nhân sự
            </th>
            {dates.map((d) => (
              <th key={d} className={`${O} min-w-36`}>
                {dayShort(d)} {fmtDayMonth(d)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {nguoi.map((n) => (
            <tr key={n.khoa} className="hover:bg-surface-sunken">
              <th
                scope="row"
                className={`${O} sticky left-0 z-10 w-40 min-w-40 bg-surface text-left font-semibold text-ink sm:w-56 sm:min-w-56`}
              >
                {n.ten}
                <span className="block text-meta font-normal text-ink-muted">
                  {n.vai || "—"}
                </span>
              </th>
              {dates.map((d) => {
                const viec = n.theoNgay[d] ?? [];
                return (
                  <td key={d} className={`${O} text-ink`}>
                    {viec.length === 0 ? (
                      <span className="text-ink-faint">—</span>
                    ) : (
                      viec.map((v, i) => (
                        <span key={i} className="block whitespace-nowrap leading-snug">
                          {v.viTri}
                          <span className="text-meta text-ink-muted"> · {v.ca}</span>
                        </span>
                      ))
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
