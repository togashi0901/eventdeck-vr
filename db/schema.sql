-- ============================================================
-- EventDeck VR データベース定義 (PostgreSQL 16)
-- 要件定義書「EventDeckVR_要件定義書」のテーブル一覧に対応
-- 文字コード: UTF-8 / タイムゾーン: すべて timestamptz (UTC保存)
-- ============================================================

-- UUID生成 (PostgreSQL 13+ 標準の gen_random_uuid を使用)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ------------------------------------------------------------
-- 1. users: 全利用者のアカウント (参加者・主催者共通の基盤)
--    主催者権限は organization_members への所属で表現する
-- ------------------------------------------------------------
CREATE TABLE users (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email              varchar(254) NOT NULL UNIQUE,
    password_hash      varchar(255) NOT NULL,               -- bcrypt/argon2 のハッシュ文字列
    is_system_admin    boolean     NOT NULL DEFAULT false,  -- サービス運営者のみ true
    email_verified_at  timestamptz,                         -- NULL = メール未確認
    last_login_at      timestamptz,
    deleted_at         timestamptz,                         -- 退会 (ソフトデリート)
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE users IS '全利用者アカウント。参加者/主催者の区別は organization_members への所属有無で決まる';

-- ------------------------------------------------------------
-- 2. user_profiles: 参加者の事前登録情報 (応募フォーム自動入力の元データ)
-- ------------------------------------------------------------
CREATE TABLE user_profiles (
    user_id            uuid        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name       varchar(50) NOT NULL,
    vrchat_username    varchar(64),                         -- VRChatユーザー名 (任意)
    platform           varchar(20) NOT NULL DEFAULT 'unknown'
        CHECK (platform IN ('pcvr', 'desktop', 'quest_standalone', 'mobile', 'unknown')),
    device_note        varchar(200),                        -- 利用機材の自由記述 (例: Quest 3 + PC)
    x_account          varchar(50),                         -- X(旧Twitter)のID (任意, @なし)
    discord_account    varchar(64),                         -- Discordユーザー名 (任意)
    bio                varchar(500),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE user_profiles IS '応募フォームに自動入力されるプロフィール。autofill_key の参照先';

-- ------------------------------------------------------------
-- 3. organizations: 主催団体 (課金契約の単位)
-- ------------------------------------------------------------
CREATE TABLE organizations (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name               varchar(100) NOT NULL,
    slug               varchar(50) NOT NULL UNIQUE
        CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$'), -- 公開URL用 (/o/{slug})
    description        text,
    website_url        varchar(500),
    stripe_customer_id varchar(64) UNIQUE,                  -- Stripe連携 (未契約時はNULL)
    plan               varchar(20) NOT NULL DEFAULT 'trial'
        CHECK (plan IN ('trial', 'standard', 'suspended')),
    trial_ends_at      timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE organizations IS '主催団体。導入費・利用料の契約単位。参加者は所属しない';

-- ------------------------------------------------------------
-- 4. organization_members: 団体への所属 (1団体に複数の主催者ユーザー可)
-- ------------------------------------------------------------
CREATE TABLE organization_members (
    organization_id    uuid        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id            uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role               varchar(20) NOT NULL DEFAULT 'member'
        CHECK (role IN ('owner', 'member')),                -- owner: 契約・メンバー管理が可能
    joined_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id, user_id)
);
COMMENT ON TABLE organization_members IS 'このテーブルに行がある user が主催者としてふるまえる';

-- ------------------------------------------------------------
-- 5. events: イベント
-- ------------------------------------------------------------
CREATE TABLE events (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    uuid        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by         uuid        NOT NULL REFERENCES users(id),
    title              varchar(100) NOT NULL,
    description        text        NOT NULL DEFAULT '',
    platform           varchar(20) NOT NULL DEFAULT 'vrchat'
        CHECK (platform IN ('vrchat', 'cluster', 'resonite', 'real', 'other')),
    world_name         varchar(100),                        -- 開催ワールド/会場名
    world_url          varchar(500),                        -- ワールドURL・招待リンク等
    starts_at          timestamptz NOT NULL,
    ends_at            timestamptz NOT NULL,
    capacity           integer     NOT NULL CHECK (capacity > 0),
    selection_method   varchar(20) NOT NULL DEFAULT 'lottery'
        CHECK (selection_method IN ('lottery', 'first_come')),
    apply_starts_at    timestamptz NOT NULL,                -- 応募受付開始
    apply_ends_at      timestamptz NOT NULL,                -- 応募締切 (抽選はこれ以降に実行)
    status             varchar(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'closed', 'finished', 'canceled')),
        -- draft: 下書き / published: 公開・受付中 / closed: 締切済(抽選・開催前)
        -- finished: 開催終了 / canceled: 開催中止
    visibility         varchar(20) NOT NULL DEFAULT 'public'
        CHECK (visibility IN ('public', 'unlisted')),       -- unlisted: URLを知る人のみ
    header_image_url   varchar(500),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at),
    CHECK (apply_ends_at > apply_starts_at),
    CHECK (apply_ends_at <= starts_at)
);
CREATE INDEX idx_events_org      ON events (organization_id, status);
CREATE INDEX idx_events_public   ON events (status, visibility, starts_at)
    WHERE status = 'published' AND visibility = 'public';   -- 公開イベント一覧用
