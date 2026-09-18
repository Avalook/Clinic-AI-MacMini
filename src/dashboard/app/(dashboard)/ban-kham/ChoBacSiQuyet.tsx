"use client";

// CHỜ BÁC SĨ QUYẾT — Slice 1 (18/09/2026).
//
// Khách đã làm xong dịch vụ nhưng bác sĩ chưa gọi lại được, vì một trong hai:
//   · kết quả chưa về (xét nghiệm gửi đối tác) — vòng đọc chưa sẵn sàng;
//   · dịch vụ KHÔNG làm được — không bao giờ tự tính là đạt.
// Trước đây những khách này không nằm trong hàng chờ nào của bác sĩ, và không
// có chỗ nào để nói "cho khách về, báo kết quả sau". Mọi luật nằm ở máy chủ:
// màn chỉ hiện việc và gửi quyết định kèm lý do (bắt buộc).

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import StatusChip from "@/components/ui/StatusChip";

import { docBang, guiThaoTac } from "../_lam-viec/api";

interface ViecChoQuyet {
  id: string;
  visit_id: string;
  ten: string;
  ma_bn: string | null;
  dich_vu: string;
  can: "PERFORMED" | "VALID_RESULT";
  trang_thai: "cho_ket_qua" | "can_quyet";
  ly_do_khong_lam: string | null;
  vong: number;
}

type HanhDong = "FOLLOW_UP" | "WAIVE";

export default function ChoBacSiQuyet({
  lanNap,
  onDaQuyet,
}: {
  /** Tăng lên khi màn cha nạp lại — khung này nạp theo. */
  lanNap: number;
  onDaQuyet: () => void;
}) {
  const [viec, setViec] = useState<ViecChoQuyet[]>([]);
  const [duocQuyet, setDuocQuyet] = useState(false);
  const [dangMo, setDangMo] = useState<{ id: string; hanh: HanhDong } | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const nap = useCallback(async () => {
    const kq = await docBang<{ viec: ViecChoQuyet[]; duoc_quyet: boolean }>("cho-quyet");
    if (kq.ok) {
      setViec(kq.data.viec);
      setDuocQuyet(kq.data.duoc_quyet);
    }
  }, []);

  useEffect(() => {
    let huy = false;
    void docBang<{ viec: ViecChoQuyet[]; duoc_quyet: boolean }>("cho-quyet").then(
      (kq) => {
        if (huy || !kq.ok) return;
        setViec(kq.data.viec);
        setDuocQuyet(kq.data.duoc_quyet);
      },
    );
    return () => {
      huy = true;
    };
  }, [lanNap]);

  if (viec.length === 0) return null;

  const gui = async () => {
    if (!dangMo || !lyDo.trim()) return;
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac("quyet-yeu-cau", dangMo.id, {
      hanh_dong: dangMo.hanh,
      ly_do: lyDo.trim(),
    });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setDangMo(null);
    setLyDo("");
    await nap();
    onDaQuyet();
  };

  return (
    <section
      aria-label="Chờ bác sĩ quyết"
      className="rounded-card bg-surface p-3.5 shadow-card"
    >
      <h2 className="text-sm font-semibold text-ink">
        Chờ bác sĩ quyết · {viec.length}
      </h2>
      <p className="mt-1 text-xs text-ink-muted">
        Khách đã làm dịch vụ nhưng chưa quay lại được: kết quả chưa về, hoặc dịch vụ
        không làm được.
      </p>
      <ul className="mt-3 grid gap-2">
        {viec.map((v) => {
          const mo = dangMo?.id === v.id;
          return (
            <li key={v.id} className="rounded-control bg-surface-muted px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-ink">{v.ten}</span>
                {v.ma_bn ? <span className="text-xs text-ink-muted">{v.ma_bn}</span> : null}
                <span className="text-sm text-ink">· {v.dich_vu}</span>
                {v.trang_thai === "can_quyet" ? (
                  <StatusChip tone="overdue" label="Không làm được" />
                ) : (
                  <StatusChip tone="blocked" label="Chờ kết quả" />
                )}
              </div>
              {v.ly_do_khong_lam ? (
                <p className="mt-1 text-xs text-ink-muted">Lý do: {v.ly_do_khong_lam}</p>
              ) : null}
              {duocQuyet && !mo ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => {
                      setDangMo({ id: v.id, hanh: "FOLLOW_UP" });
                      setLyDo("");
                      setLoi(null);
                    }}
                  >
                    Cho về, theo dõi kết quả
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => {
                      setDangMo({ id: v.id, hanh: "WAIVE" });
                      setLyDo("");
                      setLoi(null);
                    }}
                  >
                    Miễn (không cần nữa)
                  </Button>
                </div>
              ) : null}
              {mo ? (
                <div className="mt-2 grid gap-2">
                  <label className="text-xs font-semibold text-ink" htmlFor={`ly-do-${v.id}`}>
                    {dangMo?.hanh === "FOLLOW_UP"
                      ? "Vì sao cho khách về trước? (bắt buộc)"
                      : "Vì sao miễn? (bắt buộc — đổi kế hoạch thì chỉ định thêm khi đọc kết quả)"}
                  </label>
                  <input
                    id={`ly-do-${v.id}`}
                    value={lyDo}
                    onChange={(e) => setLyDo(e.target.value)}
                    className="min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink"
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="primary"
                      disabled={dangGui || !lyDo.trim()}
                      onClick={() => void gui()}
                    >
                      {dangGui ? "Đang ghi…" : "Xác nhận"}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setDangMo(null)}>
                      Thôi
                    </Button>
                  </div>
                  {loi ? (
                    <p role="alert" className="text-xs text-danger">
                      {loi}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
