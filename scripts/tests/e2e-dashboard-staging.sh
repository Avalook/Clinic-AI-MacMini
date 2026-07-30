#!/usr/bin/env bash
# Prove every business route in the dashboard reaches FastAPI (ADR-0012).
#
# The other e2e scripts call FastAPI directly. This one goes through the real
# Next dashboard in the staging container, with a real Supabase session cookie —
# the path a logged-in staff member takes.
#
# This began as a check on the *_VIA_BACKEND flags. The flags and the legacy
# direct-to-Supabase branches they guarded are gone, so it now guards the
# property they were a means to: a route answering 200 out of its own Supabase
# client, instead of the backend, must fail here. That is why each check also
# reads the api container's access log and requires the matching request to
# appear — a status code alone cannot tell the two apart.
#
# Prerequisites:
#   npx supabase start
#   psql "$DB" -f supabase/fixtures/staff_logins.sql
#   psql "$DB" -f supabase/fixtures/local_data.sql
#   CLINIC_ENV_FILE=.env.staging docker compose --env-file .env.staging \
#     -p clinicai_staging up -d --build api dashboard
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
DASH=clinicai_staging-dashboard-1
API=clinicai_staging-api-1
CLINIC=a0000000-0000-4000-8000-000000000001
pass=0; fail=0

command -v docker >/dev/null || { echo "docker not on PATH"; exit 1; }
docker inspect -f '{{.State.Running}}' "$DASH" "$API" >/dev/null 2>&1 || {
  echo "staging dashboard/api not running — see the header for the compose line"
  exit 1
}

ANON=$(cd "$REPO" && npx --yes supabase@latest status -o env 2>/dev/null \
       | grep '^ANON_KEY=' | cut -d'"' -f2)
[ -n "$ANON" ] || { echo "local Supabase not running"; exit 1; }

# ---- session cookies, minted the way the dashboard itself would --------------
# @supabase/ssr decides both the cookie name (from the Supabase URL) and the
# encoding. Hand-rolling that would be a guess that breaks on the next upgrade,
# so the dashboard's own copy of the library does it.
cookie() {  # email → "name=value; name=value"
  ANON_KEY="$ANON" node "$REPO/src/dashboard/scripts/mint-session-cookie.mjs" "$1" \
    'clinic-test-pw-123' 2>/dev/null
}

# ---- one check = one route through Next, correlated with the api log ---------
# HTTP is spoken from inside the dashboard container: only Caddy publishes a
# port, and starting Caddy just to reach a container on the same network would
# be ceremony.
call() {  # method path cookie body → status
  docker exec "$DASH" curl -s -o /tmp/flag.out -w '%{http_code}' \
    -X "$1" "http://localhost:3000$2" \
    -H "Cookie: $3" -H 'Content-Type: application/json' \
    --data-binary "${4:-{\}}"
}

# The path argument is matched as a prefix. The api scrubs long digit runs out
# of its access log (PII), and the fixture patient's uuid is nearly all zeros —
# it is logged as /api/v1/patients/e[REDACTED]-4000-... So an id-bearing route
# is correlated on "verb + endpoint", which is what is being proven anyway.
check() {  # label expected-status backend-path-prefix method status
  local label="$1" want="$2" path="$3" verb="$4" got="$5"
  local seen=0 tries=0
  while [ "$tries" -lt 15 ]; do
    seen=$(docker logs "$API" 2>&1 | tail -n +$((MARK + 1)) \
           | grep -c "\"$verb $path")
    [ "$seen" -gt 0 ] && break
    tries=$((tries + 1)); sleep 0.2
  done
  if [ "$got" = "$want" ] && [ "$seen" -gt 0 ]; then
    printf '  PASS  %-46s %s  → %s %s\n' "$label" "$got" "$verb" "$path"
    pass=$((pass+1))
  else
    printf '  FAIL  %-46s %s (want %s)\n' "$label" "$got" "$want"
    if [ "$seen" -eq 0 ]; then
      printf '        never reached FastAPI: %s %s — flag off?\n' "$verb" "$path"
    fi
    printf '        %s\n' "$(docker exec "$DASH" head -c 200 /tmp/flag.out)"
    fail=$((fail+1))
  fi
}

mark() { MARK=$(docker logs "$API" 2>&1 | wc -l | tr -d ' '); }

echo "=== signing in the fixture staff ==="
DOCTOR=$(cookie bs.a@dr4women.local)
CSKH=$(cookie cskh@dr4women.local)
SONO_BS=$(cookie bs.sa@dr4women.local)
SONO_DD=$(cookie dd.sa@dr4women.local)
CASHIER=$(cookie thungan@dr4women.local)
BOSS=$(cookie ql@dr4women.local)
for c in DOCTOR CSKH SONO_BS SONO_DD CASHIER BOSS; do
  [ -n "${!c}" ] || { echo "could not sign in as $c"; exit 1; }
done
echo "  6 roles signed in"

