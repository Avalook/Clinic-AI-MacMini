// Đếm số lệnh chỉnh đơn đang chạy — màn cha che Tổng ("đang tính lại…") tới khi
// lệnh CUỐI xong (27/11/2026). Ô số lượng của `ChinhDonQuay` tự lưu nên hai lệnh có
// thể chen nhau; cờ đúng/sai thì lệnh xong trước gỡ che khi lệnh sau chưa xong, Tổng
// hiện số giữa chừng. Lệnh báo "xong" mà chưa báo "bắt đầu" (gỡ dòng lệch) không
// làm số âm.

import { useCallback, useState } from "react";

export function demSau(n: number, viec: "bat-dau" | "xong"): number {
  return viec === "bat-dau" ? n + 1 : Math.max(0, n - 1);
}

export function useDemDangChay(): { dang: boolean; batDau: () => void; xong: () => void } {
  const [n, setN] = useState(0);
  const batDau = useCallback(() => setN((x) => demSau(x, "bat-dau")), []);
  const xong = useCallback(() => setN((x) => demSau(x, "xong")), []);
  return { dang: n > 0, batDau, xong };
}
