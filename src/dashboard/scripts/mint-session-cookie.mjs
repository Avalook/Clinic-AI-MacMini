// Mint the session cookies the dashboard itself would set, using its own
// @supabase/ssr — no guessing at the storage key or the encoding.
// The client is built with the URL the container uses (that URL decides the
// cookie name), while fetch is redirected to the host port so login works here.
import { createServerClient } from "@supabase/ssr";

const [email, password] = process.argv.slice(2);
// Tên cookie do URL Supabase quyết định (sb-<host>-auth-token), nên URL này
// PHẢI trùng với thứ container đang dùng — không thì đúc ra sb-host-* trong khi
// container đợi sb-192-*, và mọi request trả 401. Đã xảy ra đúng vậy khi
// deployment chuyển sang IP LAN còn script này vẫn hardcode host.docker.internal.
//
// Truyền SUPABASE_URL để bám theo deployment; mặc định giữ giá trị cũ.
const CONTAINER_URL = process.env.SUPABASE_URL || "http://host.docker.internal:54321";
const HOST_URL = process.env.SUPABASE_HOST_URL || "http://127.0.0.1:54321";
const ANON = process.env.ANON_KEY;

const jar = [];
const client = createServerClient(CONTAINER_URL, ANON, {
  cookies: { getAll: () => [], setAll: (set) => jar.push(...set) },
  global: {
    fetch: (input, init) =>
      fetch(String(input).replace(CONTAINER_URL, HOST_URL), init),
  },
});

const { error } = await client.auth.signInWithPassword({ email, password });
if (error) {
  console.error("login failed:", error.message);
  process.exit(1);
}
console.log(jar.map((c) => `${c.name}=${encodeURIComponent(c.value)}`).join("; "));
