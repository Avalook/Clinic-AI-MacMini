/**
 * Living style guide.
 *
 * Every token and primitive on one page, so a change to globals.css is checked
 * by looking rather than by finding out on a clinical screen. It sits outside
 * the (dashboard) group on purpose: it holds no patient data, so it must not
 * sit behind — or appear to need — a clinical session.
 */

import { notFound } from "next/navigation";

import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import Stepper from "@/components/ui/Stepper";
import {
  STATUS_PRESENTATION,
  UNSUPPORTED_BY_KERNEL,
  type DisplayStatus,
} from "@/lib/work-item-status";

export const metadata = { title: "ClinicAI — Hệ thiết kế" };

// Development only. A style guide is a tool for whoever is building, not a
// surface for a clinic to reach, and shipping it would publish the internal
// status vocabulary to anyone who guessed the URL.
function assertDev() {
  if (process.env.NODE_ENV !== "development") notFound();
}

const BRAND = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900];

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {note ? <p className="text-sm text-ink-muted">{note}</p> : null}
      </div>
      <div className="rounded-card border border-line bg-surface p-5 shadow-card">
        {children}
      </div>
    </section>
  );
}

export default function DesignSystemPage() {
  assertDev();
  const displayed = Object.keys(STATUS_PRESENTATION) as DisplayStatus[];

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 p-8">
      <header>
        <h1 className="text-2xl font-semibold text-ink">Hệ thiết kế ClinicAI</h1>
        <p className="text-sm text-ink-muted">
          Token và thành phần nền — đổi globals.css thì kiểm ở đây trước.
        </p>
      </header>

      <Section title="Màu thương hiệu" note="Teal mang hành động chính và mục nav đang chọn; không màu nào khác cạnh tranh với nó.">
        <div className="flex flex-wrap gap-2">
          {BRAND.map((s) => (
            <div key={s} className="flex flex-col items-center gap-1">
              <div
                className="h-14 w-16 rounded-control border border-line"
                style={{ background: `var(--color-brand-${s})` }}
              />
              <span className="text-xs text-ink-muted">{s}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="Trạng thái Work Item"
        note="Bộ icon đặt tên 12 trạng thái; kernel lưu 5. Phần còn lại suy ra được — xem lib/work-item-status.ts."
      >
        <div className="flex flex-wrap gap-2">
          {displayed.map((s) => (
            <StatusChip
              key={s}
              tone={STATUS_PRESENTATION[s].token as StatusTone}
              label={STATUS_PRESENTATION[s].label}
              size="md"
            />
          ))}
        </div>
        <p className="mt-4 text-sm text-ink-muted">
          Thiết kế có nhưng kernel <strong>chưa</strong> lưu được — UI không được
          hiển thị cho tới khi có lệnh thật:{" "}
          <code className="text-ink-soft">
            {UNSUPPORTED_BY_KERNEL.join(", ")}
          </code>
        </p>
      </Section>

      <Section title="Hàng chỉ số" note="Là bộ lọc, không phải trang trí: ô nào lọc được thì bấm được.">
        <StatRow>
          <StatCard label="Cần xử lý hôm nay" value={12} tone="brand" />
          <StatCard label="Quá SLA" value={3} tone="danger" />
          <StatCard label="Chờ xác nhận" value={8} tone="warning" />
          <StatCard label="Đã hoàn thành" value={24} tone="success" />
        </StatRow>
      </Section>

      <Section
        title="Stepper ngang — các bước con TRONG một node"
        note="Tiếp nhận (LUOTKHAM-01) là một work item duy nhất, gồm nhiều bước con."
      >
        <Stepper
          steps={[
            { label: "Vào hàng đợi", state: "done", detail: "10:10" },
            { label: "Đã gán quầy 2", state: "done", detail: "10:10" },
            { label: "Gọi bệnh nhân", state: "current", detail: "Chưa gọi" },
            { label: "Xác nhận có mặt", state: "upcoming", detail: "Chưa xác nhận" },
            { label: "Hoàn tất tiếp nhận", state: "upcoming", detail: "Chưa hoàn tất" },
          ]}
        />
      </Section>

      <Section
        title="Stepper dọc — chuỗi QUA nhiều node"
        note="Bốn work item riêng biệt, có cổng chặn giữa chúng."
      >
        <Stepper
          orientation="vertical"
          steps={[
            { label: "Đang thực hiện", state: "current", detail: "SA1 · 10:05" },
            { label: "Chờ thư ký hoàn thiện", state: "upcoming" },
            { label: "Chờ bác sĩ ký", state: "upcoming" },
            { label: "Hoàn tất", state: "upcoming" },
          ]}
        />
      </Section>

      <Section title="Bị chặn trông thế nào" note="Cổng đóng là thông tin, không phải lỗi.">
        <Stepper
          orientation="vertical"
          steps={[
            { label: "Tiếp nhận người bệnh", state: "done", detail: "10:10" },
            { label: "Xác minh người bệnh", state: "current" },
            { label: "Đo sinh hiệu", state: "blocked", detail: "Chờ bước xác minh" },
          ]}
        />
      </Section>
    </main>
  );
}
