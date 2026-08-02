"use client";

// CskhBoard — Không gian làm việc CSKH (image_1 + image_2 + image_10).
// 2 cột: lịch hẹn cần xác nhận (trái) + follow-up cần gọi (phải).
// Nút xử lý: Xác nhận lịch, Đã gọi, Đóng case.
//
// Trước B.4 ba nút này chỉ thêm id vào một Set trong trình duyệt: dòng biến
// mất, người bấm tưởng đã xong, F5 là việc quay lại và hai người có thể gọi
// cùng một bệnh nhân. Giờ mỗi nút là một lần ghi qua FastAPI, và danh sách
// được nạp lại từ server chứ không tự giấu dòng đi.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

interface CskhPatient {
  full_name: string | null;
  phone_primary: string | null;
}

interface CskhDoctor {
  full_name: string | null;
}

interface CskhAppt {
  id: string;
  slot_start: string;
  status: string;
  queue_number: string | null;
  booking_channel: string | null;
  patient: CskhPatient | null;
  doctor: CskhDoctor | null;
}

interface CskhFollowup {
  id: string;
  action_type: string | null;
  note: string | null;
  status: string | null;
  created_at: string;
  patient: CskhPatient | null;
}

interface Props {
  appts: CskhAppt[];
  followups: CskhFollowup[];
  /** Theo hàng rào backend (canWriteIntake), không theo danh sách vai của nav. */
  canWrite: boolean;
}

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });

// Mirrors RESOLUTIONS in cskh_service.py.
const RESOLVED = new Set(["Đã gọi", "Đã đóng"]);

async function errorOf(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string; detail?: string };
    return body.error ?? body.detail ?? "Không lưu được. Thử lại giúp tôi.";
  } catch {
    return "Không lưu được. Thử lại giúp tôi.";
  }
}

