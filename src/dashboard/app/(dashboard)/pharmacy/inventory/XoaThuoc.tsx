"use client";

// Nút Xoá trong form Sửa thuốc (Tuyền chốt 26/11/2026). Máy chủ nói thuốc đã từng được
// dùng ở đâu chưa (đơn, lô, phiếu kho, kiểm kê, quy đổi, mã vạch…): chưa → "Xoá thuốc"
// (xoá thật, ghi nhật ký ai xoá); đã có lịch sử → "Tắt thuốc" (giữ cho đơn cũ).

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { goiThuoc } from "@/lib/goi-thuoc";

export default function XoaThuoc({
  thuocId,
  ten,
  dangDung,
  onTat,
  onDaXoa,
}: {
  thuocId: string;
  ten: string;
  dangDung: boolean;
  /** Đã có lịch sử: lưu form với "Đang dùng" bỏ tick. */
  onTat: () => void;
  onDaXoa: () => void;
}) {
  const [doc, setDoc] = useState<{ id: string; xoa_duoc: boolean; ly_do: string | null } | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  // Câu trả lời của thuốc KHÁC (đổi dòng đang sửa) thì coi như chưa có.
  const kq = doc?.id === thuocId ? doc : null;

  useEffect(() => {
    let bo = false;
    void goiThuoc<{ xoa_duoc: boolean; ly_do: string | null }>("xoa-duoc", { query: { id: thuocId } }).then((r) => {
      if (bo) return;
      if (r.ok) setDoc({ id: thuocId, ...r.data });
      else setLoi(r.loi);
    });
    return () => {
      bo = true;
    };
  }, [thuocId]);

  const xoa = async () => {
    if (!window.confirm(`Xoá hẳn “${ten}” khỏi danh mục? Thuốc chưa từng được dùng nên không mất gì; không hoàn tác được.`)) return;
    setDang(true);
    const r = await goiThuoc("xoa", { body: { id: thuocId } });
    setDang(false);
    if (r.ok) onDaXoa();
    else setLoi(r.loi);
  };

  if (kq === null) return loi ? <p className="text-meta text-danger">{loi}</p> : null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {kq.xoa_duoc ? (
        <Button type="button" variant="ghost" className="text-danger" disabled={dang} onClick={() => void xoa()}>
          {dang ? "Đang xoá…" : "Xoá thuốc"}
        </Button>
      ) : dangDung ? (
        <Button type="button" variant="ghost" title={kq.ly_do ?? undefined} onClick={onTat}>
          Tắt thuốc
        </Button>
      ) : null}
      {!kq.xoa_duoc && kq.ly_do ? <span className="text-meta text-ink-muted">{kq.ly_do}</span> : null}
      {loi ? (
        <span role="alert" className="text-meta text-danger">
          {loi}
        </span>
      ) : null}
    </div>
  );
}
