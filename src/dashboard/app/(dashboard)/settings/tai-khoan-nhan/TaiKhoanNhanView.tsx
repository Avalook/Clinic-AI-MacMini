"use client";

// Danh mục TÀI KHOẢN NHẬN CHUYỂN KHOẢN (31/10/2026).
//
// Mỗi tài khoản một dòng: tên gọi · ngân hàng · số · chủ · cơ sở (hoặc dùng
// chung) · mặc định · đang dùng. [Sửa] mở form tại chỗ; [Tắt] / [Bật lại] là
// hoàn tác của nhau (không có Xoá — lần thu cũ vẫn trỏ vào tài khoản). Đặt mặc
// định thì máy chủ bỏ mặc định cũ của cùng cơ sở; tắt tài khoản mặc định thì bỏ
// luôn mặc định. Màn không tự quyết luật nào.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ChipChon from "@/components/ui/ChipChon";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { type TaiKhoan, useTaiKhoanNhan } from "../../thu-ngan/TaiKhoanNhan";

interface Form {
  id: string | null;
  ten_goi: string;
  ngan_hang: string;
  so_tai_khoan: string;
  chu_tai_khoan: string;
  location_id: string;
  mac_dinh: boolean;
  dang_dung: boolean;
}

const TRONG: Form = {
  id: null,
  ten_goi: "",
  ngan_hang: "",
  so_tai_khoan: "",
  chu_tai_khoan: "",
  location_id: "",
  mac_dinh: false,
  dang_dung: true,
};

function tuTaiKhoan(t: TaiKhoan): Form {
  return {
    id: t.id,
    ten_goi: t.ten_goi,
    ngan_hang: t.ngan_hang,
    so_tai_khoan: t.so_tai_khoan,
    chu_tai_khoan: t.chu_tai_khoan,
    location_id: t.location_id ?? "",
    mac_dinh: t.mac_dinh,
    dang_dung: t.dang_dung,
  };
}

