# NiiMap Board直接作成とPane UI調整

Version: v0.15
Status: Complete (implementation / isolated SQLite verification; release approved)
Dependency: v0.14 Account版更新・凍結／復帰基盤とinterfaces0008。

## NiiMapのBoard

Guest／Accountとも、新規作成で地図上の地点を選び、Boardを直接配置できる。Board名・詳細・座標・BoardPolicyを一つのtransactionで保存する。既存BoardPlacementの`niimap + coordinates + Collectionなし`を使い、新しいモデル・migration・独立Ownerを追加しない。

初期BoardPolicyは閲覧可能とThread作成可能がそれぞれGuest OR NiixyAccount、不可の2欄は空。作成時は既存のAccount条件UIから共通4欄を編集できる。現行Snapshotが対応するDefault（Guest／NiixyAccount／Login時の自分）、特定Account、Room参加者条件を利用し、外側OR・グループ内部AND・deny優先を共通評価する。GuestもNiixyAccount条件を候補から追加できる。

NiiMapのBoardには配置先管理者がいない。作成後の基本情報・Policy編集、削除、座標変更、未配置化・移動の操作は提供しない。作成したAccountにも管理権を与えない。作成画面で保存後に変更できない旨を案内する。Account／Roomの管理URLへMapBoard IDを渡してもscope照合で拒否する。

Mapmarker、Spot SummaryList、基本情報検索から共通BoardPaneへ進める。検索ではBoard自身の名称、閲覧可能時のみ詳細、更新日時を対象にする。独立Owner・作成者情報は保存しないため作成者条件の検索対象にしない。Field／Interface／ThreadPolicy検索を指定した場合は対応しないBoardを結果から除外する。Board内のThreadはNiiMapへ直接掲載されず、Board検索の一致理由にも使わない。

Boardの閲覧条件を満たさなければ詳細情報／Thread作成導線を出さず、直接Thread作成POSTも拒否する。名前と閲覧不可の案内はSummaryListに残し、Threadと同様に閲覧不可Boardの座標はマーカーJSONへ出さない。Board閲覧とThread作成の両方を再判定する。保存後のThread閲覧とResponseはThreadPolicy自身だけで判定し、Board作成条件を追加制限・コピーしない。Field／ThreadIF・ThreadPolicy・Response・送信IDによる重複防止は既存の共通処理を使う。

URLは`/?board=<id>`、Threadまで開く場合は`/?board=<id>&thread=<id>`。Workspaceの起点より右を置換し、Closeで元Paneへ戻る。reloadとhistory復元は同じBoard／Thread導線を使う。遅い応答を閉じたPaneへ適用しない。

API: `POST /boards/new/`、`GET /boards/<id>/pane/`、`POST /boards/<id>/threads/new/`、`GET /boards/<id>/threads/<thread-id>/`。Responseは既存の`POST /threads/<thread-id>/posts/`。緯度±90、経度±180、6桁精度、必須・有限値、Board名・詳細長、無効Policy・未対応条件・Guestのself条件をサーバーで検証する。無効入力ではBoard／Placement／Policyを残さない。

## Pane UI

AccountPageとRoomPageのHeader右側に作成日を表示する。Workspace内Account／Roomも共通Headerに同じ日付を出す。

共通PaneHeaderをPCで32px、座標行を24pxにする。スマホではHeader44px、座標行32pxとしてCloseと座標リンクの操作領域を維持する。既存のページHeaderはAccount／Roomとも42pxのまま。

Roomの座標行は`.room-overview-content`から外し、概要Pane／Room fragmentの直下へ移す。単独RoomPageとWorkspace内Roomの両方でscroll中もstickyになる。全幅／残り幅のPaneHeader・座標行・ThreadPostのborderはPane端から端まで引き、内容は既存gutterを保つ。

