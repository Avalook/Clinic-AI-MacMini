"use client";

// Trình sửa MỘT mẫu kết quả (27/09/2026).
//
// Sửa trên bản đang dùng rồi [Xuất bản] thành BẢN MỚI. Phiếu đã điền ghim bản cũ
// nên không chữ nào của phiếu cũ đổi. Đổi tên ô KHÔNG đổi mã ô (mã là khoá của dữ
// liệu đã điền); ô mới nhận mã lúc xuất bản, từ tên cuối cùng (`ganMaMoi`).
// Gửi kèm `expected_version`: ai vừa xuất bản trước thì máy chủ trả 409 — không
// lặng lẽ đè bản của người kia.

import { useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { fmtDateTime } from "@/lib/datetime";
import {
  NHAN_KIEU,
  donKhung,
  ganMaMoi,
  nhacTruocXuatBan,
  type KieuO,
  type MucMau,
  type OMau,
} from "@/lib/sua-mau";

import { docJson, guiLenh, type BieuMau } from "./du-lieu";

/** Ô nhập KHÔNG kèm độ rộng — nơi dùng tự thêm (w-full / w-36…), tránh hai
 *  lớp độ rộng giành nhau. */
const O_GOC =
  "min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink disabled:bg-surface-sunken disabled:text-ink-soft";
const O_NHAP = `${O_GOC} w-full`;

let dem = 0;
const khoa = () => `k${++dem}`;

/** Gắn khoá vẽ cho mọi mục / ô / cột (khung từ máy chủ không có). */
function coKhoa(khung: MucMau[]): MucMau[] {
  return khung.map((m) => ({
    ...m,
    k: m.k ?? khoa(),
    cot: m.cot?.map((c) => ({ ...c, k: c.k ?? khoa() })),
    block: m.block.map((o) => ({ ...o, k: o.k ?? khoa() })),
  }));
}

function doiCho<T>(ds: T[], i: number, j: number): T[] {
  if (j < 0 || j >= ds.length) return ds;
  const ra = [...ds];
  [ra[i], ra[j]] = [ra[j], ra[i]];
  return ra;
}

export default function TrinhSuaMau({
  formId,
  choSua,
  onDaXuatBan,
  onDoiBan,
}: {
  formId: string;
  choSua: boolean;
  onDaXuatBan: () => void;
  /** Báo cho cha: đang có thay đổi chưa xuất bản (để hỏi trước khi rời). */
  onDoiBan?: (ban: boolean) => void;
}) {
  const [goc, setGoc] = useState<BieuMau | null>(null);
  const [khung, setKhung] = useState<MucMau[]>([]);
  const [ten, setTen] = useState("");
  const [loi, setLoi] = useState<string | null>(null);
  const [xungDot, setXungDot] = useState(false);
  const [bao, setBao] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [lanNap, setLanNap] = useState(0);

  useEffect(() => {
    let huy = false;
    void docJson<BieuMau>(`/api/mau-ket-qua?xem=bieu-mau&form_id=${formId}`).then((kq) => {
      if (huy) return;
      if (!kq.ok) {
        setLoi(kq.loi);
        return;
      }
      setGoc(kq.d);
      setKhung(coKhoa(kq.d.khung));
      setTen(kq.d.ten);
      setLoi(null);
      setXungDot(false);
    });
    return () => {
      huy = true;
    };
  }, [formId, lanNap]);

  const doi = useMemo(() => {
    if (!goc) return false;
    return ten.trim() !== goc.ten || JSON.stringify(donKhung(khung)) !== JSON.stringify(donKhung(goc.khung));
  }, [goc, khung, ten]);

  useEffect(() => {
    onDoiBan?.(doi);
  }, [doi, onDoiBan]);

  const nhac = useMemo(() => nhacTruocXuatBan(khung), [khung]);

  if (loi && !goc) {
    return (
      <p role="alert" className="text-body text-danger">
        {loi}
      </p>
    );
  }
  if (!goc) return <p className="text-body text-ink-muted">Đang tải mẫu…</p>;

  const suaMuc = (i: number, sua: (m: MucMau) => MucMau) =>
    setKhung((k) => k.map((m, j) => (j === i ? sua(m) : m)));
  const suaO = (i: number, j: number, sua: (o: OMau) => OMau) =>
    suaMuc(i, (m) => ({ ...m, block: m.block.map((o, x) => (x === j ? sua(o) : o)) }));

  const xuatBan = async () => {
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await guiLenh<{ version: number }>({
      thao_tac: "xuat-ban",
      form_id: formId,
      khung: donKhung(ganMaMoi(khung)),
      expected_version: goc.version,
      ten: ten.trim() !== goc.ten ? ten.trim() : null,
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      setXungDot(kq.status === 409);
      // Người khác vừa xuất bản: danh sách bên trái (số bản, tên) cũng đã cũ.
      if (kq.status === 409) onDaXuatBan();
      return;
    }
    setBao(`Đã xuất bản bản ${kq.d.version}. Phiếu mở từ giờ dùng bản này.`);
    setLanNap((n) => n + 1);
    onDaXuatBan();
  };

  const khoaSua = !choSua || dang;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3 rounded-card border border-hairline bg-surface p-3">
        <label className="min-w-0 flex-1 basis-72 text-meta text-ink-muted">
          Tên mẫu
          <input
            value={ten}
            disabled={khoaSua}
            onChange={(e) => setTen(e.target.value)}
            className={`mt-1 ${O_NHAP}`}
          />
        </label>
        <div className="text-meta text-ink-muted">
          <p>
            <Chip tone="neutral">{goc.nhom}</Chip> · đang dùng bản <b className="text-ink">{goc.version}</b>
            {goc.xuat_ban_luc ? ` · ${fmtDateTime(goc.xuat_ban_luc)}` : ""}
          </p>
          <p>{goc.so_phieu_da_dien} phiếu đã điền — vẫn giữ bản cũ sau khi xuất bản.</p>
        </div>
      </div>

      {!choSua ? (
        <p className="rounded-control bg-surface-muted px-3 py-2 text-meta text-ink-muted">
          Bạn đang xem — cần quyền “Xuất bản phiên bản biểu mẫu” để sửa.
        </p>
      ) : null}

      {khung.map((m, i) => (
        <section key={m.k} className="space-y-2 rounded-card border border-hairline bg-surface p-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={m.ten}
              disabled={khoaSua}
              aria-label="Tên mục"
              placeholder="Tên mục (VD: Mô tả hình ảnh)"
              onChange={(e) => suaMuc(i, (x) => ({ ...x, ten: e.target.value }))}
              className={`${O_GOC} min-w-0 flex-1 basis-60 font-semibold`}
            />
            <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                disabled={khoaSua}
                checked={Boolean(m.cot)}
                onChange={(e) =>
                  suaMuc(i, (x) =>
                    e.target.checked
                      ? { ...x, cot: [{ ma: "", ten: "Bên trái", k: khoa() }, { ma: "", ten: "Bên phải", k: khoa() }] }
                      : { ...x, cot: undefined },
                  )
                }
              />
              Dạng bảng (nhiều cột)
            </label>
            {choSua ? (
              <span className="flex gap-1">
                <Button type="button" size="sm" variant="ghost" aria-label="Đưa mục lên" disabled={dang || i === 0} onClick={() => setKhung((k) => doiCho(k, i, i - 1))}>
                  ↑
                </Button>
                <Button type="button" size="sm" variant="ghost" aria-label="Đưa mục xuống" disabled={dang || i === khung.length - 1} onClick={() => setKhung((k) => doiCho(k, i, i + 1))}>
                  ↓
                </Button>
                <Button type="button" size="sm" variant="danger" disabled={dang} onClick={() => setKhung((k) => k.filter((_, j) => j !== i))}>
                  Xoá mục
                </Button>
              </span>
            ) : null}
          </div>

          {m.cot ? (
            <div className="flex flex-wrap items-center gap-2 rounded-control bg-surface-muted p-2">
              <span className="text-meta text-ink-muted">Cột:</span>
              {m.cot.map((c, x) => (
                <span key={c.k} className="flex items-center gap-1">
                  <input
                    value={c.ten}
                    disabled={khoaSua}
                    aria-label={`Tên cột ${x + 1}`}
                    onChange={(e) =>
                      suaMuc(i, (mm) => ({
                        ...mm,
                        cot: mm.cot?.map((cc, y) => (y === x ? { ...cc, ten: e.target.value } : cc)),
                      }))
                    }
                    className={`${O_GOC} w-32`}
                  />
                  {choSua && m.cot!.length > 1 ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      aria-label={`Xoá cột ${c.ten}`}
                      disabled={dang}
                      onClick={() => suaMuc(i, (mm) => ({ ...mm, cot: mm.cot?.filter((_, y) => y !== x) }))}
                    >
                      ×
                    </Button>
                  ) : null}
                </span>
              ))}
              {choSua && m.cot.length < 8 ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={dang}
                  onClick={() =>
                    suaMuc(i, (mm) => ({ ...mm, cot: [...(mm.cot ?? []), { ma: "", ten: `Cột ${(mm.cot?.length ?? 0) + 1}`, k: khoa() }] }))
                  }
                >
                  + Cột
                </Button>
              ) : null}
            </div>
          ) : null}

          <ul className="space-y-2">
            {m.block.map((o, j) => (
              <li key={o.k} className="space-y-2 rounded-control border border-line p-2">
                {/* Hai hàng: tên + nút / kiểu + đơn vị — cột phải hẹp (danh sách mẫu
                    chiếm cột trái) nên 4 cột một hàng cắt chữ "Đoạn văn". */}
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    value={o.ten}
                    disabled={khoaSua}
                    aria-label="Tên ô"
                    placeholder="Tên ô (VD: Buồng trứng trái)"
                    onChange={(e) => suaO(i, j, (x) => ({ ...x, ten: e.target.value }))}
                    className={`${O_GOC} min-w-0 flex-1 basis-56`}
                  />
                  <select
                    value={o.kieu}
                    disabled={khoaSua}
                    aria-label={`Kiểu ô ${o.ten}`}
                    onChange={(e) => suaO(i, j, (x) => ({ ...x, kieu: e.target.value as KieuO }))}
                    className={`${O_GOC} w-36`}
                  >
                    {(Object.keys(NHAN_KIEU) as KieuO[]).map((k) => (
                      <option key={k} value={k}>
                        {NHAN_KIEU[k]}
                      </option>
                    ))}
                  </select>
                  <input
                    value={o.goi_y ?? ""}
                    disabled={khoaSua}
                    aria-label={`Đơn vị / gợi ý của ${o.ten}`}
                    placeholder="Đơn vị (mm, tuần…)"
                    onChange={(e) => suaO(i, j, (x) => ({ ...x, goi_y: e.target.value }))}
                    className={`${O_GOC} w-40`}
                  />
                  {choSua ? (
                    <span className="flex gap-1">
                      <Button type="button" size="sm" variant="ghost" aria-label="Đưa ô lên" disabled={dang || j === 0} onClick={() => suaMuc(i, (mm) => ({ ...mm, block: doiCho(mm.block, j, j - 1) }))}>
                        ↑
                      </Button>
                      <Button type="button" size="sm" variant="ghost" aria-label="Đưa ô xuống" disabled={dang || j === m.block.length - 1} onClick={() => suaMuc(i, (mm) => ({ ...mm, block: doiCho(mm.block, j, j + 1) }))}>
                        ↓
                      </Button>
                      <Button type="button" size="sm" variant="ghost" aria-label={`Xoá ô ${o.ten}`} disabled={dang} onClick={() => suaMuc(i, (mm) => ({ ...mm, block: mm.block.filter((_, x) => x !== j) }))}>
                        ×
                      </Button>
                    </span>
                  ) : null}
                </div>

                {o.kieu === "chon" ? (
                  <label className="block text-meta text-ink-muted">
                    Lựa chọn — mỗi dòng một
                    <textarea
                      value={(o.chon ?? []).join("\n")}
                      disabled={khoaSua}
                      rows={Math.max(2, (o.chon ?? []).length)}
                      onChange={(e) => suaO(i, j, (x) => ({ ...x, chon: e.target.value.split("\n") }))}
                      className={`mt-1 ${O_NHAP} py-2`}
                    />
                  </label>
                ) : null}

                {m.cot ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-meta text-ink-muted">Câu bình thường điền sẵn:</span>
                    {m.cot.map((c) => {
                      const md = typeof o.mac_dinh === "object" ? o.mac_dinh : {};
                      return (
                        <input
                          key={c.k}
                          value={c.ma ? (md[c.ma] ?? "") : ""}
                          disabled={khoaSua || !c.ma}
                          aria-label={`Điền sẵn cột ${c.ten}`}
                          placeholder={c.ma ? c.ten : `${c.ten} (lưu mẫu trước)`}
                          onChange={(e) =>
                            suaO(i, j, (x) => ({
                              ...x,
                              mac_dinh: { ...(typeof x.mac_dinh === "object" ? x.mac_dinh : {}), [c.ma]: e.target.value },
                            }))
                          }
                          className={`${O_GOC} w-40`}
                        />
                      );
                    })}
                  </div>
                ) : o.kieu === "chon" ? (
                  <label className="flex flex-wrap items-center gap-2 text-meta text-ink-muted">
                    Chọn sẵn
                    <select
                      value={typeof o.mac_dinh === "string" ? o.mac_dinh : ""}
                      disabled={khoaSua}
                      onChange={(e) => suaO(i, j, (x) => ({ ...x, mac_dinh: e.target.value || undefined }))}
                      className={`${O_GOC} w-auto`}
                    >
                      <option value="">— không —</option>
                      {(o.chon ?? []).filter((x) => x.trim()).map((x) => (
                        <option key={x} value={x.trim()}>
                          {x.trim()}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : o.kieu === "text" || o.kieu === "doan_van" ? (
                  <input
                    value={typeof o.mac_dinh === "string" ? o.mac_dinh : ""}
                    disabled={khoaSua}
                    aria-label={`Câu bình thường điền sẵn của ${o.ten}`}
                    placeholder="Câu bình thường điền sẵn (bỏ trống nếu là số đo)"
                    onChange={(e) => suaO(i, j, (x) => ({ ...x, mac_dinh: e.target.value }))}
                    className={O_NHAP}
                  />
                ) : null}
              </li>
            ))}
          </ul>
          {choSua ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={dang}
              onClick={() =>
                suaMuc(i, (mm) => ({ ...mm, block: [...mm.block, { ma: "", ten: "", kieu: "text", k: khoa() }] }))
              }
            >
              + Thêm ô
            </Button>
          ) : null}
        </section>
      ))}

      {choSua ? (
        <Button
          type="button"
          variant="secondary"
          disabled={dang}
          onClick={() => setKhung((k) => [...k, { ma: "", ten: "", block: [], k: khoa() }])}
        >
          + Thêm mục
        </Button>
      ) : null}

      {choSua ? (
        // Dưới md có thanh điều hướng đáy (BottomNav, cố định) — dính ở bottom-0
        // thì nút Xuất bản nằm DƯỚI nó (bấm thật ở 375, 27/09).
        <div className="sticky bottom-16 space-y-2 rounded-card border border-hairline bg-surface p-3 md:bottom-0">
          {nhac.length > 0 ? (
            <ul className="list-disc space-y-0.5 pl-5 text-meta text-warning">
              {nhac.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          ) : null}
          {loi ? (
            <p role="alert" className="text-meta text-danger">
              {loi}
            </p>
          ) : null}
          {bao ? <p className="text-meta text-success">{bao}</p> : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="primary" disabled={dang || !doi} onClick={() => void xuatBan()}>
              {dang ? "Đang xuất bản…" : `Xuất bản bản ${goc.version + 1}`}
            </Button>
            {doi ? (
              <Button type="button" variant="ghost" disabled={dang} onClick={() => setLanNap((n) => n + 1)}>
                {xungDot ? "Tải bản mới (bỏ thay đổi đang sửa)" : "Bỏ thay đổi"}
              </Button>
            ) : (
              <span className="text-meta text-ink-muted">Chưa có thay đổi.</span>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
