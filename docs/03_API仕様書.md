# EventDeck VR API仕様書 (v1)

対応文書: 「EventDeckVR_要件定義書」「01_DB設計書」「02_抽選仕様書」
実装: FastAPI / ベースパス: `/api/v1`

各エンドポイントの `[M番号]` は開発時のマイルストーン区分を示す(実装はすべて完了している)。

---

## 1. 共通仕様

### 1.1 認証方式

**httpOnlyクッキーによるセッション認証**(セッション実体はRedisに保存)。

- ログイン成功時に `Set-Cookie: session_id=...; HttpOnly; Secure; SameSite=Lax; Max-Age=1209600`(14日)。
- SPAは同一オリジンで配信されるためCookieが自動送付される。JS からトークンに触れないためXSS耐性が高い。
- CSRF対策: 状態変更系(POST/PUT/DELETE)は `X-Requested-With: XMLHttpRequest` ヘッダを必須とする(SameSite=Laxと併用)。
- Redisのキー: `session:{session_id}` → `{user_id, created_at}`。ログアウトで削除。

### 1.2 認可レベル

| レベル | 条件 |
|---|---|
| public | 未ログインで可 |
| user | ログイン必須 |
| member | 対象リソースの organization に所属(organization_members に行がある) |
| owner | 所属かつ role='owner' |

memberチェックは「URL中のリソース → event → organization_id → organization_members」で解決する。**リソースの存在有無を漏らさないため、権限なしは404を返す**(403ではなく)。

### 1.3 エラー形式

```json
{ "error": { "code": "validation_error", "message": "説明", "details": [ { "field": "email", "reason": "invalid" } ] } }
```

| HTTP | code(代表) | 用途 |
|---|---|---|
| 400 | validation_error | 入力不正 |
| 401 | unauthenticated | 未ログイン・セッション失効 |
| 404 | not_found | 不存在 or 権限なし |
| 409 | conflict / precondition_failed | 重複応募、締切前の抽選実行など |
| 422 | unprocessable | 意味的に処理不能(枠合計>定員 など) |
| 429 | rate_limited | ログイン試行超過など |
| 500 | internal_error | サーバ内部エラー(詳細は返さない) |

### 1.4 その他の規約

- 日時はすべて ISO 8601 / UTC(例: `2026-08-01T12:00:00Z`)。表示側でJST変換。
- 一覧系は `?page=1&per_page=20`(per_page最大100)。レスポンスに `meta: {page, per_page, total}` を含む。
- IDはすべてUUID文字列。
- レート制限: `POST /auth/login` と `POST /auth/register` はIPあたり10回/分(Redisカウンタ)。

---

## 2. エンドポイント一覧

### 2.1 認証 [M1]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| POST `/auth/register` | public | `{email, password}`。201。確認メールを送信(dev環境はMailHog) |
| POST `/auth/verify-email` | public | `{token}`。`users.email_verified_at` をセット |
| POST `/auth/login` | public | `{email, password}` → セッションCookie発行。未確認メールは403相当のエラーコード `email_not_verified` |
| POST `/auth/logout` | user | セッション破棄 |
| GET `/auth/me` | user | `{id, email, has_profile, organizations: [{id, name, role}]}` |
| POST `/auth/password-reset/request` | public | `{email}`。存在有無に関わらず200(列挙防止) |
| POST `/auth/password-reset/confirm` | public | `{token, new_password}` |

### 2.2 プロフィール・マイページ [M1, 通知はM4]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| GET `/me/profile` | user | user_profiles の内容。未登録なら404 |
| PUT `/me/profile` | user | upsert。`{display_name, vrchat_username?, platform, device_note?, x_account?, discord_account?, bio?}` |
| GET `/me/applications` | user | 自分の応募一覧(イベント概要・status・入場コード含む)[M3] |
| GET `/me/notifications` | user | アプリ内通知一覧(channel='in_app')。`?unread_only=true` [M4] |
| POST `/me/notifications/{id}/read` | user | read_at をセット [M4] |
| POST `/me/push-subscriptions` | user | `{fcm_token, user_agent?}`。既存トークンならlast_used_at更新 [M4] |
| DELETE `/me/push-subscriptions/{fcm_token}` | user | 購読解除 [M4] |

