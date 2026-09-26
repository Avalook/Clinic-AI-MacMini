"use client";

// Tab "Sửa · tạo mẫu": cột trái là danh sách mẫu (theo nhóm) + tạo mẫu mới;
// cột phải là trình sửa của mẫu đang chọn. Màn hẹp: danh sách là ô chọn ở trên.

import { useCallback, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";

import TrinhSuaMau from "./TrinhSuaMau";
import { guiLenh, type BangGan } from "./du-lieu";

const O_NHAP =
  "min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink";

export default function SuaMau({ bang, onDoi }: { bang: BangGan; onDoi: () => void }) {
  const [chon, setChon] = useState<string | null>(bang.mau[0]?.form_id ?? null);
  const [moTao, setMoTao] = useState(false);
  const [ten, setTen] = useState("");
  const [nhom, setNhom] = useState("");
  const [chep, setChep] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const choTao = bang.quyen.xuat_ban;
  // Đang có thay đổi chưa xuất bản → đổi mẫu thì hỏi tại chỗ trước (đổi là mất).
  const [ban, setBan] = useState(false);
  const [cho, setCho] = useState<string | null>(null);
  const onDoiBan = useCallback((b: boolean) => setBan(b), []);
  const doiMau = (f: string | null) => {
    if (f === chon) return;
    if (ban) setCho(f);
    else setChon(f);
  };

  const theoNhom = useMemo(() => {
    const m = new Map<string, typeof bang.mau>();
    for (const x of bang.mau) m.set(x.nhom, [...(m.get(x.nhom) ?? []), x]);
    return [...m.entries()];
  }, [bang]);

  const tao = async () => {
    setDang(true);
    setLoi(null);
    const kq = await guiLenh<{ form_id: string }>({
      thao_tac: "tao",
      ten,
      nhom,
      chep_tu: chep || null,
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setTen("");
    setChep("");
    setMoTao(false);
    setChon(kq.d.form_id);
    onDoi();
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
      <aside className="space-y-3">
        <label className="block lg:hidden">
          <span className="text-meta font-medium text-ink-muted">Mẫu đang sửa</span>
          <select
            value={chon ?? ""}
            onChange={(e) => doiMau(e.target.value || null)}
            className={`mt-1 ${O_NHAP}`}
          >
            {theoNhom.map(([n, ds]) => (
              <optgroup key={n} label={n}>
                {ds.map((m) => (
                  <option key={m.form_id} value={m.form_id}>
                    {m.ten}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <nav aria-label="Danh sách mẫu" className="hidden space-y-3 lg:block">
          {theoNhom.map(([n, ds]) => (
            <div key={n}>
              <p className="px-2 text-meta font-semibold uppercase tracking-wide text-ink-muted">{n}</p>
              <ul className="mt-1 space-y-0.5">
                {ds.map((m) => (
                  <li key={m.form_id}>
                    <button
                      type="button"
                      onClick={() => doiMau(m.form_id)}
                      aria-current={chon === m.form_id ? "true" : undefined}
                      className={`w-full rounded-control px-2 py-1.5 text-left text-body ${
                        chon === m.form_id
                          ? "bg-brand-50 font-semibold text-brand-700"
                          : "text-ink hover:bg-surface-muted"
                      }`}
                    >
                      {m.ten}
                      <span className="ml-1 text-meta font-normal text-ink-faint">bản {m.version ?? "—"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {choTao ? (
          moTao ? (
            <div className="space-y-2 rounded-card border border-hairline bg-surface p-3">
              <p className="text-body font-semibold text-ink">Tạo mẫu mới</p>
              <label className="block text-meta text-ink-muted">
                Tên mẫu
                <input value={ten} onChange={(e) => setTen(e.target.value)} className={`mt-1 ${O_NHAP}`} />
              </label>
              <label className="block text-meta text-ink-muted">
                Nhóm
                <input
                  value={nhom}
                  onChange={(e) => setNhom(e.target.value)}
                  list="nhom-mau-ket-qua"
                  placeholder="VD: Siêu âm chuyên khoa"
                  className={`mt-1 ${O_NHAP}`}
                />
                <datalist id="nhom-mau-ket-qua">
                  {theoNhom.map(([n]) => (
                    <option key={n} value={n} />
                  ))}
                </datalist>
              </label>
              <label className="block text-meta text-ink-muted">
                Bắt đầu từ
                <select value={chep} onChange={(e) => setChep(e.target.value)} className={`mt-1 ${O_NHAP}`}>
                  <option value="">Mẫu trống (có sẵn mục Kết luận)</option>
                  {bang.mau.map((m) => (
                    <option key={m.form_id} value={m.form_id}>
                      Chép từ: {m.ten}
                    </option>
                  ))}
                </select>
              </label>
              {loi ? (
                <p role="alert" className="text-meta text-danger">
                  {loi}
                </p>
              ) : null}
              <div className="flex gap-2">
                <Button type="button" variant="primary" disabled={dang || !ten.trim()} onClick={() => void tao()}>
                  {dang ? "Đang tạo…" : "Tạo mẫu"}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setMoTao(false)}>
                  Thôi
                </Button>
              </div>
            </div>
          ) : (
            <Button type="button" variant="secondary" onClick={() => setMoTao(true)}>
              + Tạo mẫu mới
            </Button>
          )
        ) : null}
      </aside>

      <div className="min-w-0 space-y-2">
        {cho !== null ? (
          <XacNhanTaiCho
            cau="Mẫu đang sửa còn thay đổi CHƯA xuất bản — sang mẫu khác là bỏ các thay đổi ấy."
            nhanDongY="Bỏ thay đổi, sang mẫu khác"
            onDongY={() => {
              setChon(cho);
              setCho(null);
              setBan(false);
            }}
            onThoi={() => setCho(null)}
          />
        ) : null}
        {chon ? (
          <TrinhSuaMau
            key={chon}
            formId={chon}
            choSua={bang.quyen.xuat_ban}
            onDaXuatBan={onDoi}
            onDoiBan={onDoiBan}
          />
        ) : (
          <p className="text-body text-ink-muted">Chưa có mẫu nào.</p>
        )}
      </div>
    </div>
  );
}
