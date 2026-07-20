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
      className="w-full rounded-md border border-[#262626] px-3 py-1.5 text-sm text-[#a1a1aa] transition-colors duration-150 hover:bg-[#1a1a1a] hover:text-[#d4d4d8]"
    >
      Đăng xuất
    </button>
  );
}