COMMENT ON TABLE events IS 'イベント本体。抽選(lottery)か先着(first_come)かを selection_method で選ぶ';

-- ------------------------------------------------------------
-- 6. form_items: イベントごとの応募フォーム設問定義
-- ------------------------------------------------------------
CREATE TABLE form_items (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id           uuid        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    label              varchar(200) NOT NULL,               -- 設問文
    help_text          varchar(500),
    item_type          varchar(20) NOT NULL
        CHECK (item_type IN ('text', 'textarea', 'select', 'radio', 'checkbox', 'number')),
    options            jsonb,                               -- select/radio/checkbox の選択肢: ["A","B"]
    is_required        boolean     NOT NULL DEFAULT false,
    autofill_key       varchar(30)                          -- プロフィール自動入力の対応キー
        CHECK (autofill_key IN ('display_name', 'vrchat_username', 'platform',
                                'device_note', 'x_account', 'discord_account')),
    sort_order         integer     NOT NULL DEFAULT 0,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CHECK ( (item_type IN ('select', 'radio', 'checkbox')) = (options IS NOT NULL) )
);
CREATE INDEX idx_form_items_event ON form_items (event_id, sort_order);
COMMENT ON COLUMN form_items.autofill_key IS 'NULL以外なら user_profiles の該当項目を初期値として自動入力する';

-- ------------------------------------------------------------
-- 7. applications: 応募 (1ユーザー1イベント1件)
-- ------------------------------------------------------------
CREATE TABLE applications (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id           uuid        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id            uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status             varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'won', 'lost', 'waitlisted', 'canceled')),
        -- pending: 応募中(結果待ち) / won: 当選(先着確定含む) / lost: 落選
        -- waitlisted: 補欠 / canceled: 応募者都合キャンセル(当選後の辞退含む)
    promoted           boolean     NOT NULL DEFAULT false,  -- true: 補欠からの繰り上げ当選
    canceled_at        timestamptz,
    cancel_reason      varchar(200),
    applied_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, user_id),
    CHECK ( (status = 'canceled') = (canceled_at IS NOT NULL) )
);
CREATE INDEX idx_applications_event ON applications (event_id, status);
CREATE INDEX idx_applications_user  ON applications (user_id, applied_at DESC);
COMMENT ON TABLE applications IS '状態遷移はDB設計書の遷移図に従う。繰り上げ当選は won + promoted=true';

-- ------------------------------------------------------------
-- 8. application_answers: 応募フォームの回答
-- ------------------------------------------------------------
CREATE TABLE application_answers (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id     uuid        NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    form_item_id       uuid        NOT NULL REFERENCES form_items(id) ON DELETE CASCADE,
    answer_text        text,                                -- text/textarea/select/radio/number の回答
    answer_json        jsonb,                               -- checkbox(複数選択) の回答: ["A","B"]
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (application_id, form_item_id),
    CHECK (answer_text IS NOT NULL OR answer_json IS NOT NULL)
);
COMMENT ON TABLE application_answers IS '設問1つにつき1行。単一値は answer_text、複数選択は answer_json';

