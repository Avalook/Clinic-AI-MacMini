// Lịch làm việc chính thức (chỉ đọc).
//
// KHÔNG CÒN THÂN RIÊNG. Bảng này và bảng trang chủ vốn đã là "cùng một bảng ở
// hai chỗ" — cùng dữ liệu, cùng form, cùng cách đọc — nhưng được viết hai lần,
// và hai bản ĐÃ lệch nhau: bản kia gắn hậu tố ca vào tên người, bản này thì
// không; bản kia chỉ vẽ gạch "trống" ở hàng trên, bản này vẽ ở cả hai.
//
// Lật bảng sang form Excel (16/09/2026) là lúc phải chép lần thứ ba. Thay vì
// thế, dùng lại. Còn đúng một thân bảng để sửa, và không còn chỗ nào để lệch.

import { type Station } from "../../../lib/roster";
import WorkRosterTable, { type DongCaRow, type RosterRow } from "../home/WorkRosterTable";

export type OfficialRosterRow = RosterRow;

export default function OfficialRosterTable({
  stations,
  dates,
  rows,
  dong = [],
}: {
  stations: readonly Station[];
  dates: string[];
  rows: OfficialRosterRow[];
  dong?: DongCaRow[];
}) {
  return <WorkRosterTable stations={stations} dates={dates} rows={rows} dong={dong} />;
}
