"use client";

// POSTs to /api/admin/users. The server side validates that the caller
// is an admin again (defense in depth — never trust the client).

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface StaffOption {
  id: string;
  label: string;
}

const MIN_PASSWORD = 8;

export default function NewUserForm({
  staffOptions,
}: {
  staffOptions: StaffOption[];
}) {
  const router = useRouter();
  const [staffId, setStaffId] = useState(staffOptions[0]?.id ?? "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (!staffId) {
      setError("Chọn nhân viên để link.");
      return;
    }
    if (password.length < MIN_PASSWORD) {
      setError(`Mật khẩu phải có ít nhất ${MIN_PASSWORD} ký tự.`);
      return;
    }
    setLoading(true);
    const res = await fetch("/api/admin/users", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password, staffId }),
    });
    const body = (await res.json()) as {
      ok?: boolean;
      error?: string;
      staffName?: string;
      email?: string;
    };
    setLoading(false);
    if (!res.ok || !body.ok) {
      setError(body.error ?? `Lỗi máy chủ (${res.status})`);
      return;
    }
    setSuccess(
      `Đã tạo tài khoản ${body.email} và link với ${body.staffName}.`,
    );
    setEmail("");
    setPassword("");
    // Refresh so the Settings staff list sees the new linked row when
    // the operator goes back.
    router.refresh();
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="max-w-md space-y-4 rounded-lg border border-[#e4e4e7] bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
    >
      <div className="space-y-1">
        <label
          htmlFor="staff"
          className="text-sm font-medium text-[#4d4d4d]"
        >
          Nhân viên
        </label>
        <select
          id="staff"
          required
          value={staffId}
          onChange={(e) => setStaffId(e.target.value)}
          className="w-full rounded-md border border-[#e4e4e7] px-3 py-2.5 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:py-2 sm:text-sm"
        >
          {staffOptions.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label htmlFor="email" className="text-sm font-medium text-[#4d4d4d]">
          Email đăng nhập
        </label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-md border border-[#e4e4e7] px-3 py-2.5 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:py-2 sm:text-sm"
          autoComplete="off"
        />
      </div>

      <div className="space-y-1">
        <label
          htmlFor="password"
          className="text-sm font-medium text-[#4d4d4d]"
        >
          Mật khẩu tạm thời
        </label>
        <input
          id="password"
          type="text"
          required
          minLength={MIN_PASSWORD}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-md border border-[#e4e4e7] px-3 py-2.5 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:py-2 sm:text-sm"
          autoComplete="off"
          placeholder="Gửi cho NV qua kênh an toàn — NV sẽ tự đổi sau đăng nhập đầu"
        />
        <p className="text-xs text-[#888888]">
          Tối thiểu {MIN_PASSWORD} ký tự. NV nên đổi mật khẩu lần đăng nhập
          đầu (Quên mật khẩu → đặt lại).
        </p>
      </div>

      {error && (
        <p className="rounded bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error}
        </p>
      )}

      {success && (
        <p className="rounded bg-[#dcfce7] px-3 py-2 text-sm text-[#15803d]">
          {success}
        </p>
      )}

      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
        <button
          type="submit"
          disabled={loading}
          className="min-h-11 w-full rounded-md bg-[#ec4899] px-3.5 py-2.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-[#db2777] active:bg-[#db2777] disabled:opacity-50 sm:min-h-0 sm:w-auto sm:py-2"
        >
          {loading ? "Đang tạo..." : "Tạo tài khoản"}
        </button>
        <Link
          href="/settings"
          className="py-2 text-center text-sm text-[#71717a] hover:text-[#171717] sm:py-0"
        >
          ← Về Cài đặt
        </Link>
      </div>
    </form>
  );
}
