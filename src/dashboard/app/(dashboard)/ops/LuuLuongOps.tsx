"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Lock,
  ShieldAlert,
  RefreshCw,
  KeyRound,
  ArrowRight,
  Activity,
  Smartphone,
  Laptop,
  Globe,
  Clock,
  CheckCircle2,
  TrendingUp,
} from "lucide-react";

interface TrafficData {
  updated_at: string;
  total: number;
  hours: Record<string, number>;
  devices: Record<string, number>;
  top_ips: Record<string, number>;
  top_routes: Record<string, number>;
  statuses: {
    ok?: number;
    client_err?: number;
    server_err?: number;
  };
}

function fmtNum(n: number): string {
  return new Intl.NumberFormat("vi-VN").format(n);
}

export default function LuuLuongOps() {
  const [pin, setPin] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TrafficData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [hoveredHour, setHoveredHour] = useState<{ hour: string; count: number } | null>(null);

  const fetchTrafficData = useCallback(async (pinToUse: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/ops/traffic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: pinToUse }),
      });
      const resJson = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(resJson.message || resJson.error || "Mã PIN không chính xác");
      }
      if (resJson.data) {
        setData(resJson.data);
        setIsUnlocked(true);
        sessionStorage.setItem("clinicai_ops_traffic_pin", pinToUse);
      } else {
        throw new Error("Không có dữ liệu lưu lượng.");
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

  useEffect(() => {
    const savedPin = sessionStorage.getItem("clinicai_ops_traffic_pin");
    if (savedPin) {
      setPin(savedPin);
      fetchTrafficData(savedPin);
    }
  }, [fetchTrafficData]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!pin.trim()) {
      setError("Vui lòng nhập mã PIN");
      return;
    }
    fetchTrafficData(pin.trim());
  };

  const handleLock = () => {
    sessionStorage.removeItem("clinicai_ops_traffic_pin");
    setIsUnlocked(false);
    setData(null);
    setPin("");
    setError(null);
  };

  if (!isUnlocked || !data) {
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

  // Phân tích chỉ số cao điểm
  const hourEntries = Object.entries(data.hours || {});
  const maxHourVal = Math.max(...hourEntries.map(([, v]) => v), 1);
  const peakHour = hourEntries.reduce(
    (max, cur) => (cur[1] > max[1] ? cur : max),
    ["—", 0]
  );

  const okRate =
    data.total > 0
      ? (((data.statuses?.ok ?? data.total) / data.total) * 100).toFixed(1)
      : "100";

  return (
    <main className="page-in flex min-w-0 flex-col gap-5 p-4 lg:p-5">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-surface p-4 shadow-card">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 ring-4 ring-emerald-100 animate-pulse" />
            <h1 className="text-lg font-semibold text-ink lg:text-xl">
              Lưu lượng & Thiết bị truy cập
            </h1>
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            Dữ liệu máy chủ Caddy tổng hợp 24 giờ qua · Cập nhật lúc {data.updated_at}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchTrafficData(pin)}
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

      {/* 4 Thẻ chỉ số chính */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-card border border-line bg-surface p-4 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-muted">Tổng lượt gọi (24h)</span>
            <span className="rounded-chip bg-brand-50 p-2 text-brand-600">
              <Activity size={18} />
            </span>
          </div>
          <div className="mt-3 text-2xl font-bold tracking-tight text-ink">
            {fmtNum(data.total)}
          </div>
          <p className="mt-1 text-xs text-ink-muted">Bao gồm toàn bộ trang & API</p>
        </div>

        <div className="rounded-card border border-line bg-surface p-4 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-muted">Giờ cao điểm nhất</span>
            <span className="rounded-chip bg-amber-50 p-2 text-amber-600">
              <TrendingUp size={18} />
            </span>
          </div>
          <div className="mt-3 text-2xl font-bold tracking-tight text-amber-600">
            {peakHour[0]}
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            {fmtNum(peakHour[1])} lượt request trong khung giờ này
          </p>
        </div>

        <div className="rounded-card border border-line bg-surface p-4 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-muted">Độ tin cậy HTTP</span>
            <span className="rounded-chip bg-emerald-50 p-2 text-emerald-600">
              <CheckCircle2 size={18} />
            </span>
          </div>
          <div className="mt-3 text-2xl font-bold tracking-tight text-emerald-600">
            {okRate}%
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            {fmtNum(data.statuses?.ok ?? 0)} lượt phản hồi thành công
          </p>
        </div>

        <div className="rounded-card border border-line bg-surface p-4 shadow-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-muted">Địa chỉ mạng chính</span>
            <span className="rounded-chip bg-blue-50 p-2 text-blue-600">
              <Globe size={18} />
            </span>
          </div>
          <div className="mt-3 text-2xl font-bold tracking-tight text-ink">
            {Object.keys(data.top_ips || {}).length} Mạng IP
          </div>
          <p className="mt-1 text-xs text-ink-muted">Đường truyền phòng khám kết nối</p>
        </div>
      </section>

      {/* Biểu đồ lượng request theo từng khung giờ */}
      <section className="rounded-card border border-line bg-surface p-5 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-4">
          <div>
            <h2 className="text-sm font-semibold text-ink flex items-center gap-2">
              <Clock size={16} className="text-brand-600" />
              <span>Phân bổ lưu lượng theo từng giờ (24 giờ qua)</span>
            </h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              Biết chính xác thời điểm phòng khám hoạt động đông nhất trong ngày.
            </p>
          </div>
          {hoveredHour && (
            <div className="rounded-control bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700 animate-fadeIn">
              Khung {hoveredHour.hour}: {fmtNum(hoveredHour.count)} lượt (
              {((hoveredHour.count / data.total) * 100).toFixed(1)}%)
            </div>
          )}
        </div>

        {/* Cột đồ thị */}
        <div className="mt-6 flex h-48 items-end gap-1 sm:gap-2 pt-6">
          {hourEntries.map(([hour, count]) => {
            const heightPercent = Math.max(Math.round((count / maxHourVal) * 100), 4);
            const isPeak = count === peakHour[1];
            return (
              <div
                key={hour}
                className="group relative flex flex-1 flex-col items-center h-full justify-end"
                onMouseEnter={() => setHoveredHour({ hour, count })}
                onMouseLeave={() => setHoveredHour(null)}
              >
                <div
                  style={{ height: `${heightPercent}%` }}
                  className={`w-full rounded-t transition-all duration-300 group-hover:brightness-110 ${
                    isPeak
                      ? "bg-gradient-to-t from-amber-500 to-amber-400 shadow-sm"
                      : "bg-gradient-to-t from-brand-600 to-brand-400 group-hover:from-brand-500 group-hover:to-brand-300"
                  }`}
                />
                <span className="mt-2 text-[10px] text-ink-muted group-hover:text-ink font-mono scale-90 sm:scale-100">
                  {hour.split(":")[0]}h
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Hai cột: Thiết bị & Top đường dẫn */}
      <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Cột 1: Thiết bị truy cập */}
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          <h2 className="text-sm font-semibold text-ink flex items-center gap-2 border-b border-line pb-3">
            <Smartphone size={16} className="text-brand-600" />
            <span>Nền tảng & Thiết bị</span>
          </h2>

          <div className="mt-4 space-y-4">
            {Object.entries(data.devices || {}).map(([device, count]) => {
              const pct = data.total > 0 ? ((count / data.total) * 100).toFixed(1) : "0";
              const isPc = device.includes("Windows") || device.includes("macOS");
              return (
                <div key={device}>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-ink flex items-center gap-1.5">
                      {isPc ? <Laptop size={14} className="text-ink-muted" /> : <Smartphone size={14} className="text-ink-muted" />}
                      {device}
                    </span>
                    <span className="text-ink-muted font-mono">
                      {fmtNum(count)} ({pct}%)
                    </span>
                  </div>
                  <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                    <div
                      style={{ width: `${pct}%` }}
                      className={`h-full rounded-full ${
                        device.includes("Windows")
                          ? "bg-blue-500"
                          : device.includes("Mac")
                            ? "bg-purple-500"
                            : device.includes("Android")
                              ? "bg-emerald-500"
                              : "bg-amber-500"
                      }`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Cột 2: Top nghiệp vụ & Mạng IP */}
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          <h2 className="text-sm font-semibold text-ink flex items-center gap-2 border-b border-line pb-3">
            <Globe size={16} className="text-brand-600" />
            <span>Địa chỉ mạng & Nghiệp vụ hàng đầu</span>
          </h2>

          <div className="mt-4 space-y-4">
            <div>
              <p className="text-xs font-semibold text-ink-muted mb-2 uppercase tracking-wide">
                Trang & Dịch vụ gọi nhiều nhất
              </p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(data.top_routes || {})
                  .slice(0, 8)
                  .map(([route, count]) => (
                    <span
                      key={route}
                      className="inline-flex items-center gap-1 rounded-control border border-line bg-surface-muted px-2.5 py-1 text-xs font-medium text-ink"
                    >
                      <span className="font-mono text-ink-muted">{route}</span>
                      <span className="rounded bg-brand-100 px-1.5 py-0.2 text-[10px] font-bold text-brand-700">
                        {fmtNum(count)}
                      </span>
                    </span>
                  ))}
              </div>
            </div>

            <div className="pt-2">
              <p className="text-xs font-semibold text-ink-muted mb-2 uppercase tracking-wide">
                Mạng phòng khám gửi request chính
              </p>
              <div className="space-y-2">
                {Object.entries(data.top_ips || {})
                  .slice(0, 4)
                  .map(([ip, count]) => {
                    const pct = data.total > 0 ? ((count / data.total) * 100).toFixed(1) : "0";
                    return (
                      <div
                        key={ip}
                        className="flex items-center justify-between rounded-control border border-line bg-surface px-3 py-2 text-xs"
                      >
                        <span className="font-mono font-medium text-ink">{ip}</span>
                        <span className="text-ink-muted font-mono">
                          {fmtNum(count)} lượt ({pct}%)
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
