"use client";

// Chuông thông báo lịch — CHỈ render ở Trang chủ (đặt <RosterBell/> trong home).
// Đọc state từ NotificationContext (bộ phát hiện chạy nền ở layout). Trang khác
// không có chuông; thay vào đó mục "Trang chủ" ở sidebar nhấp nháy "!" (xem Nav).

import { useState } from "react";
import { Bell, Check, X } from "lucide-react";
import { useNotifications } from "./NotificationContext";

export default function RosterBell() {
  const { notifs, unread, transient, markAllRead, dismissTransient } =
    useNotifications();
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="fixed right-4 top-3 z-[70]">
        <button
          onClick={() => {
            setOpen((o) => !o);
            markAllRead();
          }}
          aria-label="Thông báo lịch làm việc"
          className="relative flex h-9 w-9 items-center justify-center rounded-full border border-line bg-white text-ink-soft shadow-sm hover:bg-surface-sunken"
        >
          <Bell size={18} />
          {unread > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-brand-600 px-1 text-[10px] font-semibold text-white">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>

        {open && (
          <div className="absolute right-0 top-11 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-line bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-surface-sunken px-3 py-2">
              <span className="text-sm font-semibold text-ink">
                Thông báo lịch làm việc
              </span>
              <button
                onClick={() => setOpen(false)}
                aria-label="Đóng"
                className="text-ink-faint hover:text-ink-muted"
              >
                <X size={15} />
              </button>
            </div>
            {notifs.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-ink-faint">
                Chưa có thông báo nào.
              </p>
            ) : (
              <ul className="max-h-80 divide-y divide-surface-sunken overflow-auto">
                {notifs.map((n) => (
                  <li key={n.key} className="flex gap-2 px-3 py-2">
                    <span
                      className={
                        "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full " +
                        (n.approved
                          ? "bg-success-bg text-success"
                          : "bg-danger-bg text-danger")
                      }
                    >
                      {n.approved ? <Check size={12} /> : <X size={12} />}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-ink">{n.title}</p>
                      <p className="text-xs text-ink-soft">{n.detail}</p>
                      <p className="text-[10px] text-ink-faint">{n.at}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Popup ngắn — liếc nhanh rồi tự ẩn. Chỉ ở Trang chủ. */}
      {transient.length > 0 && (
        <div className="fixed right-4 top-14 z-[65] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
          {transient.map((t) => (
            <div
              key={t.key}
              className={
                "rounded-xl border p-3 shadow-lg " +
                (t.approved
                  ? "border-success-bg bg-success-bg"
                  : "border-danger bg-danger-bg")
              }
            >
              <div className="flex items-start justify-between gap-2">
                <p
                  className={
                    "text-sm font-semibold " +
                    (t.approved ? "text-success" : "text-danger")
                  }
                >
                  {t.title}
                </p>
                <button
                  onClick={() => dismissTransient(t.key)}
                  aria-label="Đóng"
                  className="text-ink-faint hover:text-ink-muted"
                >
                  <X size={14} />
                </button>
              </div>
              <p className="mt-1 text-xs text-ink-soft">{t.detail}</p>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
