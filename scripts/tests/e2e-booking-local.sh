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
NURSE=$(tok dd.sa@dr4women.local)
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

# Re-check-in after an undo. This returned 200 while changing NOTHING: the visit
# row survives undo_checkin, so the second check-in hit uq_visit_appointment_id,
# _open_visit swallowed the UniqueViolationError, and the already-aborted
# transaction committed as a rollback — status, queue number and audit event all
# discarded behind {"ok": true}. The receptionist is told the patient arrived.
APPT2=$(uuidgen | tr 'A-Z' 'a-z')
OFF2=$(( (RANDOM % 9000 + 100) * 20 ))
psql "$DB" -q -v appt="$APPT2" -v mins="$OFF2" <<SQL
INSERT INTO appointment (id, clinic_id, clinic_patient_id, location_id,
                         service_type_id, slot_start, slot_end, status)
SELECT :'appt'::uuid, '$CLINIC', '$PATIENT',
       (SELECT id FROM clinic_location WHERE clinic_id='$CLINIC' AND is_active
         ORDER BY code LIMIT 1),
       (SELECT id FROM service_type WHERE clinic_id='$CLINIC' AND is_active
         ORDER BY code LIMIT 1),
       now() + (:mins * interval '1 minute'),
       now() + (:mins * interval '1 minute') + interval '30 minutes',
       'SCHEDULED';
SQL
call PATCH "/api/v1/appointments/$APPT2" "$RECEPTION" '{"action":"checkin"}' >/dev/null
call PATCH "/api/v1/appointments/$APPT2" "$RECEPTION" '{"action":"undo_checkin"}' >/dev/null
check "re-check-in after undo is accepted" 200 \
  "$(call PATCH "/api/v1/appointments/$APPT2" "$RECEPTION" '{"action":"checkin"}')"
actual=$(psql "$DB" -tAc "SELECT status FROM appointment WHERE id='$APPT2';" | tr -d ' ')
check "…and it actually persisted (not a silent rollback)" "CHECKED_IN" "$actual"

