#!/usr/bin/env bash
# 発表デモの状態を一発で整えるスクリプト (Macから実行)
#
# やること:
#   1. デモ2イベントの応募・抽選・入場・通知データを全リセット
#   2. 応募フォーム (autofill付き設問3つ) を両イベントに設定
#   3. 「体験応募デモ」イベント (先着・受付中) を用意 ← 当日ここに生で応募して見せる
#   4. fan01〜08 を「デモVRライブ」に応募させる (回答付き)
#   5. 「デモVRライブ」の応募締切を過去に移動 (抽選実行可能な状態にする)
#
# 使い方:  ./scripts/demo_stage.sh
# 注意:   ログインを9回行うため、1分以内に連続再実行するとレート制限(429)になる。
#         その場合は1分待って再実行する。
set -euo pipefail

HOST="${HOST:-161.33.130.254}"
BASE="http://$HOST"
SSH_DEST="ubuntu@$HOST"
COMPOSE="sudo docker compose -f docker-compose.prod.yml"
JAR=$(mktemp)
XH="X-Requested-With: XMLHttpRequest"
CT="Content-Type: application/json"
trap 'rm -f "$JAR"' EXIT

jqpy() { python3 -c "import json,sys; d=json.load(sys.stdin); $1"; }

login() { # login <email>
  rm -f "$JAR"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -c "$JAR" -H "$XH" -H "$CT" \
    -X POST "$BASE/api/v1/auth/login" \
    -d "{\"email\":\"$1\",\"password\":\"Passw0rd!\"}")
  if [ "$code" != "200" ]; then
    echo "!! ログイン失敗 ($1): HTTP $code (429ならレート制限。1分待って再実行)" >&2
    exit 1
  fi
}

echo "== 1/5 デモデータをリセット =="
ssh "$SSH_DEST" "cd eventdeck-vr && $COMPOSE exec -T db psql -U eventdeck -d eventdeck -q" << 'SQL'
CREATE TEMP TABLE demo_events AS
  SELECT id FROM events WHERE title IN ('デモVRライブ', '体験応募デモ');
DELETE FROM checkins WHERE event_id IN (SELECT id FROM demo_events);
DELETE FROM lottery_results WHERE lottery_id IN
  (SELECT id FROM lotteries WHERE event_id IN (SELECT id FROM demo_events));
DELETE FROM lotteries WHERE event_id IN (SELECT id FROM demo_events);
DELETE FROM notifications WHERE event_id IN (SELECT id FROM demo_events);
DELETE FROM application_answers WHERE application_id IN
  (SELECT id FROM applications WHERE event_id IN (SELECT id FROM demo_events));
DELETE FROM applications WHERE event_id IN (SELECT id FROM demo_events);
-- 日付は毎回「今」を基準に振り直す (前回実行から日が経つと過去日になり CHECK に触れるため)
UPDATE events SET status = 'published',
  starts_at       = now() + interval '14 day',
  ends_at         = now() + interval '14 day' + interval '2 hour',
  apply_starts_at = now() - interval '1 day',
  apply_ends_at   = now() + interval '7 day'
  WHERE id IN (SELECT id FROM demo_events);
SQL
echo "  リセット完了"

echo "== 2/5 主催者でフォーム設定 & 体験イベント確認 =="
login organizer@example.com
ORG=$(curl -s -b "$JAR" "$BASE/api/v1/auth/me" | jqpy "print(d['organizations'][0]['id'])")
MAIN=$(curl -s "$BASE/api/v1/events" | jqpy "print([i['id'] for i in d['items'] if i['title']=='デモVRライブ'][0])")

