"use client";

// Khối "Khách không mua đơn này" / "Mở lại cả đơn" ở đầu khung chi tiết LƯỢT
// (16/11/2026). Trước đây chỉ có nút từng dòng, phải gõ lý do từng dòng và không
// mở lại được — đơn không mua dồn mãi ở "Đang xử lý".
//
// Hiện nút nào là do MÁY CHỦ quyết (`luot.khong_lay_ca_don`, `luot.mo_lai_ca_don`);
// máy chủ vẫn kiểm lại và trả câu tiếng Việt khi từ chối — hiện nguyên văn.

import { useState } from "react";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/Button";
import { INPUT } from "../form-ui";
import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";
import { CHAM } from "./DongThuoc";
import type { LuotThuoc } from "./ban-thuoc";

export default function KhachKhongLayCaDon({ luot }: { luot: LuotThuoc }) {
  const router = useRouter();
  const [lyDo, setLyDo] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [tin, setTin] = useState<string | null>(null);

  if (!luot.khong_lay_ca_don && !luot.mo_lai_ca_don) return null;

  async function goi(action: string, body: Record<string, unknown>, xong: (n: number) => string) {
    setDangGui(true);
    setLoi(null);
    setTin(null);
    const thaoTac = dinhDanhThaoTac(action, JSON.stringify(body));
    try {
      const res = await fetch(`/api/pharmacy/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": khoaThaoTac(thaoTac) },
        body: JSON.stringify(body),
      });
      const d = (await res.json().catch(() => null)) as {
        so_dong?: number;
        error?: string;
        message?: string;
        detail?: string;
      } | null;
      if (!res.ok) {
        setLoi(d?.message ?? d?.detail ?? d?.error ?? "Không lưu được. Thử lại giúp em.");
        return;
      }
      setTin(xong(d?.so_dong ?? 0));
      setLyDo("");
      xongThaoTac(thaoTac);
      router.refresh();
    } finally {
      setDangGui(false);
    }
  }

  return (
    <div className="space-y-2 rounded-card border border-line bg-surface-muted p-3">
      {luot.khong_lay_ca_don ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="block min-w-0 flex-1 text-xs text-ink-muted">
            Khách không mua thuốc nào trong đơn — ghi lý do (bắt buộc)
            <input
              value={lyDo}
              onChange={(e) => setLyDo(e.target.value)}
              placeholder="Khách đã có thuốc ở nhà…"
              className={`${INPUT} mt-1`}
            />
          </label>
          <Button
            className={CHAM}
            variant="danger"
            disabled={dangGui || !lyDo.trim()}
            onClick={() =>
              goi(
                "khong-lay-ca-don",
                { visit_id: luot.visit_id, ly_do: lyDo },
                (n) => `Đã ghi khách không lấy ${n} thuốc. Khách đổi ý thì bấm “Mở lại cả đơn”.`,
              )
            }
          >
            Khách không mua đơn này
          </Button>
        </div>
      ) : null}
      {luot.mo_lai_ca_don ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="min-w-0 flex-1 text-meta text-ink-soft">
            Khách đổi ý, lấy lại thuốc đã ghi “không lấy”?
          </span>
          <Button
            className={CHAM}
            size="sm"
            variant="secondary"
            disabled={dangGui}
            onClick={() =>
              goi(
                "mo-lai-ca-don",
                { visit_id: luot.visit_id },
                (n) => `Đã mở lại ${n} thuốc — đơn về lại “Đang xử lý”.`,
              )
            }
          >
            Mở lại cả đơn
          </Button>
        </div>
      ) : null}
      {tin ? (
        <p role="status" className="text-meta text-ink">
          {tin}
        </p>
      ) : null}
      {loi ? (
        <p className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
