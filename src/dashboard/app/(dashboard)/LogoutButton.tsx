"use client";

import { useRouter } from "next/navigation";
import { getSupabaseBrowser } from "../../lib/supabase-browser";

export default function LogoutButton() {
  const router = useRouter();
  async function handleLogout() {
    const supabase = getSupabaseBrowser();
    await supabase.auth.signOut();
    router.replace("/login");
    router.refresh();
  }
  return (
    <button
      onClick={handleLogout}
      className="w-full rounded-md border border-line px-3 py-1.5 text-sm text-ink-muted transition-colors duration-150 hover:bg-surface-sunken hover:text-ink"
    >
      Đăng xuất
    </button>
  );
}
