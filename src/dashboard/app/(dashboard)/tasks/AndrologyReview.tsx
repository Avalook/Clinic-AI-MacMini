"use client";

// Bảng đọc kèm phiếu Nam khoa: chỉ số nào dưới ngưỡng, và nên cân nhắc xét
// nghiệm di truyền nào.
//
// KHÔNG MỘT CON SỐ NÀO TÍNH Ở ĐÂY. Ngưỡng WHO sống ở bảng
// `semen_reference_range`; điểm, cờ và gợi ý do backend trả về. WHO đã đổi
// ngưỡng qua ba ấn bản — nhốt số vào TSX là mất luôn câu trả lời cho "kết quả
// năm ngoái được đọc theo ngưỡng nào".
//
// VÀ KHÔNG TỰ TICK GÌ CẢ. Gợi ý hiện kèm LÝ DO để bác sĩ cân nhắc; việc chỉ
// định là của bác sĩ (Notion §13: hệ thống không tự tạo chỉ định). Một danh
// sách xét nghiệm không kèm lý do thì hoặc bị bỏ qua cả danh sách, hoặc bị chỉ
// định hết — cả hai đều tệ hơn là không gợi ý gì.

import { useEffect, useState } from "react";
import { AlertTriangle, Lightbulb, Info } from "lucide-react";
import type { FormData } from "../../../lib/form-schemas/types";

interface SemenFlag {
  parameter: string;
  label: string;
  value: number;
  lower_limit: number;
  unit: string;
  source: string;
  message: string;
}

interface GeneticSuggestion {
  test: string;
  reason: string;
}

interface Review {
  semen_flags: SemenFlag[];
  genetic_suggestions: GeneticSuggestion[];
  bmi: number | null;
  notes: string[];
  reference_source: string | null;
}

/** Chờ người dùng ngừng gõ rồi mới hỏi máy chủ. Mỗi phím một lượt gọi thì bảng
 *  nhấp nháy và máy chủ nhận vài chục lượt cho một ô số. */
const CHO_MS = 600;

export default function AndrologyReview({ values }: { values: FormData }) {
  const [review, setReview] = useState<Review | null>(null);
  const [loi, setLoi] = useState(false);

  useEffect(() => {
    let con_song = true;
    const hen = setTimeout(async () => {
      try {
        const res = await fetch("/api/clinical-form/andrology-review", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ form_data: values }),
        });
        if (!con_song) return;
        if (!res.ok) {
          setLoi(true);
          return;
        }
        setReview((await res.json()) as Review);
        setLoi(false);
      } catch {
        if (con_song) setLoi(true);
      }
    }, CHO_MS);
    return () => {
      con_song = false;
      clearTimeout(hen);
    };
  }, [values]);

  if (loi) {
    return (
      <p className="mt-3 text-xs text-ink-muted">
        Chưa đọc được ngưỡng tham chiếu từ máy chủ — các con số ở trên vẫn lưu
        bình thường, chỉ phần đối chiếu tạm thời không hiện.
      </p>
    );
  }
  if (!review) return null;

  const co_gi =
    review.semen_flags.length > 0 ||
    review.genetic_suggestions.length > 0 ||
    review.notes.length > 0 ||
    review.bmi !== null;
  if (!co_gi) return null;

  return (
    <aside className="mt-4 space-y-3 rounded-card border border-line bg-brand-50/40 p-3">
      <h5 className="text-sm font-semibold text-ink">
        Máy đọc giúp
        <span className="ml-2 text-xs font-normal text-ink-muted">
          gợi ý để bác sĩ cân nhắc — không phải chẩn đoán, không phải chỉ định
        </span>
      </h5>

      {review.bmi !== null && (
        <p className="text-sm text-ink-soft">
          BMI <span className="font-medium text-ink">{review.bmi}</span>
        </p>
      )}

      {review.semen_flags.length > 0 && (
        <div>
          <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-warning">
            <AlertTriangle size={13} className="shrink-0" />
            Dưới ngưỡng tham chiếu
            {review.reference_source && (
              <span className="font-normal text-ink-muted">
                ({review.reference_source})
              </span>
            )}
          </p>
          <ul className="space-y-1">
            {review.semen_flags.map((f) => (
              <li key={f.parameter} className="text-sm text-ink-soft">
                {f.label}{" "}
                <span className="font-medium text-ink">
                  {f.value} {f.unit}
                </span>{" "}
                <span className="text-ink-muted">
                  — dưới ngưỡng {f.lower_limit}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {review.genetic_suggestions.length > 0 && (
        <div>
          <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-brand-800">
            <Lightbulb size={13} className="shrink-0" />
            Cân nhắc xét nghiệm di truyền
          </p>
          <ul className="space-y-1">
            {review.genetic_suggestions.map((g) => (
              <li key={g.test} className="text-sm text-ink-soft">
                <span className="font-medium text-ink">{g.test}</span>
                <span className="text-ink-muted"> — {g.reason}</span>
              </li>
            ))}
          </ul>
          {/* Nói thẳng ra rằng đây KHÔNG phải chỉ định. Một danh sách mã xét
              nghiệm trông y hệt một phiếu chỉ định nếu không có dòng này. */}
          <p className="mt-1 text-xs text-ink-muted">
            Hệ thống không tự tạo chỉ định — bác sĩ tự chọn trong màn Chỉ định
            dịch vụ.
          </p>
        </div>
      )}

      {review.notes.length > 0 && (
        <ul className="space-y-1">
          {review.notes.map((n) => (
            <li
              key={n}
              className="flex items-start gap-1.5 text-sm text-ink-soft"
            >
              <Info size={13} className="mt-1 shrink-0 text-ink-muted" />
              <span>{n}</span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
