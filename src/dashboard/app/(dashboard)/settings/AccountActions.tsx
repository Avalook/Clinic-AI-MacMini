"use client";

// Per-row account actions on the Settings staff table.
// Calls PATCH /api/admin/users (máy chủ gác lại quyền `account.manage`).
//
// Thao tác tại chỗ (không window.alert/confirm):
//   - "Đổi tên đăng nhập": hiện ô tên + Lưu/Huỷ.
//   - "Đặt lại mật khẩu": hiện ô mật khẩu + Lưu/Huỷ.
//   - "Gỡ tài khoản": gỡ nối + khoá app_credential + xoá login GoTrue.
//   - "Khoá & nghỉ việc": cấm đăng nhập (GoTrue ban) + deactivate membership.
//     Nếu còn ca trực tương lai (work_roster) → cho chọn gỡ ca hoặc giữ.
//   - "Mở lại": gỡ cấm đăng nhập (GoTrue unban) + activate membership.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  DUOI_TEN_DANG_NHAP,
  emailTuTenDangNhap,
  loiTenDangNhap,
  tenHienThi,
} from "../../../lib/ten-dang-nhap";

const MIN_PASSWORD = 8;

interface FutureShift {
  id: string;
  work_date: string;
  shift: string;
  station: string;
  status?: string;
}

/** Bảng tên đăng nhập, nạp MỘT LẦN cho cả bảng. */
let nickDangNap: Promise<Record<string, string>> | null = null;
function napNick(): Promise<Record<string, string>> {
  nickDangNap ??= fetch("/api/admin/users")
    .then((r) => (r.ok ? r.json() : { emails: {} }))
    .then((d: { emails?: Record<string, string> }) => d.emails ?? {})
    .catch(() => ({}));
  return nickDangNap;
}

type Mode =
  | "idle"
  | "reset"
  | "email"
  | "confirmUnlink"
  | "confirmBan"
  | "confirmUnban";