-- ------------------------------------------------------------
-- 9. lotteries: 抽選の実行記録 (公平性の証跡)
--    同一イベントで複数回実行可 (追加抽選・キャンセル補充)
-- ------------------------------------------------------------
CREATE TABLE lotteries (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id           uuid        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    round              integer     NOT NULL DEFAULT 1,      -- 同一イベント内の実行回数 (1始まり)
    executed_by        uuid        NOT NULL REFERENCES users(id),
    seed               bigint      NOT NULL,                -- 乱数シード (再現・監査用に保存)
    algorithm_version  varchar(20) NOT NULL DEFAULT 'v1',   -- 抽選ロジックのバージョン識別子
    winner_quota       integer     NOT NULL CHECK (winner_quota >= 0),  -- この回で選ぶ当選者数
    waitlist_quota     integer     NOT NULL DEFAULT 0 CHECK (waitlist_quota >= 0),
    config             jsonb       NOT NULL DEFAULT '{}',   -- 優先枠などの設定スナップショット
    executed_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, round)
);
COMMENT ON TABLE lotteries IS '抽選仕様書(別文書)のロジックで実行。seed+config+対象者集合から結果を再現できる';

-- ------------------------------------------------------------
-- 10. lottery_results: 抽選対象と結果の明細 (どの応募がどう扱われたか)
-- ------------------------------------------------------------
CREATE TABLE lottery_results (
    lottery_id         uuid        NOT NULL REFERENCES lotteries(id) ON DELETE CASCADE,
    application_id     uuid        NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    result             varchar(20) NOT NULL
        CHECK (result IN ('won', 'lost', 'waitlisted')),
    draw_rank          integer     NOT NULL,                -- 抽選順位 (1が最上位)
    quota_name         varchar(50) NOT NULL DEFAULT 'general', -- 適用された枠 (general/first_timer 等)
    PRIMARY KEY (lottery_id, application_id)
);
CREATE INDEX idx_lottery_results_app ON lottery_results (application_id);
COMMENT ON TABLE lottery_results IS '抽選ごとの全対象応募の結果明細。applications.status 更新の根拠となる証跡';

-- ------------------------------------------------------------
-- 11. notifications: 通知の配信履歴 (アプリ内通知の実体も兼ねる)
-- ------------------------------------------------------------
CREATE TABLE notifications (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id       uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id           uuid        REFERENCES events(id) ON DELETE SET NULL,
    type               varchar(30) NOT NULL
        CHECK (type IN ('result_won', 'result_lost', 'result_waitlisted',
                        'promoted', 'reminder', 'event_updated', 'event_canceled',
                        'announcement')),
    channel            varchar(10) NOT NULL
        CHECK (channel IN ('in_app', 'email', 'push')),
    title              varchar(200) NOT NULL,
    body               text        NOT NULL,
    status             varchar(10) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'sent', 'failed')),
    error_detail       varchar(500),
    sent_at            timestamptz,
    read_at            timestamptz,                         -- in_app のみ使用
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_recipient ON notifications (recipient_id, channel, created_at DESC);
CREATE INDEX idx_notifications_queue     ON notifications (status, created_at) WHERE status = 'queued';
COMMENT ON TABLE notifications IS '1宛先×1チャネルで1行。通知ワーカーが queued を取り出して配信する';

-- ------------------------------------------------------------
-- 12. push_subscriptions: プッシュ通知の宛先 (FCMトークン)
-- ------------------------------------------------------------
CREATE TABLE push_subscriptions (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fcm_token          varchar(512) NOT NULL UNIQUE,
    user_agent         varchar(300),                        -- 登録元ブラウザの識別用
    created_at         timestamptz NOT NULL DEFAULT now(),
    last_used_at       timestamptz
);
CREATE INDEX idx_push_subs_user ON push_subscriptions (user_id);

-- ------------------------------------------------------------
-- 13. checkins: 当日の入場記録
-- ------------------------------------------------------------
CREATE TABLE checkins (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id           uuid        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    application_id     uuid        NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
    method             varchar(10) NOT NULL DEFAULT 'code'
        CHECK (method IN ('code', 'qr', 'manual')),          -- code: 入場コード照合 / manual: 手動チェック
    operator_id        uuid        REFERENCES users(id),     -- チェックを行った主催者
    checked_in_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_checkins_event ON checkins (event_id, checked_in_at);
COMMENT ON TABLE checkins IS '1応募につき最大1行 (UNIQUE)。参加率 = checkins数 / won数 で算出';

-- ------------------------------------------------------------
-- updated_at 自動更新トリガ
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['users','user_profiles','organizations','events',
                             'form_items','applications','application_answers']
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    END LOOP;
END $$;
