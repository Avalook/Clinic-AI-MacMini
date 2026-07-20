"use client";

// Per-row account actions on the Settings staff table. Only rendered for
// staff that already have a linked login account. Calls PATCH
// /api/admin/users (the server re-checks the caller is MANAGEMENT).
//
// Two actions, both inline (no window.alert/confirm — lint-safe + nicer):
//   - "Đặt lại mật khẩu": reveals a password input + Lưu/Huỷ.
//   - "Gỡ tài khoản": two-step (click → "Xác nhận?") to avoid an accidental
//     irreversible delete of the Auth user.

import { useState } from "react";
import { useRouter } from "next/navigation";

const MIN_PASSWORD = 8;

type Mode = "idle" | "reset" | "confirmUnlink";

export default function AccountActions({
  staffId,
  staffName,
}: {
  staffId: string;
  staffName: string;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("idle");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  function reset() {
    setMode("idle");
    setPassword("");
    setBusy(false);
  }

  async function call(body: Record<string, unknown>) {
    setBusy(true);
    setMsg(null);
    const res = await fetch("/api/admin/users", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = (await res.json()) as { ok?: boolean; error?: string; warning?: string };
    setBusy(false);
    if (!res.ok || !data.ok) {
      setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
      return false;
    }
    if (data.warning) setMsg({ kind: "err", text: data.warning });
    return true;
  }

  async function submitReset() {
    if (password.length < MIN_PASSWORD) {
      setMsg({ kind: "err", text: `Mật khẩu tối thiểu ${MIN_PASSWORD} ký tự.` });
      return;
    }
    const ok = await call({ staffId, action: "reset_password", password });
    if (ok) {
      setMsg({ kind: "ok", text: `Đã đặt lại mật khẩu cho ${staffName}.` });
      reset();
    }
  }

  async function submitUnlink() {
    const ok = await call({ staffId, action: "unlink" });
    setMode("idle");
    if (ok) {
      setMsg({ kind: "ok", text: `Đã gỡ tài khoản của ${staffName}.` });
      router.refresh();
    }
  }

  return (
    <div className="space-y-1.5">
      {mode === "idle" && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setMsg(null);
              setMode("reset");
            }}
            className="rounded border border-[#e4e4e7] px-2 py-1 text-xs text-[#4d4d4d] transition-colors hover:border-[#ec4899] hover:text-[#ec4899]"
          >
            Đặt lại mật khẩu
          </button>
          <button
            type="button"
            onClick={() => {
              setMsg(null);
              setMode("confirmUnlink");
            }}
            className="rounded border border-[#e4e4e7] px-2 py-1 text-xs text-[#4d4d4d] transition-colors hover:border-[#dc2626] hover:text-[#dc2626]"
          >
            Gỡ tài khoản
          </button>
        </div>
      )}

      {mode === "reset" && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={password}
            autoFocus
            onChange={(e) => setPassword(e.target.value)}
            placeholder={`Mật khẩu mới (≥${MIN_PASSWORD})`}
            className="w-full rounded-md border border-[#e4e4e7] px-2 py-2 text-base text-[#171717] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/20 sm:w-48 sm:py-1 sm:text-xs"
          />
          <button
            type="button"
            disabled={busy}
            onClick={submitReset}
            className="rounded bg-[#ec4899] px-2 py-1 text-xs font-medium text-white hover:bg-[#db2777] disabled:opacity-50"
          >
            {busy ? "..." : "Lưu"}
          </button>
          <button
            type="button"
            onClick={reset}
            className="text-xs text-[#71717a] hover:text-[#171717]"
          >
            Huỷ
          </button>
        </div>
      )}

      {mode === "confirmUnlink" && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-[#dc2626]">Xoá login của {staffName}?</span>
          <button
            type="button"
            disabled={busy}
            onClick={submitUnlink}
            className="rounded bg-[#dc2626] px-2 py-1 text-xs font-medium text-white hover:bg-[#b91c1c] disabled:opacity-50"
          >
            {busy ? "..." : "Xác nhận gỡ"}
          </button>
          <button
            type="button"
            onClick={() => setMode("idle")}
            className="text-xs text-[#71717a] hover:text-[#171717]"
          >
            Huỷ
          </button>
        </div>
      )}

      {msg && (
        <p
          className={
            msg.kind === "ok"
              ? "text-xs text-[#15803d]"
              : "text-xs text-[#dc2626]"
          }
        >
          {msg.text}
        </p>
      )}
    </div>
  );
}
