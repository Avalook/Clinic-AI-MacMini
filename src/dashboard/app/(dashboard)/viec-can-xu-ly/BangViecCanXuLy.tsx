"use client";

// Danh sách việc của khu vận hành + nút đóng việc.
//
// Hai loại việc ở đây đều sinh ra từ SỰ KIỆN, không ai gõ tay: khách đã trả tiền
// mà dịch vụ không làm được, và dịch vụ bị dừng giữa chừng. Màn này chỉ hiện và
// đóng — quyết định hoàn tiền hay xếp lại phòng nằm ở màn của việc ấy.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { nhanLoi } from "@/lib/loi-api";

import NutXemLuot from "../_lam-viec/NutXemLuot";
import { useNgheBang } from "../dung-nghe-bang";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";

interface Viec {
  id: string;
  node_code: string;
  node_name: string | null;
  status: string;
  version: number;
  visit_id: string | null;
  created_at: string | null;
  actionable_by_me: boolean;
  /** Khớp `WorklistPatient` ở routers/work_items.py (27/09 đợt 3: trước đây
   *  màn đọc `ten`/`ma_bn` — không có trong API — nên tên khách luôn trống). */
  patient: { full_name?: string | null; patient_code?: string | null } | null;
}

/** Nhãn của ba node khu vận hành — mã THẬT ở migration 20260923000007 (đợt 3
 *  sửa: bản trước dùng hai mã tự đặt không tồn tại). Mã lạ → tên node. */
const NHAN: Record<string, string> = {
  "OPS-FINANCIAL-RESOLUTION": "Đối soát tiền — khách đã trả mà không làm",
  "OPS-SERVICE-INTERRUPTED": "Quyết định làm lại — dịch vụ bị dừng giữa chừng",
  "OPS-ROUTING-REASSIGN": "Điều phối lại — phòng cũ không còn dùng được",
};

type KetQua = { ok: true; ds: Viec[] } | { ok: false; loi: string };

function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}

export default function BangViecCanXuLy() {
  const [ds, setDs] = useState<Viec[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangDong, setDangDong] = useState<string | null>(null);

  const doc = useCallback(async (): Promise<KetQua> => {
    try {
      const r = await fetch("/api/work-items?workspace=khu_van_hanh", {
        cache: "no-store",
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) return { ok: false, loi: nhanLoi(d, "Không đọc được danh sách việc.") };
      return { ok: true, ds: (d ?? []) as Viec[] };
    } catch {
      return { ok: false, loi: "Mất kết nối tới máy chủ." };
    }
  }, []);

  const nap = useCallback(async () => {
    const kq = await doc();
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setLoi(null);
    setDs(kq.ds);
  }, [doc]);

  useEffect(() => {
    let huy = false;
    const lay = () => {
      void doc().then((kq) => {
        if (huy) return;
        if (!kq.ok) setLoi(kq.loi);
        else {
          setLoi(null);
          setDs(kq.ds);
        }
      });
    };
    lay();
    // Việc sinh ra từ sự kiện chạy nền, nên màn phải tự làm mới.
    // SỰ KIỆN THAY NHỊP HỎI (27/09/2026): nghe tin bảng đổi qua dòng SSE chung
    // (`useNgheBang`) → nạp lại NGAY; nhịp hỏi giãn còn 60 giây làm lưới an toàn.
    // Tab ẩn thì huỷ hẳn nhịp; hiện lại thì tin `null` của RealtimeRefresher (qua
    // `useNgheBang`) đã hỏi lại một lần — nhịp không hỏi thêm (30/09/2026).
    const goNhip = nhipKhiHien(lay, 60000, { hoiKhiHien: false });
    return () => {
      huy = true;
      goNhip();
    };
  }, [doc]);

  useNgheBang(["work_item", "work_item_event", "staff_task"], () => void nap());

  // "Đã xử lý" = [start nếu việc còn chờ] → complete. Máy trạng thái của kernel
  // chỉ cho `complete` từ IN_PROGRESS — việc mới mở luôn ở PENDING, nên bản cũ
  // chỉ gửi `complete` thì LUÔN 409 (đợt 3, 27/09/2026). Máy chủ vẫn quyết từng
  // lệnh; màn chỉ gửi đúng thứ tự hai lệnh có sẵn.
  const lenh = async (
    id: string,
    thaoTac: "start" | "complete",
    version: number,
  ): Promise<{ ok: true; version: number } | { ok: false; loi: string }> => {
    try {
      const r = await fetch(`/api/work-items/${id}/commands/${thaoTac}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_version: version }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        return { ok: false, loi: nhanLoi(d, "Đóng việc không thành công — tải lại rồi thử lại.") };
      }
      return { ok: true, version: (d as { version?: number } | null)?.version ?? version };
    } catch {
      return { ok: false, loi: "Mất kết nối — việc CHƯA được đóng." };
    }
  };

  const dong = async (v: Viec) => {
    setDangDong(v.id);
    let version = v.version;
    if (v.status === "PENDING") {
      const bd = await lenh(v.id, "start", version);
      if (!bd.ok) {
        setDangDong(null);
        setLoi(bd.loi);
        return;
      }
      version = bd.version;
    }
    const kq = await lenh(v.id, "complete", version);
    setDangDong(null);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    await nap();
  };

  // Lần nạp đầu lỗi → nói rõ lỗi, không đứng "Đang tải…" mãi (đợt 3, 27/09).
  if (ds === null) {
    return loi ? (
      <p role="alert" className="text-sm text-danger">
        {loi}
      </p>
    ) : (
      <p className="text-sm text-ink-muted">Đang tải…</p>
    );
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
                  <p className="mt-0.5 text-meta text-ink-muted">
                    {[
                      v.patient?.full_name,
                      v.patient?.patient_code,
                      v.created_at ? `mở lúc ${gio(v.created_at)}` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                  {v.visit_id ? <NutXemLuot visitId={v.visit_id} nhan="Xem lượt" /> : null}
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
