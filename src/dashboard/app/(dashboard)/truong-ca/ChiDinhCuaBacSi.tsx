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

import { useCallback, useEffect, useState } from "react";

import DoiPhong from "../_lam-viec/DoiPhong";


interface PhongLamDuoc {
  id: string;
  name: string;
  floor: string | null;
  /** Số khách đang CHỜ (chưa gọi) ở phòng này. */
  waiting: number;
  /** Ngưỡng "đầy" quản lý đặt cho phòng (dispatch_threshold.max_waiting). */
  threshold_waiting: number;
}

interface ChiDinh {
  id: string;
  service_code: string;
  service_name: string;
  node_code: string;
  node_name: string | null;
  exec_status: string;
  /** Việc đối tác làm — không xếp phòng của phòng khám. */
  doi_tac?: boolean;
  version: number;
  room_id: string | null;
  room_name: string | null;
  room_floor: string | null;
  work_status: string | null;
  /** Số người đang chờ Ở BƯỚC NÀY trong cả phòng khám — số thật, từ backend. */
  dang_cho_buoc: number;
  phong_lam_duoc: PhongLamDuoc[];
  xong: boolean;
  /** Có = chỉ định đời mới (khách đã chọn dịch vụ) — đổi phòng bằng khối chung. */
  selection_status: string | null;
  routing_revision: number;
  /** Máy chủ nói đổi phòng được (cùng luật với Bàn khám / Xem lượt). */
  doi_phong_duoc: boolean;
}

/** Chuyển phòng được khi chỉ định đang chờ xếp/đang chờ ở phòng — phòng cũ đã
 *  gọi hoặc đang làm thì thôi (máy chủ cũng chặn). */
function chuyenDuoc(x: ChiDinh): boolean {
  return (
    (x.exec_status === "authorized" || x.exec_status === "assigned") &&
    x.work_status !== "called" &&
    x.work_status !== "serving"
  );
}

function khoaGuiLai(): string {
  return `cp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
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
  const [lan, setLan] = useState(0);
  const [chonPhong, setChonPhong] = useState<Record<string, string>>({});
  const [dangChuyen, setDangChuyen] = useState<string | null>(null);
  const [baoChuyen, setBaoChuyen] = useState<{ ok: boolean; text: string } | null>(null);

  const chuyen = useCallback(async (x: ChiDinh) => {
    const phong = chonPhong[x.id];
    if (!phong) return;
    setDangChuyen(x.id);
    setBaoChuyen(null);
    try {
      const r = await fetch("/api/luot-kham", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": khoaGuiLai() },
        body: JSON.stringify({
          thao_tac: "xep-phong",
          id: x.id,
          du_lieu: { room_id: phong, expected_version: x.version },
        }),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) {
        setBaoChuyen({ ok: false, text: d?.message ?? d?.error ?? "Không chuyển được." });
        return;
      }
      const ten = x.phong_lam_duoc.find((p) => p.id === phong)?.name ?? "phòng mới";
      setBaoChuyen({ ok: true, text: `Đã chuyển ${x.service_name} sang ${ten}.` });
      setChonPhong((c) => ({ ...c, [x.id]: "" }));
      setLan((n) => n + 1);
    } catch {
      setBaoChuyen({ ok: false, text: "Mất kết nối — CHƯA chuyển được." });
    } finally {
      setDangChuyen(null);
    }
  }, [chonPhong]);

  // Đổi bệnh nhân = component được dựng lại (key ở nơi gọi), nên KHÔNG cần
  // dọn state trong thân effect — gọi setState ở đó là một vòng vẽ thừa và
  // react-hooks/set-state-in-effect chặn đúng chỗ ấy.
  useEffect(() => {
    let song = true;
    void fetch(`/api/dispatch-read?what=chi-dinh&visit_id=${visitId}`, {
      cache: "no-store",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { items?: ChiDinh[]; ok?: boolean } | null) => {
        if (!song) return;
        // `{ ok: false }` = máy chủ không trả được (từ chối quyền, lỗi) — KHÔNG
        // phải "không có chỉ định". Bấm thật 24/09: bác sĩ mở màn trưởng ca bị
        // 403 mà màn ghi "Bác sĩ chưa chỉ định dịch vụ nào" — sai sự thật.
        if (!j || j.ok === false || !Array.isArray(j.items)) {
          setLoi(true);
          return;
        }
        setDs(j.items);
      })
      .catch(() => song && setLoi(true));
    return () => {
      song = false;
    };
  }, [visitId, lan]);

  const conLai = (ds ?? []).filter((x) => !x.xong);

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>
        Bác sĩ chỉ định gì
      </div>

      {loi ? (
        <p className="text-label text-danger">
          Không đọc được chỉ định (có thể tài khoản này chưa có quyền điều phối) —
          thử tải lại.
        </p>
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
                  {x.doi_tac && (x.exec_status === "authorized" || x.exec_status === "assigned")
                    ? "Đã gửi đối tác"
                    : NHAN_TRANG_THAI[x.exec_status] ?? x.exec_status}
                </span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-label text-ink-muted">
                <span className="truncate">{x.node_name ?? x.node_code}</span>
                {x.room_name && (
                  <span className="truncate">
                    · {x.room_name}
                  </span>
                )}
                {!x.xong && x.room_id && (
                  <span
                    className={
                      x.dang_cho_buoc >= 3 ? "font-semibold text-warning" : ""
                    }
                  >
                    · {x.dang_cho_buoc} người đang chờ phòng này
                  </span>
                )}
              </div>
              {x.selection_status !== null ? (
                // Đời mới: khối "Đổi phòng" chung (`xep-phong-v1`) — lối điều
                // phối cũ từ chối chỉ định này (24/09).
                !x.xong && !x.doi_tac ? (
                  <DoiPhong
                    orderId={x.id}
                    phongHienTaiId={x.room_id}
                    routingRevision={x.routing_revision}
                    choDoi={x.doi_phong_duoc}
                    onDaDoi={() => setLan((n) => n + 1)}
                    nguon="truong_ca"
                  />
                ) : null
              ) : !x.xong && !x.doi_tac && chuyenDuoc(x) && x.phong_lam_duoc.length > 1 && (
                <div className="mt-1.5 flex gap-1.5">
                  <select
                    id={`chuyen-phong-${x.id}`}
                    aria-label={`Chuyển ${x.service_name} sang phòng`}
                    value={chonPhong[x.id] ?? ""}
                    onChange={(e) => setChonPhong((c) => ({ ...c, [x.id]: e.target.value }))}
                    className="min-h-9 min-w-0 flex-1 rounded-control border border-line bg-surface px-2 text-label text-ink"
                  >
                    <option value="">Chuyển sang phòng…</option>
                    {x.phong_lam_duoc
                      .filter((p) => p.id !== x.room_id)
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} — chờ {p.waiting}
                          {p.waiting >= p.threshold_waiting ? " (đầy)" : ""}
                        </option>
                      ))}
                  </select>
                  <button
                    type="button"
                    disabled={!chonPhong[x.id] || dangChuyen === x.id}
                    onClick={() => void chuyen(x)}
                    className="inline-flex min-h-9 items-center rounded-control bg-brand-600 px-3 text-label font-semibold text-white disabled:opacity-50"
                  >
                    {dangChuyen === x.id ? "Đang chuyển…" : "Chuyển"}
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {baoChuyen && (
        <p
          role={baoChuyen.ok ? "status" : "alert"}
          className={`mt-1.5 text-label ${baoChuyen.ok ? "text-success" : "text-danger"}`}
        >
          {baoChuyen.text}
        </p>
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
