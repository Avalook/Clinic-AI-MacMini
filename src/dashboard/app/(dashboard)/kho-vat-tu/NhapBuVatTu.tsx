"use client";

// Nhập bù dòng quầy quên ghi: chọn khách, vật tư, số lượng, nơi lấy, lý do. Chỉ trừ
// kho, không phát sinh tiền (Tuyền chốt A). Máy chủ kiểm mọi thứ.

import { useState } from "react";

import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import { guiVatTu, khoaChongGuiTrung, xoaKhoaChongGuiTrung } from "./gui-vat-tu";
import type { NoiChua } from "./TonVatTu";

interface KhachTim {
  clinic_patient_id: string;
  full_name: string;
  patient_code: string | null;
  phone_primary: string | null;
}

export default function NhapBuVatTu({
  noiChua,
  vatTu,
  onXong,
}: {
  noiChua: NoiChua[];
  vatTu: DongVatTu[];
  onXong: () => void;
}) {
  const [q, setQ] = useState("");
  const [ketQua, setKetQua] = useState<KhachTim[] | null>(null);
  const [khach, setKhach] = useState<KhachTim | null>(null);
  const [vt, setVt] = useState("");
  const [so, setSo] = useState("1");
  const [noi, setNoi] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function tim() {
    setLoi(null);
    const r = await fetch(`/api/vat-tu-kho/ban-tim-khach?${new URLSearchParams({ q })}`, { cache: "no-store" }).catch(() => null);
    const d = r?.ok ? ((await r.json().catch(() => null)) as { items?: KhachTim[] } | null) : null;
    if (!d?.items) {
      setLoi("Không tìm được khách — thử lại.");
      return;
    }
    setKetQua(d.items);
  }

  async function luu() {
    if (!khach) return;
    setDang(true);
    setLoi(null);
    const body = {
      clinic_patient_id: khach.clinic_patient_id,
      vat_tu_id: vt,
      so_luong: so,
      room_id: noi || null,
      ly_do: lyDo,
    };
    const khoa = khoaChongGuiTrung(body);
    const kq = await guiVatTu("ban-nhap-bu", body, khoa);
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    xoaKhoaChongGuiTrung(khoa);
    onXong();
  }

  return (
    <div className="space-y-2 rounded-card border border-line bg-surface p-3">
      <p className="text-meta text-ink-muted">Dòng này chỉ trừ kho, không phát sinh tiền.</p>
      {khach ? (
        <p className="text-body text-ink">
          Khách: {khach.full_name} {khach.patient_code ? `(${khach.patient_code})` : ""}{" "}
          <Button type="button" size="sm" variant="ghost" onClick={() => setKhach(null)}>Đổi khách</Button>
        </p>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap items-end gap-2">
            <label className="min-w-40 flex-1 text-meta text-ink-soft">
              <span className="mb-1 block">Tìm khách (tên, mã, số điện thoại)</span>
              <ONhap aria-label="Tìm khách" className="w-full" value={q} onChange={(e) => setQ(e.target.value)} />
            </label>
            <Button type="button" size="sm" variant="secondary" disabled={q.trim().length < 2} onClick={() => void tim()}>Tìm</Button>
          </div>
          {ketQua?.length === 0 ? <p className="text-meta text-ink-muted">Không thấy khách nào.</p> : null}
          {ketQua?.map((k) => (
            <Button key={k.clinic_patient_id} type="button" size="sm" variant="ghost" onClick={() => setKhach(k)}>
              {k.full_name} {k.patient_code ? `(${k.patient_code})` : ""}
            </Button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-40 flex-1 text-meta text-ink-soft">
          <span className="mb-1 block">Vật tư</span>
          <OChon aria-label="Vật tư nhập bù" className="w-full" value={vt} onChange={(e) => setVt(e.target.value)}>
            <option value="">Chọn vật tư</option>
            {vatTu.map((v) => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </OChon>
        </label>
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Số lượng</span>
          <ONhap aria-label="Số lượng nhập bù" inputMode="decimal" className="w-24" value={so} onChange={(e) => setSo(e.target.value)} />
        </label>
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Lấy từ</span>
          <OChon aria-label="Nơi lấy nhập bù" value={noi} onChange={(e) => setNoi(e.target.value)}>
            {noiChua.map((n) => (
              <option key={n.room_id ?? "kho"} value={n.room_id ?? ""}>{n.ten}</option>
            ))}
          </OChon>
        </label>
        <label className="min-w-40 flex-1 text-meta text-ink-soft">
          <span className="mb-1 block">Lý do</span>
          <ONhap aria-label="Lý do nhập bù" className="w-full" value={lyDo} onChange={(e) => setLyDo(e.target.value)} />
        </label>
        <Button type="button" size="sm" disabled={dang || !khach || !vt} onClick={() => void luu()}>
          {dang ? "Đang lưu…" : "Lưu nhập bù"}
        </Button>
      </div>
      {loi ? <p role="alert" className="text-meta text-danger">{loi}</p> : null}
    </div>
  );
}
