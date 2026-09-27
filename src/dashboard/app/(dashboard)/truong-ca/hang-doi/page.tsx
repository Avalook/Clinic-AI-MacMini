import { redirect } from "next/navigation";

// GỘP (27/09/2026): "Hàng đợi theo trạm" nay là "Điều phối ca" ở /truong-ca.
export default function Page() {
  redirect("/truong-ca");
}