NiiMapは保存済み検索条件を復元し、検索結果とMap表示範囲のソートが確定するまで一覧をhiddenにしてloadingを出す。Room→Threadの未sort一覧を一瞬見せない。検索または初期地図読込の失敗はerror／再試行を表示し、古い順序へ戻さない。Fieldソートでも検索結果の順序を初期から適用する。検索実行後は実行したsort条件を保持し、未実行のselect変更で順序を変えない。

## 隔離QA

`config.settings`は`manage.py test`時にSQLiteの`:memory:`へ切り替える。ブラウザーQAはStaticLiveServerTestCaseの一時portを使い、SharedSQLiteStaticFilesHandlerでテストDB接続の競合を抑える。共有Neon／通常8000 serverは操作しない。

直接回帰: `rooms.tests_map_boards`、既存`rooms.tests`／`rooms.tests_account_boards`／`events.test_thread_policy`／関連`events.tests`。ブラウザー: `scripts.map_board_browser_tests`、`scripts.workspace_browser_tests`。指定の`scripts/browser_smoke.py --base-url <isolated-live-server>`も既存LiveServer fixtureから実行する。PC1280×720／mobile390×844の表示を確認する。

生成物は未追跡`.artifacts/browser-smoke/`、`.artifacts/workspace-regression/`、`.artifacts/map-board-ui/`。後者に作成画面、Board Thread／Response、Room sticky、Account作成日を保存する。基盤で初期Roomが2Boardになったため、既存ThreadPolicy fixtureは「掲示板」を明示して取得する。

## 公開前の互換性と順序

今回の変更に追加migrationはない。既存roomsのBoardPlacement／BoardPolicyCondition／eventsのThreadPolicy schemaを使用する。Account共通処理はv0.14の`interfaces/0008_account_application_versions`に依存する。v0.14 docs整合commitとv0.15実装commitを区切り、一度のpush／Vercel本番buildで公開する。

公開・共有interfaces0008・通常server再起動はユーザー承認済み。Vercelの自動migrateを使い、手動適用は重ねない。限定backupとmigration planを公開前に読取確認し、公開後にschema／値／日時／履歴参照を照合する。公開確認後、通常serverをAGENTS.md指定検査・明示restartし、代表HTTP／Guestの読取browser_smokeを実施する。共有DBへテストAccount／投稿／設定を書き込まない。AccountLayout本体、Thread版更新、Snapshotは対象外。


## 2026-10-05 QA結果

- 既存Room／AccountBoard 51件pass（最初の65件run中、ThreadPolicy14件は初期2Boardに未対応fixtureで失敗。そのfixtureを修正し次のrunで全件pass）。
- `rooms.tests_map_boards events.tests events.test_thread_policy`: 44件pass。Policyフラグ省略時の検証を追加した後、MapBoard直接6件もpass。
- 指定browser_smoke CLI: 隔離LiveServerでPC／mobile pass。Workspace回帰: 起点保持／右置換／遅い応答／Close／history／reduced-motion、両viewport pass。
- MapBoardブラウザー: Guest作成時4欄条件追加→Board→Thread→Response→reload→Close、marker選択、作成日、Pane edge border／高さ、Room座標の実scroll sticky、PC／mobile pass。
- 初期sortブラウザー: 応答待ちloading、保存済み更新順が最初から適用、失敗時error／retryから復帰、pass。
- Django check、隔離settingsでmakemigrations check／dry-run、JS構文check、inboxを除外したgit diff whitespace check: pass。追加migrationなし。
- `.artifacts/browser-smoke/desktop-workspace.png`／`mobile-workspace.png`、MapBoard Thread／Room sticky／Account日付画像を目視確認。

隔離QA時点では公開DBでの互換QA、共有interfaces0008、通常server再起動、公開は未実施。その後v0.14／v0.15公開工程が承認された。上記の順で一度pushし、公開と通常serverの読取確認結果を別途報告する。PostgreSQL同時公開／更新の競合検証は未実施。