# ---- a fresh appointment per run --------------------------------------------
# enforce_slot_capacity allows 2+1 per doctor per 15-minute window (CAP-01), so
# reusing now() makes the third run of the day fail while doing its job.
APPT=$(uuidgen | tr 'A-Z' 'a-z')
PATIENT=e0000000-0000-4000-8000-0000000000f1
OFFSET_MIN=$(( (RANDOM % 20000 + 1) * 20 ))
psql "$DB" -q -v appt="$APPT" -v mins="$OFFSET_MIN" <<SQL
INSERT INTO appointment (id, clinic_id, clinic_patient_id, location_id,
                         service_type_id, slot_start, slot_end, status, doctor_id)
SELECT :'appt'::uuid, '$CLINIC', '$PATIENT',
       (SELECT id FROM clinic_location WHERE clinic_id='$CLINIC' LIMIT 1),
       (SELECT id FROM service_type LIMIT 1),
       now() + (:mins * interval '1 minute'),
       now() + (:mins * interval '1 minute') + interval '30 minutes',
       'CHECKED_IN',
       (SELECT id FROM staff WHERE full_name='BS A local');
SQL
VISIT=$(psql "$DB" -tAc "INSERT INTO visit (clinic_id, clinic_patient_id, appointment_id, status)
                         VALUES ('$CLINIC','$PATIENT','$APPT','IN_PROGRESS')
                         RETURNING visit_id;" | head -1 | tr -d ' ')
CODE=$(psql "$DB" -tAc "SELECT code FROM service_type LIMIT 1;" | tr -d ' ')
SERVICE=$(psql "$DB" -tAc "SELECT id FROM service_type LIMIT 1;" | tr -d ' ')
LOCATION=$(psql "$DB" -tAc "SELECT id FROM clinic_location WHERE clinic_id='$CLINIC' LIMIT 1;" | tr -d ' ')
# The patient edit is a full replace, so send the name back unchanged rather
# than renaming a fixture patient every run.
PNAME=$(psql "$DB" -tAc "SELECT full_name FROM patient WHERE clinic_patient_id='$PATIENT';" | sed 's/^ *//;s/ *$//')
TODAY=$(date -u +%Y-%m-%d)
MONDAY=$(date -u -v-mon +%Y-%m-%d)

echo
echo "=== each flag, through the dashboard, must land in FastAPI ==="

# 1. Lab order
mark
s=$(call POST /api/lab-result "$DOCTOR" \
     "{\"clinicPatientId\":\"$PATIENT\",\"test_name\":\"flag check\"}")
check "LAB — doctor orders a test" 201 /api/v1/lab/orders POST "$s"

# 2. Clinical record
mark
s=$(call POST /api/clinical-record "$DOCTOR" \
     "{\"appointmentId\":\"$APPT\",\"clinicPatientId\":\"$PATIENT\",\"vitalsOnly\":true,\"objective\":{\"vitals\":{\"bp\":\"120/80\"}},\"chiefComplaint\":\"flag check\"}")
check "CLINICAL_RECORD — vitals saved" 200 /api/v1/clinical-records POST "$s"

# 3. Exam form. PK is a FORM code, which is what the UI sends
#    (resolveServiceCode maps the service NAME to it), validated against
#    clinical_form_catalogue rather than service_type — see migration
#    20260730000011 for why that distinction was the whole bug.
mark
s=$(call POST /api/clinical-form "$DOCTOR" \
     "{\"visitId\":\"$VISIT\",\"serviceCode\":\"PK\",\"form_data\":{\"a\":1}}")
check "CLINICAL_FORM — exam form saved" 200 /api/v1/clinical-forms PUT "$s"

# 4. Ultrasound measurements
mark
s=$(call POST /api/ultrasound "$SONO_BS" \
     "{\"appointmentId\":\"$APPT\",\"clinicPatientId\":\"$PATIENT\",
       \"measurements\":{\"bpd\":45}}")
check "ULTRASOUND — sonographer writes measurements" 200 \
      /api/v1/ultrasound/measurements POST "$s"

# 5. Ultrasound queue (service log)
mark
s=$(call POST /api/sono "$SONO_DD" \
     "{\"kind\":\"SA\",\"service_name\":\"Sieu am flag check\"}")
check "SERVICE_LOG — ultrasound queue entry" 201 /api/v1/sono/queue POST "$s"

# 6. Payment — the cashier gate is on the APPOINTMENT being
#    COMPLETED ("the doctor has finished"), not on the visit. Finish it first so
#    this is a real receipt rather than a 409.
psql "$DB" -q -c "UPDATE appointment SET status='COMPLETED' WHERE id='$APPT';"
mark
s=$(call POST /api/payment "$CASHIER" \
     "{\"visitId\":\"$VISIT\",\"kind\":\"dich_vu\",\"amount\":150000}")
check "PAYMENT — cashier takes money" 200 /api/v1/payments POST "$s"

# 7. Customer care action
mark
s=$(call POST /api/cskh-action "$CSKH" \
     "{\"category\":\"CALL\",\"description\":\"flag check\"}")
check "CSKH — customer care action logged" 201 /api/v1/cskh/actions POST "$s"

# 8. Patient admin edit
mark
s=$(call PATCH /api/patients "$CSKH" \
     "{\"clinic_patient_id\":\"$PATIENT\",\"full_name\":\"$PNAME\",\"phone_primary\":\"0900000000\"}")
check "PATIENT_EDIT — admin details corrected" 200 /api/v1/patients/ PATCH "$s"

# 9. Booking
mark
BOOK_MIN=$(( (RANDOM % 20000 + 1) * 20 ))
START=$(date -u -v+${BOOK_MIN}M +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u -v+$((BOOK_MIN + 30))M +%Y-%m-%dT%H:%M:%SZ)
s=$(call POST /api/appointments "$CSKH" \
     "{\"clinic_patient_id\":\"$PATIENT\",\"service_type_id\":\"$SERVICE\",\"location_id\":\"$LOCATION\",\"slot_start\":\"$START\",\"slot_end\":\"$END\"}")
check "BOOKING — CSKH books a slot" 201 /api/v1/appointments/bookings POST "$s"

# 10. Episode — 409 is the backend refusing an episode that is not
#     PENDING_CLOSE. It is still proof the rule now runs there, not in Next.
mark
EPI=$(psql "$DB" -tAc "SELECT id FROM care_episode WHERE clinic_id='$CLINIC' LIMIT 1;" | tr -d ' ')
s=$(call PATCH /api/episodes "$CSKH" "{\"id\":\"$EPI\",\"action\":\"close\"}")
check "EPISODE — CSKH closes an episode" 409 /api/v1/episodes/ PATCH "$s"

# 11. Roster (clinic config)
mark
s=$(call POST /api/roster "$BOSS" \
     "{\"week_start\":\"$MONDAY\",\"work_date\":\"$TODAY\",\"station\":\"Flag check\",\"shift\":\"SANG\"}")
check "CONFIG — management schedules a shift" 201 /api/v1/roster/shifts POST "$s"

# ---- ROLE-02, through the front door ---------------------------------------
# The schema test proves the policy; this proves the screens that policy could
# have broken still work, and that the note really is unreadable over the API
# the browser uses.
echo
echo "=== ROLE-02: the note is closed, the board still works ==="
ANON_KEY_HDR="apikey: $ANON"
rows_for() {  # email → how many clinical_record rows PostgREST hands them
  local tok
  tok=$(curl -s -X POST "http://127.0.0.1:54321/auth/v1/token?grant_type=password" \
        -H "$ANON_KEY_HDR" -H 'Content-Type: application/json' \
        -d "{\"email\":\"$1\",\"password\":\"clinic-test-pw-123\"}" \
        | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))')
  curl -s "http://127.0.0.1:54321/rest/v1/clinical_record?select=visit_id" \
       -H "$ANON_KEY_HDR" -H "Authorization: Bearer $tok" \
       | python3 -c 'import sys,json;d=json.load(sys.stdin);print(len(d) if isinstance(d,list) else -1)'
}
for who in cskh thungan; do
  n=$(rows_for "$who@dr4women.local")
  if [ "$n" = "0" ]; then
    printf '  PASS  %-46s reads 0 clinical_record rows\n' "$who"; pass=$((pass+1))
  else
    printf '  FAIL  %-46s reads %s clinical_record rows\n' "$who" "$n"; fail=$((fail+1))
  fi
