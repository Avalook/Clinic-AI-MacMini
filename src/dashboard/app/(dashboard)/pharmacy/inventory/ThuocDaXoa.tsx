"use client";

// "Thuốc đã xoá" (26/11/2026): mỗi lần Xoá ở Danh mục, máy chủ lưu bản chụp thuốc +
// đơn vị quy đổi + mã vạch rồi mới xoá. Ở đây xem ai xoá, lúc nào, lý do; bấm
// "Khôi phục" là dựng lại đúng thuốc ấy (hoàn tác). Gập sẵn — chỉ mở khi cần.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { goiThuoc, type ThuocDaXoa as Dong } from "@/lib/goi-thuoc";

const gio = (s: string) =>
  new Date(s).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

export default function ThuocDaXoa({ ghiDuoc = false }: { ghiDuoc?: boolean }) {
  const router = useRouter();
  const [ds, setDs] = useState<Dong[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  const tai = async () => {
    const kq = await goiThuoc<{ items: Dong[] }>("da-xoa");
    if (kq.ok) setDs(kq.data.items);
    else setLoi(kq.loi);
  };

  const khoiPhuc = async (id: string) => {
    setLoi(null);
    const kq = await goiThuoc("khoi-phuc", { body: { id } });
    if (!kq.ok) setLoi(kq.loi);
    await tai();
    router.refresh();
  };

  return (
    <details
      className="rounded-card border border-line bg-surface p-3"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open && ds === null) void tai();
      }}
    >
      <summary className="cursor-pointer text-body text-ink">Thuốc đã xoá (khôi phục được)</summary>
      {ds === null ? (
        <p className="mt-2 text-meta text-ink-muted">Đang tải…</p>
      ) : ds.length === 0 ? (
        <p className="mt-2 text-meta text-ink-muted">Chưa xoá thuốc nào.</p>
      ) : (
        <ul className="mt-2 divide-y divide-hairline">
          {ds.map((x) => (
            <li key={x.id} className="flex flex-wrap items-center gap-2 py-2">
              <span className={`min-w-0 flex-1 ${x.da_khoi_phuc ? "text-ink-faint" : "text-ink"}`}>
                <span className="font-medium">{x.ten}</span>
                <span className="block text-meta text-ink-muted">
                  Xoá bởi {x.nguoi_xoa ?? "—"} · {gio(x.xoa_luc)} · {x.ly_do}
                  {x.da_khoi_phuc ? ` · đã khôi phục bởi ${x.nguoi_khoi_phuc ?? "—"}` : ""}
                </span>
              </span>
              {ghiDuoc && !x.da_khoi_phuc ? (
                <Button type="button" size="sm" variant="secondary" onClick={() => void khoiPhuc(x.id)}>
                  Khôi phục
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {loi ? (
        <p role="alert" className="mt-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </details>
  );
}
