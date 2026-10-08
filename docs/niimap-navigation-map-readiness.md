# NiiMapのBoard遷移・地図準備状態

## 修正

Spot一覧からBoardを開くと、使っていないnative Thread詳細Paneが幅を残していた。
Workspace trailが開いている場合、Thread/Roomの親stageを持たない詳細PaneだけをCSSでレイアウトから外す。
Paneは削除せず、Close後には元の一覧配置へ戻す。Thread詳細、Room、Room内の一覧/Board/Thread stageでは親Paneを保持する。

地図SDKのload前に発生する、欠落したvector source layerの警告を地図全体の失敗として表示していた。
実際にlocal/publicで観測し、その後loadへ回復したメッセージ形式だけを限定して読み込み継続とする。
HTTP statusを持つエラー、style解析失敗、その他の初期化エラーは失敗表示と再試行を維持する。
タイムアウトは追加・延長していない。未知のエラーを一律に無視しない。

地図と初回検索の準備状態を独立して扱い、地図のload後も検索待ちなら「読み込み中...」を表示する。
初回検索が失敗した場合は検索エラーと再試行を保持し、地図エラーへ置き換えない。
SDKのerrorとloadは異なるイベントである（[MapLibreのイベント定義](https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapEventType/#error)）。

## QA（2026-10-08）

- `scripts.niimap_navigation_browser_tests` の2メソッド、PC/mobile計12シナリオ。
  - Spot→Boardの隣接・空白なし・Close復元。
  - native Thread→Account、およびnative Room→Member→Accountの親保持とClose復元。
  - 欠落source-layer警告、同じメッセージでもHTTP statusを持つ失敗、load後の検索待ち表示。
  - 実SDKが不正なstyle JSONでloadできないケースと、reloadによる再試行。
  - 初回検索の不正JSON応答と、地図をreloadしない検索再試行。
- 初回runはRoom確認に存在しないownerリンクを指定して2ケース失敗した。実在するMember導線へ直し、遷移メソッドを再実行：1テスト / 13.369秒、PC/mobile全6シナリオ成功。
- HTTP status判定とload後の検索待ちを追加確認した地図メソッド：1テスト / 6.812秒、PC/mobile全6シナリオ成功。
- 既存`browser_smoke.py` CLIを隔離SQLite LiveServerで1回実行：1テスト / 32.541秒、PC/mobileとも成功、warnings/browser errorsなし。Workspace画像を目視確認した。
- 通常serverでは既存デモBoardをGETだけで確認し、実SDKの6件のsource-layer警告が出ても誤った失敗表示が出ず、load後に一覧が表示された。Spot/Board間の空白もなくなった。初回検索POSTは一時browser context内でSSR IDから応答し、共有DBへ送信していない。
- `node --check`、test AST、対象diff checkが成功。

テストrunnerはdotenv読込を無効化し、SQLite `:memory:`とDB一つをassertする。
fixture作成と検索POSTは隔離LiveServerだけで行い、8000/publicへの誤接続をguardで禁止する。
共有DBの変更、migration、通常server再起動は行っていない。test DBの既存migration適用は一時SQLite内のみ。
JavaScript/CSS内容だけの製品変更で、templateのasset versionは変更していない。

ignored `.artifacts/niimap-fixes-2026-10-08/` に画像・結果、`smoke/`に既存smoke画像、`existing-data/`に実SDK確認記録を保持する。
README、inbox、既存の他差分、調査時のartifactは編集・stageしていない。

## 公開範囲

作業開始時のlocal HEADは`1ad8715`、remote masterは`ddef8887100d93aa435d2e0eb506eef6689ddf2a`。
間にBasic入力検証（`b9bb409`）、Basic URL復元（`450f30d`）、補助Pane cleanup（`0d889fb`）、デモデータscript/QA（`1ad8715`）の4コミットがある。
今回の2件以外を公開する承認範囲が確定しないため、local commit後、push前に親タスクへ公開範囲の判断を返す。
force/amend/rebase、Git/Vercel設定変更は行わない。
