"use client";

// BÁC SĨ ĐÃ CHỈ ĐỊNH GÌ — thay khối "Tuyến điều phối" (Tuyền 16/09/2026).
//
// *"chỗ tuyến điều phối ấy, mình không nên để cứng như vậy… nếu phòng đó mà
// đang đông thì mới bị tắc nên chuyển bác sĩ với phòng ở dưới mới hiệu quả
// được. Cái tuyến lúc ấn vào hiện tại nó quá cứng, cần mềm để linh hoạt."*
//
// Tuyến là một QUY TRÌNH MẪU áp lên cả lượt khám: chọn một cái tên rồi hệ thống
// dựng lại chuỗi bước. Nó buộc trưởng ca phải nghĩ thay bác sĩ, trong khi việc
// đã có sẵn trong chỉ định. Khối này chỉ trả lời hai câu ông ấy thật sự hỏi:
// còn việc nào chưa làm, và chỗ làm việc ấy có đang tắc không — rồi để chính
// ông ấy quyết đổi phòng hay đổi bác sĩ bằng hai khối ngay bên dưới.

import { useEffect, useState } from "react";

interface ChiDinh {
  id: string;
  service_code: string;
  service_name: string;
  node_code: string;
  node_name: string | null;
  exec_status: string;
  room_name: string | null;
  room_floor: string | null;
  work_status: string | null;
  /** Số người đang chờ Ở BƯỚC NÀY trong cả phòng khám — số thật, từ backend. */
  dang_cho_buoc: number;
  xong: boolean;
}

const NHAN_TRANG_THAI: Record<string, string> = {
  draft: "BS chưa duyệt",
  authorized: "Đã duyệt · chờ xếp phòng",
  assigned: "Đã xếp phòng",
  in_progress: "Đang làm",
  performed: "Đã xong",
  not_performed: "Không làm",
  cancelled: "Đã huỷ",
};

export default function ChiDinhCuaBacSi({ visitId }: { visitId: string }) {
  const [ds, setDs] = useState<ChiDinh[] | null>(null);
  const [loi, setLoi] = useState(false);

  // Đổi bệnh nhân = component được dựng lại (key ở nơi gọi), nên KHÔNG cần
  // dọn state trong thân effect — gọi setState ở đó là một vòng vẽ thừa và
  // react-hooks/set-state-in-effect chặn đúng chỗ ấy.
  useEffect(() => {
    let song = true;
    void fetch(`/api/dispatch-read?what=chi-dinh&visit_id=${visitId}`, {
      cache: "no-store",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { items?: ChiDinh[] } | null) => {
        if (!song) return;
        if (!j) {
          setLoi(true);
          return;
        }
        setDs(j.items ?? []);
      })
      .catch(() => song && setLoi(true));
    return () => {
      song = false;
    };
  }, [visitId]);

  const conLai = (ds ?? []).filter((x) => !x.xong);

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>
        Bác sĩ chỉ định gì
      </div>

      {loi ? (
        <p className="text-label text-danger">Không đọc được chỉ định — thử tải lại.</p>
      ) : ds === null ? (
        <p className="text-label text-ink-muted">Đang đọc chỉ định…</p>
      ) : ds.length === 0 ? (
        /* KHÔNG CÓ CHỈ ĐỊNH LÀ MỘT CÂU TRẢ LỜI, không phải khối trống: bác sĩ
           chưa chỉ định gì thì không có việc nào để xếp phòng, và trưởng ca
           đừng tự nghĩ ra việc. */
        <p className="text-label text-ink-muted">
          Bác sĩ chưa chỉ định dịch vụ nào cho lượt này.
        </p>
      ) : (
        <ul style={{ display: "grid", gap: 6 }}>
          {ds.map((x) => (
            <li
              key={x.id}
              className={`rounded-control border px-2.5 py-2 ${
                x.xong
                  ? "border-line bg-surface-muted"
                  : x.dang_cho_buoc >= 3
                    ? "border-warning/40 bg-warning-bg"
                    : "border-line bg-surface"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span
                  className={`truncate text-body font-semibold ${
                    x.xong ? "text-ink-muted line-through" : "text-ink"
                  }`}
                >
                  {x.service_name}
                </span>
                <span className="shrink-0 text-label text-ink-muted">
                  {NHAN_TRANG_THAI[x.exec_status] ?? x.exec_status}
                </span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-label text-ink-muted">
                <span className="truncate">{x.node_name ?? x.node_code}</span>
                {x.room_name && (
                  <span className="truncate">
                    · {x.room_name}
                    {x.room_floor ? ` (tầng ${x.room_floor})` : ""}
                  </span>
                )}
                {!x.xong && (
                  <span
                    className={
                      x.dang_cho_buoc >= 3 ? "font-semibold text-warning" : ""
                    }
                  >
                    · {x.dang_cho_buoc} người đang chờ bước này
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {conLai.length > 0 && (
        <p className="mt-1.5 text-label text-ink-muted">
          Còn {conLai.length} việc chưa làm. Chỗ nào đang đông thì đổi phòng hoặc
          đổi bác sĩ ở dưới.
        </p>
      )}
    </div>
  );
}