### 2.3 団体 [M2]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| POST `/organizations` | user | `{name, slug, description?}`。作成者が owner になる |
| GET `/organizations/{slug}` | public | 団体公開ページ(名前・説明・公開中イベント一覧) |
| GET `/orgs/{org_id}` | member | 管理用詳細 |
| PUT `/orgs/{org_id}` | owner | 更新 |
| GET `/orgs/{org_id}/members` | member | メンバー一覧 |
| POST `/orgs/{org_id}/members` | owner | `{email, role}`。登録済みユーザーをメールアドレスで追加(MVP。招待フローは将来) |
| DELETE `/orgs/{org_id}/members/{user_id}` | owner | 除名。最後のownerは削除不可(409) |

### 2.4 イベント [M2]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| GET `/events` | public | 公開イベント一覧。`?platform=&from=&q=&page=`。status='published' かつ visibility='public' のみ |
| GET `/events/{event_id}` | public/member | published は誰でも可。draft 等は member のみ(非該当は404) |
| POST `/orgs/{org_id}/events` | member | 作成(status='draft')。本文は events テーブルの列に対応 |
| PUT `/events/{event_id}` | member | 更新。published 後は capacity の減少を禁止(422) |
| POST `/events/{event_id}/publish` | member | draft → published。時系列CHECKに反する場合422 |
| POST `/events/{event_id}/cancel` | member | → canceled。全応募者へ event_canceled 通知を積む [M4連動] |
| GET `/orgs/{org_id}/events` | member | ダッシュボード用一覧。`?status=` |

### 2.5 応募フォーム [M3]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| GET `/events/{event_id}/form` | public | 設問一覧(sort_order順)。**ログイン済みかつプロフィール登録済みなら `prefill: {form_item_id: 初期値}` を同梱**(autofill_key解決はサーバ側で行う) |
| PUT `/events/{event_id}/form` | member | 設問の全置換 `{items: [...]}`。**応募が1件以上あるイベントでは、既存設問の削除・item_type変更・is_required の false→true 変更を禁止(409 `form_locked`)**。ラベル修正と設問追加は可 |

### 2.6 応募 [M3]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| POST `/events/{event_id}/applications` | user | `{answers: [{form_item_id, value?, values?}]}`。単一値は value、checkbox は values。検証: 受付期間内か / 必須回答が揃っているか / options に含まれる値か / 重複応募でないか(409 `already_applied`)。**プロフィール未登録は422 `profile_required`**。selection_method='first_come' の場合、残定員内なら即 status='won' |
| GET `/events/{event_id}/applications` | member | 応募者一覧。`?status=&q=`(qは表示名・VRChat名を部分一致)。回答内容を含む |
| GET `/applications/{id}` | 本人 or member | 詳細 |
| POST `/applications/{id}/cancel` | 本人 | → canceled。**won からのキャンセル時は繰り上げ処理をトリガ**(02_抽選仕様書 §7) |
| GET `/me/applications/{id}/entry-code` | 本人 | `{application_id, short_code}`。short_code = application_id の先頭8桁(表示用)。QRコードの中身は application_id 全体 |

### 2.7 抽選 [M4]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| POST `/events/{event_id}/lotteries/preview` | member | `{quotas, waitlist_count}` を受け、**実行せずに**集計を返す: `{target_count, remaining_capacity, quota_matches: {first_timer: 12, ...}}`。設定不正は422 |
| POST `/events/{event_id}/lotteries` | member | 抽選実行。ボディは preview と同じ。前提条件(02_仕様書§3)を満たさない場合409 `precondition_failed`。成功時は `{lottery_id, round, won: n, waitlisted: n, lost: n}`。通知行の作成まで同一トランザクションで行う |
| GET `/events/{event_id}/lotteries` | member | 実行履歴(round、実行者、件数サマリ) |
| GET `/lotteries/{id}/results` | member | 明細(application、result、draw_rank、quota_name)。ページング |
| POST `/applications/{id}/promote` | member | 手動繰り上げ(waitlisted → won, promoted=true)。順位無視の指名繰り上げは不可: **対象は「次の繰り上げ候補」のみ**。候補でない場合409 |

