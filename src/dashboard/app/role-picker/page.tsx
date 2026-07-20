// Retired: listing all staff enabled identity/role impersonation. Each person
// must authenticate with the account linked via staff.auth_user_id.

import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function RolePickerPage() {
  redirect("/login");
}
