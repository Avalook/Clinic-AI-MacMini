"use client";

// MỘT khung thiết lập cho luật số chỗ. Một form, một bảng.
//
// Bản trước tách làm hai tab — "Theo Khung giờ & Ngày" và "Theo Bác sĩ" — và
// Quang hỏi đúng câu phải hỏi: *"tại sao ta không cho vào 1 khung thiết lập
// chung?"* Hai tab đó là hai BẢNG trong database (luật tạm / luật thường trực)
// bị phơi thẳng lên màn hình. Ba tầng là cách LƯU, không phải cách NGHĨ; bắt
// người vận hành chọn tab nghĩa là bắt họ học cấu trúc bảng trước khi đặt được
// một con số. Tệ hơn: không tab nào cho thấy tab kia, nên một luật tạm quên xoá
// làm mọi luật lưu sau đó trông như không chạy — mà không có chỗ nào nhìn ra.
//
// Giờ một luật là một câu: AI — THỨ MẤY — KHUNG GIỜ NÀO — MẤY CHỖ — TỚI BAO GIỜ.
// Cột "Áp dụng" nói "Mãi mãi" hay một khoảng ngày; backend chọn bảng.

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  INPUT,
  LABEL,
  BTN,
  BTN_GHOST,
  CARD,
  TBL_WRAP,
  TBL_HEAD,
  TBL_ROW,
} from "../form-ui";
import { CheckCircle2, AlertCircle } from "lucide-react";
import type { BookingPolicy, BookingRule } from "../../../lib/booking-policy";

export interface DoctorOpt {
  id: string;
  name: string;
}

const WEEKDAY_LABEL = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

