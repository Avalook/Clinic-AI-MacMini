// Mint the session cookies the dashboard itself would set, using its own
// @supabase/ssr — no guessing at the storage key or the encoding.
// The client is built with the URL the container uses (that URL decides the
// cookie name), while fetch is redirected to the host port so login works here.
import { createServerClient } from "@supabase/ssr";

const [email, password] = process.argv.slice(2);
const CONTAINER_URL = "http://host.docker.internal:54321";
const HOST_URL = "http://127.0.0.1:54321";
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
