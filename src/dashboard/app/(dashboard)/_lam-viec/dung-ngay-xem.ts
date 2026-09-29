"use client";

// NGÀY XEM của các màn làm việc — Đo sinh hiệu, Bàn khám tư vấn, Bàn khám, phòng
// dịch vụ (Tuyền 29/09/2026: "để bác sĩ hay bất kỳ ai quay lại ngày đó xem và
// sửa").
//
// Ngày nằm trên THANH ĐỊA CHỈ (`?ngay=yyyy-mm-dd`), không giữ state riêng: F5
// không mất ngày, gửi link là người kia mở đúng ngày. Hôm nay thì bỏ tham số cho
// link gọn. Đổi ngày chỉ ghi lại URL (`history.replaceState` — Next đồng bộ
// `useSearchParams`), không tải lại trang.
//
// Ngày rác / tương lai → hôm nay (`ngayXemTuUrl`, hàm thuần có test). Máy chủ
// vẫn tự đọc lại (`doc_ngay_xem`) và trả `hom_nay` — màn tin câu ấy khi vẽ.

import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

import { ngayXemTuUrl } from "@/lib/thanh-ngay";
import { homNayVn } from "@/lib/validation";

export function useNgayXem(): {
  ngay: string;
  homNay: string;
  laHomNay: boolean;
  chonNgay: (moi: string) => void;
} {
  const [homNay] = useState(homNayVn);
  const sp = useSearchParams();
  const pathname = usePathname();
  const ngay = ngayXemTuUrl(sp.get("ngay"), homNay);
  const chonNgay = useCallback(
    (moi: string) => {
      const q = new URLSearchParams(window.location.search);
      const ngayMoi = ngayXemTuUrl(moi, homNay);
      if (ngayMoi === homNay) q.delete("ngay");
      else q.set("ngay", ngayMoi);
      const qs = q.toString();
      window.history.replaceState(null, "", qs ? `${pathname}?${qs}` : pathname);
    },
    [homNay, pathname],
  );
  return { ngay, homNay, laHomNay: ngay === homNay, chonNgay };
}