export default function CskhBoard({ appts, followups, canWrite }: Props) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const filteredAppts = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return appts;
    return appts.filter(
      (a) =>
        a.patient?.full_name?.toLowerCase().includes(q) ||
        a.patient?.phone_primary?.toLowerCase().includes(q),
    );
  }, [appts, search]);

  // Việc đã đóng không tự biến mất khỏi truy vấn hôm nay — hiển thị đúng trạng
  // thái server trả về thay vì giấu dòng đi, để người sau biết ai đã gọi rồi.
  const pendingAppts = filteredAppts.filter((a) => a.status !== "CSKH_CONFIRMED");
  const pendingFus = followups.filter((f) => !RESOLVED.has(f.status ?? ""));

  async function send(
    method: "POST" | "PATCH",
    path: string,
    body: unknown,
    id: string,
    done: string,
  ) {
    if (busyId) return;
    setBusyId(id);
    setError(null);
    setFlash(null);
    try {
      const response = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        setError(await errorOf(response));
        return;
      }
      setFlash(done);
      router.refresh();
    } catch {
      setError("Mất kết nối. Kiểm tra mạng rồi thử lại.");
    } finally {
      setBusyId(null);
    }
  }

  // Lịch hẹn đã có sẵn máy trạng thái ở booking_service.py — dùng đúng nó, đừng
  // mở đường ghi thứ hai chỉ vì nút nằm trên màn khác.
  const confirmAppt = (a: CskhAppt) =>
    send(
      "PATCH",
      "/api/appointments",
      { id: a.id, action: "cskh_confirm" },
      a.id,
      `Đã xác nhận lịch ${fmtTime(a.slot_start)}.`,
    );

  const resolveFollowup = (f: CskhFollowup, outcome: "called" | "closed") =>
    send(
      "POST",
      `/api/cskh-action/${f.id}/resolve`,
      { outcome },
      f.id,
      outcome === "called" ? "Đã ghi nhận cuộc gọi." : "Đã đóng việc.",
    );

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      {error ? (
        <p className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {flash ? (
        <p
          role="status"
          className="rounded-control bg-success-bg px-3 py-2 text-sm text-success"
        >
          {flash}
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
        {/* Cột trái: lịch hẹn cần xác nhận */}
        <section className="flex flex-col rounded-control border border-line bg-surface">
          <div className="border-b border-line p-3">
            <h2 className="text-sm font-semibold text-ink">
              Lịch hẹn cần xác nhận
            </h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              {pendingAppts.length} lịch chờ xử lý
            </p>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm tên / SĐT…"
              className="mt-2 w-full rounded-control border border-line bg-surface-muted px-2.5 py-1.5 text-sm text-ink outline-none focus:border-brand-500"
            />
          </div>
          <div className="flex-1 overflow-y-auto">
            {pendingAppts.length === 0 ? (
              <p className="p-4 text-sm text-ink-muted">
                Không có lịch chờ xác nhận.
              </p>
            ) : (
              pendingAppts.map((a) => (
                <div key={a.id} className="border-b border-line px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-ink">
                      {a.patient?.full_name ?? "Chưa có tên"}
                    </span>
                    <span className="shrink-0 text-xs text-ink-faint">
                      {fmtTime(a.slot_start)}
                    </span>
                  </div>
                  <div className="mt-0.5 text-xs text-ink-muted">
                    {a.patient?.phone_primary ?? "—"} ·{" "}
                    {a.doctor?.full_name ?? "Chưa phân BS"}
                  </div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <span className="rounded-full bg-warning-bg px-2 py-0.5 text-[11px] font-medium text-warning">
                      Chờ xác nhận
                    </span>
                    {canWrite ? (
                      <button
                        onClick={() => confirmAppt(a)}
                        disabled={busyId !== null}
                        className="ml-auto rounded-control bg-brand-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
                      >
                        {busyId === a.id ? "Đang lưu…" : "Xác nhận lịch"}
                      </button>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Cột phải: follow-up cần gọi */}
        <section className="flex flex-col rounded-control border border-line bg-surface">
          <div className="border-b border-line p-3">
            <h2 className="text-sm font-semibold text-ink">Follow-up cần gọi</h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              {pendingFus.length} việc chờ xử lý
            </p>
          </div>
          <div className="flex-1 overflow-y-auto">
            {pendingFus.length === 0 ? (
              <p className="p-4 text-sm text-ink-muted">
                Không có follow-up hôm nay.
              </p>
            ) : (
              pendingFus.map((f) => (
                <div key={f.id} className="border-b border-line px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-ink">
                      {f.patient?.full_name ?? "Chưa có tên"}
                    </span>
                    <span className="shrink-0 text-xs text-ink-faint">
                      {fmtDate(f.created_at)}
                    </span>
                  </div>
                  <div className="mt-0.5 text-xs text-ink-muted">
                    {f.patient?.phone_primary ?? "—"} ·{" "}
                    {f.action_type ?? "Follow-up"}
                  </div>
                  {f.note && (
                    <div className="mt-1 truncate text-xs text-ink-soft">
                      {f.note}
                    </div>
                  )}
                  <div className="mt-1.5 flex items-center gap-2">
                    <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700">
                      {f.status ?? "MỞ"}
                    </span>
                    {canWrite ? (
                      <>
                        <button
                          onClick={() => resolveFollowup(f, "called")}
                          disabled={busyId !== null}
                          className="ml-auto rounded-control bg-success px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-success/90 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
                        >
                          {busyId === f.id ? "Đang lưu…" : "Đã gọi"}
                        </button>
                        <button
                          onClick={() => resolveFollowup(f, "closed")}
                          disabled={busyId !== null}
                          className="rounded-control border border-line px-3 py-1 text-xs font-medium text-ink transition-colors hover:bg-surface-muted disabled:cursor-not-allowed disabled:text-ink-faint"
                        >
                          Đóng case
                        </button>
                      </>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
