"use client";

// "Xuất hoá đơn về công ty" ở quầy thu (Tuyền 16/10/2026). Tick THEO LƯỢT THU: hồ sơ
// khách chỉ giữ danh sách công ty, lượt nào không tick vẫn xuất cho cá nhân. Thu
// ngân chỉ CHỌN công ty đã có trong hồ sơ (ghi / sửa công ty là việc của Kế toán +
// Quản lý) — tick xong hiện đúng thông tin sẽ in vào file hoá đơn cuối ngày.

import { useEffect, useState } from "react";

export interface CongTyThu {
  id: string;
  ten_cong_ty: string;
  dia_chi_cong_ty: string;
  ma_so_thue: string;
  email_nhan_hd: string;
}

export default function CongTyKhiThu({
  congTy,
  onDoi,
}: {
  /** Công ty trong hồ sơ khách (máy chủ báo trong bảng quầy; dùng gần nhất đứng đầu). */
  congTy: CongTyThu[] | undefined;
  /** id công ty được chọn; null = xuất cho cá nhân. */
  onDoi: (id: string | null) => void;
}) {
  const ds = congTy ?? [];
  const [bat, setBat] = useState(false);
  const [chonId, setChonId] = useState<string | null>(null);
  // Công ty đang chọn phải còn trong danh sách (hồ sơ có thể đổi giữa hai lần tải).
  const dangChon = bat ? (ds.find((c) => c.id === chonId) ?? ds[0] ?? null) : null;

  useEffect(() => {
    onDoi(dangChon ? dangChon.id : null);
    // onDoi do cha truyền, đổi mỗi lần render — không đưa vào deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dangChon?.id]);

  return (
    <div className="space-y-2">
      <label className={`flex items-center gap-2 text-body ${ds.length ? "text-ink" : "text-ink-faint"}`}>
        <input
          type="checkbox"
          checked={bat && ds.length > 0}
          disabled={ds.length === 0}
          onChange={(e) => setBat(e.target.checked)}
          className="size-4 accent-brand-600"
        />
        Xuất hoá đơn về công ty
      </label>


      {dangChon ? (
        <div className="space-y-2 rounded-control border border-line bg-surface-raised px-3 py-2">
          {ds.length > 1 ? (
            <div className="space-y-1" role="radiogroup" aria-label="Công ty nhận hoá đơn">
              {ds.map((c) => (
                <label key={c.id} className="flex items-center gap-1.5 text-meta text-ink">
                  <input
                    type="radio"
                    name="cong-ty-khi-thu"
                    checked={c.id === dangChon.id}
                    onChange={() => setChonId(c.id)}
                    className="accent-brand-600"
                  />
                  {c.ten_cong_ty}
                </label>
              ))}
            </div>
          ) : null}
          <dl className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-x-2 gap-y-0.5 text-meta">
            <dt className="text-ink-muted">Công ty</dt>
            <dd className="break-words font-semibold text-ink">{dangChon.ten_cong_ty}</dd>
            <dt className="text-ink-muted">Mã số thuế</dt>
            <dd className="break-words text-ink">{dangChon.ma_so_thue || "—"}</dd>
            <dt className="text-ink-muted">Địa chỉ</dt>
            <dd className="break-words text-ink">{dangChon.dia_chi_cong_ty || "—"}</dd>
            <dt className="text-ink-muted">Email</dt>
            <dd className="break-words text-ink">{dangChon.email_nhan_hd || "—"}</dd>
          </dl>
          <p className="text-meta text-ink-muted">
            Chỉ lượt thu này xuất về công ty; cuối ngày kế toán xuất file theo thông tin trên.
          </p>
        </div>
      ) : null}
    </div>
  );
}
