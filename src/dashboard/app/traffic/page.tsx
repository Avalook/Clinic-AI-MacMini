"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Lock,
  ShieldAlert,
  RefreshCw,
  User,
  KeyRound,
  ArrowRight,
  Activity,
  Smartphone,
  Laptop,
  Globe,
  Clock,
  CheckCircle2,
  TrendingUp,
  LogOut,
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

export default function DirectTrafficPage() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TrafficData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [hoveredHour, setHoveredHour] = useState<{ hour: string; count: number } | null>(null);

  const handleLogin = useCallback(async (u: string, p: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/ops/traffic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p }),
      });
      const resJson = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(resJson.message || resJson.error || "Tài khoản hoặc mật khẩu không chính xác");
      }
      if (resJson.data) {
        setData(resJson.data);
        setIsUnlocked(true);
        sessionStorage.setItem("dr4women_traffic_u", u);
        sessionStorage.setItem("dr4women_traffic_p", p);
      } else {
        throw new Error("Không tìm thấy dữ liệu lưu lượng.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Đã có lỗi xảy ra";
      setError(msg);
      setIsUnlocked(false);
      sessionStorage.removeItem("dr4women_traffic_u");
      sessionStorage.removeItem("dr4women_traffic_p");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const savedU = sessionStorage.getItem("dr4women_traffic_u");
    const savedP = sessionStorage.getItem("dr4women_traffic_p");
    if (savedU && savedP) {
      // Nạp lại từ sessionStorage (dữ liệu ngoài) — cùng mẫu ChonDichVuKham.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setUsername(savedU);
      setPassword(savedP);
      void handleLogin(savedU, savedP);
    }
  }, [handleLogin]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Vui lòng điền đủ tài khoản và mật khẩu");
      return;
    }
    handleLogin(username.trim(), password.trim());
  };

  const handleLogout = () => {
    sessionStorage.removeItem("dr4women_traffic_u");
    sessionStorage.removeItem("dr4women_traffic_p");
    setIsUnlocked(false);
    setData(null);
    setPassword("");
    setError(null);
  };

  if (!isUnlocked || !data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
            <Lock size={26} />
          </div>

          <h1 className="mt-4 text-center text-xl font-bold text-slate-900">
            Quản trị Lưu lượng & Thiết bị
          </h1>
          <p className="mt-1 text-center text-xs text-slate-500">
            Khu vực giám sát máy chủ Dr4Women. Vui lòng đăng nhập để tiếp tục.
          </p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-700">Tên tài khoản</label>
              <div className="relative mt-1">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  required
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 pl-10 text-sm text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                />
                <User size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700">Mật khẩu</label>
              <div className="relative mt-1">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoFocus
                  required
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 pl-10 text-sm text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                />
                <KeyRound size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                <ShieldAlert size={16} className="shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  <span>Đang kiểm tra...</span>
                </>
              ) : (
                <>
                  <span>Đăng nhập hệ thống</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    );
  }

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
    <div className="min-h-screen bg-slate-50 p-4 sm:p-6 lg:p-8 text-slate-800">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="flex h-3 w-3 rounded-full bg-emerald-500 ring-4 ring-emerald-100 animate-pulse"></span>
              <h1 className="text-xl font-bold text-slate-900">Lưu lượng & Thiết bị truy cập hệ thống</h1>
              <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700">Dr4Women Live</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Dữ liệu máy chủ Caddy tổng hợp 24 giờ qua · Cập nhật lúc {data.updated_at}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => handleLogin(username, password)}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              Làm mới
            </button>
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-700 shadow-sm hover:bg-rose-100 transition"
            >
              <LogOut size={14} />
              Đăng xuất
            </button>
          </div>
        </header>

        {/* 4 Thẻ chỉ số */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Tổng lượt gọi (24h qua)</span>
              <span className="rounded-xl bg-indigo-50 p-2.5 text-indigo-600">
                <Activity size={20} />
              </span>
            </div>
            <div className="mt-3 text-3xl font-extrabold text-slate-900">{fmtNum(data.total)}</div>
            <p className="mt-1 text-xs text-slate-400">Bao gồm toàn bộ trang & API</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Giờ cao điểm nhất</span>
              <span className="rounded-xl bg-amber-50 p-2.5 text-amber-600">
                <TrendingUp size={20} />
              </span>
            </div>
            <div className="mt-3 text-3xl font-extrabold text-amber-600">{peakHour[0]}</div>
            <p className="mt-1 text-xs text-slate-400">{fmtNum(peakHour[1])} lượt trong khung giờ này</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Độ tin cậy máy chủ</span>
              <span className="rounded-xl bg-emerald-50 p-2.5 text-emerald-600">
                <CheckCircle2 size={20} />
              </span>
            </div>
            <div className="mt-3 text-3xl font-extrabold text-emerald-600">{okRate}%</div>
            <p className="mt-1 text-xs text-slate-400">{fmtNum(data.statuses?.ok ?? 0)} lượt phản hồi HTTP 200</p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">Mạng phòng khám chính</span>
              <span className="rounded-xl bg-blue-50 p-2.5 text-blue-600">
                <Globe size={20} />
              </span>
            </div>
            <div className="mt-3 text-3xl font-extrabold text-slate-900">{Object.keys(data.top_ips || {}).length} Địa chỉ IP</div>
            <p className="mt-1 text-xs text-slate-400">Thiết bị bác sĩ & quầy lễ tân</p>
          </div>
        </section>

        {/* Biểu đồ cột 24 giờ */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Clock size={16} className="text-indigo-600" />
                <span>Biểu đồ phân bổ lưu lượng theo từng giờ (24 giờ qua)</span>
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">Rê chuột vào từng cột để xem chi tiết số lượt và tỷ lệ % tải của phòng khám.</p>
            </div>
            {hoveredHour && (
              <div className="rounded-lg bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 animate-fadeIn">
                Khung {hoveredHour.hour}: {fmtNum(hoveredHour.count)} lượt ({((hoveredHour.count / data.total) * 100).toFixed(1)}%)
              </div>
            )}
          </div>

          <div className="mt-8 flex h-52 items-end gap-1.5 sm:gap-2.5 pt-6 px-2">
            {hourEntries.map(([hour, count]) => {
              const pct = Math.max(Math.round((count / maxHourVal) * 100), 6);
              const isPeak = count === peakHour[1];
              return (
                <div
                  key={hour}
                  className="group relative flex flex-1 flex-col items-center h-full justify-end cursor-pointer"
                  onMouseEnter={() => setHoveredHour({ hour, count })}
                  onMouseLeave={() => setHoveredHour(null)}
                >
                  <div
                    style={{ height: `${pct}%` }}
                    className={`w-full rounded-t-md transition-all duration-300 group-hover:brightness-110 ${
                      isPeak
                        ? "bg-gradient-to-t from-amber-500 to-amber-400 shadow-sm"
                        : "bg-gradient-to-t from-indigo-600 to-indigo-400 group-hover:from-indigo-500 group-hover:to-indigo-300"
                    }`}
                  />
                  <span className="mt-2 text-[10px] font-mono text-slate-400 group-hover:text-slate-800">
                    {hour.split(":")[0]}h
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        {/* Hai cột: Thiết bị & Top chức năng */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Cột 1: Thiết bị */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Smartphone size={16} className="text-indigo-600" />
              <span>Nền tảng & Thiết bị truy cập</span>
            </h2>

            <div className="mt-5 space-y-4">
              {Object.entries(data.devices || {}).map(([device, count]) => {
                const pct = data.total > 0 ? ((count / data.total) * 100).toFixed(1) : "0";
                const isPc = device.includes("Windows") || device.includes("Mac");
                return (
                  <div key={device}>
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                        {isPc ? <Laptop size={14} className="text-slate-500" /> : <Smartphone size={14} className="text-slate-500" />}
                        {device}
                      </span>
                      <span className="font-mono text-slate-500 font-semibold">
                        {fmtNum(count)} lượt ({pct}%)
                      </span>
                    </div>
                    <div className="h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">
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

          {/* Cột 2: Chức năng & IP */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-3">
              <Globe size={16} className="text-indigo-600" />
              <span>Chức năng & Mạng IP phòng khám</span>
            </h2>

            <div className="mt-5 space-y-4">
              <div>
                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Trang & Nghiệp vụ dùng nhiều nhất</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(data.top_routes || {})
                    .slice(0, 8)
                    .map(([route, count]) => (
                      <span
                        key={route}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700"
                      >
                        <span className="font-mono text-slate-600">{route}</span>
                        <span className="rounded bg-indigo-100 text-indigo-700 px-1.5 py-0.5 text-[10px] font-bold">
                          {fmtNum(count)}
                        </span>
                      </span>
                    ))}
                </div>
              </div>

              <div className="pt-2">
                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Mạng IP nội bộ phòng khám gửi request chính</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(data.top_ips || {})
                    .slice(0, 4)
                    .map(([ip, count]) => {
                      const pct = data.total > 0 ? ((count / data.total) * 100).toFixed(1) : "0";
                      return (
                        <div key={ip} className="rounded-xl border border-slate-100 bg-slate-50 p-2.5">
                          <p className="font-mono font-bold text-slate-800">{ip}</p>
                          <p className="text-[11px] text-slate-500 mt-0.5">{fmtNum(count)} lượt ({pct}%)</p>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
