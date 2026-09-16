"use client";

// Danh sách việc chờ kết quả + ô gửi tệp cho từng việc.
//
// MỖI VIỆC MỘT NÚT GỬI, không có ô "chọn bệnh nhân". Đối tác không khai người
// nhận; họ chỉ nói "đây là kết quả của việc này", còn việc ấy thuộc về ai là do
// máy chủ tra ra. Thiếu ràng buộc đó thì một tài khoản ngoài phòng khám gửi
// được tệp cho bất kỳ bệnh nhân nào — chỉ cần đoán đúng một mã.

import { useCallback, useEffect, useRef, useState } from "react";

interface Viec {
  chi_dinh_id: string;
  ten_dich_vu: string;
  ten_khach: string;
  ma_khach: string;
  chi_dinh_luc: string | null;
}

function gioVn(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

// Đọc danh sách — KHÔNG đụng state. Tách ra để chỗ gọi tự quyết định có nhận kết
// quả hay không: lần tải đầu chạy trong effect và phải bỏ kết quả nếu người dùng
// đã rời màn, còn lần tải lại sau khi gửi thì luôn nhận.
async function docDanhSach(): Promise<{ items: Viec[] } | { loi: string }> {
  try {
    const r = await fetch("/api/doi-tac", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | { items?: Viec[]; error?: string }
      | null;
    if (!r.ok) return { loi: d?.error ?? "Không đọc được danh sách việc." };
    return { items: d?.items ?? [] };
  } catch {
    return { loi: "Mất kết nối tới máy chủ." };
  }
}

export default function BangDoiTac() {
  const [ds, setDs] = useState<Viec[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);

  const nhan = useCallback((kq: { items: Viec[] } | { loi: string }) => {
    if ("loi" in kq) {
      setLoi(kq.loi);
      return;
    }
    setLoi(null);
    setDs(kq.items);
  }, []);

  const tai = useCallback(async () => {
    nhan(await docDanhSach());
  }, [nhan]);

  useEffect(() => {
    // Cờ huỷ: gửi tệp xong là màn tải lại, nên hai lần đọc có thể chồng nhau và
    // lần cũ về sau sẽ dựng lại đúng việc vừa gửi xong.
    let huy = false;
    void docDanhSach().then((kq) => {
      if (!huy) nhan(kq);
    });
    return () => {
      huy = true;
    };
  }, [nhan]);

  if (loi && ds === null) {
    return (
      <section className="rounded-card border border-line bg-surface p-4 shadow-card">
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      </section>
    );
  }
  if (ds === null) {
    return <p className="text-body text-ink-muted">Đang tải…</p>;
  }
  if (ds.length === 0) {
    return (
      <section className="rounded-card border border-line bg-surface p-6 text-center shadow-card">
        <p className="text-body text-ink">Không có việc nào đang chờ kết quả.</p>
        <p className="mt-1 text-meta text-ink-muted">
          Phòng khám gửi việc sang thì nó hiện ở đây.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {xong ? (
        <p className="rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">
          {xong}
        </p>
      ) : null}
      {ds.map((v) => (
        <MotViec
          key={v.chi_dinh_id}
          viec={v}
          dangGui={dangGui === v.chi_dinh_id}
          onGui={async (tep) => {
            setDangGui(v.chi_dinh_id);
            setLoi(null);
            setXong(null);
            try {
              const fd = new FormData();
              fd.append("chi_dinh_id", v.chi_dinh_id);
              fd.append("file", tep);
              const r = await fetch("/api/doi-tac", { method: "POST", body: fd });
              const d = (await r.json().catch(() => null)) as
                | { error?: string; message?: string }
                | null;
              if (!r.ok) {
                setLoi(d?.message ?? d?.error ?? "Gửi không được.");
                return;
              }
              setXong(`Đã gửi kết quả cho ${v.ten_khach}.`);
              await tai();
            } catch {
              setLoi("Mất kết nối — tệp CHƯA được gửi.");
            } finally {
              setDangGui(null);
            }
          }}
        />
      ))}
    </section>
  );
}

function MotViec({
  viec,
  dangGui,
  onGui,
}: {
  viec: Viec;
  dangGui: boolean;
  onGui: (tep: File) => Promise<void>;
}) {
  const oTep = useRef<HTMLInputElement>(null);
  return (
    <article className="rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-body font-semibold text-ink">{viec.ten_khach}</p>
          <p className="text-meta text-ink-muted">
            {viec.ma_khach} · {viec.ten_dich_vu}
          </p>
          <p className="mt-1 text-meta text-ink-muted">
            Phòng khám gửi lúc {gioVn(viec.chi_dinh_luc)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={oTep}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={(e) => {
              const t = e.target.files?.[0];
              // Xoá giá trị NGAY: chọn lại đúng tệp vừa gửi hỏng phải bắn được
              // sự kiện change lần nữa, không thì nút im lặng không làm gì.
              e.target.value = "";
              if (t) void onGui(t);
            }}
          />
          <button
            type="button"
            disabled={dangGui}
            onClick={() => oTep.current?.click()}
            className="inline-flex min-h-10 items-center rounded-control border border-brand-500 bg-brand-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {dangGui ? "Đang gửi…" : "Chọn tệp kết quả"}
          </button>
        </div>
      </div>
      <p className="mt-2 text-meta text-ink-muted">
        Nhận ảnh hoặc phiếu PDF. Gửi xong việc này rời khỏi danh sách.
      </p>
    </article>
  );
}
