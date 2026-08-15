"use client";

// Toggle card to switch between CSKH_ONLY and FULL_CLINIC modes.
// Only MANAGEMENT sees this card. Calls PUT /api/config/feature-mode.

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Zap, Building2 } from "lucide-react";

const MODES = [
  {
    value: "CSKH_ONLY",
    label: "Chỉ CSKH & Đặt lịch",
    desc: "Chỉ hiện các màn hình CSKH, đặt lịch, quản lý. Ẩn phần lâm sàng (Bàn khám, Siêu âm, Thu ngân, Nhà thuốc).",
    icon: Zap,
    color: "text-amber-600",
    bg: "bg-amber-50 border-amber-200",
    active: "ring-2 ring-amber-400 border-amber-400",
  },
  {
    value: "FULL_CLINIC",
    label: "Đầy đủ phòng khám",
    desc: "Hiện tất cả tính năng: CSKH, Lâm sàng, Thu ngân, Nhà thuốc, Xét nghiệm.",
    icon: Building2,
    color: "text-brand-600",
    bg: "bg-brand-50 border-brand-200",
    active: "ring-2 ring-brand-400 border-brand-400",
  },
] as const;

export default function FeatureModeCard({
  currentMode,
}: {
  currentMode: string;
}) {
  const [mode, setMode] = useState(currentMode);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSwitch(newMode: string) {
    if (newMode === mode || isPending) return;
    setMode(newMode);
    startTransition(async () => {
      try {
        const res = await fetch("/api/config/feature-mode", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: newMode }),
        });
        if (!res.ok) {
          setMode(mode); // revert
          return;
        }
        router.refresh(); // re-render sidebar
      } catch {
        setMode(mode); // revert
      }
    });
  }

  return (
    <section className="rounded-card border border-line bg-surface p-4 shadow-card sm:p-5">
      <div className="mb-3">
        <h2 className="text-base font-semibold text-ink">
          Chế độ phòng khám
        </h2>
        <p className="mt-0.5 text-sm text-ink-muted">
          Chọn tính năng muốn bật. Khi phòng khám mới bắt đầu, hãy dùng
          &ldquo;Chỉ CSKH&rdquo; trước, sau khi quen tay thì mở đầy đủ.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {MODES.map((m) => {
          const selected = mode === m.value;
          const Icon = m.icon;
          return (
            <button
              key={m.value}
              type="button"
              disabled={isPending}
              onClick={() => handleSwitch(m.value)}
              className={`flex items-start gap-3 rounded-lg border p-4 text-left transition-all duration-200 ${
                m.bg
              } ${
                selected ? m.active : "hover:shadow-sm"
              } disabled:opacity-60`}
            >
              <Icon size={22} className={`shrink-0 mt-0.5 ${m.color}`} />
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-semibold ${m.color}`}>
                  {m.label}
                  {selected && (
                    <span className="ml-1.5 inline-flex items-center rounded-full bg-white/80 px-1.5 py-0.5 text-label font-medium text-ink-muted">
                      Đang dùng
                    </span>
                  )}
                </p>
                <p className="mt-0.5 text-xs text-ink-muted">{m.desc}</p>
              </div>
            </button>
          );
        })}
      </div>
      {isPending && (
        <p className="mt-2 text-xs text-ink-muted animate-pulse">
          Đang cập nhật...
        </p>
      )}
    </section>
  );
}
