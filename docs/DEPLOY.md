# デプロイ手順 — Oracle Cloud Always Free(無料枠デモ用)

目的: 発表時に「クラウドサービスとして動いている」ことを見せる。**費用は一切かからない**
(Always Free の範囲内。カード登録は本人確認のみで課金されない)。

構成: Always Free の ARM VM 1台に `docker-compose.prod.yml` を丸ごと載せる。
dev 環境との違いは compose ファイル冒頭のコメントを参照。

---

## 1. Oracle Cloud アカウントと VM の作成(ブラウザ操作)

1. https://www.oracle.com/jp/cloud/free/ から無料アカウントを作成
   (本人確認にクレジットカードが必要。**Always Free リソースのみ使う限り課金されない**。
   誤課金が心配なら、アップグレードせず「Always Free」のまま使うこと)
2. コンソール → Compute → Instances → **Create instance**
   - Shape: **VM.Standard.E2.1.Micro**(Shape series「Specialty and previous generation」内。
     Always Free-eligible。AMD x86・1GB RAM。**在庫切れがほぼ無い**)
   - Image: **Ubuntu 24.04**(x86_64。Shape確定後に選ぶと自動でx86版になる)
   - Networking: 既存VCNの **public subnet** を選び、
     **「Automatically assign public IPv4 address」を必ずON**
   - SSH公開鍵を登録(手元の `~/.ssh/id_ed25519.pub` の中身を貼り付け)
   - ※ 代替: Ampere A1 Flex(ARM・2 OCPU/12GB)は高性能だが東京では在庫切れが頻発する。
     取れた場合はスワップ作成(§2の手順)を省略してよい
3. **ポート開放**(2箇所必要):
   - VCN → サブネットの **Security List** に Ingress ルールを追加:
     - `0.0.0.0/0` → TCP **80**(アプリ本体)
     - `0.0.0.0/0` → TCP **8025**(Mailpit メール確認UI。デモ用)
   - VM 内の iptables も開放(Ubuntu イメージは既定で REJECT が入っている):
     ```bash
     sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
     sudo iptables -I INPUT -p tcp --dport 8025 -j ACCEPT
     sudo netfilter-persistent save   # 無ければ: sudo apt install iptables-persistent
     ```

## 2. VM のセットアップ(SSH)

```bash
ssh ubuntu@<VMのパブリックIP>

# (E2.1.Micro の場合必須) スワップ4GBを作成 — RAM 1GB ではビルドがメモリ不足になるため
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab   # 再起動後も有効化

# Docker のインストール(公式スクリプト)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit   # 反映のため一度ログアウト→再SSH
```

## 3. アプリの配置と起動

```bash
# コードを配置 (git remote があれば clone、無ければ手元から scp)
git clone <このリポジトリ> eventdeck-vr && cd eventdeck-vr
# または手元から: scp -r ./eventdeck-vr ubuntu@<IP>:~/

# 本番用 .env を作成
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://eventdeck:eventdeck@db:5432/eventdeck
REDIS_URL=redis://redis:6379/0
SESSION_SECRET=$(openssl rand -hex 32)
SMTP_HOST=mailpit
SMTP_PORT=1025
MAIL_FROM=noreply@eventdeck.local
BASE_URL=http://<VMのパブリックIP>
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
FCM_CREDENTIALS_JSON=
APP_ENV=prod
COOKIE_SECURE=false
EOF

# 起動 (マイグレーションは api 起動時に自動実行される)
# E2.1.Micro は初回ビルドが遅い (30〜60分)。SSH切断でビルドが止まらないよう nohup で実行し、
# ログを tail で見守る
nohup make prod-up > build.log 2>&1 &
tail -f build.log     # 「Started」が並んだら Ctrl+C で tail を抜ける (ビルドは継続する)

# デモデータ投入
make prod-seed
```

確認: `http://<VMのパブリックIP>/` でアプリ、`:8025` でメールUI、
`/api/v1/healthz` が `{"status":"ok","db":true,"redis":true}`。

## 4. 運用コマンド

| 操作 | コマンド |
|---|---|
| 停止(発表後) | `make prod-down`(DBデータはボリュームに残る) |
| ログ確認 | `make prod-logs` |
| DBバックアップ | `make backup` → `backups/eventdeck-*.sql.gz` |
| 完全削除 | `docker compose -f docker-compose.prod.yml down -v` |

## 5. 注意事項

- **HTTPSなしのデモ構成**(`COOKIE_SECURE=false`)。実運用に進む場合はドメインを取り、
  Caddy か certbot で HTTPS 化して `COOKIE_SECURE` の行を消す(自動でSecureになる)。
- Mailpit のUIを公開しているのはデモのため。**実メールアドレスを登録しない**こと
  (シードの organizer / fan01〜08 を使う)。
- DBパスワードは compose 内固定(外部非公開ポートのため)。公開する場合は変更する。
- Always Free の Ampere VM はアイドルでも停止されないので、発表前に起動しっぱなしでよい。
  心配なら発表の前日に `make prod-up` で立ち上げて疎通確認しておく。
