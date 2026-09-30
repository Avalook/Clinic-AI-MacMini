"use client";

import { useState, useEffect, useCallback } from "react";
import { Lock, ShieldAlert, RefreshCw, KeyRound, ArrowRight } from "lucide-react";

export default function LuuLuongOps() {
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);
  const [htmlContent, setHtmlContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUnlocked, setIsUnlocked] = useState(false);

  const fetchTrafficReport = useCallback(async (pinToUse: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/ops/traffic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: pinToUse }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.message || data.error || "Mã PIN không chính xác");
      }
      if (data.html) {
        setHtmlContent(data.html);
        setIsUnlocked(true);
        sessionStorage.setItem("clinicai_ops_traffic_pin", pinToUse);
      } else {
        throw new Error("Không nhận được nội dung báo cáo.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Đã có lỗi xảy ra";
      setError(msg);
      setIsUnlocked(false);
      sessionStorage.removeItem("clinicai_ops_traffic_pin");
    } finally {
      setLoading(false);
    }
  }, []);

  // Tự động kiểm tra phiên nếu đã nhập PIN trước đó
  useEffect(() => {
    const savedPin = sessionStorage.getItem("clinicai_ops_traffic_pin");
    if (savedPin) {
      setPin(savedPin);
      fetchTrafficReport(savedPin);
    }
  }, [fetchTrafficReport]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!pin.trim()) {
      setError("Vui lòng nhập mã PIN");
      return;
    }
    fetchTrafficReport(pin.trim());
  };

  const handleLock = () => {
    sessionStorage.removeItem("clinicai_ops_traffic_pin");
    setIsUnlocked(false);
    setHtmlContent(null);
    setPin("");
    setError(null);
  };

  if (!isUnlocked) {
    return (
      <main className="flex min-h-[500px] flex-col items-center justify-center p-4">
        <div className="w-full max-w-md rounded-card border border-line bg-surface p-6 shadow-card transition-all sm:p-8">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-control bg-brand-50 text-brand-600">
            <Lock size={28} />
          </div>

          <h2 className="mt-4 text-center text-lg font-semibold text-ink sm:text-xl">
            Lưu lượng & Thiết bị
          </h2>
          <p className="mt-1.5 text-center text-sm text-ink-muted">
            Khu vực giám sát máy chủ. Vui lòng nhập mã PIN quản trị để tiếp tục.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="pin-input" className="sr-only">
                Mã PIN
              </label>
              <div className="relative">
                <input
                  id="pin-input"
                  type="password"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  placeholder="Nhập mã PIN..."
                  autoFocus
                  className="w-full rounded-control border border-line bg-surface px-4 py-2.5 pl-10 text-center text-lg tracking-widest text-ink shadow-control outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                />
                <KeyRound
                  size={18}
                  className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint"
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-control border border-danger/20 bg-danger-bg p-3 text-xs text-danger">
                <ShieldAlert size={16} className="shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-control bg-brand-600 py-2.5 font-medium text-white shadow-control transition hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  <span>Đang kiểm tra...</span>
                </>
              ) : (
                <>
                  <span>Mở khoá báo cáo</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <main className="page-in flex min-w-0 flex-col gap-3 p-4 lg:p-5">
      <header className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-surface px-4 py-3 shadow-card">
        <div>
          <h1 className="text-base font-semibold text-ink lg:text-lg">
            Báo cáo lưu lượng & thiết bị truy cập
          </h1>
          <p className="text-xs text-ink-muted">
            Dữ liệu tổng hợp từ Caddy Access Log qua GoAccess trong 24 giờ qua.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchTrafficReport(pin)}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-control border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink shadow-control transition hover:bg-surface-muted disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            <span>Làm mới</span>
          </button>
          <button
            onClick={handleLock}
            className="flex items-center gap-1.5 rounded-control border border-line bg-surface px-3 py-1.5 text-xs font-medium text-danger shadow-control transition hover:bg-danger-bg"
          >
            <Lock size={14} />
            <span>Khoá lại</span>
          </button>
        </div>
      </header>

      {htmlContent && (
        <div className="relative min-w-0 flex-1 overflow-hidden rounded-card border border-line bg-surface shadow-card">
          <iframe
            title="Báo cáo lưu lượng GoAccess"
            srcDoc={htmlContent}
            className="h-[calc(100vh-180px)] min-h-[600px] w-full border-0"
            sandbox="allow-scripts allow-same-origin"
          />
        </div>
      )}
    </main>
  );
}
