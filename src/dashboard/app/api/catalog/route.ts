// Danh mục dùng chung cho picker form khám (đọc-only, runtime — KHÔNG hardcode
// vào schema tĩnh):
//   - drugs : drug_catalog (mig 051) → picker "Đơn thuốc" (name_raw VERBATIM + variant).
//   - cls   : service_price group='dich_vu' (mig 044/051) → picker "Chỉ định CLS",
//             gom nhóm theo category (group_label trong phiếu PK).
// Cả 2 bảng có RLS SELECT cho authenticated → đọc qua server client thường.
// Catalog chỉ là MENU gợi ý; input vẫn cho gõ tự do (không phải safety gate).

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";

export async function GET() {
  const db = await getSupabaseServer();
  const {
    data: { user },
  } = await db.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const [drugRes, clsRes] = await Promise.all([
    db
      .from("drug_catalog")
      .select("name_base, name_raw, variant, needs_review")
      .eq("is_active", true)
      .order("name_base"),
    db
      .from("service_price")
      .select("service_code, name, category")
      .eq("group", "dich_vu")
      .eq("active", true)
      .order("category")
      .order("name"),
  ]);

  if (drugRes.error || clsRes.error) {
    return NextResponse.json(
      { error: drugRes.error?.message ?? clsRes.error?.message ?? "Lỗi đọc danh mục." },
      { status: 500 },
    );
  }

  return NextResponse.json({
    drugs: drugRes.data ?? [],
    cls: clsRes.data ?? [],
  });
}