export default function AccountActions({
  staffId,
  staffName,
  isActive = true,
  hasAuthUser = true,
}: {
  staffId: string;
  staffName: string;
  isActive?: boolean;
  hasAuthUser?: boolean;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("idle");
  const [password, setPassword] = useState("");
  const [nick, setNick] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [futureShifts, setFutureShifts] = useState<FutureShift[]>([]);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  useEffect(() => {
    if (!hasAuthUser) return;
    let bo = false;
    napNick().then((m) => {
      if (bo) return;
      const mail = m[staffId] ? tenHienThi(m[staffId]) : null;
      setNick(mail);
      setEmail(mail ?? "");
    });
    return () => {
      bo = true;
    };
  }, [staffId, hasAuthUser]);

  function reset() {
    setMode("idle");
    setPassword("");
    setEmail(nick ?? "");
    setFutureShifts([]);
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
    const data = (await res.json()) as {
      ok?: boolean;
      error?: string;
      warning?: string;
    };
    setBusy(false);
    if (!res.ok || !data.ok) {
      setMsg({
        kind: "err",
        text: data.error ?? `Lỗi máy chủ (${res.status})`,
      });
      return false;
    }
    if (data.warning) setMsg({ kind: "err", text: data.warning });
    return true;
  }

  async function submitReset() {
    if (password.length < MIN_PASSWORD) {
      setMsg({
        kind: "err",
        text: `Mật khẩu tối thiểu ${MIN_PASSWORD} ký tự.`,
      });
      return;
    }
    const ok = await call({ staffId, action: "reset_password", password });
    if (ok) {
      setMsg({ kind: "ok", text: `Đã đặt lại mật khẩu cho ${staffName}.` });
      reset();
    }
  }

  async function submitEmail() {
    const loi = loiTenDangNhap(email);
    if (loi) {
      setMsg({ kind: "err", text: loi });
      return;
    }
    const moi = emailTuTenDangNhap(email);
    const ok = await call({ staffId, action: "change_email", email: moi });
    if (ok) {
      setMsg({
        kind: "ok",
        text: `${staffName} đăng nhập bằng ${tenHienThi(moi)} từ giờ.`,
      });
      setNick(tenHienThi(moi));
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

  async function handleStartBan() {
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch(
        `/api/admin/users?action=future_shifts&staffId=${encodeURIComponent(staffId)}`,
      );
      if (res.ok) {
        const data = (await res.json()) as {
          ok?: boolean;
          shifts?: FutureShift[];
        };
        setFutureShifts(data.shifts ?? []);
      } else {
        setFutureShifts([]);
      }
    } catch {
      setFutureShifts([]);
    } finally {
      setBusy(false);
      setMode("confirmBan");
    }
  }

  async function submitBan(goCaTruc: boolean) {
    const ok = await call({ staffId, action: "ban_staff", goCaTruc });
    setMode("idle");
    if (ok) {
      setMsg({
        kind: "ok",
        text: `Đã khoá & đánh dấu nghỉ việc cho ${staffName}.`,
      });
      router.refresh();
    }
  }

  async function submitUnban() {
    const ok = await call({ staffId, action: "unban_staff" });
    setMode("idle");
    if (ok) {
      setMsg({
        kind: "ok",
        text: `Đã mở lại tài khoản và kích hoạt nhân sự ${staffName}.`,
      });
      router.refresh();
    }
  }

  return (
    <div className="space-y-1.5">
      {mode === "idle" && nick && (
        <p className="font-mono text-label text-ink-muted">{nick}</p>
      )}

      {mode === "idle" && (
        <div className="flex flex-wrap items-center gap-2">
          {hasAuthUser && (
            <>
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
            </>
          )}

          {isActive ? (
            <button
              type="button"
              disabled={busy}
              onClick={handleStartBan}
              className="rounded border border-line px-2 py-1 text-xs text-ink-soft transition-colors hover:border-danger hover:text-danger disabled:opacity-50"
            >
              Khoá & nghỉ việc
            </button>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setMsg(null);
                setMode("confirmUnban");
              }}
              className="rounded border border-line px-2 py-1 text-xs text-success transition-colors hover:border-success hover:bg-success-bg disabled:opacity-50"
            >
              Mở lại
            </button>
          )}
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
          <span className="text-xs text-danger">
            Xoá login của {staffName}?
          </span>
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

      {mode === "confirmBan" && (
        <div className="rounded-control border border-danger/30 bg-danger-bg/50 p-2 text-xs space-y-2">
          {futureShifts.length > 0 ? (
            <>
              <p className="font-medium text-danger">
                {staffName} còn {futureShifts.length} ca trực sắp tới:
              </p>
              <ul className="max-h-24 overflow-y-auto space-y-1 rounded bg-surface p-1.5 border border-line font-mono text-meta text-ink-soft">
                {futureShifts.map((s) => (
                  <li key={s.id}>
                    • {s.work_date} · Ca {s.shift} · Vị trí {s.station}
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => submitBan(true)}
                  className="rounded-chip bg-danger px-2.5 py-1 text-xs font-medium text-surface hover:opacity-90 disabled:opacity-50"
                >
                  {busy ? "..." : "Gỡ khỏi các ca & Khoá"}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => submitBan(false)}
                  className="rounded-chip bg-warning px-2.5 py-1 text-xs font-medium text-surface hover:opacity-90 disabled:opacity-50"
                >
                  {busy ? "..." : "Giữ ca & Khoá"}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={reset}
                  className="text-xs text-ink-muted hover:text-ink"
                >
                  Huỷ
                </button>
              </div>
            </>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-danger font-medium">
                Khoá & nghỉ việc {staffName}?
              </span>
              <button
                type="button"
                disabled={busy}
                onClick={() => submitBan(false)}
                className="rounded-chip bg-danger px-2 py-1 text-xs font-medium text-surface disabled:opacity-50"
              >
                {busy ? "..." : "Xác nhận khoá"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={reset}
                className="text-xs text-ink-muted hover:text-ink"
              >
                Huỷ
              </button>
            </div>
          )}
        </div>
      )}

      {mode === "confirmUnban" && (
        <div className="flex flex-wrap items-center gap-2 rounded-control border border-success/30 bg-success-bg/50 p-2 text-xs">
          <span className="text-success font-medium">
            Mở lại và kích hoạt {staffName}?
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={submitUnban}
            className="rounded-chip bg-success px-2 py-1 text-xs font-medium text-surface disabled:opacity-50"
          >
            {busy ? "..." : "Xác nhận mở lại"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={reset}
            className="text-xs text-ink-muted hover:text-ink"
          >
            Huỷ
          </button>
        </div>
      )}

      {msg && (
        <p
          className={
            msg.kind === "ok" ? "text-xs text-success" : "text-xs text-danger"
          }
        >
          {msg.text}
        </p>
      )}
    </div>
  );
}