done
n=$(rows_for bs.a@dr4women.local)
if [ "$n" -gt 0 ] 2>/dev/null; then
  printf '  PASS  %-46s still reads the note (%s rows)\n' "bs.a (DOCTOR)" "$n"; pass=$((pass+1))
else
  printf '  FAIL  %-46s cannot read the note — policy too tight\n' "bs.a (DOCTOR)"; fail=$((fail+1))
fi

# The progress bar reception depends on must survive losing that read.
mark
TODAY_VN=$(date -u -v+7H +%Y-%m-%d)
s=$(docker exec "$DASH" curl -s -o /tmp/flag.out -w '%{http_code}' \
    "http://localhost:3000/home" -H "Cookie: $CSKH")
seen=$(docker logs "$API" 2>&1 | tail -n +$((MARK + 1)) \
       | grep -c '"GET /api/v1/visits/progress')
if [ "$s" = "200" ] && [ "$seen" -gt 0 ]; then
  printf '  PASS  %-46s %s  → GET /api/v1/visits/progress\n' "/home renders for CSKH" "$s"
  pass=$((pass+1))
else
  printf '  FAIL  %-46s %s (backend hits: %s)\n' "/home renders for CSKH" "$s" "$seen"
  fail=$((fail+1))
fi

echo
psql "$DB" -q -c "DELETE FROM work_roster WHERE station = 'Flag check';"
echo "=== $pass passed, $fail failed ==="
[ "$fail" -eq 0 ]
