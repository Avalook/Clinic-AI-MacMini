"use client";

// Tab "Ai xem hồ sơ" (24/11/2026, NĐ 356/2025): ai đã mở hồ sơ khách nào, lúc
// nào, loại gì, qua cửa nào. Máy chủ (`services/nhat_ky_xem_ho_so.py`) lọc theo
// phòng khám + quyền `permission.manage` (chỉ Quản lý) và trả sẵn
// nhãn vai / loại — màn chỉ vẽ. Chỉ MÃ khách, không họ tên.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { fmtDateTime } from "@/lib/datetime";

interface Dong {
  luc: string;
  nguoi_xem: string;
  staff_id: string;
  vai_ten: string;
  ma_khach: string;
  loai_ten: string;
  cua: string;
}
interface DuLieu {
  tu: string;
  den: string;
  dong: Dong[];
  bi_cat: boolean;
  nhan_vien: { staff_id: string; ten: string }[];
}

function homNay(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export default function AiXemHoSo() {
  const [tu, setTu] = useState(homNay());
  const [den, setDen] = useState(homNay());
  const [maKhach, setMaKhach] = useState("");
  const [maGui, setMaGui] = useState("");
  const [nhanVien, setNhanVien] = useState("");
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [khongQuyen, setKhongQuyen] = useState(false);

  useEffect(() => {
    let huy = false;
    const q = new URLSearchParams({ xem: "xem-ho-so", tu, den });
    if (maGui) q.set("ma_khach", maGui);
    if (nhanVien) q.set("staff_id", nhanVien);
    void fetch(`/api/ops/theo-doi?${q.toString()}`, { cache: "no-store" })
      .then(async (r) => {
        if (huy) return;
        if (!r.ok) {
          const body = (await r.json().catch(() => null)) as { message?: string } | null;
          setKhongQuyen(r.status === 403);
          setLoi(
            r.status === 403
              ? (body?.message ?? "Chỉ quản lý xem được nhật ký ai mở hồ sơ.")
              : "Không đọc được nhật ký.",
          );
          setDl(null);
          return;
        }
        setLoi(null);
        setDl((await r.json()) as DuLieu);
      })
      .catch(() => !huy && setLoi("Mất kết nối."));
    return () => {
      huy = true;
    };
  }, [tu, den, maGui, nhanVien]);

  if (khongQuyen) {
    return (
      <div className="p-4 lg:p-5">
        <p role="alert" className="rounded-control border border-line bg-surface-muted px-3 py-2 text-body text-ink-muted">
          {loi}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 lg:p-5">
      <p className="text-meta text-ink-muted">
        Mỗi lần nhân viên mở hồ sơ, bệnh án, kết quả, đơn thuốc hay bản in của một khách đều được ghi lại
        (cùng người mở cùng hồ sơ trong 5 phút tính một lần). Chỉ ghi mã khách, không ghi nội dung. Không ai
        sửa hay xoá được nhật ký này.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-meta text-ink-muted">
          Từ ngày
          <ONhap type="date" value={tu} onChange={(e) => e.target.value && setTu(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-meta text-ink-muted">
          Đến ngày
          <ONhap type="date" value={den} onChange={(e) => e.target.value && setDen(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-meta text-ink-muted">
          Nhân viên
          <OChon value={nhanVien} onChange={(e) => setNhanVien(e.target.value)}>
            <option value="">Tất cả</option>
            {(dl?.nhan_vien ?? []).map((n) => (
              <option key={n.staff_id} value={n.staff_id}>
                {n.ten}
              </option>
            ))}
          </OChon>
        </label>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setMaGui(maKhach.trim());
          }}
        >
          <label className="flex flex-col gap-1 text-meta text-ink-muted">
            Mã khách
            <ONhap
              type="search"
              value={maKhach}
              onChange={(e) => setMaKhach(e.target.value)}
              placeholder="Mã khách (đúng mã)"
            />
          </label>
          <Button type="submit" size="sm" variant="secondary">
            Lọc
          </Button>
          {maGui ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setMaKhach("");
                setMaGui("");
              }}
            >
              Bỏ lọc khách
            </Button>
          ) : null}
        </form>
      </div>

      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {!dl && !loi ? <p className="text-body text-ink-muted">Đang tải…</p> : null}

      {dl ? (
        <section className="space-y-2">
          <h2 className="flex flex-wrap items-center gap-2 text-emph font-semibold text-ink">
            {dl.dong.length} lượt mở hồ sơ
            {dl.bi_cat ? <Chip tone="warning">chỉ hiện 500 dòng mới nhất — lọc hẹp hơn để xem đủ</Chip> : null}
          </h2>
          <ul className="divide-y divide-hairline rounded-card border border-hairline bg-surface">
            {dl.dong.length === 0 ? (
              <li className="px-3 py-3 text-body text-ink-muted">Chưa có ai mở hồ sơ trong khoảng này.</li>
            ) : (
              dl.dong.map((d, i) => (
                <li
                  key={`${d.luc}-${d.staff_id}-${i}`}
                  className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 px-3 py-2 text-body"
                >
                  <span className="shrink-0 tabular-nums text-ink-muted">{fmtDateTime(d.luc)}</span>
                  <span className="min-w-0 flex-1">
                    <b className="font-semibold text-ink">{d.nguoi_xem}</b>
                    <span className="text-ink-muted"> ({d.vai_ten})</span>
                    <span className="text-ink"> mở {d.loai_ten.toLowerCase()} · khách </span>
                    <b className="font-semibold text-ink">{d.ma_khach}</b>
                  </span>
                  <span className="w-full break-all text-meta text-ink-faint sm:w-auto">{d.cua}</span>
                </li>
              ))
            )}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
