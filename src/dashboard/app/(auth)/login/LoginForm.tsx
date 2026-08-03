"use client";

import { useActionState } from "react";
import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, Mail, Lock } from "lucide-react";
import { loginStaff } from "./actions";

export default function LoginForm() {
  const [state, formAction, pending] = useActionState(loginStaff, null);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-brand-50 via-white to-brand-100 px-4">
      {/* Subtle decorative circles */}
      <div className="pointer-events-none absolute -left-32 -top-32 h-80 w-80 rounded-full bg-brand-200/30 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-brand-100/40 blur-3xl" />

      <form
        action={formAction}
        className="animate-in fade-in slide-in-from-bottom-4 relative w-full max-w-sm space-y-5 rounded-2xl bg-white/90 p-7 shadow-[0_4px_24px_rgba(0,0,0,0.08)] backdrop-blur-sm duration-500"
      >
        {/* Logo + Context */}
        <div className="flex flex-col items-center space-y-2">
          <Image
            src="/clinicai-logo.svg"
            alt="ClinicAI"
            width={180}
            height={50}
            priority
            className="object-contain"
          />
          <p className="text-sm text-ink-muted">
            Đăng nhập bằng tài khoản cá nhân
          </p>
        </div>

        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-medium text-ink-soft">
            Email
          </label>
          <div className="relative">
            <Mail
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
            />
            <input
              id="email"
              name="email"
              type="email"
              required
              autoFocus
              autoComplete="email"
              placeholder="email@phongkham.vn"
              className="w-full rounded-lg border border-line pl-10 pr-3 py-2.5 text-base text-ink outline-none transition-all duration-200 focus:border-brand-600 focus:ring-2 focus:ring-brand-600/20 sm:py-2 sm:text-sm"
            />
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <label
              htmlFor="password"
              className="text-sm font-medium text-ink-soft"
            >
              Mật khẩu
            </label>
            <Link
              href="/forgot-password"
              className="text-xs text-brand-600 hover:underline"
            >
              Quên mật khẩu?
            </Link>
          </div>
          <div className="relative">
            <Lock
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
            />
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              placeholder="Nhập mật khẩu"
              className="w-full rounded-lg border border-line pl-10 pr-3 py-2.5 text-base text-ink outline-none transition-all duration-200 focus:border-brand-600 focus:ring-2 focus:ring-brand-600/20 sm:py-2 sm:text-sm"
            />
          </div>
        </div>

        {state?.error && (
          <p className="rounded-lg bg-danger-bg px-3 py-2 text-sm text-danger">
            {state.error}
          </p>
        )}

        <button
          type="submit"
          disabled={pending}
          className="min-h-11 w-full rounded-lg bg-brand-600 px-3 py-2.5 text-sm font-medium text-white shadow-sm transition-all duration-200 hover:bg-brand-700 hover:shadow-md active:bg-brand-700 disabled:opacity-50"
        >
          {pending ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>

        <div className="flex items-center justify-between text-xs text-ink-muted">
          <Link
            href="/enter"
            className="inline-flex items-center gap-1 text-brand-600 hover:underline"
          >
            <ArrowLeft size={12} />
            Quay lại cổng
          </Link>
          <span>Chưa có tài khoản? Liên hệ quản lý.</span>
        </div>
      </form>
    </div>
  );
}
