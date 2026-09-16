"use client";

// Bàn của đối tác: DANH SÁCH KHÁCH, mỗi khách một thẻ, dưới là việc của họ.
//
// Bản đầu liệt kê chỉ định phẳng — mỗi việc một dòng. Tuyền bác đúng: bàn đón
// NGƯỜI, không đón việc. Một khách tới lấy máu có thể mang hai ba chỉ định, và
// danh sách phẳng làm cùng một người hiện ba dòng cách xa nhau, đúng lúc người
// ngồi bàn đang cầm ống nghiệm và cần biết "người này còn gì nữa không".
//
// MỖI VIỆC VẪN MỘT NÚT GỬI RIÊNG, và vẫn KHÔNG có ô "chọn bệnh nhân". Đối tác
// không khai người nhận; họ chỉ nói "đây là kết quả của việc này", còn việc ấy
// thuộc về ai là do máy chủ tra ra. Thiếu ràng buộc đó thì một tài khoản ngoài
// phòng khám gửi được tệp cho bất kỳ ai — chỉ cần đoán đúng một mã.

import { useCallback, useEffect, useRef, useState } from "react";

interface Viec {
  chi_dinh_id: string;
  ten_dich_vu: string;
  chi_dinh_luc: string | null;
}

interface Khach {
  clinic_patient_id: string;
  ten_khach: string;
  ma_khach: string;
  cho_tu: string | null;
  viec: Viec[];
}

type KetQua = { khach: Khach[]; so_viec: number } | { loi: string };

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

function choBaoLau(iso: string | null): string {
  if (!iso) return "";
  const phut = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(phut) || phut < 0) return "";
  if (phut < 60) return `chờ ${phut} phút`;
  const gio = Math.floor(phut / 60);
  if (gio < 24) return `chờ ${gio} giờ`;
  return `chờ ${Math.floor(gio / 24)} ngày`;
}

// Đọc danh sách — KHÔNG đụng state. Tách ra để chỗ gọi tự quyết định có nhận kết
// quả hay không: lần tải đầu chạy trong effect và phải bỏ kết quả nếu người dùng
// đã rời màn, còn lần tải lại sau khi gửi thì luôn nhận.
async function docDanhSach(): Promise<KetQua> {
  try {
    const r = await fetch("/api/doi-tac", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | { khach?: Khach[]; so_viec?: number; error?: string }
      | null;
    if (!r.ok) return { loi: d?.error ?? "Không đọc được danh sách khách." };
    return { khach: d?.khach ?? [], so_viec: d?.so_viec ?? 0 };
  } catch {
    return { loi: "Mất kết nối tới máy chủ." };
  }
}

export default function BangDoiTac() {
  const [ds, setDs] = useState<Khach[] | null>(null);
  const [soViec, setSoViec] = useState(0);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);

  const nhan = useCallback((kq: KetQua) => {
    if ("loi" in kq) {
      setLoi(kq.loi);
      return;
    }
    setLoi(null);
    setDs(kq.khach);
    setSoViec(kq.so_viec);
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

  const gui = useCallback(
    async (v: Viec, k: Khach, tep: File) => {
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
        setXong(`Đã gửi ${v.ten_dich_vu} của ${k.ten_khach}.`);
        await tai();
      } catch {
        setLoi("Mất kết nối — tệp CHƯA được gửi.");
      } finally {
        setDangGui(null);
      }
    },
    [tai],
  );

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

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="text-body font-semibold text-ink">
          {ds.length} khách đang chờ
        </p>
        <p className="text-meta text-ink-muted">{soViec} việc chưa có kết quả</p>
      </div>

      {loi ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger"
        >
          {loi}
        </p>
      ) : null}
      {xong ? (
        <p className="rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">
          {xong}
        </p>
      ) : null}

      {ds.length === 0 ? (
        <div className="rounded-card border border-line bg-surface p-6 text-center shadow-card">
          <p className="text-body text-ink">Không có khách nào đang chờ.</p>
          <p className="mt-1 text-meta text-ink-muted">
            Phòng khám gửi khách sang thì họ hiện ở đây.
          </p>
        </div>
      ) : (
        ds.map((k) => (
          <MotKhach
            key={k.clinic_patient_id}
            khach={k}
            dangGui={dangGui}
            onGui={(v, tep) => gui(v, k, tep)}
          />
        ))
      )}
    </section>
  );
}

function MotKhach({
  khach,
  dangGui,
  onGui,
}: {
  khach: Khach;
  dangGui: string | null;
  onGui: (viec: Viec, tep: File) => void;
}) {
  return (
    <article className="rounded-card border border-line bg-surface shadow-card">
      <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <p className="text-body font-semibold text-ink">{khach.ten_khach}</p>
          <p className="text-meta text-ink-muted">{khach.ma_khach}</p>
        </div>
        <p className="text-meta text-ink-muted">
          {gioVn(khach.cho_tu)}
          {choBaoLau(khach.cho_tu) ? ` · ${choBaoLau(khach.cho_tu)}` : ""}
        </p>
      </header>
      <ul className="divide-y divide-line">
        {khach.viec.map((v) => (
          <MotViec
            key={v.chi_dinh_id}
            viec={v}
            dangGui={dangGui === v.chi_dinh_id}
            onGui={(tep) => onGui(v, tep)}
          />
        ))}
      </ul>
    </article>
  );
}

function MotViec({
  viec,
  dangGui,
  onGui,
}: {
  viec: Viec;
  dangGui: boolean;
  onGui: (tep: File) => void;
}) {
  const oTep = useRef<HTMLInputElement>(null);
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="text-body text-ink">{viec.ten_dich_vu}</p>
        <p className="text-meta text-ink-muted">
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
            if (t) onGui(t);
          }}
        />
        <button
          type="button"
          disabled={dangGui}
          onClick={() => oTep.current?.click()}
          className="inline-flex min-h-10 items-center rounded-control border border-brand-500 bg-brand-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          {dangGui ? "Đang gửi…" : "Tải kết quả lên"}
        </button>
      </div>
    </li>
  );
}
