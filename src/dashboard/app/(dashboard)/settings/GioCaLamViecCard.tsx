"use client";

// Giờ ba ca làm việc — quản lý tự sửa.
//
// VÌ SAO Ở CÀI ĐẶT CHỨ KHÔNG Ở LỊCH LÀM VIỆC. Màn Lịch làm việc xếp AI trực ca
// nào; đây định nghĩa CA LÀ GÌ. Hai việc khác nhau, và cái sau là cấu hình của
// phòng khám nên đi cùng các luật đặt lịch khác, nơi đã có sẵn lớp gác Trưởng
// ca + Quản lý.
//
// VÌ SAO CÓ MÀN NÀY. Từ 21/08/2026 giờ ca đã ra khỏi mã nguồn vào
// `clinic.settings->'ca_lam_viec'` để mỗi phòng khám khai riêng — nhưng không
// có chỗ nào để khai, nghĩa là vẫn phải gọi người viết code. Đúng thứ mà việc
// đưa cấu hình ra khỏi mã sinh ra để tránh.
//
// CẢNH BÁO TẠI CHỖ, KHÔNG ĐỢI BẤM LƯU. Kiểu sai nguy hiểm nhất ở đây không báo
// gì: ca tràn ngoài giờ mở cửa vẫn lưu được nhưng bị CẮT lúc đọc — màn hình
// hiện 22:00 còn hệ chỉ nhận lịch tới 21:00. Máy chủ vẫn là chốt cuối; phần
// dưới đây chỉ để người dùng thấy sớm.

import { useEffect, useMemo, useState } from "react";
import { Clock, TriangleAlert } from "lucide-react";

import {
  CAC_CA,
  NHAN,
  soatLoi,
  type Khung,
  type GioMoCua,
  type MaCa,
} from "../../../lib/soat-gio-ca";

const O =
  "w-28 rounded-control border border-line bg-surface px-2 py-1.5 text-sm tabular-nums";

export default function GioCaLamViecCard() {
  const [ca, setCa] = useState<Record<MaCa, Khung> | null>(null);
  const [gio, setGio] = useState<GioMoCua>({});
  const [dangLuu, setDangLuu] = useState(false);
  const [loiLuu, setLoiLuu] = useState<string | null>(null);
  const [xong, setXong] = useState(false);
  const [khongDoc, setKhongDoc] = useState(false);

  useEffect(() => {
    let bo = false;
    fetch("/api/ca-lam-viec")
      .then((r) => (r.ok ? r.json() : null))
      .then(
        (
          d: {
            ca_lam_viec?: Record<string, Khung>;
            gio_mo_cua?: GioMoCua;
          } | null,
        ) => {
          if (bo) return;
          // Đọc hụt thì KHÔNG hiện ba ô trống: ba ô trống trông y hệt "chưa khai
          // ca", và quản lý sẽ gõ lại rồi ghi đè lên cấu hình đang chạy tốt.
          if (!d?.ca_lam_viec) {
            setKhongDoc(true);
            return;
          }
          const v = d.ca_lam_viec;
          setCa({
            SANG: v.SANG ?? { bat_dau: "", ket_thuc: "" },
            CHIEU: v.CHIEU ?? { bat_dau: "", ket_thuc: "" },
            TOI: v.TOI ?? { bat_dau: "", ket_thuc: "" },
          });
          setGio(d.gio_mo_cua ?? {});
        },
      )
      .catch(() => {
        if (!bo) setKhongDoc(true);
      });
    return () => {
      bo = true;
    };
  }, []);

  const loi = useMemo(() => (ca ? soatLoi(ca, gio) : []), [ca, gio]);

  function sua(ma: MaCa, o: keyof Khung, v: string) {
    setXong(false);
    setLoiLuu(null);
    setCa((cu) => (cu ? { ...cu, [ma]: { ...cu[ma], [o]: v } } : cu));
  }

  async function luu() {
    if (!ca) return;
    setDangLuu(true);
    setLoiLuu(null);
    setXong(false);
    try {
      const res = await fetch("/api/ca-lam-viec", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ca_lam_viec: ca }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          message?: string;
          error?: string;
        } | null;
        // Giữ nguyên câu của máy chủ: nó nói rõ ca nào sai và sai thế nào.
        setLoiLuu(d?.message ?? d?.error ?? "Không lưu được.");
        return;
      }
      setXong(true);
    } finally {
      setDangLuu(false);
    }
  }

  return (
    <section className="space-y-4 rounded-card border border-line bg-surface p-4 shadow-card">
      <header className="space-y-1">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Clock size={16} /> Giờ ca làm việc
        </h2>
        <p className="text-xs text-ink-muted">
          Một ngày chia làm ba ca. Phòng khám chỉ nhận đặt lịch trong các khung
          này — ngoài ca thì lưới không mời, và máy chủ từ chối.
        </p>
      </header>

      {khongDoc && (
        <p className="rounded-control bg-warning-bg px-3 py-2 text-xs text-warning">
          Không đọc được giờ ca đang dùng. Tải lại trang rồi thử lại — đừng nhập
          mới, vì có thể ghi đè lên cấu hình đang chạy.
        </p>
      )}

      {ca && (
        <>
          <div className="space-y-2">
            {CAC_CA.map((ma) => (
              <div key={ma} className="flex items-center gap-3">
                <span className="w-20 text-sm text-ink-soft">{NHAN[ma]}</span>
                <input
                  className={O}
                  value={ca[ma].bat_dau}
                  onChange={(e) => sua(ma, "bat_dau", e.target.value)}
                  placeholder="08:00"
                  aria-label={`${NHAN[ma]} bắt đầu`}
                />
                <span className="text-ink-faint">→</span>
                <input
                  className={O}
                  value={ca[ma].ket_thuc}
                  onChange={(e) => sua(ma, "ket_thuc", e.target.value)}
                  placeholder="13:00"
                  aria-label={`${NHAN[ma]} kết thúc`}
                />
              </div>
            ))}
          </div>

          {loi.length > 0 && (
            <ul className="space-y-1 rounded-control bg-warning-bg px-3 py-2 text-xs text-warning">
              {loi.map((x) => (
                <li key={x} className="flex gap-2">
                  <TriangleAlert size={14} className="mt-0.5 shrink-0" />
                  <span>{x}</span>
                </li>
              ))}
            </ul>
          )}

          {loiLuu && (
            <p className="whitespace-pre-line rounded-control bg-danger-bg px-3 py-2 text-xs text-danger">
              {loiLuu}
            </p>
          )}
          {xong && (
            <p className="rounded-control bg-success-bg px-3 py-2 text-xs text-success">
              Đã lưu. Lưới đặt lịch dùng giờ mới ngay từ lần mở tiếp theo. Lịch
              hẹn đã đặt trước đó giữ nguyên.
            </p>
          )}

          <button
            type="button"
            onClick={luu}
            disabled={dangLuu || loi.length > 0}
            className="rounded-control bg-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {dangLuu ? "Đang lưu…" : "Lưu giờ ca"}
          </button>
        </>
      )}
    </section>
  );
}
