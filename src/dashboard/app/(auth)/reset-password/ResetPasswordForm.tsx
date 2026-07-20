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
    <div className="flex min-h-screen items-center justify-center bg-[#fafafa] px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
      >
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold text-[#171717]">
            <span className="h-2 w-2 rounded-full bg-[#ec4899]" />
            Đặt lại mật khẩu
          </h1>
          {stage === "ready" && (
            <p className="text-sm text-[#888888]">Chọn mật khẩu mới.</p>
          )}
        </div>

        {stage === "waiting" && (
          <p className="text-sm text-[#888888]">Đang xác thực link...</p>
        )}

        {stage === "no-session" && (
          <>
            <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
              Link đặt lại không hợp lệ hoặc đã hết hạn.
            </div>
            <Link
              href="/forgot-password"
              className="block text-center text-sm text-[#ec4899] hover:underline"
            >
              Yêu cầu link mới
            </Link>
          </>
        )}

        {stage === "done" && (
          <>
            <div className="rounded-md bg-[#dcfce7] px-3 py-2 text-sm text-[#15803d]">
              Đặt lại mật khẩu thành công. Đang chuyển về trang đăng nhập...
            </div>
            <Link
              href="/login"
              className="block text-center text-sm text-[#ec4899] hover:underline"
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
                className="text-sm font-medium text-[#4d4d4d]"
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
                className="w-full rounded-md border border-[#e4e4e7] px-3 py-2.5 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:py-2 sm:text-sm"
                autoComplete="new-password"
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="confirm"
                className="text-sm font-medium text-[#4d4d4d]"
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
                className="w-full rounded-md border border-[#e4e4e7] px-3 py-2.5 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:py-2 sm:text-sm"
                autoComplete="new-password"
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
              {loading ? "Đang lưu..." : "Đặt mật khẩu mới"}
            </button>
          </>
        )}
      </form>
    </div>
  );
}
