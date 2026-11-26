"use client";

// Yêu cầu "Nhờ kho thêm thuốc" từ màn kê đơn (26/11/2026): bác sĩ gõ tên chưa có trong
// danh mục. Người kho thêm thuốc (có giá) ở Danh mục bên dưới rồi bấm "Xong"; bấm nhầm
// thì "Mở lại". Danh sách tự làm mới khi có yêu cầu mới (bảng `thuoc_nho_kho`).

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { goiThuoc, type YeuCauNhoKho as YeuCau } from "@/lib/goi-thuoc";
import { useNgheBang } from "../../dung-nghe-bang";

const gio = (s: string) =>
  new Date(s).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

export default function YeuCauNhoKho({ ghiDuoc = false }: { ghiDuoc?: boolean }) {
  const [ds, setDs] = useState<YeuCau[]>([]);
  const [loi, setLoi] = useState<string | null>(null);
  const [xemXong, setXemXong] = useState(false);

  const tai = useCallback(
    () =>
      goiThuoc<{ items: YeuCau[] }>("nho-kho").then((kq) => {
        if (kq.ok) setDs(kq.data.items);
      }),
    [],
  );
  useEffect(() => {
    let bo = false;
    void goiThuoc<{ items: YeuCau[] }>("nho-kho").then((kq) => {
      if (!bo && kq.ok) setDs(kq.data.items);
    });
    return () => {
      bo = true;
    };
  }, []);
  useNgheBang(["thuoc_nho_kho"], tai);

  const danhDau = async (id: string, xong: boolean) => {
    setLoi(null);
    const kq = await goiThuoc("danh-dau", { body: { id, xong } });
    if (!kq.ok) setLoi(kq.loi);
    await tai();
  };

  const mo = ds.filter((x) => !x.xong);
  const hien = xemXong ? ds : mo;
  if (ds.length === 0) return null;
  return (
    <section aria-label="Yêu cầu thêm thuốc" className="space-y-2 rounded-card border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-title text-ink">Bác sĩ nhờ thêm thuốc ({mo.length})</h3>
        <Button type="button" size="sm" variant="ghost" className="ml-auto" onClick={() => setXemXong(!xemXong)}>
          {xemXong ? "Chỉ yêu cầu đang chờ" : "Xem cả yêu cầu đã xong"}
        </Button>
      </div>
      {mo.length === 0 && !xemXong ? <p className="text-meta text-ink-muted">Không có yêu cầu nào đang chờ.</p> : null}
      <ul className="divide-y divide-hairline">
        {hien.map((x) => (
          <li key={x.id} className="flex flex-wrap items-center gap-2 py-2">
            <span className={`min-w-0 flex-1 ${x.xong ? "text-ink-faint" : "text-ink"}`}>
              <span className="font-medium">{x.ten_go}</span>
              <span className="block text-meta text-ink-muted">
                {x.nguoi_nho ?? "—"} · {gio(x.tao_luc)}
                {x.xong ? ` · xong bởi ${x.nguoi_xong ?? "—"}` : ""}
              </span>
            </span>
            {ghiDuoc ? (
              <Button type="button" size="sm" variant={x.xong ? "ghost" : "secondary"} onClick={() => void danhDau(x.id, !x.xong)}>
                {x.xong ? "Mở lại" : "Xong"}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