# The workflow kernel had 37 node definitions and zero work items until now:
# nothing created one, so the clinic ran on staff_task. Checking a patient in
# must materialise their visit spine.
spine=$(psql "$DB" -tAc "SELECT count(*) FROM work_item w JOIN visit v ON v.visit_id = w.visit_id
                          WHERE v.appointment_id = '$APPT2' AND w.status <> 'CANCELLED';" | tr -d ' ')
check "check-in materialises the 7-step visit spine" "7" "$spine"

arrival=$(psql "$DB" -tAc "SELECT w.status FROM work_item w JOIN visit v ON v.visit_id = w.visit_id
                            WHERE v.appointment_id = '$APPT2' AND w.node_code = 'LUOTKHAM-01'
                              AND w.status <> 'CANCELLED';" | tr -d ' ')
check "the arrival step itself is already done" "COMPLETED" "$arrival"

# Materialising the chain must not let anyone jump it: vitals waits on
# verification, which is what the FS gates are for.
blocked=$(psql "$DB" -tAc "SELECT count(*) FROM work_item_gate_blockers(
    (SELECT w.id FROM work_item w JOIN visit v ON v.visit_id = w.visit_id
      WHERE v.appointment_id = '$APPT2' AND w.node_code = 'LUOTKHAM-03'
        AND w.status <> 'CANCELLED'), 'start');" | tr -d ' ')
if [ "${blocked:-0}" -gt 0 ]; then
  printf '  PASS  %-52s %s\n' "vitals stay gated behind verification" "$blocked blocker"
  pass=$((pass+1))
else
  printf '  FAIL  %-52s not gated\n' "vitals stay gated behind verification"; fail=$((fail+1))
fi

# The read path. Without it the feature is unverifiable in staging and the first
# "why is the cashier's button greyed out?" ticket is unanswerable.
VISIT2=$(psql "$DB" -tAc "SELECT visit_id FROM visit WHERE appointment_id = '$APPT2';" | tr -d ' ')
board=$(curl -s "$API/api/v1/visits/$VISIT2/work-items" \
        -H "Authorization: Bearer $RECEPTION" -H "X-API-Key: $KEY")
check "the board lists the visit's steps" "7" \
  "$(printf '%s' "$board" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"

# Flow order, not alphabetical: ordering by flow_group put "tạo chỉ định" above
# the check-in that has to happen first.
check "…in flow order, arrival first" "LUOTKHAM-01" \
  "$(printf '%s' "$board" | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["node_code"])')"

# The board tells the client what this role may act on, so no client has to
# re-implement the rule — and so it agrees with what the gate will allow.
check "…and says which step is reception's to do next" "LUOTKHAM-02" \
  "$(printf '%s' "$board" | python3 -c '
import sys, json
rows = json.load(sys.stdin)
nxt = [r for r in rows if r["actionable_by_me"] and not r["blocked"]
       and r["status"] == "PENDING"]
print(nxt[0]["node_code"] if nxt else "(none)")')"

# The doctor's board is the SAME query with one parameter changed
# (workspace=khu_bac_si). If that stops being true, two boards have quietly
# become two implementations.
doc=$(curl -s "$API/api/v1/work-items?workspace=khu_bac_si" \
      -H "Authorization: Bearer $DOCTOR" -H "X-API-Key: $KEY")
check "the doctor's board is the same endpoint, different workspace" "LUOTKHAM-05" \
  "$(printf '%s' "$doc" | python3 -c '
import sys, json
rows = [r for r in json.load(sys.stdin) if r["visit_id"] == sys.argv[1]]
print(rows[0]["node_code"] if rows else "(none)")' "$VISIT2")"

# Gate chain across three roles. This is the whole point of the kernel: the
# doctor cannot start until the nurse has finished, and nobody had to encode
# that in a screen.
w05=$(psql "$DB" -tAc "SELECT id FROM work_item WHERE visit_id='$VISIT2'
                        AND node_code='LUOTKHAM-05' AND status <> 'CANCELLED';" | tr -d ' ')
blockers_of() { psql "$DB" -tAc "SELECT count(*) FROM work_item_gate_blockers('$1','start');" | tr -d ' '; }
before=$(blockers_of "$w05")
if [ "${before:-0}" -gt 0 ]; then
  printf '  PASS  %-52s %s\n' "doctor is gated behind the nurse" "$before blocker"; pass=$((pass+1))
else
  printf '  FAIL  %-52s not gated\n' "doctor is gated behind the nurse"; fail=$((fail+1))
fi

# Each step is done by the role that owns it. Using one token for both fails,
# and that failure is the role gate working: sinh hiệu belongs to the nurse, and
# reception cannot complete it however convenient that would be for a test.
advance() {  # node token
  wi=$(psql "$DB" -tAc "SELECT id FROM work_item WHERE visit_id='$VISIT2'
                          AND node_code='$1' AND status <> 'CANCELLED';" | tr -d ' ')
  for c in start complete; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
      "$API/api/v1/work-items/$wi/commands/$c" \
      -H "Authorization: Bearer $2" -H "X-API-Key: $KEY" \
      -H 'Content-Type: application/json' -d '{}')
    [ "$code" = "200" ] || echo "        (advance $1 $c → HTTP $code)"
  done
}
advance LUOTKHAM-02 "$RECEPTION"
advance LUOTKHAM-03 "$NURSE"
check "…and is released once the upstream steps finish" "0" "$(blockers_of "$w05")"

echo "        audit: $(psql "$DB" -tAc "SELECT string_agg(replace(event_type,'appointment.',''), ' -> ' ORDER BY occurred_at) FROM event_log WHERE aggregate_id='$APPT';")"
printf '=== %d passed, %d failed ===\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
