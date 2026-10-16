"use client";

import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { KeyRound, X } from "lucide-react";
import { getSupabaseBrowser } from "../../lib/supabase-browser";
import Button from "@/components/ui/Button";

const MIN_PASSWORD = 8;

interface Props {
  open: boolean;
  onClose: () => void;
  staffName?: string;
}

export function DoiMatKhauModal({ open, onClose, staffName }: Props) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  const handleClose = useCallback(() => {
    if (busy) return;
    setOldPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setBusy(false);
    setMsg(null);
    onClose();
  }, [busy, onClose]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open && !busy) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, busy, handleClose]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);

    if (!oldPassword) {
      setMsg({ kind: "err", text: "Vui lòng nhập mật khẩu hiện tại." });
      return;
    }
    if (newPassword.length < MIN_PASSWORD) {
      setMsg({
        kind: "err",
        text: `Mật khẩu mới phải có ít nhất ${MIN_PASSWORD} ký tự.`,
      });
      return;
    }
    if (newPassword !== confirmPassword) {
      setMsg({ kind: "err", text: "Nhập lại mật khẩu mới không khớp." });
      return;
    }

    setBusy(true);
    try {
      const supabase = getSupabaseBrowser();
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user?.email) {
        setMsg({
          kind: "err",
          text: "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
        });
        setBusy(false);
        return;
      }

      // Xác thực mật khẩu cũ bằng cách thử đăng nhập
      const { error: signInErr } = await supabase.auth.signInWithPassword({
        email: user.email,
        password: oldPassword,
      });

      if (signInErr) {
        setMsg({ kind: "err", text: "Mật khẩu hiện tại không chính xác." });
        setBusy(false);
        return;
      }

      // Cập nhật mật khẩu mới
      const { error: updateErr } = await supabase.auth.updateUser({
        password: newPassword,
      });

      if (updateErr) {
        setMsg({ kind: "err", text: updateErr.message });
        setBusy(false);
        return;
      }

      // Đăng xuất mọi phiên trên máy khác, giữ máy hiện tại
      await supabase.auth.signOut({ scope: "others" });

      // Ghi nhật ký vào backend
      await fetch("/api/auth/nhat-ky-doi-mat-khau", {
        method: "POST",
      }).catch((err) => {
        console.error("Lỗi ghi nhật ký đổi mật khẩu:", err);
      });

      setMsg({
        kind: "ok",
        text: "Đổi mật khẩu thành công! Các phiên đăng nhập trên thiết bị khác đã được đăng xuất.",
      });

      // Tự đóng sau 1.5 giây
      setTimeout(() => {
        handleClose();
      }, 1500);
    } catch {
      setMsg({
        kind: "err",
        text: "Có lỗi xảy ra khi đổi mật khẩu. Vui lòng thử lại.",
      });
    } finally {
      setBusy(false);
    }
  }

  // Portal ra <body>: GlobalHeader có backdrop-blur nên `fixed` của hộp đặt TRONG
  // header bị tính theo header (cao 47px), không theo màn hình — hộp cắt mất phần
  // trên, ô Mật khẩu hiện tại ngoài màn hình (16/10/2026).
  return createPortal(
    <div
      className="fixed inset-0 z-50 overflow-y-auto bg-ink/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="doi-mat-khau-title"
    >
      {/* Cuộn được: màn thấp (laptop phóng to, điện thoại ngang) mà hộp căn giữa
          không cuộn thì ô "Mật khẩu hiện tại" nằm ngoài màn hình, nút Lưu xám
          mãi (Tuyền, 16/10/2026). `min-h-full` giữ hộp ở giữa khi màn cao. */}
      <div className="flex min-h-full items-center justify-center">
        <div className="w-full max-w-md rounded-panel border border-line bg-surface p-5 shadow-panel animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <div className="flex size-8 items-center justify-center rounded-control bg-brand-50 text-brand-600">
                <KeyRound size={18} aria-hidden />
              </div>
              <div>
                <h2
                  id="doi-mat-khau-title"
                  className="text-base font-semibold text-ink"
                >
                  Đổi mật khẩu cá nhân
                </h2>
                {staffName && (
                  <p className="text-xs text-ink-muted">{staffName}</p>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={handleClose}
              disabled={busy}
              className="rounded-control p-1 text-ink-muted transition-colors hover:bg-surface-tint hover:text-ink disabled:opacity-50"
              aria-label="Đóng"
            >
              <X size={18} aria-hidden />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div>
              <label
                htmlFor="old-password"
                className="mb-1 block text-xs font-medium text-ink"
              >
                Mật khẩu hiện tại
              </label>
              <input
                id="old-password"
                type="password"
                autoFocus
                aria-required="true"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                disabled={busy}
                autoComplete="current-password"
                placeholder="Nhập mật khẩu đang dùng"
                className="w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-brand-600 focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
              />
            </div>

            <div>
              <label
                htmlFor="new-password"
                className="mb-1 block text-xs font-medium text-ink"
              >
                Mật khẩu mới
              </label>
              <input
                id="new-password"
                type="password"
                aria-required="true"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                disabled={busy}
                autoComplete="new-password"
                placeholder={`Tối thiểu ${MIN_PASSWORD} ký tự`}
                className="w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-brand-600 focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
              />
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="mb-1 block text-xs font-medium text-ink"
              >
                Nhập lại mật khẩu mới
              </label>
              <input
                id="confirm-password"
                type="password"
                aria-required="true"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={busy}
                autoComplete="new-password"
                placeholder="Nhập lại chính xác mật khẩu mới"
                className="w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-brand-600 focus:ring-2 focus:ring-brand-200 disabled:opacity-50"
              />
            </div>

            {msg && (
              <p
                className={`rounded-control p-2.5 text-xs ${
                  msg.kind === "ok"
                    ? "bg-success-bg text-success"
                    : "bg-danger-bg text-danger"
                }`}
              >
                {msg.text}
              </p>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={handleClose}
                disabled={busy}
              >
                Huỷ
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={busy || !oldPassword || !newPassword || !confirmPassword}
              >
                {busy ? "Đang xử lý..." : "Lưu thay đổi"}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>,
    document.body,
  );
}
