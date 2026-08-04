"use client";

// Màn LỊCH SỬ ĐIỀU PHỐI — ai chuyển ai, từ đâu sang đâu, vì sao.
//
// Không có nhịp làm mới: đây là nhật ký, không phải bảng vận hành. Một danh sách
// tự nhảy dưới tay người đang đọc thì khó theo dõi hơn là hữu ích.

import { ArrowRight } from "lucide-react";
import type { DispatchHistoryRow } from "./types";
import { nodeLabel } from "./types";

export default function HistoryClient({ rows }: { rows: DispatchHistoryRow[] }) {
  return (
    <div className="dispatch-scope">
      <HistoryTable rows={rows} />
    </div>
  );
}

const EVENT_LABEL: Record<string, string> = {
  "dispatch.moved": "Chuyển bước",
  "dispatch.transfer_room": "Chuyển phòng",
  "dispatch.route_applied": "Áp dụng tuyến",
  "dispatch.checkin": "Tiếp nhận",
};

function HistoryTable({ rows }: { rows: DispatchHistoryRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Thời gian</th>
            <th>Thao tác</th>
            <th>Bệnh nhân</th>
            <th>Từ</th>
            <th>Đến</th>
            <th>Lý do</th>
            <th>Người thực hiện</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={7} style={{ color: "var(--ink-muted)" }}>
                Chưa có thao tác điều phối nào.
              </td>
            </tr>
          )}
          {rows.map((h, i) => (
            <tr key={i}>
              <td style={{ whiteSpace: "nowrap" }}>
                {new Date(h.at).toLocaleString("vi-VN", {
                  timeZone: "Asia/Ho_Chi_Minh",
                  day: "2-digit",
                  month: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </td>
              <td>{EVENT_LABEL[h.event_type] ?? h.event_type}</td>
              <td>
                {h.patient_name ?? "—"}
                <div style={{ fontSize: 11, color: "var(--ink-muted)" }}>
                  {h.patient_code ?? ""}
                </div>
              </td>
              <td>{h.from_room ?? nodeLabel(h.from_node)}</td>
              <td>
                <ArrowRight size={11} /> {h.to_room ?? nodeLabel(h.to_node)}
              </td>
              <td style={{ color: "var(--ink-muted)" }}>{h.reason ?? ""}</td>
              <td>{h.actor_name ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