### 2.8 入場管理 [M5]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| POST `/events/{event_id}/checkins` | member | `{application_id}` または `{short_code}`、`{method: code\|qr\|manual}`。検証: 対象応募がこのイベントの won であること / 未入場であること(重複は409 `already_checked_in`) |
| GET `/events/{event_id}/checkins` | member | 入場済み一覧 + `{won_count, checkin_count, checkin_rate}` |
| DELETE `/checkins/{id}` | member | 誤操作の取り消し |

### 2.9 通知(主催者からの一斉配信) [M4]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| POST `/events/{event_id}/notifications` | member | `{type: reminder\|announcement, target: won\|all_applicants, title, body, channels: [in_app, email, push]}`。宛先×チャネルぶんの notifications 行を queued で一括INSERT。レスポンスは `{queued: n}` |
| GET `/events/{event_id}/notifications` | member | 配信履歴(type別・状態別の集計付き) |

### 2.10 分析 [M6]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| GET `/events/{event_id}/analytics` | member | `{applications_total, by_status, checkin_rate, first_timer_rate, daily_applications: [{date, count}]}` |
| GET `/orgs/{org_id}/analytics/summary` | member | 団体横断: イベント別の応募数・参加率・リピート率(2回以上入場したユニークユーザー率) |

### 2.11 課金(Stripe) [M6・最小限]

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| POST `/orgs/{org_id}/billing/checkout-session` | owner | Stripe Checkout セッションを作成しURLを返す(主催者ユーザー数ぶんのサブスクリプション) |
| POST `/webhooks/stripe` | public(署名検証) | `checkout.session.completed` で plan='standard'、`customer.subscription.deleted` で 'suspended' に更新 |

### 2.12 運用

| メソッド/パス | 認可 | 説明 |
|---|---|---|
| GET `/healthz` | public | `{status: "ok", db: true, redis: true}`。監視用 [M1] |

---

## 3. 主要レスポンス例

### GET /events/{event_id} (public)

```json
{
  "id": "e1a2...", "title": "新酒発表VRライブ",
  "organization": { "id": "...", "name": "三途酒造イベント部", "slug": "santo-brew" },
  "platform": "vrchat", "world_name": "Santo Brewery Hall",
  "starts_at": "2026-08-01T12:00:00Z", "ends_at": "2026-08-01T14:00:00Z",
  "capacity": 50, "selection_method": "lottery",
  "apply_starts_at": "2026-07-10T00:00:00Z", "apply_ends_at": "2026-07-25T00:00:00Z",
  "status": "published",
  "application_state": { "applied": true, "status": "pending" }
}
```
`application_state` はログイン済みユーザーにのみ含める(自分の応募状況)。

### GET /events/{event_id}/form (ログイン済み)

```json
{
  "items": [
    { "id": "f1", "label": "VRChatユーザー名", "item_type": "text",
      "is_required": true, "autofill_key": "vrchat_username", "options": null },
    { "id": "f2", "label": "参加予定プラットフォーム", "item_type": "radio",
      "is_required": true, "autofill_key": "platform",
      "options": ["PCVR", "Quest単体", "デスクトップ"] }
  ],
  "prefill": { "f1": "togashi_vrc", "f2": "PCVR" }
}
```

### POST /events/{event_id}/lotteries (成功)

```json
{ "lottery_id": "...", "round": 1, "won": 50, "waitlisted": 5, "lost": 45,
  "executed_at": "2026-07-25T03:00:00Z" }
```

---

## 4. 実装上の注意(Claude Code向け)

1. ルーティングは `app/api/v1/` 配下にリソース単位で分割する(auth.py, events.py, applications.py, lotteries.py ...)。
2. 認可チェックはFastAPIの依存性注入(`Depends`)で共通化する: `current_user`, `require_member(event_id)`, `require_owner(org_id)`。
3. Pydanticスキーマはリクエスト/レスポンスで分離し、DBモデルを直接返さない。
4. 抽選実行(2.7)はイベント単位の排他制御を行う: `SELECT ... FOR UPDATE` でイベント行をロックしてから 02_仕様書§5 のトランザクションを実行する。
5. 先着(first_come)の当選判定も同様にイベント行ロック下で「残定員チェック→won確定」を行う(同時応募の競合対策)。
6. 通知の実配信はAPIプロセスでは行わない。queued 行の作成まで。配信は通知ワーカーの責務(M4)。
