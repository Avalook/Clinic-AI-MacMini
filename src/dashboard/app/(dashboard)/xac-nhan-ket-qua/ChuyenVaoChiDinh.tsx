// (Client — `HangChoXacNhanKetQua.tsx` và `ban-xet-nghiem/EmailDaGan.tsx` dùng.) Gmail G13 (Tuyền 11/11): tờ email "gắn theo lượt khám" (thư về lúc khách chưa có chỉ
// định) ⇒ nhập chỉ định xong thì chuyển tờ vào chỉ định bằng NÚT (người kiểm chọn đúng
// một). Danh sách chỉ định nhận được, từ chối tờ cũ, gán tờ mới đều do máy chủ
// (`gmail_vao_chi_dinh.py`) — màn chỉ vẽ và gửi lệnh.

import { useState } from "react";

import Button from "@/components/ui/Button";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { lenh } from "../ban-xet-nghiem/kieu";

interface ChiDinh {
  service_order_id: string;
  ten_dich_vu: string;
}

export default function ChuyenVaoChiDinh({
  tepId,
  onXong,
}: {
  tepId: string;
  onXong: (tenDichVu: string) => void;
}) {
  const [ds, setDs] = useState<ChiDinh[] | null>(null);
  const [dangChay, setDangChay] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function mo() {
    setDangChay(true);
    setLoi(null);
    try {
      const r = await fetch(
        `/api/xet-nghiem/ban/to-theo-luot-chi-dinh?tep_id=${encodeURIComponent(tepId)}`,
        { cache: "no-store" },
      );
      const body: unknown = await r.json().catch(() => null);
      if (!r.ok) {
        setLoi(loiDocDuoc(body, `Chưa tải được chỉ định (HTTP ${r.status}).`));
        return;
      }
      setDs((body as { chi_dinh?: ChiDinh[] } | null)?.chi_dinh ?? []);
    } catch {
      setLoi("Mất kết nối — chưa tải được chỉ định.");
    } finally {
      setDangChay(false);
    }
  }

  async function chuyen(c: ChiDinh) {
    setDangChay(true);
    setLoi(null);
    const l = await lenh("to-vao-chi-dinh", {
      tep_id: tepId,
      service_order_id: c.service_order_id,
    });
    setDangChay(false);
    if (l) setLoi(l);
    else onXong(c.ten_dich_vu);
  }

  if (ds === null) {
    return (
      <div className="flex flex-col items-end gap-1">
        <Button size="sm" disabled={dangChay} onClick={() => void mo()}>
          {dangChay ? "Đang tải…" : "Chuyển vào chỉ định"}
        </Button>
        {loi ? (
          <p role="alert" className="text-xs font-medium text-danger">
            {loi}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col gap-2 rounded-control border border-line bg-surface-muted p-3 text-sm">
      {ds.length === 0 ? (
        <p className="text-ink-soft">
          Khách chưa có chỉ định xét nghiệm nào khác của đối tác này còn trống kết quả.
          Nhập chỉ định ở Bàn khám (trong cùng lượt khám, chậm nhất 7 ngày sau ngày thư
          về) rồi bấm lại.
        </p>
      ) : (
        <>
          <p className="font-semibold text-ink">Chọn chỉ định nhận tờ này:</p>
          <ul className="flex flex-col gap-2">
            {ds.map((c) => (
              <li key={c.service_order_id}>
                <Button
                  size="sm"
                  variant="primary"
                  disabled={dangChay}
                  onClick={() => void chuyen(c)}
                  // Tên dịch vụ dài (ThinPrep…) phải xuống dòng — nút mặc định nowrap
                  // làm tràn ngang ở 375.
                  className="h-auto! min-h-7 w-full justify-start py-1 text-left whitespace-normal! sm:w-auto"
                >
                  Chuyển vào: {c.ten_dich_vu}
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
      {loi ? (
        <p role="alert" className="text-xs font-medium text-danger">
          {loi}
        </p>
      ) : null}
      <div>
        <Button size="sm" variant="ghost" disabled={dangChay} onClick={() => setDs(null)}>
          Thôi
        </Button>
      </div>
    </div>
  );
}
