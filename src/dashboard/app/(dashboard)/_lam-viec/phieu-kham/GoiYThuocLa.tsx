"use client";

// Gõ tên thuốc không có trong danh mục (26/11/2026, kế hoạch đơn vị mẹ/con mục 7, 12):
// máy chủ gợi ý thuốc gần giống theo TÊN và BIỆT DƯỢC ("Indurate" → Idurat 5mg), hoặc
// bác sĩ bấm "Nhờ kho thêm thuốc" (yêu cầu + chuông cho người kho). Không còn thêm dòng
// gõ tự do — tên lạ làm cả hoá đơn thuốc của lượt kẹt ở quầy.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { goiThuoc, type GoiYThuoc } from "@/lib/goi-thuoc";

export default function GoiYThuocLa({
  ten,
  onChon,
}: {
  ten: string;
  /** Chọn thuốc gợi ý (mã danh mục) — màn kê đơn tìm trong danh mục đã tải. */
  onChon: (drugCatalogId: string) => void;
}) {
  // Câu trả lời gắn với chữ đã hỏi: gõ tiếp thì câu cũ tự thôi hiện.
  const [tra, setTra] = useState<{ go: string; items: GoiYThuoc[] } | null>(null);
  const [baoCua, setBao] = useState<{ go: string; tot: boolean; chu: string } | null>(null);
  const [dang, setDang] = useState(false);
  const go = ten.trim();
  const goiY = go.length < 3 ? [] : tra?.go === go ? tra.items : null;
  const bao = baoCua?.go === go ? baoCua : null;

  useEffect(() => {
    if (go.length < 3) return;
    let bo = false;
    // Gộp nhịp gõ: chỉ hỏi khi ngừng tay 300ms.
    const h = setTimeout(() => {
      void goiThuoc<{ items: GoiYThuoc[] }>("goi-y", { query: { ten: go } }).then((kq) => {
        if (!bo) setTra({ go, items: kq.ok ? kq.data.items : [] });
      });
    }, 300);
    return () => {
      bo = true;
      clearTimeout(h);
    };
  }, [go]);

  const nho = async () => {
    setDang(true);
    const kq = await goiThuoc<{ moi: boolean }>("nho-kho", { body: { ten: go } });
    setDang(false);
    setBao(
      kq.ok
        ? {
            go,
            tot: true,
            chu: kq.data.moi
              ? `Đã nhờ kho thêm “${go}”. Kho thêm xong thì tìm lại để kê.`
              : `“${go}” đã được nhờ trước đó — kho đang xử lý.`,
          }
        : { go, tot: false, chu: kq.loi },
    );
  };

  if (!go) return null;
  return (
    <div className="space-y-2 rounded-card bg-surface-muted p-3 text-body" aria-live="polite">
      <p className="text-ink">“{go}” không có trong danh mục thuốc.</p>
      {goiY === null ? (
        <p className="text-meta text-ink-muted">Đang tìm thuốc gần giống…</p>
      ) : goiY.length > 0 ? (
        <div className="space-y-1">
          <p className="text-meta text-ink-muted">Có phải:</p>
          <div className="flex flex-wrap gap-2">
            {goiY.map((g) => (
              <Button key={g.drug_catalog_id} type="button" size="sm" variant="secondary" onClick={() => onChon(g.drug_catalog_id)}>
                {g.ten}
                {g.biet_duoc ? <span className="ml-1 font-normal text-ink-muted">({g.biet_duoc})</span> : null}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="ghost" disabled={dang} onClick={() => void nho()}>
          {dang ? "Đang gửi…" : "Nhờ kho thêm thuốc"}
        </Button>
        {bao ? (
          <span role={bao.tot ? "status" : "alert"} className={`text-meta ${bao.tot ? "text-success" : "text-danger"}`}>
            {bao.chu}
          </span>
        ) : null}
      </div>
    </div>
  );
}
