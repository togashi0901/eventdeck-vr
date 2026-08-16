# EventDeck VR

VRイベント主催者向けのイベント運営管理SaaS。募集ページ作成・応募フォーム(プロフィール自動入力)・
公平な抽選(seed保存で再現可能)・結果通知(アプリ内/メール)・QR入場管理・分析までを一気通貫で提供する。

開発: 冨樫 大和(Team EventDeck)

| | |
|---|---|
| リポジトリ | https://github.com/togashi0901/eventdeck-vr |
| 画面の一覧 | [docs/screenshots/](docs/screenshots/) |
| システム構成図 | [docs/assets/システム構成図.png](docs/assets/システム構成図.png) |

## 特徴

- **公平性を検証できる抽選** — 乱数シード・抽選条件・対象者を保存し、後から同じ結果を再現できる。
  抽選記録は追記専用で、実行後に書き換えられない
- **プロフィール自動入力** — 参加者が一度登録すれば、応募フォームに登録済みの情報が自動で入る
- **通知の自動配信** — 当落・繰り上げ当選をアプリ内通知とメールで自動送信(APIと分離した非同期ワーカー)
- **QR入場管理** — QRコードと8桁コードで受付。二重入場はDBの一意制約で防止
- **Docker Compose で7サービス** — `make up` 一発で全環境が起動し、同じ構成のままクラウドへデプロイできる

## 技術構成

| 領域 | 採用技術 |
|---|---|
| バックエンド | Python 3.12 / FastAPI / SQLAlchemy 2(async)/ Alembic |
| フロントエンド | React 18 / TypeScript / Vite / Tailwind CSS 3 / React Router / TanStack Query |
| データストア | PostgreSQL 16 / Redis 7 |
| インフラ | Docker Compose(nginx / api / worker / front / db / redis / mail)/ Oracle Cloud Infrastructure |
| テスト | pytest(85件・実DBに対して実行) |

システム構成図: [docs/assets/システム構成図.png](docs/assets/システム構成図.png)

## 起動手順(開発環境)

前提: Docker (compose v2)。

```bash
cp .env.example .env   # そのままでOK (dev用デフォルト)
make up                # 全コンテナ起動 (nginx/api/worker/front/db/redis/mailhog)
make migrate           # alembic upgrade head (初回のみ)
make seed              # デモデータ投入 (何度実行してもよい)
```

| URL | 内容 |
|---|---|
| http://localhost | アプリ本体 |
| http://localhost:8025 | MailHog(送信メールの確認UI) |
| http://localhost/api/v1/healthz | ヘルスチェック |

シードアカウント(パスワードは全員 `Passw0rd!`):

- 主催者: `organizer@example.com`(団体 Team EventDeck の owner)
- 参加者: `fan01@example.com` 〜 `fan08@example.com`(プロフィール登録済み)

## テスト実行手順

```bash
make test   # backend: pytest (テスト用DBを自動作成・破棄。抽選リファレンステスト含む)
make lint   # ruff + ESLint
```

バックエンドは pytest 85件(実DBに対して実行し、同時応募の競合と抽選の再現性を含む)。
フロントエンドは型チェック(tsc)と ESLint で担保し、自動テストは書いていない。

## デモシナリオ(一連の流れ)

1. **募集**: organizer でログイン → ダッシュボード → 新規イベント作成(定員5・抽選)→
   「設問」で応募フォームを設計(VRChatユーザー名に自動入力を設定)→「公開する」
2. **応募**: fan01〜fan08 でログイン → イベント詳細 → 応募(プロフィールが自動入力される)→
   マイページに「応募中」
3. **抽選**: organizer → 「抽選」→ プレビュー(対象8・当選枠5)→ 実行 →
   当選5/補欠2/落選1。各参加者のマイページ・アプリ内通知・MailHogのメールに結果が届く
4. **繰り上げ**: 当選者がマイページでキャンセル → 補欠1位が自動で繰り上げ当選し通知が届く
5. **入場**: 当選者のマイページにQRコード+短縮コード → organizer の「入場」画面で
   短縮コードを照合 → 入場率が更新される(二重入場はエラー)
6. **分析**: organizer の「分析」で応募推移・参加率・初参加率・リピート率を確認

※ 抽選は応募締切後のみ実行可能。デモで即実行したい場合は締切をDBで過去に移す:
`make psql` → `UPDATE events SET apply_ends_at = now() - interval '1 hour' WHERE id = '<event_id>';`

デモ状態は次のスクリプトで一括再現できる: `./scripts/demo_stage.sh`

## クラウドへのデプロイ

Oracle Cloud Infrastructure の仮想マシン1台に `docker-compose.prod.yml` で載せる。
手順は **[docs/DEPLOY.md](docs/DEPLOY.md)** を参照。

```bash
make prod-up    # 本番構成で起動 (静的ビルド・reload無し)
make backup     # DBバックアップ → backups/
```

## ドキュメント

| ファイル | 内容 |
|---|---|
| [docs/01_DB設計書.md](docs/01_DB設計書.md) | テーブル定義・状態遷移(`db/schema.sql` が正) |
| [docs/02_抽選仕様書.md](docs/02_抽選仕様書.md) | 抽選アルゴリズムと公平性の担保方法 |
| [docs/03_API仕様書.md](docs/03_API仕様書.md) | 全エンドポイント・認証・エラー規約 |
| [docs/DEPLOY.md](docs/DEPLOY.md) | クラウドへのデプロイ手順 |
| [docs/screenshots/](docs/screenshots/) | 各画面のスクリーンショットと機能説明 |

## ライセンス

MIT License([LICENSE](LICENSE))
