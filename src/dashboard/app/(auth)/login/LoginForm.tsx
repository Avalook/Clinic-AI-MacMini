"use client";

import { useActionState } from "react";
import Link from "next/link";
import { loginStaff } from "./actions";

export default function LoginForm() {
  const [state, formAction, pending] = useActionState(loginStaff, null);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#fafafa] px-4">
      <form
        action={formAction}
        className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
      >
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold text-[#171717]">
            <span className="h-2 w-2 rounded-full bg-[#ec4899]" />
            Đăng nhập
          </h1>
          <p className="text-sm text-[#888888]">
            Đăng nhập bằng tài khoản của bạn để vào thẳng phần việc của mình.
          </p>
        </div>

        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-medium text-[#4d4d4d]">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoFocus
            autoComplete="email"
            className="w-full rounded-md border border-[#e4e4e7] px-3 py-2.5 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:py-2 sm:text-sm"
          />
        </div>

        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <label
              htmlFor="password"
              className="text-sm font-medium text-[#4d4d4d]"
            >
              Mật khẩu
            </label>
            <Link
              href="/forgot-password"
              className="text-xs text-[#ec4899] hover:underline"
            >
              Quên mật khẩu?
            </Link>
          </div>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
            className="w-full rounded-md border border-[#e4e4e7] px-3 py-2.5 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:py-2 sm:text-sm"
          />
        </div>

        {state?.error && (
          <p className="rounded bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
            {state.error}
          </p>
        )}

        <button
          type="submit"
          disabled={pending}
          className="min-h-11 w-full rounded-md bg-[#ec4899] px-3 py-2.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-[#db2777] active:bg-[#db2777] disabled:opacity-50"
        >
          {pending ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>

        <p className="text-xs text-[#888888]">
          Chưa có tài khoản? Liên hệ quản lý phòng khám.
        </p>
      </form>
    </div>
  );
}
