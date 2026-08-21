/**
 * Progress through a sequence of steps.
 *
 * The design set uses two of these and they mean different things, so they are
 * one component with an orientation rather than two that drift apart:
 *
 *   horizontal  sub-states WITHIN one node — "Vào hàng đợi → Đã gán quầy →
 *               Gọi bệnh nhân → Xác nhận có mặt → Hoàn tất tiếp nhận" on the
 *               reception screen is all one work item, LUOTKHAM-01.
 *   vertical    a chain ACROSS nodes — "Đang thực hiện → Chờ thư ký hoàn thiện
 *               → Chờ bác sĩ ký → Hoàn tất" on the ultrasound screen is four
 *               separate work items with gates between them.
 *
 * Steps carry their own timestamp because every design that shows a stepper
 * also shows when each step happened; a stepper without times answers "where
 * are we" but not "how long have we been here", which is the question the
 * person at the desk is actually asking.
 */

import type { ReactNode } from "react";

export type StepState = "done" | "current" | "upcoming" | "blocked";

export interface Step {
  label: string;
  state: StepState;
  /** "10:10", or "Chưa gọi" when nothing has happened yet. */
  detail?: string;
  icon?: ReactNode;
  /** BẤM ĐƯỢC VÀO CHÍNH NÚT TRÒN — tuỳ chọn (Tuyền 20/08/2026).
   *
   *  Màn hàng đợi lễ tân biến hai node này thành hành động: bấm là làm, bấm lại
   *  là hoàn tác — cùng cơ chế nút tròn của màn CSKH. Ba màn còn lại dùng
   *  Stepper (Trang chủ ×2, Siêu âm) KHÔNG truyền `onClick`, nên chúng vẫn là
   *  chỉ-báo thuần và không đổi một dòng nào.
   *
   *  Không có `onClick` ⇒ render `<span>` như cũ, không tiêu điểm bàn phím,
   *  không con trỏ tay: một biểu tượng trông bấm được mà không bấm được còn tệ
   *  hơn một biểu tượng tĩnh. */
  onClick?: () => void;
  /** Câu giải thích cho người dùng bàn phím / trình đọc màn hình. Bắt buộc trên
   *  thực tế khi có `onClick`, vì nút tròn chỉ có dấu ✓ chứ không có chữ. */
  actionLabel?: string;
  /** Đang gửi lệnh — khoá nút để không bấm đúp thành hai lệnh ngược nhau. */
  busy?: boolean;
}

/** Nút tròn: `<button>` khi bấm được, `<span>` khi không.
 *
 *  Cùng một lớp CSS cho cả hai để hình dạng không nhảy giữa hai chế độ; chỉ
 *  thêm con trỏ tay + vòng tiêu điểm khi thật sự bấm được. */
function ChamTron({
  step,
  className,
}: {
  step: Step;
  className: string;
}) {
  const ruot = step.icon ?? (step.state === "done" ? "✓" : null);
  if (!step.onClick) {
    return (
      <span className={className} aria-hidden>
        {ruot}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={step.onClick}
      disabled={step.busy}
      aria-label={step.actionLabel ?? step.label}
      title={step.actionLabel ?? step.label}
      className={`${className} cursor-pointer transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-wait disabled:opacity-60`}
    >
      {step.busy ? "…" : ruot}
    </button>
  );
}

const DOT: Record<StepState, string> = {
  done: "border-status-completed bg-status-completed text-white",
  current: "border-brand-600 bg-brand-600 text-white",
  upcoming: "border-line-strong bg-surface text-ink-faint",
  blocked: "border-status-blocked bg-status-blocked-bg text-status-blocked",
};

const LABEL: Record<StepState, string> = {
  done: "text-ink-soft",
  current: "text-ink font-medium",
  upcoming: "text-ink-faint",
  blocked: "text-status-blocked font-medium",
};

/** The connector is coloured by the step BEFORE it, so progress reads as a fill. */
const LINE: Record<StepState, string> = {
  done: "bg-status-completed",
  current: "bg-brand-600",
  upcoming: "bg-line",
  blocked: "bg-line",
};

export interface StepperProps {
  steps: Step[];
  orientation?: "horizontal" | "vertical";
}

export default function Stepper({
  steps,
  orientation = "horizontal",
}: StepperProps) {
  if (orientation === "vertical") {
    return (
      <ol className="flex flex-col">
        {steps.map((s, i) => (
          <li key={s.label} className="flex gap-3">
            <div className="flex flex-col items-center">
              <ChamTron
                step={s}
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-label ${DOT[s.state]}`}
              />
              {i < steps.length - 1 ? (
                <span className={`w-0.5 flex-1 ${LINE[s.state]}`} aria-hidden />
              ) : null}
            </div>
            <div className={`pb-5 text-sm ${LABEL[s.state]}`}>
              <div>{s.label}</div>
              {s.detail ? (
                <div className="text-xs text-ink-faint">{s.detail}</div>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    );
  }

  return (
    <ol className="flex items-start">
      {steps.map((s, i) => (
        <li key={s.label} className="flex flex-1 items-start last:flex-none">
          <div className="flex flex-col items-center gap-1.5 px-1">
            <ChamTron
              step={s}
              className={`flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs ${DOT[s.state]}`}
            />
            <span className={`text-center text-xs ${LABEL[s.state]}`}>
              {s.label}
            </span>
            {s.detail ? (
              <span className="text-center text-xs text-ink-faint">
                {s.detail}
              </span>
            ) : null}
          </div>
          {i < steps.length - 1 ? (
            <span className={`mt-4 h-0.5 flex-1 ${LINE[s.state]}`} aria-hidden />
          ) : null}
        </li>
      ))}
    </ol>
  );
}
