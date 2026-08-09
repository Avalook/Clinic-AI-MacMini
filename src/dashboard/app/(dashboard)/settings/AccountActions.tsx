"use client";

// Per-row account actions on the Settings staff table. Only rendered for
// staff that already have a linked login account. Calls PATCH
// /api/admin/users (the server re-checks the caller is MANAGEMENT).
//
// Ba việc, đều làm tại chỗ (không window.alert/confirm):
//   - "Đổi tên đăng nhập": hiện ô tên + Lưu/Huỷ. Gõ tên trần được, đuôi
//     mail do hệ thống gắn (xem lib/ten-dang-nhap.ts).
//   - "Đặt lại mật khẩu": hiện ô mật khẩu + Lưu/Huỷ.
//   - "Gỡ tài khoản": hai bước (bấm → "Xác nhận?") vì nó xoá hẳn tài khoản
//     đăng nhập, không lùi lại được.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  DUOI_TEN_DANG_NHAP,
  emailTuTenDangNhap,
  loiTenDangNhap,
} from "../../../lib/ten-dang-nhap";

const MIN_PASSWORD = 8;

/** Bảng tên đăng nhập, nạp MỘT LẦN cho cả bảng.
 *
 * Mỗi dòng là một component riêng, nên nếu mỗi dòng tự gọi API thì bảng 44
 * người là 44 lượt gọi cho cùng một câu trả lời. Giữ lời hứa ở tầng module để
 * mọi dòng cùng chờ đúng một lượt.
 */
let nickDangNap: Promise<Record<string, string>> | null = null;
function napNick(): Promise<Record<string, string>> {
  nickDangNap ??= fetch("/api/admin/users")
    .then((r) => (r.ok ? r.json() : { emails: {} }))
    .then((d: { emails?: Record<string, string> }) => d.emails ?? {})
    .catch(() => ({}));
  return nickDangNap;
}

type Mode = "idle" | "reset" | "email" | "confirmUnlink";

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
  const [nick, setNick] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  useEffect(() => {
    let bo = false;
    napNick().then((m) => {
      if (bo) return;
      const mail = m[staffId] ?? null;
      setNick(mail);
      setEmail(mail ?? "");
    });
    return () => {
      bo = true;
    };
  }, [staffId]);

  function reset() {
    setMode("idle");
    setPassword("");
    setEmail(nick ?? "");
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

  async function submitEmail() {
    // KHÔNG còn đòi phải là email. Gõ "cskhdieuhoa" là đủ — đuôi do
    // `emailTuTenDangNhap` gắn, cùng hàm mà màn đăng nhập dùng để tra.
    const loi = loiTenDangNhap(email);
    if (loi) {
      setMsg({ kind: "err", text: loi });
      return;
    }
    const moi = emailTuTenDangNhap(email);
    const ok = await call({ staffId, action: "change_email", email: moi });
    if (ok) {
      setMsg({ kind: "ok", text: `${staffName} đăng nhập bằng ${moi} từ giờ.` });
      setNick(moi);
      // Bảng nick đã cũ sau khi đổi — bỏ đi để lần sau nạp lại.
      nickDangNap = null;
      setMode("idle");
      setBusy(false);
      router.refresh();
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
      {/* Nick hiện tại hiện ngay tại chỗ. Không hiện thì quản lý phải bấm
          "Đổi tên đăng nhập" mới biết nick đang là gì — vào chế độ SỬA chỉ
          để ĐỌC. */}
      {mode === "idle" && nick && (
        <p className="font-mono text-[11px] text-ink-muted">{nick}</p>
      )}
      {mode === "idle" && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setMsg(null);
              setMode("email");
            }}
            className="rounded border border-line px-2 py-1 text-xs text-ink-soft transition-colors hover:border-brand-600 hover:text-brand-600"
          >
            Đổi tên đăng nhập
          </button>
          <button
            type="button"
            onClick={() => {
              setMsg(null);
              setMode("reset");
            }}
            className="rounded border border-line px-2 py-1 text-xs text-ink-soft transition-colors hover:border-brand-600 hover:text-brand-600"
          >
            Đặt lại mật khẩu
          </button>
          <button
            type="button"
            onClick={() => {
              setMsg(null);
              setMode("confirmUnlink");
            }}
            className="rounded border border-line px-2 py-1 text-xs text-ink-soft transition-colors hover:border-danger hover:text-danger"
          >
            Gỡ tài khoản
          </button>
        </div>
      )}

      {mode === "email" && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={email}
            autoFocus
            onChange={(e) => setEmail(e.target.value)}
            placeholder={`vd: bacsithanh (tự thêm @${DUOI_TEN_DANG_NHAP})`}
            autoComplete="off"
            className="w-full rounded-control border border-line bg-surface px-2 py-2 text-base text-ink outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-200 sm:w-64 sm:py-1 sm:text-xs"
          />
          <button
            type="button"
            disabled={busy}
            onClick={submitEmail}
            className="rounded-chip bg-brand-600 px-2 py-1 text-xs font-medium text-surface hover:bg-brand-700 disabled:opacity-50"
          >
            {busy ? "..." : "Lưu"}
          </button>
          <button
            type="button"
            onClick={reset}
            className="text-xs text-ink-muted hover:text-ink"
          >
            Huỷ
          </button>
        </div>
      )}

      {mode === "reset" && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="password"
            value={password}
            autoFocus
            onChange={(e) => setPassword(e.target.value)}
            placeholder={`Mật khẩu mới (≥${MIN_PASSWORD})`}
            autoComplete="new-password"
            className="w-full rounded-control border border-line bg-surface px-2 py-2 text-base text-ink outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-200 sm:w-48 sm:py-1 sm:text-xs"
          />
          <button
            type="button"
            disabled={busy}
            onClick={submitReset}
            className="rounded-chip bg-brand-600 px-2 py-1 text-xs font-medium text-surface hover:bg-brand-700 disabled:opacity-50"
          >
            {busy ? "..." : "Lưu"}
          </button>
          <button
            type="button"
            onClick={reset}
            className="text-xs text-ink-muted hover:text-ink"
          >
            Huỷ
          </button>
        </div>
      )}

      {mode === "confirmUnlink" && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-danger">Xoá login của {staffName}?</span>
          <button
            type="button"
            disabled={busy}
            onClick={submitUnlink}
            className="rounded-chip bg-danger px-2 py-1 text-xs font-medium text-surface disabled:opacity-50"
          >
            {busy ? "..." : "Xác nhận gỡ"}
          </button>
          <button
            type="button"
            onClick={() => setMode("idle")}
            className="text-xs text-ink-muted hover:text-ink"
          >
            Huỷ
          </button>
        </div>
      )}

      {msg && (
        <p
          className={
            msg.kind === "ok"
              ? "text-xs text-success"
              : "text-xs text-danger"
          }
        >
          {msg.text}
        </p>
      )}
    </div>
  );
}