TRIAL=$(curl -s -b "$JAR" "$BASE/api/v1/orgs/$ORG/events" | jqpy "
ids=[e['id'] for e in d if e['title']=='体験応募デモ']
print(ids[0] if ids else '')")
if [ -z "$TRIAL" ]; then
  TIMES=$(python3 -c "
from datetime import datetime, timedelta, UTC
n = datetime.now(UTC)
print((n-timedelta(days=1)).isoformat(), (n+timedelta(days=30)).isoformat(),
      (n+timedelta(days=31)).isoformat(), (n+timedelta(days=31,hours=2)).isoformat())")
  read -r APS APE STS ETS <<< "$TIMES"
  TRIAL=$(curl -s -b "$JAR" -H "$XH" -H "$CT" -X POST "$BASE/api/v1/orgs/$ORG/events" -d "{
    \"title\":\"体験応募デモ\",\"description\":\"発表で実際に応募して見せる用 (先着・即当選)\",
    \"platform\":\"vrchat\",\"world_name\":\"EventDeck Demo Hall\",
    \"starts_at\":\"$STS\",\"ends_at\":\"$ETS\",\"capacity\":20,
    \"selection_method\":\"first_come\",
    \"apply_starts_at\":\"$APS\",\"apply_ends_at\":\"$APE\",\"visibility\":\"public\"}" \
    | jqpy "print(d['id'])")
  curl -s -o /dev/null -b "$JAR" -H "$XH" -X POST "$BASE/api/v1/events/$TRIAL/publish"
  echo "  体験応募デモ を作成・公開: $TRIAL"
else
  echo "  体験応募デモ は既存: $TRIAL"
fi

FORM_ITEMS='{"items":[
  {"label":"VRChatユーザー名","item_type":"text","is_required":true,"autofill_key":"vrchat_username"},
  {"label":"参加予定プラットフォーム","item_type":"radio","is_required":true,
   "options":["PCVR","Quest単体","デスクトップ"]},
  {"label":"意気込み (任意)","item_type":"textarea","is_required":false}]}'
for EV in "$MAIN" "$TRIAL"; do
  curl -s -o /dev/null -b "$JAR" -H "$XH" -H "$CT" -X PUT "$BASE/api/v1/events/$EV/form" -d "$FORM_ITEMS"
done
echo "  フォーム設定完了 (autofill付き設問3つ × 2イベント)"

echo "== 3/5 fan01〜08 が「デモVRライブ」に応募 =="
FORM=$(curl -s "$BASE/api/v1/events/$MAIN/form")
I1=$(echo "$FORM" | jqpy "print(d['items'][0]['id'])")
I2=$(echo "$FORM" | jqpy "print(d['items'][1]['id'])")
PLATFORMS=("PCVR" "Quest単体" "デスクトップ")
for i in 1 2 3 4 5 6 7 8; do
  login "fan0$i@example.com"
  PF=${PLATFORMS[$((i % 3))]}
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -b "$JAR" -H "$XH" -H "$CT" \
    -X POST "$BASE/api/v1/events/$MAIN/applications" -d "{
      \"answers\":[{\"form_item_id\":\"$I1\",\"value\":\"fan0${i}_vrc\"},
                   {\"form_item_id\":\"$I2\",\"value\":\"$PF\"}]}")
  echo "  fan0$i 応募: HTTP $CODE"
  sleep 1
done

echo "== 4/5 「デモVRライブ」の締切を過去へ (抽選可能に) =="
ssh "$SSH_DEST" "cd eventdeck-vr && $COMPOSE exec -T db psql -U eventdeck -d eventdeck -q -c \
  \"UPDATE events SET apply_starts_at = now() - interval '2 day', \
    apply_ends_at = now() - interval '1 hour' WHERE title = 'デモVRライブ'\""
echo "  締切クローズ完了"

echo "== 5/5 最終状態 =="
ssh "$SSH_DEST" "cd eventdeck-vr && $COMPOSE exec -T db psql -U eventdeck -d eventdeck -tA -c \
  \"SELECT e.title || ': 応募 ' || count(a.id) || ' 件 (' || e.status || ')' \
    FROM events e LEFT JOIN applications a ON a.event_id = e.id \
    WHERE e.title IN ('デモVRライブ','体験応募デモ') GROUP BY e.title, e.status\""
echo ""
echo "準備完了!"
echo "  アプリ:    $BASE/"
echo "  Mailpit:  $BASE:8025"
echo "  抽選画面:  organizer でログイン → ダッシュボード → デモVRライブ「抽選」"
