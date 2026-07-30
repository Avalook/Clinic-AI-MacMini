#!/usr/bin/env bash
# End-to-end smoke for the W5 booking + lifecycle endpoints against local
# Supabase. Prerequisites are the same as e2e-clinical-local.sh.
set -uo pipefail
API=${API:-http://127.0.0.1:8100}
SUPA=${SUPA:-http://127.0.0.1:54321}
DB=${DB:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}
KEY=${KEY:-staging-local-api-key}
CLINIC=a0000000-0000-4000-8000-000000000001
PATIENT=e0000000-0000-4000-8000-0000000000f1
pass=0; fail=0

ANON=$(npx --yes supabase@latest status -o env 2>/dev/null | grep '^ANON_KEY=' | cut -d'"' -f2)
tok() { curl -s -X POST "$SUPA/auth/v1/token?grant_type=password" -H "apikey: $ANON" \
  -H "Content-Type: application/json" -d "{\"email\":\"$1\",\"password\":\"clinic-test-pw-123\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))'; }
call() { curl -s -o /tmp/bk.out -w '%{http_code}' -X "$1" "$API$2" \
  -H "Authorization: Bearer $3" -H "X-API-Key: $KEY" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" -d "$4"; }
check() { if [ "$3" = "$2" ]; then printf '  PASS  %-52s %s\n' "$1" "$3"; pass=$((pass+1));
  else printf '  FAIL  %-52s got %s\n        %s\n' "$1" "$3" "$(head -c 160 /tmp/bk.out)"; fail=$((fail+1)); fi; }

DOCTOR=$(tok bs.a@dr4women.local)
CSKH=$(tok cskh@dr4women.local)
RECEPTION=$(tok letan@dr4women.local)
[ -z "$DOCTOR" ] || [ -z "$CSKH" ] || [ -z "$RECEPTION" ] && {
  echo "missing test logins"
  exit 1
}

LOC=$(psql "$DB" -tAc "SELECT id FROM clinic_location WHERE clinic_id='$CLINIC' AND is_active ORDER BY code LIMIT 1" | tr -d ' ')
SVCT=$(psql "$DB" -tAc "SELECT id FROM service_type WHERE clinic_id='$CLINIC' AND is_active ORDER BY code LIMIT 1" | tr -d ' ')
DOC=$(psql "$DB" -tAc "SELECT id FROM staff WHERE full_name='BS A local'" | tr -d ' ')
# Its own 15-minute window: enforce_slot_capacity allows 2+1 per doctor per slot.
read -r S1 S2 <<< "$(python3 -c "
import datetime, random
d = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=random.randint(500, 900000))
print(d.isoformat(), (d + datetime.timedelta(minutes=30)).isoformat())")"

BOOK="{\"clinic_patient_id\":\"$PATIENT\",\"service_type_id\":\"$SVCT\",\"location_id\":\"$LOC\",\"slot_start\":\"$S1\",\"slot_end\":\"$S2\",\"doctor_id\":\"$DOC\",\"patient_kind\":\"NEW\"}"

check "booking is intake work — a doctor is refused" 403 "$(call POST /api/v1/appointments/bookings "$DOCTOR" "$BOOK")"
check "CSKH books" 201 "$(call POST /api/v1/appointments/bookings "$CSKH" "$BOOK")"
APPT=$(python3 -c 'import json;print(json.load(open("/tmp/bk.out")).get("appointment_id",""))' 2>/dev/null)
psql "$DB" -tAc "SELECT '        episode attached: ' || (episode_id IS NOT NULL)::text FROM appointment WHERE id='$APPT';"

check "the doctor accepts their own case" 200 "$(call PATCH "/api/v1/appointments/$APPT" "$DOCTOR" '{"action":"confirm"}')"
check "cannot finish before the patient arrives" 409 "$(call PATCH "/api/v1/appointments/$APPT" "$DOCTOR" '{"action":"complete"}')"
check "CSKH cannot check the patient in" 403 "$(call PATCH "/api/v1/appointments/$APPT" "$CSKH" '{"action":"checkin"}')"
check "reception checks the patient in" 200 "$(call PATCH "/api/v1/appointments/$APPT" "$RECEPTION" '{"action":"checkin"}')"
psql "$DB" -tAc "SELECT '        queue_number=' || coalesce(queue_number,'(none)') || ' visits=' || (SELECT count(*) FROM visit WHERE appointment_id='$APPT') FROM appointment WHERE id='$APPT';"
check "now it can be finished" 200 "$(call PATCH "/api/v1/appointments/$APPT" "$DOCTOR" '{"action":"complete"}')"
check "a doctor may not cancel" 403 "$(call PATCH "/api/v1/appointments/$APPT" "$DOCTOR" '{"action":"cancel"}')"
check "and a finished appointment cannot be cancelled" 409 "$(call PATCH "/api/v1/appointments/$APPT" "$CSKH" '{"action":"cancel"}')"

echo "        audit: $(psql "$DB" -tAc "SELECT string_agg(replace(event_type,'appointment.',''), ' -> ' ORDER BY occurred_at) FROM event_log WHERE aggregate_id='$APPT';")"
printf '=== %d passed, %d failed ===\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
