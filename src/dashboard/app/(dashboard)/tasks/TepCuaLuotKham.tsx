"use client";

// TỆP KẾT QUẢ NGAY TRONG HỒ SƠ KHÁM (Tuyền chốt 16/09/2026).
//
// Kho tệp kết quả đã có từ 09/08 nhưng chỉ CSKH và Lễ tân mở được — tức chính
// những người không cầm kết quả trên tay. Bác sĩ siêu âm chụp xong, kỹ thuật
// viên có phiếu xét nghiệm, điều dưỡng cầm phim: cả ba phải nhờ người khác tải
// hộ, và bản gốc đi qua Zalo trước khi vào hồ sơ.
//
// Khối này bọc đúng component CSKH đang dùng, chỉ thêm việc tự nạp danh sách —
// hồ sơ khám là màn client, không có lát dữ liệu dựng sẵn ở server như màn kia.
// Dùng chung một component nghĩa là một chỗ sửa: nhãn, luật "chờ bác sĩ cho
// phép gửi", cách xem trước ảnh/PDF đều không thể trôi khỏi nhau.

import { useEffect, useState } from "react";

import TepKetQua, { type TepKetQuaRow } from "../customers/TepKetQua";

export default function TepCuaLuotKham({
  clinicPatientId,
  appointmentId,
  tieuDe = "Tệp kết quả của lượt khám",
}: {
  clinicPatientId: string;
  appointmentId: string | null;
  tieuDe?: string;
}) {
  const [items, setItems] = useState<TepKetQuaRow[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  // Đổi số này là nạp lại. Khối con tải lên xong gọi `onDaThayDoi` → tăng số →
  // effect chạy lại. Không có nó, tệp vừa tải lên thành công mà không hiện ra.
  const [lanNap, setLanNap] = useState(0);

  useEffect(() => {
    let song = true;
    void fetch(
      `/api/cskh/ket-qua?clinic_patient_id=${encodeURIComponent(clinicPatientId)}`,
      { cache: "no-store" },
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((json: { items?: TepKetQuaRow[] } | null) => {
        if (!song) return;
        // "Không đọc được" KHÁC "chưa có tệp nào" — hiện nhầm cái thứ nhất
        // thành cái thứ hai là mời người ta tải lên lần thứ hai.
        if (json === null) setLoi("Không đọc được danh sách tệp kết quả.");
        else {
          setLoi(null);
          // Chỉ tệp CỦA LƯỢT NÀY khi biết lượt — khách tái khám nhiều lần thì
          // ảnh siêu âm lần trước không được lẫn vào phiếu lần này.
          const ds = json.items ?? [];
          setItems(appointmentId ? ds.filter((t) => t.appointment_id === appointmentId) : ds);
        }
      })
      .catch(() => song && setLoi("Không đọc được danh sách tệp kết quả."));
    return () => {
      song = false;
    };
  }, [clinicPatientId, appointmentId, lanNap]);

  return (
    <section className="rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{tieuDe}</h3>
        <p className="text-label text-ink-muted">
          Ảnh · video · phiếu xét nghiệm · phim chụp
        </p>
      </div>
      {loi ? (
        <p className="mt-2 text-label text-danger">{loi}</p>
      ) : items === null ? (
        <p className="mt-2 text-label text-ink-muted">Đang đọc danh sách tệp…</p>
      ) : (
        <div className="mt-2">
          <TepKetQua
            clinicPatientId={clinicPatientId}
            appointmentId={appointmentId}
            items={items}
            onDaThayDoi={() => setLanNap((n) => n + 1)}
          />
        </div>
      )}
    </section>
  );
}
