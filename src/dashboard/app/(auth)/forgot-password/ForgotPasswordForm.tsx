"use client";

// Forgot-password step 1 — send a magic-link reset email via Supabase
// Auth ``resetPasswordForEmail``. The link target is ``/reset-password``;
// Supabase appends the recovery token as a URL hash that ``reset-password``
// reads via ``supabase.auth.exchangeCodeForSession``.

import { useState } from "react";
import Link from "next/link";
import { getSupabaseBrowser } from "../../../lib/supabase-browser";

const REDIRECT_PATH = "/reset-password";

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const supabase = getSupabaseBrowser();
    const redirectTo =
      typeof window !== "undefined"
        ? `${window.location.origin}${REDIRECT_PATH}`
        : REDIRECT_PATH;
    const { error: authError } = await supabase.auth.resetPasswordForEmail(
      email,
      { redirectTo },
    );
    setLoading(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    setSent(true);
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#fafafa] px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
      >
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold text-[#171717]">
            <span className="h-2 w-2 rounded-full bg-[#ec4899]" />
            Quên mật khẩu
          </h1>
          <p className="text-sm text-[#888888]">
            Nhập email tài khoản để nhận link đặt lại mật khẩu.
          </p>
        </div>

        {sent ? (
          <div className="space-y-3">
            <div className="rounded-md bg-[#dcfce7] px-3 py-2 text-sm text-[#15803d]">
              Đã gửi email đặt lại mật khẩu đến <strong>{email}</strong>. Kiểm
              tra hộp thư và bấm vào link để tiếp tục.
            </div>
            <p className="text-xs text-[#888888]">
              Không thấy email? Kiểm tra Spam hoặc liên hệ quản trị viên.
            </p>
            <Link
              href="/login"
              className="block text-center text-sm text-[#ec4899] hover:underline"
            >
              ← Về trang đăng nhập
            </Link>
          </div>
        ) : (
          <>
            <div className="space-y-1">
              <label
                htmlFor="email"
                className="text-sm font-medium text-[#4d4d4d]"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md border border-[#e4e4e7] px-3 py-2.5 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:py-2 sm:text-sm"
                autoComplete="email"
              />
            </div>

            {error && (
              <p className="rounded bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="min-h-11 w-full rounded-md bg-[#ec4899] px-3 py-2.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-[#db2777] active:bg-[#db2777] disabled:opacity-50"
            >
              {loading ? "Đang gửi..." : "Gửi link đặt lại"}
            </button>

            <Link
              href="/login"
              className="block text-center text-sm text-[#ec4899] hover:underline"
            >
              ← Về trang đăng nhập
            </Link>
          </>
        )}
      </form>
    </div>
  );
}
