# supabase/fixtures — setup data, not assertions

Everything in `supabase/tests/` is run by CI's `db_fresh` job, in a loop, against a
throwaway Postgres. That loop treats each file as a test: if it errors, the build
is red.

These files are neither tests nor safe to run there — they need `seed.sql` to
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
psql "$DB" -f supabase/fixtures/demo_clinic_day.sql # 40 patients, one busy day
psql "$DB" -f supabase/fixtures/clinic_roster.sql  # 35 nhân sự thật của Dr4Women
```

`staff_logins.sql`, `local_data.sql` and `demo_clinic_day.sql` are LOCAL /
STAGING ONLY: invented people, one shared weak password. Never run them against
a database holding real patient data.

`clinic_roster.sql` is the exception — it is the **real** Dr4Women roster
(working names only: "BS Thành", "ĐD Trang Lê"), trích từ bản dữ liệu vận hành
khách gửi, and belongs in prod too. It creates no logins and holds no HR data;
see the header of that file for the source columns. It is not in `seed.sql`
because `seed.sql` is documented as staff-free (`supabase/README.md`).
