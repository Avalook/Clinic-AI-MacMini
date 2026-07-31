"use client";

// Forgot-password step 2 — handles the recovery token Supabase puts in
// the URL hash after the magic-link click. The ssr browser client
// automatically exchanges that hash for a session on first read of
// ``getUser``; the form then calls ``auth.updateUser({ password })``.
//
// Three UI states:
// * "waiting"   — verifying the recovery session (≤1 sec)
// * "ready"     — show the new-password form
// * "no-session"— user landed here without a valid recovery link
// * "done"      — password updated; offer the login link

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getSupabaseBrowser } from "../../../lib/supabase-browser";

type Stage = "waiting" | "ready" | "no-session" | "done";

const MIN_PASSWORD = 8;

export default function ResetPasswordForm() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("waiting");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // The Supabase browser client reads the recovery hash on
    // initialisation and turns it into a session. Wait a tick, then
    // confirm a user is present.
    const supabase = getSupabaseBrowser();
    let cancelled = false;
    void supabase.auth.getSession().then(({ data }) => {
      if (cancelled) return;
      setStage(data.session ? "ready" : "no-session");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < MIN_PASSWORD) {
      setError(`Mật khẩu phải có ít nhất ${MIN_PASSWORD} ký tự.`);
      return;
    }
    if (password !== confirm) {
      setError("Mật khẩu xác nhận không khớp.");
      return;
    }
    setLoading(true);
    const supabase = getSupabaseBrowser();
    const { error: authError } = await supabase.auth.updateUser({
      password,
    });
    setLoading(false);
    if (authError) {
      setError(authError.message);
      return;
    }
    // Sign the user out so the new password is required next time.
    await supabase.auth.signOut();
    setStage("done");
    // Auto-bounce to login after a short pause so the success state is
    // visible.
    setTimeout(() => router.push("/login"), 2500);
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-muted px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
      >
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold text-ink">
            <span className="h-2 w-2 rounded-full bg-brand-600" />
            Đặt lại mật khẩu
          </h1>
          {stage === "ready" && (
            <p className="text-sm text-ink-muted">Chọn mật khẩu mới.</p>
          )}
        </div>

        {stage === "waiting" && (
          <p className="text-sm text-ink-muted">Đang xác thực link...</p>
        )}

        {stage === "no-session" && (
          <>
            <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
              Link đặt lại không hợp lệ hoặc đã hết hạn.
            </div>
            <Link
              href="/forgot-password"
              className="block text-center text-sm text-brand-600 hover:underline"
            >
              Yêu cầu link mới
            </Link>
          </>
        )}

        {stage === "done" && (
          <>
            <div className="rounded-md bg-success-bg px-3 py-2 text-sm text-success">
              Đặt lại mật khẩu thành công. Đang chuyển về trang đăng nhập...
            </div>
            <Link
              href="/login"
              className="block text-center text-sm text-brand-600 hover:underline"
            >
              Về trang đăng nhập ngay
            </Link>
          </>
        )}

        {stage === "ready" && (
          <>
            <div className="space-y-1">
              <label
                htmlFor="password"
                className="text-sm font-medium text-ink-soft"
              >
                Mật khẩu mới
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={MIN_PASSWORD}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md border border-line px-3 py-2.5 text-base text-ink outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-600/20 sm:py-2 sm:text-sm"
                autoComplete="new-password"
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="confirm"
                className="text-sm font-medium text-ink-soft"
              >
                Xác nhận mật khẩu
              </label>
              <input
                id="confirm"
                type="password"
                required
                minLength={MIN_PASSWORD}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full rounded-md border border-line px-3 py-2.5 text-base text-ink outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-600/20 sm:py-2 sm:text-sm"
                autoComplete="new-password"
              />
            </div>

            {error && (
              <p className="rounded bg-danger-bg px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="min-h-11 w-full rounded-md bg-brand-600 px-3 py-2.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-brand-700 active:bg-brand-700 disabled:opacity-50"
            >
              {loading ? "Đang lưu..." : "Đặt mật khẩu mới"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
