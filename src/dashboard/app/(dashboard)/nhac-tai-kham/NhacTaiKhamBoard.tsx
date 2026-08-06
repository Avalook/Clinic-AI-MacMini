"use client";

// Bảng gọi nhắc tái khám. Dữ liệu do GET /api/v1/cskh/recalls dựng sẵn; ở đây
// chỉ còn xếp nhóm theo hạn, lọc, và ghi lại cuộc gọi.
//
// GỌI XONG NGƯỜI TA KHÔNG BIẾN MẤT. Endpoint loại người đã có lịch hẹn, không
// loại người đã được gọi — nên một cuộc gọi không kèm đặt lịch vẫn để họ ở đây
// ngày mai. Đó là đúng (vẫn cần theo tiếp), nhưng nghĩa là màn hình phải nói rõ
// ai đã gọi rồi và gọi hôm nào, không thì hai người trực cùng ca gọi trùng.
// `last_called_date` từ cskh_log lo phần đó và nó SỐNG QUA TẢI LẠI TRANG —
// khác với đánh dấu tạm trong bộ nhớ trình duyệt.

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertTriangle,
  CalendarClock,
  CalendarPlus,
  CheckCircle2,
  PhoneCall,
  Search,
} from "lucide-react";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import { unaccentVi } from "../../../lib/validation";

export interface RecallRow {
  clinic_patient_id: string;
  full_name: string;
  phone_primary: string | null;
  /** Ngày bác sĩ hẹn tái khám, dạng "YYYY-MM-DD". */
  due_date: string;
  /** Mã xét nghiệm cần làm lại (HM/SH/SA/DXA/PS…). */
  repeat_tests: string[];
  /** Lời dặn của bác sĩ — KHÔNG phải bệnh án. */
  instruction: string;
  /** Ngày gọi nhắc gần nhất, null nếu chưa ai gọi. */
  last_called_date: string | null;
}

type Tab = "overdue" | "today" | "soon" | "called" | "all";

// Nhãn dùng cho dòng "Đang lọc: …". Không dùng lại nhãn của ô số vì ô "Sắp đến
// hạn (7 ngày)" có phần trong ngoặc chỉ hợp lý khi đứng cạnh con số.
const NHAN_LOC: Record<Exclude<Tab, "all">, string> = {
  overdue: "Quá hạn",
  today: "Đến hạn hôm nay",
  soon: "Sắp đến hạn trong 7 ngày",
  called: "Đã gọi hôm nay",
};

// LỌC BẰNG CHÍNH BỐN Ô SỐ Ở TRÊN, không có hàng tab riêng.
//
// Trước đây màn này có cả hai: bốn ô số, rồi ngay dưới là năm tab lặp lại đúng
// những con số ấy. Hai chỗ bấm cho cùng một việc — người dùng phải đọc con số ở
// trên rồi đi tìm cái tên tương ứng ở dưới mới bấm được, và hai chỗ ấy là hai
// chỗ để lệch nhau khi sửa. Chú thích của chính `components/ui/StatCard` đã ghi
// điều này từ đầu: "hàng số là một BỘ LỌC, không phải trang trí".
//
// "Tất cả" vẫn là mặc định — danh sách vốn xếp quá-hạn-trước nên nó đã cho thấy
// việc gấp nhất; mở thẳng vào "Quá hạn" thì hôm nào không ai quá hạn, người
// trực gặp màn hình trống và tưởng máy hỏng. Bấm lại đúng ô đang chọn thì quay
// về "Tất cả".

/** Số ngày từ `from` đến `to`, cả hai là "YYYY-MM-DD".
 *
 *  Đọc hai chuỗi ở mốc UTC nên không dính múi giờ máy: hai ngày lịch trừ nhau
 *  ra đúng số ngày, không ra "23 tiếng" vì đổi giờ mùa hè ở đâu đó. `today` do
 *  server tính theo giờ Việt Nam (vnYmd), cùng mốc ngày backend dùng. */