export default function TaiKhoanNhanView({ coSo }: { coSo: { id: string; name: string }[] }) {
  const { ds, tai } = useTaiKhoanNhan();
  const [form, setForm] = useState<Form | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  async function gui(f: Form, cau: string) {
    setDang(true);
    setLoi(null);
    setBao(null);
    try {
      const r = await fetch("/api/tai-khoan-nhan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...f, location_id: f.location_id || null }),
      });
      const d = (await r.json().catch(() => null)) as { ok?: boolean } | null;
      if (!r.ok || !d?.ok) {
        setLoi(loiDocDuoc(d, `Chưa lưu được (HTTP ${r.status}).`));
        return;
      }
      setForm(null);
      setBao(cau);
      await tai();
    } catch {
      setLoi("Mất kết nối — chưa lưu.");
    } finally {
      setDang(false);
    }
  }

  const sua = (k: keyof Form, v: string | boolean) => setForm((f) => (f ? { ...f, [k]: v } : f));
  const ds_ = ds?.tai_khoan ?? [];

  return (
    <section aria-label="Tài khoản nhận chuyển khoản" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-2xl text-body text-ink-muted">
          Tài khoản ngân hàng quầy thu chọn khi khách chuyển khoản. Báo cáo cuối ngày, chốt ca và danh sách
          hoá đơn tách tiền chuyển khoản theo từng tài khoản. Mỗi cơ sở một tài khoản mặc định; cơ sở chỉ có
          một tài khoản thì quầy không phải chọn.
        </p>
        {ds?.quan_ly && !form ? (
          <Button type="button" variant="primary" onClick={() => setForm({ ...TRONG })}>
            + Thêm tài khoản
          </Button>
        ) : null}
      </div>

      {bao ? <p className="text-meta text-success">{bao}</p> : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}

      {form ? (
        <div className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
          <p className="text-emph font-semibold text-ink">{form.id ? "Sửa tài khoản" : "Thêm tài khoản"}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-meta text-ink-soft">
              Tên gọi ngắn (quầy thấy tên này)
              <ONhap value={form.ten_goi} maxLength={60} placeholder="vd VCB Hào Nam" onChange={(e) => sua("ten_goi", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-meta text-ink-soft">
              Ngân hàng
              <ONhap value={form.ngan_hang} maxLength={100} placeholder="vd Vietcombank" onChange={(e) => sua("ngan_hang", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-meta text-ink-soft">
              Số tài khoản
              <ONhap value={form.so_tai_khoan} maxLength={40} inputMode="numeric" onChange={(e) => sua("so_tai_khoan", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-meta text-ink-soft">
              Chủ tài khoản
              <ONhap value={form.chu_tai_khoan} maxLength={120} onChange={(e) => sua("chu_tai_khoan", e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-meta text-ink-soft">
              Thuộc cơ sở
              <OChon value={form.location_id} onChange={(e) => sua("location_id", e.target.value)}>
                <option value="">Dùng chung mọi cơ sở</option>
                {coSo.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </OChon>
            </label>
            <div className="flex flex-wrap items-end gap-2">
              <ChipChon chon={form.mac_dinh} disabled={!form.dang_dung} onDoi={() => sua("mac_dinh", !form.mac_dinh)}>
                Mặc định của cơ sở
              </ChipChon>
              <ChipChon chon={form.dang_dung} onDoi={() => sua("dang_dung", !form.dang_dung)}>
                Đang dùng
              </ChipChon>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="primary" disabled={dang} onClick={() => void gui(form, "Đã lưu tài khoản.")}>
              {dang ? "Đang lưu…" : "Lưu"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setForm(null)}>
              Thôi
            </Button>
          </div>
        </div>
      ) : null}

      {ds && ds_.length === 0 ? (
        <p className="text-body text-ink-muted">
          Chưa có tài khoản nào — quầy thu chuyển khoản vẫn bình thường, tiền ghi là “Chưa phân loại”.
        </p>
      ) : null}
      {!ds ? <p className="text-body text-ink-muted">Đang tải…</p> : null}

      <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface shadow-card">
        {ds_.map((t) => (
          <li key={t.id} className={`flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 ${t.dang_dung ? "" : "bg-surface-muted"}`}>
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2 text-emph font-medium text-ink">
                {t.ten_goi}
                {t.mac_dinh ? <Chip tone="brand">Mặc định</Chip> : null}
                {!t.dang_dung ? <Chip tone="neutral">Đã tắt</Chip> : null}
              </p>
              <p className="text-meta text-ink-muted">
                {t.ngan_hang} · <span className="tabular-nums">{t.so_tai_khoan}</span> · {t.chu_tai_khoan}
              </p>
              <p className="text-meta text-ink-muted">
                {t.ten_co_so ?? "Dùng chung mọi cơ sở"}
                {t.so_lan_thu > 0 ? ` · ${t.so_lan_thu.toLocaleString("vi-VN")} lần thu` : ""}
              </p>
            </div>
            {ds?.quan_ly ? (
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="secondary" onClick={() => setForm(tuTaiKhoan(t))}>
                  Sửa
                </Button>
                {t.dang_dung && !t.mac_dinh ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={dang}
                    onClick={() => void gui({ ...tuTaiKhoan(t), mac_dinh: true }, `“${t.ten_goi}” là mặc định.`)}
                  >
                    Đặt mặc định
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={dang}
                  onClick={() =>
                    void gui(
                      { ...tuTaiKhoan(t), dang_dung: !t.dang_dung, mac_dinh: false },
                      t.dang_dung ? `Đã tắt “${t.ten_goi}” — bấm Bật lại để hoàn tác.` : `Đã bật lại “${t.ten_goi}”.`,
                    )
                  }
                >
                  {t.dang_dung ? "Tắt" : "Bật lại"}
                </Button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