function hhmm(minuteOfDay: number): string {
  const h = Math.floor(minuteOfDay / 60);
  const m = minuteOfDay % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function toMinutes(value: string): number {
  const [h, m] = value.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

function ddmm(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export default function OverridePolicyCard({
  doctors,
  policy,
  rules,
}: {
  doctors: DoctorOpt[];
  /** Luật mặc định của phòng khám — dùng làm giá trị khởi tạo cho form, để ô
   *  số chỗ bắt đầu từ con số đang chạy chứ không phải một số bịa. */
  policy: BookingPolicy | null;
  /** Mọi luật còn hiệu lực, hai tầng đã gộp. */
  rules: BookingRule[];
}) {
  const router = useRouter();
  const doctorName = new Map(doctors.map((d) => [d.id, d.name]));

  const [doctorIds, setDoctorIds] = useState<string[]>([]);
  const [weekday, setWeekday] = useState<string>("");
  const [from, setFrom] = useState<string>("18:00");
  const [to, setTo] = useState<string>("18:15");
  const [regularCap, setRegularCap] = useState<number>(policy?.regularCap ?? 3);
  const [walkinCap, setWalkinCap] = useState<number>(policy?.walkinCap ?? 1);
  // "forever" là mặc định vì luật của phòng khám là luật đứng yên. Khoảng ngày
  // là ngoại lệ ("tuần này BS bận"), nên nó phải là lựa chọn thứ hai.
  const [scope, setScope] = useState<"forever" | "dates">("forever");
  const today = new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
  const [dateStart, setDateStart] = useState<string>(today);
  const [dateEnd, setDateEnd] = useState<string>(today);
  const [reason, setReason] = useState<string>("");

  const [busy, setBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  /** Luật này có nói thêm điều gì so với luật nền không? */
  function isRedundant(r: BookingRule): boolean {
    return (
      r.kind === "standing" &&
      !!policy &&
      r.regular_cap === policy.regularCap &&
      r.walkin_cap === policy.walkinCap
    );
  }

  function toggleDoctor(id: string) {
    setDoctorIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function saveRule() {
    const minuteStart = toMinutes(from);
    // "24:00" không nhập được từ <input type="time">, nên 00:00 ở ô ĐẾN nghĩa
    // là hết ngày — chứ không phải một khung rỗng.
    const minuteEnd = to === "00:00" ? 1440 : toMinutes(to);
    if (minuteEnd <= minuteStart) {
      setMsg({ kind: "err", text: "Giờ kết thúc phải sau giờ bắt đầu." });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch("/api/booking-rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doctor_ids: doctorIds,
          weekday: scope === "dates" || weekday === "" ? null : Number(weekday),
          minute_start: minuteStart,
          minute_end: minuteEnd,
          regular_cap: regularCap,
          walkin_cap: walkinCap,
          date_start: scope === "dates" ? dateStart : null,
          date_end: scope === "dates" ? dateEnd : null,
          reason: reason || null,
        }),
      });
      const data = (await res.json()) as {
        ok?: boolean;
        error?: string;
        saved?: { replaced: unknown[] }[];
        shadowed_by?: { date_end: string }[];
      };
      setBusy(false);
      if (!res.ok || !data.ok) {
        setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
        return;
      }

      const who =
        doctorIds.length === 0
          ? "tất cả bác sĩ"
          : doctorIds.map((id) => doctorName.get(id) ?? "?").join(", ");
      const when =
        scope === "dates"
          ? `${ddmm(dateStart)} – ${ddmm(dateEnd)}`
          : weekday === ""
            ? "mọi thứ, mãi mãi"
            : `${WEEKDAY_LABEL[Number(weekday)]} hằng tuần, mãi mãi`;

      // Luật cũ bị cắt là chuyện phải NÓI RA: nó xảy ra mà không ai bấm nút xoá.
      const cut = (data.saved ?? []).reduce(
        (n, s) => n + s.replaced.length,
        0,
      );
      // Và "đã lưu" mà lưới không đổi là cách nhanh nhất để người dùng kết luận
      // chức năng hỏng — nếu một luật có ngày đang đè lên, nói ngay.
      const shadow = data.shadowed_by ?? [];
      setMsg({
        kind: "ok",
        text:
          `Đã lưu: ${who} · ${when} · ${from}–${to} · ` +
          `${regularCap} đặt trước + ${walkinCap} vãng lai.` +
          (cut > 0 ? ` (${cut} luật cũ phủ khung này đã được cắt lại.)` : "") +
          (shadow.length > 0
            ? ` Lưu ý: khung này đang bị một luật có ngày đè lên (đến ${shadow
                .map((s) => ddmm(s.date_end))
                .join(", ")}) — xoá luật đó ở bảng dưới thì luật vừa lưu mới có hiệu lực.`
            : ""),
      });
      router.refresh();
    } catch {
      setBusy(false);
      setMsg({ kind: "err", text: "Không kết nối được máy chủ" });
    }
  }

  async function deleteRule(rule: BookingRule) {
    setDeletingId(rule.id);
    setMsg(null);
    // Hai bảng bên dưới ⇒ hai đường xoá. `kind` đi kèm từng dòng nên chỗ này
    // không phải đoán, và người dùng vẫn chỉ thấy một nút "Xoá".
    const path = rule.kind === "temp" ? "slot" : "doctor";
    try {
      const res = await fetch(`/api/booking-overrides/${path}/${rule.id}`, {
        method: "DELETE",
      });
      const data = (await res.json()) as { ok?: boolean; error?: string };
      setDeletingId(null);
      if (!res.ok || !data.ok) {
        setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
        return;
      }
      // Xoá KHÔNG để lại khoảng trống: khung đó rơi xuống luật chung hơn. Nói
      // ra, vì "đã xoá" một mình dễ bị hiểu là khung ấy không còn đặt được.
      setMsg({
        kind: "ok",
        text: "Đã xoá luật. Khung giờ đó quay về luật chung hơn đang phủ nó.",
      });
      router.refresh();
    } catch {
      setDeletingId(null);
      setMsg({ kind: "err", text: "Không kết nối được máy chủ" });
    }
  }

  return (
    <div className={CARD}>
      <div className="border-b border-line pb-4">
        <h2 className="text-base font-semibold text-ink">Luật số chỗ theo khung giờ</h2>
        <p className="mt-0.5 text-xs text-ink-muted">
          Một luật là một câu: <b>ai — thứ mấy — khung giờ nào — mấy chỗ — tới bao
          giờ</b>. VD: BS Thành + BS Hoa, thứ 3, 18:00–18:15, 8 đặt trước + 1 vãng
          lai, mãi mãi.
        </p>
      </div>

      <div className="mt-4 space-y-4">
        <div>
          <label className={LABEL}>Bác sĩ (không chọn ai = tất cả bác sĩ)</label>
          <div className="flex flex-wrap gap-2">
            {doctors.map((d) => {
              const on = doctorIds.includes(d.id);
              return (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => toggleDoctor(d.id)}
                  className={on ? BTN : BTN_GHOST}
                >
                  {d.name}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className={LABEL}>Từ giờ</label>
            <input
              type="time"
              step={300}
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className={INPUT}
            />
          </div>
          <div>
            <label className={LABEL}>Đến giờ</label>
            <input
              type="time"
              step={300}
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className={INPUT}
            />
            <p className="mt-1 text-xs text-ink-muted">
              Không gồm mốc cuối: 18:00–18:15 là đúng một khung 18:00.
            </p>
          </div>
          <div>
            <label className={LABEL}>Số ca đặt trước / khung</label>
            <input
              type="number"
              min={1}
              max={50}
              value={regularCap}
              onChange={(e) => setRegularCap(Number(e.target.value))}
              className={INPUT}
            />
          </div>
          <div>
            <label className={LABEL}>Số ca vãng lai / khung</label>
            <input
              type="number"
              min={0}
              max={50}
              value={walkinCap}
              onChange={(e) => setWalkinCap(Number(e.target.value))}
              className={INPUT}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div>
            <label className={LABEL}>Áp dụng</label>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value as "forever" | "dates")}
              className={INPUT}
            >
              <option value="forever">Mãi mãi (lặp mỗi tuần)</option>
              <option value="dates">Chỉ từ ngày … đến ngày …</option>
            </select>
          </div>

          {scope === "forever" ? (
            <div>
              <label className={LABEL}>Thứ</label>
              <select
                value={weekday}
                onChange={(e) => setWeekday(e.target.value)}
                className={INPUT}
              >
                <option value="">Mọi thứ trong tuần</option>
                {WEEKDAY_LABEL.map((w, i) => (
                  <option key={w} value={String(i)}>
                    {w} hằng tuần
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={LABEL}>Từ ngày</label>
                <input
                  type="date"
                  value={dateStart}
                  onChange={(e) => setDateStart(e.target.value)}
                  className={INPUT}
                />
              </div>
              <div>
                <label className={LABEL}>Đến ngày</label>
                <input
                  type="date"
                  value={dateEnd}
                  onChange={(e) => setDateEnd(e.target.value)}
                  className={INPUT}
                />
              </div>
            </div>
          )}

          <div>
            <label className={LABEL}>Ghi chú / Lý do</label>
            <input
              type="text"
              placeholder="VD: BS khám nhanh / giờ cao điểm"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className={INPUT}
            />
          </div>
        </div>

        <div className="pt-1">
          <button onClick={saveRule} disabled={busy} className={BTN}>
            {busy ? "Đang lưu..." : "Lưu luật"}
          </button>
        </div>

        {msg && (
          <div
            className={`flex items-start gap-2 rounded-lg p-3 text-sm ${
              msg.kind === "ok"
                ? "bg-success-bg text-success"
                : "bg-danger-bg text-danger"
            }`}
          >
            {msg.kind === "ok" ? (
              <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
            ) : (
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
            )}
            <span>{msg.text}</span>
          </div>
        )}

        {/* MỘT bảng cho mọi luật. Đây là nửa còn lại của màn hình: không có nó,
            người dùng sửa một thứ mình không nhìn thấy. */}
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink">
            Các luật đang áp dụng
          </h3>
          {!policy ? (
            <p className="text-xs text-ink-muted">
              Chưa đọc được luật mặc định của phòng khám, nên bảng này chưa nói
              đủ. Tải lại trang.
            </p>
          ) : (
            <div className={TBL_WRAP}>
              <table className="w-full text-sm">
                <thead className={TBL_HEAD}>
                  <tr>
                    <th className="px-3 py-2 text-left">Áp dụng</th>
                    <th className="px-3 py-2 text-left">Bác sĩ</th>
                    <th className="px-3 py-2 text-left">Khung giờ</th>
                    <th className="px-3 py-2 text-right">Đặt trước</th>
                    <th className="px-3 py-2 text-right">Vãng lai</th>
                    <th className="px-3 py-2 text-left">Lý do</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {/* LUẬT NỀN, luôn là dòng đầu.
                      Nó KHÔNG nằm trong `rules` vì nó không phải một hàng trong
                      bảng ngoại lệ — nó là thẻ "Luật đặt lịch" ở trên. Nhưng bỏ
                      nó khỏi đây thì bảng chỉ liệt kê NGOẠI LỆ, và người đọc
                      không có cách nào thấy "mọi khung 15 phút đều 3+1". Tệ hơn:
                      một ngoại lệ trùng đúng số mặc định (prod đang có một dòng
                      như thế cho khung 18:00) làm cả bảng trông như 3+1 chỉ áp
                      cho mỗi khung ấy. Câu hỏi đó đã được hỏi, nên câu trả lời
                      phải nằm trên màn hình. */}
                  <tr className={`${TBL_ROW} bg-surface-muted`}>
                    <td className="px-3 py-2 font-medium">Mặc định · mọi thứ</td>
                    <td className="px-3 py-2">Tất cả bác sĩ</td>
                    <td className="px-3 py-2">
                      Cả ngày — mỗi khung {policy.slotMinutes} phút
                    </td>
                    <td className="px-3 py-2 text-right">{policy.regularCap}</td>
                    <td className="px-3 py-2 text-right">{policy.walkinCap}</td>
                    <td className="px-3 py-2 text-ink-muted">
                      Từ thẻ “Luật đặt lịch” ở trên
                    </td>
                    <td className="px-3 py-2" />
                  </tr>
                  {rules.map((r) => (
                    <tr key={r.id} className={TBL_ROW}>
                      <td className="px-3 py-2">
                        {r.kind === "temp" && r.date_start && r.date_end ? (
                          <span>
                            {ddmm(r.date_start)} – {ddmm(r.date_end)}
                          </span>
                        ) : r.weekday === null ? (
                          "Mãi mãi · mọi thứ"
                        ) : (
                          `Mãi mãi · ${WEEKDAY_LABEL[r.weekday]}`
                        )}
                        {/* Luật này đúng nhưng hôm nay không phải con số có
                            hiệu lực. Không nói ra thì người dùng nhìn bảng và
                            tin vào một số mà hệ thống đang bỏ qua. */}
                        {r.shadowed && (
                          <span className="ml-2 rounded bg-warning-bg px-1.5 py-0.5 text-xs text-warning">
                            đang bị luật có ngày đè
                          </span>
                        )}
                        {/* Ngoại lệ đặt đúng bằng số mặc định thì không đổi gì
                            cả — nó chỉ làm bảng trông như luật nền chỉ áp cho
                            mỗi khung ấy. Prod đang có một dòng như vậy. Không tự
                            xoá: đó là dữ liệu người dùng, và họ có thể đang giữ
                            nó để sắp đổi số. Chỉ nói ra là nó thừa. */}
                        {isRedundant(r) && (
                          <span className="ml-2 rounded bg-surface-muted px-1.5 py-0.5 text-xs text-ink-muted">
                            trùng số mặc định — xoá cũng không đổi gì
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {r.doctor_id
                          ? (doctorName.get(r.doctor_id) ?? "—")
                          : "Tất cả bác sĩ"}
                      </td>
                      <td className="px-3 py-2">
                        {hhmm(r.minute_start)}–{hhmm(r.minute_end)}
                      </td>
                      <td className="px-3 py-2 text-right">{r.regular_cap ?? "—"}</td>
                      <td className="px-3 py-2 text-right">{r.walkin_cap ?? "—"}</td>
                      <td className="px-3 py-2 text-ink-muted">{r.reason ?? ""}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => deleteRule(r)}
                          disabled={deletingId === r.id}
                          className={BTN_GHOST}
                        >
                          {deletingId === r.id ? "Đang xoá…" : "Xoá"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-2 text-xs text-ink-muted">
            Đọc từ <b>dưới lên</b>: khung nào có luật riêng thì theo luật đó, còn
            lại theo dòng <b>Mặc định</b> ở trên cùng. Nên một luật riêng cho
            18:00–18:15 chỉ đổi đúng khung ấy — mọi khung khác của bác sĩ đó vẫn
            là số mặc định. Nhiều luật cùng phủ một khung thì hệ thống chọn cái{" "}
            <b>cụ thể nhất</b>: luật có ngày thắng luật mãi mãi · luật ghi rõ bác
            sĩ thắng luật &ldquo;tất cả bác sĩ&rdquo; · luật ghi rõ thứ thắng luật
            &ldquo;mọi thứ&rdquo;.
          </p>
        </div>
      </div>
    </div>
  );
}
