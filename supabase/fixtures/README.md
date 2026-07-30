# supabase/fixtures — setup data, not assertions

Everything in `supabase/tests/` is run by CI's `database` job, in a loop, against a
throwaway Postgres. That loop treats each file as a test: if it errors, the build
is red.

These two files are neither tests nor safe to run there — they need `seed.sql` to
have loaded, and `staff_logins.sql` writes columns that only a real GoTrue
`auth.users` has. They lived in `supabase/tests/` briefly and turned CI red for
exactly that reason.

They exist so the local end-to-end scripts do not depend on rows somebody typed
into one particular Mac — `supabase db reset` wipes those, and then nobody else
can run the scripts.

```bash
DB=postgresql://postgres:postgres@127.0.0.1:54322/postgres
psql "$DB" -f supabase/fixtures/staff_logins.sql   # 6 staff, one login each
psql "$DB" -f supabase/fixtures/local_data.sql     # a patient, a session, an episode
```

LOCAL / STAGING ONLY. Invented people, one shared weak password. Never run either
against a database holding real patient data.
