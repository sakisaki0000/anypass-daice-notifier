# AnyPASS リセール Da-iCE 通知

AnyPASS STORE のリセール一覧（https://store.anypass.jp/resale-list）をチェックして、Da-iCE の新しい出品があれば LINE に通知します。

```
[Da-iCE] Da-iCE のチケットが見つかりました。

タイトル: Da-iCE ARENA TOUR 2026 ...
場所: 大阪府 大阪城ホール
時間: 2026/12/01 17:00 / 18:00
席種: 指定席 × 2枚
価格: ¥9,900/1枚

https://store.anypass.jp/resale/xxxxxx/?t=...
```

> LINE Notify は 2025年3月31日でサービス終了したため、後継の **LINE Messaging API**（LINE公式アカウント）を使っています。

---

## ① LINE の準備（どちらの方法でも必要・10分程度）

1. https://entry.line.biz/ から **LINE公式アカウント** を作成（無料のコミュニケーションプランでOK）
2. [LINE Official Account Manager](https://manager.line.biz/) → 設定 → **Messaging API** →「Messaging APIを利用する」→ プロバイダーを作成/選択
3. [LINE Developers コンソール](https://developers.line.biz/console/) で作成されたチャネルを開く
   - **チャネル基本設定** タブの一番下「あなたのユーザーID」（`U` から始まる）→ これが `LINE_USER_ID`
   - **Messaging API設定** タブの一番下「チャネルアクセストークン（長期）」→ 発行 → これが `LINE_CHANNEL_ACCESS_TOKEN`
   - 同じタブの QR コードを LINE で読み取り、**公式アカウントを友だち追加**（しないと届きません）
4. （任意）Official Account Manager の「応答設定」で自動応答メッセージをオフにしておくと静かです

無料プランは月200通まで。1回のチェックで複数件見つかっても1通としてまとめて送るので、通常は十分です。

---

## ② A. GitHub Actions で動かす（PCオフでも24時間）

1. GitHub で新しいリポジトリを作成（**Public にする**。Private だと無料枠の月2,000分を5分間隔の実行で使い切ってしまうため。トークン等は Secrets に入れるので公開されません）し、このフォルダの中身を全部アップロード
   （`.github/workflows/check.yml` も含めて。Webでアップロードする場合、隠しフォルダが入らないことがあるので、なければ「Add file → Create new file」で `.github/workflows/check.yml` を作って中身を貼り付け）
2. リポジトリの **Settings → Secrets and variables → Actions → New repository secret** で2つ登録
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_USER_ID`
3. **Actions** タブ →「anypass Da-iCE check」→ **Run workflow** で手動実行して動作確認
4. 以降は約5分ごとに自動実行されます

注意:
- GitHub の定期実行は混雑時に数分〜十数分遅れることがあります
- 60日間リポジトリに更新がないと定期実行が自動停止します（通知済みリストの自動コミットがあれば延長されますが、止まっていたら Actions タブから再有効化）
- 万一 AnyPASS 側が GitHub のサーバー（海外IP）からのアクセスを弾いた場合は、Actions のログにエラーが出ます。その場合は B の PC 版を使ってください

## ② B. 自分の Windows PC で動かす（1〜2分間隔）

1. [Python](https://www.python.org/downloads/) をインストール（インストール時「Add python.exe to PATH」にチェック）
2. `.env.example` をコピーして `.env` にリネームし、トークンとユーザーIDを記入
3. テスト通知: このフォルダでコマンドプロンプトを開き
   ```
   pip install -r requirements.txt
   python notifier.py --test
   ```
4. `run_windows.bat` をダブルクリック → 120秒ごとに監視開始（黒い画面を閉じると停止）

PC起動時に自動で始めたい場合は、`run_windows.bat` のショートカットを `Win + R` →`shell:startup` で開くフォルダに入れてください。

---

## 設定の変更

- **間隔（PC版）**: `run_windows.bat` の `--loop 120` の数字（秒、最低60）。サイトに負荷をかけないよう短くしすぎないでください
- **間隔（Actions版）**: `check.yml` の `cron: "*/5 * * * *"`（5分未満にはできません）
- **対象アーティスト**: `ARTIST_KEYWORDS`（カンマ区切りで複数可 例 `Da-iCE,AAA`）。Actions 版は Settings → Variables に `ARTIST_KEYWORDS` を登録
- 表記ゆれ（DA-ICE / ＤＡ－ＩＣＥ など）は自動で吸収します

## 仕組み

- リセール一覧ページ（新着順）を取得し、アーティスト名・公演名にキーワードを含む出品を抽出
- 出品ID（`/resale/数字`）を `seen.json` に記録し、同じ出品は2回通知しません
- 初回実行時は、その時点で出品中の Da-iCE チケットもすべて通知されます

## ファイル

| ファイル | 役割 |
|---|---|
| `notifier.py` | 本体 |
| `.github/workflows/check.yml` | GitHub Actions 設定 |
| `run_windows.bat` | Windows で常駐起動 |
| `.env.example` | PC用設定のひな形 |
| `seen.json` | 通知済み出品IDの記録 |
