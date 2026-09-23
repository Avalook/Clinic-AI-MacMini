"use client";

// Danh sách việc của khu vận hành + nút đóng việc.
//
// Hai loại việc ở đây đều sinh ra từ SỰ KIỆN, không ai gõ tay: khách đã trả tiền
// mà dịch vụ không làm được, và dịch vụ bị dừng giữa chừng. Màn này chỉ hiện và
// đóng — quyết định hoàn tiền hay xếp lại phòng nằm ở màn của việc ấy.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";

interface Viec {
  id: string;
  node_code: string;
  node_name: string | null;
  status: string;
  version: number;
  visit_id: string | null;
  created_at: string | null;
  actionable_by_me: boolean;
  patient: { ten?: string | null; ma_bn?: string | null } | null;
}

const NHAN: Record<string, string> = {
  "OPS-DOI-SOAT-TIEN": "Đối soát tiền — khách đã trả mà không làm",
  "OPS-QUYET-LAM-LAI": "Quyết định làm lại — dịch vụ bị dừng giữa chừng",
};

function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}

export default function BangViecCanXuLy() {
  const [ds, setDs] = useState<Viec[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangDong, setDangDong] = useState<string | null>(null);

  const doc = useCallback(async (): Promise<Viec[] | null> => {
    const r = await fetch("/api/work-items?workspace=khu_van_hanh", {
      cache: "no-store",
    });
    return r.ok ? ((await r.json()) as Viec[]) : null;
  }, []);

  const nap = useCallback(async () => {
    const kq = await doc();
    if (kq === null) {
      setLoi("Không đọc được danh sách việc.");
      return;
    }
    setLoi(null);
    setDs(kq);
  }, [doc]);

  useEffect(() => {
    let huy = false;
    const lay = () => {
      void doc().then((kq) => {
        if (huy) return;
        if (kq === null) setLoi("Không đọc được danh sách việc.");
        else {
          setLoi(null);
          setDs(kq);
        }
      });
    };
    lay();
    // Việc sinh ra từ sự kiện chạy nền, nên màn phải tự làm mới. 20 giây là đủ
    // cho loại việc mà hạn xử lý tính bằng giờ.
    const t = setInterval(lay, 20000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [doc]);

  const dong = async (v: Viec) => {
    setDangDong(v.id);
    const r = await fetch(`/api/work-items/${v.id}/commands/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_version: v.version }),
    });
    setDangDong(null);
    if (!r.ok) {
      setLoi("Đóng việc không thành công — tải lại rồi thử lại.");
      return;
    }
    await nap();
  };

  if (ds === null) {
    return <p className="text-sm text-ink-muted">Đang tải…</p>;
  }

  return (
    <section className="flex flex-col gap-3">
      {loi ? (
        <p role="alert" className="text-sm text-danger">
          {loi}
        </p>
      ) : null}

      {ds.length === 0 ? (
        <p className="rounded-card bg-surface-muted p-4 text-sm text-ink-muted shadow-card">
          Không có việc nào đang chờ. Đây là trạng thái bình thường — việc chỉ
          sinh ra khi có chuyện cần người xử lý.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {ds.map((v) => (
            <li
              key={v.id}
              className="rounded-card bg-surface-muted p-3.5 shadow-card"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">
                    {NHAN[v.node_code] ?? v.node_name ?? v.node_code}
                  </p>
                  <p className="mt-0.5 text-label text-ink-muted">
                    {v.patient?.ten ? `${v.patient.ten} · ` : ""}
                    {v.patient?.ma_bn ?? ""}
                    {v.created_at ? ` · mở lúc ${gio(v.created_at)}` : ""}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={dangDong === v.id || !v.actionable_by_me}
                  onClick={() => void dong(v)}
                >
                  {dangDong === v.id ? "Đang đóng…" : "Đã xử lý"}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