function dayDiff(from: string, to: string): number {
  const a = Date.parse(`${from}T00:00:00Z`);
  const b = Date.parse(`${to}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b)) return 0;
  return Math.round((b - a) / 86_400_000);
}

/** "2026-08-06" → "06/08/2026". Chuỗi ngày trần, không dựng Date để khỏi lệch. */
function fmtYmd(ymd: string): string {
  const [y, m, d] = ymd.split("-");
  return y && m && d ? `${d}/${m}/${y}` : ymd;
}

export default function NhacTaiKhamBoard({
  rows,
  today,
  unreachable,
}: {
  rows: RecallRow[];
  today: string;
  unreachable: boolean;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("all");

  /** Bấm một ô số = lọc theo ô đó. Bấm lại đúng ô đang chọn = bỏ lọc. */
  const chonLoc = (key: Tab) => setTab((cu) => (cu === key ? "all" : key));
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Ghi nhận lạc quan: hàng vừa gọi hiện "đã gọi hôm nay" ngay, không đợi
  // router.refresh() đi vòng qua server rồi mới đổi.
  const [justCalled, setJustCalled] = useState<Set<string>>(new Set());
  // State chỉ đổi ở lần render sau, nên hai cú bấm nhanh đều lọt qua `saving`.
  // useRef đổi ngay lập tức.
  const savingRef = useRef(false);

  const enriched = useMemo(
    () =>
      rows
        .map((r) => {
          const calledOn = justCalled.has(r.clinic_patient_id)
            ? today
            : r.last_called_date;
          return {
            ...r,
            // Âm = quá hạn bấy nhiêu ngày, 0 = hôm nay, dương = còn bấy nhiêu ngày.
            days: dayDiff(today, r.due_date),
            calledOn,
            calledToday: calledOn === today,
          };
        })
        .sort((a, b) => a.days - b.days || a.full_name.localeCompare(b.full_name, "vi")),
    [rows, today, justCalled],
  );

  const stats = useMemo(
    () => ({
      overdue: enriched.filter((r) => r.days < 0).length,
      today: enriched.filter((r) => r.days === 0).length,
      soon: enriched.filter((r) => r.days > 0).length,
      called: enriched.filter((r) => r.calledToday).length,
    }),
    [enriched],
  );

  const visible = useMemo(() => {
    const needle = unaccentVi(query.trim());
    return enriched.filter((r) => {
      if (tab === "overdue" && r.days >= 0) return false;
      if (tab === "today" && r.days !== 0) return false;
      if (tab === "soon" && r.days <= 0) return false;
      if (tab === "called" && !r.calledToday) return false;
      if (!needle) return true;
      return unaccentVi(
        [r.full_name, r.phone_primary, r.instruction, ...r.repeat_tests]
          .filter(Boolean)
          .join(" "),
      ).includes(needle);
    });
  }, [enriched, tab, query]);

  async function saveCall(patientId: string) {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/cskh-followup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: patientId,
          note: note.trim() || undefined,
        }),
      });
      const payload = (await res.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!res.ok) {
        setError(payload.error ?? "Không ghi được cuộc gọi.");
        return;
      }
      setJustCalled((prev) => new Set(prev).add(patientId));
      setOpenId(null);
      setNote("");
      // Đọc lại từ server để `last_called_date` là số thật, không phải cái
      // đánh dấu trong trình duyệt.
      router.refresh();
    } catch {
      setError("Không kết nối được máy chủ.");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      {unreachable ? (
        <div className="flex items-start gap-2 rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            <b>Không đọc được danh sách từ máy chủ.</b> Danh sách trống dưới đây
            KHÔNG có nghĩa là hôm nay không ai cần gọi — hãy tải lại trang, nếu
            vẫn vậy thì báo kỹ thuật.
          </span>
        </div>
      ) : null}

      <StatRow>
        <StatCard
          label="Quá hạn"
          value={stats.overdue}
          tone="danger"
          icon={<AlertTriangle className="size-5" />}
          onSelect={() => chonLoc("overdue")}
          active={tab === "overdue"}
        />
        <StatCard
          label="Đến hạn hôm nay"
          value={stats.today}
          tone="brand"
          icon={<CalendarClock className="size-5" />}
          onSelect={() => chonLoc("today")}
          active={tab === "today"}
        />
        <StatCard
          label="Sắp đến hạn (7 ngày)"
          value={stats.soon}
          tone="warning"
          icon={<CalendarPlus className="size-5" />}
          onSelect={() => chonLoc("soon")}
          active={tab === "soon"}
        />
        <StatCard
          label="Đã gọi hôm nay"
          value={stats.called}
          tone="success"
          icon={<CheckCircle2 className="size-5" />}
          onSelect={() => chonLoc("called")}
          active={tab === "called"}
        />
      </StatRow>

      {tab !== "all" ? (
        <div className="flex items-center gap-2 text-sm text-ink-muted">
          <span>
            Đang lọc: <b className="text-ink">{NHAN_LOC[tab]}</b>
          </span>
          <button
            type="button"
            onClick={() => setTab("all")}
            className="rounded-control px-2 py-0.5 font-medium text-brand-700 underline-offset-2 hover:underline"
          >
            Bỏ lọc, xem tất cả
          </button>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-surface p-3 shadow-card">
        <label className="flex min-h-9 flex-1 items-center gap-2 rounded-xl border border-line px-3 text-ink-muted focus-within:border-brand-500">
          <Search className="size-4" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm theo tên, số điện thoại, lời dặn"
            className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
      </div>

      {error ? (
        <div className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          {error}
        </div>
      ) : null}

      <section
        aria-label="Danh sách cần gọi nhắc tái khám"
        className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
      >
        {visible.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-ink-muted">
            {unreachable
              ? "Chưa có dữ liệu để hiển thị."
              : "Không có ai trong nhóm này."}
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {visible.map((r) => {
              const overdue = r.days < 0;
              const dueLabel =
                r.days === 0
                  ? "Đến hạn hôm nay"
                  : overdue
                    ? `Quá hạn ${-r.days} ngày`
                    : `Còn ${r.days} ngày`;
              return (
                <li key={r.clinic_patient_id} className="px-4 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-ink">
                          {r.full_name}
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            overdue
                              ? "bg-status-overdue-bg text-status-overdue"
                              : r.days === 0
                                ? "bg-brand-50 text-brand-700"
                                : "bg-surface-sunken text-ink-soft"
                          }`}
                        >
                          {dueLabel}
                        </span>
                        {r.calledToday ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-status-completed-bg px-2 py-0.5 text-[11px] font-medium text-status-completed">
                            <CheckCircle2 className="size-3" aria-hidden />
                            Đã gọi hôm nay
                          </span>
                        ) : r.calledOn ? (
                          <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-[11px] text-ink-soft">
                            Gọi lần cuối {fmtYmd(r.calledOn)}
                          </span>
                        ) : null}
                      </div>

                      <p className="mt-1 text-xs text-ink-muted">
                        Hẹn tái khám {fmtYmd(r.due_date)}
                        {r.phone_primary ? (
                          <>
                            {" · "}
                            <a
                              href={`tel:${r.phone_primary}`}
                              className="font-medium text-brand-700 hover:underline"
                            >
                              {r.phone_primary}
                            </a>
                          </>
                        ) : (
                          " · chưa có số điện thoại"
                        )}
                      </p>

                      {r.repeat_tests.length > 0 ? (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {r.repeat_tests.map((t) => (
                            <span
                              key={t}
                              className="rounded-full bg-surface-sunken px-2 py-0.5 text-[11px] text-ink-soft"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      ) : null}

                      {r.instruction ? (
                        <p className="mt-1.5 text-xs text-ink">
                          <span className="text-ink-muted">Bác sĩ dặn: </span>
                          {r.instruction}
                        </p>
                      ) : null}
                    </div>

                    <div className="flex shrink-0 flex-col items-stretch gap-1.5">
                      <button
                        type="button"
                        onClick={() => {
                          setOpenId(
                            openId === r.clinic_patient_id
                              ? null
                              : r.clinic_patient_id,
                          );
                          setNote("");
                          setError(null);
                        }}
                        className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg bg-brand-600 px-3 text-sm font-medium text-white transition-colors hover:bg-brand-700"
                      >
                        <PhoneCall className="size-4" aria-hidden />
                        {r.calledOn ? "Gọi lại" : "Đã gọi"}
                      </button>
                      <Link
                        href={`/customers?q=${encodeURIComponent(
                          r.phone_primary ?? r.full_name,
                        )}&selected=${r.clinic_patient_id}`}
                        className="inline-flex min-h-9 items-center justify-center rounded-lg border border-line px-3 text-sm font-medium text-ink transition-colors hover:bg-surface-sunken"
                      >
                        Mở hồ sơ · đặt lịch
                      </Link>
                    </div>
                  </div>

                  {openId === r.clinic_patient_id ? (
                    <div className="mt-3 rounded-xl border border-line bg-surface-sunken p-3">
                      <label className="text-xs font-medium text-ink-muted">
                        Ghi chú cuộc gọi (không bắt buộc)
                      </label>
                      <textarea
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        rows={2}
                        maxLength={2000}
                        placeholder="Khách hẹn gọi lại chiều mai / đã nhận lời hẹn tuần sau…"
                        className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand-600"
                      />
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => saveCall(r.clinic_patient_id)}
                          className="min-h-9 rounded-lg bg-brand-600 px-3 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
                        >
                          {saving ? "Đang lưu…" : "Lưu cuộc gọi"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setOpenId(null);
                            setNote("");
                          }}
                          className="min-h-9 rounded-lg border border-line px-3 text-sm font-medium text-ink transition-colors hover:bg-surface"
                        >
                          Huỷ
                        </button>
                      </div>
                      <p className="mt-2 text-[11px] text-ink-faint">
                        Ghi lại cuộc gọi KHÔNG tạo lịch hẹn. Khách nhận lời thì
                        bấm <b>Mở hồ sơ · đặt lịch</b> để đặt — đặt xong họ mới
                        rời danh sách này.
                      </p>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
