# BoardList・InterfaceList参照とfav / bad

Status: 公開済み（最新公開基準 `e17e00e188e6863914a0863dc33c67f19cf85e6f`、親工程からの引き継ぎ）。新しいVersion番号は未割当。以下の実装開始時の基準・公開計画・隔離QAの「未実施」は当時の記録として保持する。accounts0003～0005、rooms0010～0011、interfaces0010は共有環境に適用済み。[最新状態と検証境界](qa-status-2026-10-06.md)を参照する。

Version未割当。2026-10-05承認済みのAccountList後続工程。基準local HEAD `829f8b056fd77d581a99abd200f96b42e78242fe`。公開はv0.16 / `80a39cf`。この工程は実装、隔離SQLite QA、ローカルcheckpointだけで、push・共有Neon migration・通常runserverの起動停止/restartは行わない。

## 要件と保存

既存`rooms.Collection`は利用者向けにBoardListと呼ぶ。モデル・既存URL・DOM操作属性は保持する。配置先としての役割に自由な参照を追加し、配置は従来の`BoardPlacement`だけを正とする。新`BoardListReference(board_list, target, created_at)`は本人AccountのBoardListだけに追加できる。RoomのListを追加先に使わず、別Room / Account / NiiMapのBoardを参照しても移動・コピー・所有権変更しない。参照解除も元Board・Thread・Responseを削除しない。既存List削除時の配置Boardを未分類へ移す振る舞いは保持し、確認文で説明する。

`InterfaceList(owner, name, submission_id, created_at, updated_at)`と`InterfaceListReference(interface_list, target, created_at)`は公開Interface定義の自由な参照。Interfaceの種別（AccountIF / RoomIF / ThreadIF / ResponseIF）と公開定義の現在versionを表示し、Accountへの適用・適用版固定・値入力は行わない。Draft・未公開・deleted定義を新規追加できない。参照後の公開更新では同一定義の最新公開版を示し、Draft内容は返さない。

ListはGuestを含め誰でも閲覧でき、作成・改名・削除・参照追加/解除は所有Accountだけ。POSTのowner / author / target IDを信頼せず、本人はrequest.user、対象はURLで確定する。POST / CSRFを要求する。List名は前後空白除去後、BoardList 1〜120文字（既存Collectionの上限維持）、InterfaceList 1〜80文字。未分類BoardListの改名/削除は禁止を維持する。

List作成は所有Account + submission UUID、参照はList + targetでDB unique。重複送信・再試行でList/参照を増やさず、既存Listを暗黙改名しない。既存Collectionにはnullable `list_submission_id`を追加し、旧writerもtoken無しで作成できる。既存List・Board・Interfaceの値や配置をbackfill / 改名しない。List内List、他種類混在、手動sort、ListPolicyは今回対象外。

## 公開評価

Board / 公開Interfaceに `fav｜bad｜追加` を表示する。fav / badは公開・排他的で紹介文を要求しない。選択済みボタンのクリックで解除、もう一方のクリックで切替。`BoardRating` / `InterfaceRating`はauthor + target uniqueとfav / bad DB checkを持つ。APIはdesired sentiment（fav / bad / 空）を保存し、再送で反転しない。target行をtransaction内でlockして未作成rating同士も直列化する。公開件数と評価Account一覧を閲覧できる。AccountのLove / Hateと紹介文Reviewは変更しない。Board閲覧不可の場合は評価/Picker操作を返さず、APIも拒否する。

## URLとPolicy

AccountListの`accounts/internal_urls.py`を再利用する。新正規URLは `/boards/<id>/`、`/interfaces/<id>/`、`/board-lists/<id>/`、`/interface-lists/<id>/`。Picker内で対象URLを共有し、List詳細のURL入力で参照追加できる。ブラウザに貼ると直接表示する。既存Account / Room / NiiMapのURLは保持する。Board用fragmentは `/boards/<id>/reference/` とし、既存Map専用 `/boards/<id>/pane/` のscopeを広げない。

現在request originと明示した`NIIXY_REFERENCE_ORIGINS`だけを許可し、scheme / host / port、正規path、存在するIDと型をローカル解析する。credentials、外部origin、query/fragment、encoded path、IDの非正規表記、別種類、List型、管理/Draft URLを拒否する。外部HTTP fetch・DNS照会・redirect追跡は行わない。

参照ListのownerをBoard管理者として扱わない。元配置先のAccount / RoomOwnerと既存BoardPolicyで判定し、閲覧不可時は従来の題名/更新日時・不足条件だけを返し、本文・Policy全体・Thread一覧・Thread作成UIを返さない。参照経由のThreadも元Board所属と既存ThreadPolicyで判定する。現在閲覧不可のBoardを新規追加する操作は保守的に拒否する。後からPolicyが変わった既存参照は残し、クリック可能な不可Summaryを示す。

## Workspaceと残す判断

既存Workspace Trailの起点以降置換、右Pane、Close、保持DOM/scroll、AbortControllerと接続確認による遅いGET無視を使う。新Listは既存AccountListの入力/draft/submission UUID・pending guard・Close中POST継続処理を再利用する。共通SummaryのList IDはkindも照合して、AccountList / BoardList / InterfaceListの同じ数値IDを誤更新しない。

Boardの通常参照Paneも既存Boardの操作初期化を再利用し、公開正規URLからThread作成/閲覧できる。Interface定義参照は適用Paneとは別に表示する。

削除されたtargetはnullable / SET_NULLの参照行を残し、機密snapshotを保存しない。Interfaceの公開不可状態も名前やDraftを返さないplaceholderとする。この削除表示の最終UX、復元時の扱い、Mute対象の管理UIは未決として後続へ残す。Muteは表示filterだけで、閲覧者本人のMute対象creatorを参照のpagination前に除外する。保存済み参照数はMute非表示・placeholderを含む総数のまま。ListPolicy・visible countへの変更をこの工程で確定しない。

## Migrationと共有反映計画

新migrationは `rooms/0011_content_lists.py` と `interfaces/0010_content_lists.py`。前提はrooms0010 / interfaces0009とAccountList工程まで。共有未適用のaccounts0003 Review、0004 Mute、0005 AccountList、rooms0010 creatorも必要。公開工程で適用済みmigrationをread-only確認し、対象schema/データのprivate backupと公開scope/versionを確定する。Django migration graphに従って必要migrationを適用してから新コードを有効化する。新テンプレートの評価件数queryは新tableを使うので、table追加前に新コードを通常/公開serverへ切り替えない。

公開後はAGENTSに従い検証済み通常runserver pairだけrestartし、asset marker `20261006-content-lists`と代表GET・Guestを確認する。共有DBへの実験書込は行わない。rollbackはコードを先に戻してList/参照/ratingとnullable token列を保存する。新migrationの逆適用によるデータ削除を自動実行しない。

## QA結果

隔離SQLiteだけで、直接151件とBrowser 4件を複数の絞込runで確認した。全域反復は行っていない。

- 新規直接 `accounts.tests_content_lists` 19件、`accounts.tests_content_list_migration` 1件。本人/他人/Guest、POST/CSRF、owner/author/target偽装、Room側追加拒否、List作成再送、参照重複/二重解除、一意制約・評価enum、名前上限、元配置/他List/元コンテンツの保全、未分類保護、List削除の既存配置移動、Policy変更後の不可メタ情報、Draft/未公開/deleted漏出拒否、公開版更新と適用不発生、URL型/不明origin/非正規ID/encoding/管理URL拒否・外部fetch無し、Mute表示filter、公開評価件数/作者、同一配置先の別BoardへのThread取り違え拒否・ThreadPolicyを確認した。
- migration検証はrooms0010 / interfaces0009から新migrationへ。全既存tableの全行が同一、Collection以外のtable schemaが同一、Collectionの追加nullable tokenが既存行でNULL、追加5tableが空であることを確認した。
- 既存直接回帰は `rooms.tests_account_boards` / `rooms.tests_map_boards` 17件、`accounts.tests_lists` 15件、Review 10件、Mute 11件、AccountPage 15件、`rooms.tests` 39件、`interfaces.tests.InterfaceManagementViewTests` 24件。既存Room/Account Boardの管理・配置・PolicyとInterface管理/Draft/公開版表示を確認した。初期runの不可表示文言と古いasset期待値、誤ったbrowserテスト指定を修正し、失敗箇所を絞って再実行した。Roomの`account_conditions.js`期待値は現テンプレートの`20261005-map-board-ui`に合わせ、変更していない`room.js`は`20261004-17`を維持した。
- `scripts.content_list_browser_tests` 2件。Edge headlessでPC 1280px / mobile 390pxの両List、fav→bad→解除、評価通信失敗と再試行、評価二重submit、公開評価Account一覧、Picker/URL共有、既存参照・重複、作成/Close入力保持/通信失敗、参照先子Pane、保持DOMの評価同期、URL追加、改名、参照解除、直接URL/reload、Close中POST完了後の再表示、遅いGET無視、Guest閲覧・owner form非表示、正規BoardからのThread作成/Policy/再読込/Closeを確認した。
- 既存 `scripts.account_list_browser_tests` と `scripts.account_board_browser_tests.AccountBoardBrowserTests.test_account_board_workflow_desktop_and_mobile` 各1件も成功。共通ListのMute Cancel/失敗と入力固定・復元、既存Board作成・Field選択・Thread/Response・再読込・nested Accountを確認した。
- `scripts/browser_smoke.py` の変更していないentry pointを同じ隔離LiveServerへ実行。PC/mobileとも各17check、warnings / browser_errorsは0。新機能Browserでもconsole/page errorは0。
- Django check、makemigrations --check --dry-run、変更JS 3本のNode構文検査、許可されたコード/docs範囲のgit diff --checkが成功。development-only依存はAGENTSのpipコマンドで既存venvに導入済みであることを確認した。

画像は `.artifacts/content-lists/` と `.artifacts/browser-smoke/` にgitignore内で保存。PC/mobileのBoard・Interface参照Pane/List・Guestと、smokeのdesktop-workspace / mobile-workspace / desktop / mobile画像を目視確認した。公開Interfaceの余白、Guest無効表示、評価の選択色を整えて代表Browserを再実行した。

通常serverの保全確認として行った`Get-CimInstance Win32_Process`のread-only列挙はOSの「アクセス拒否」で失敗した。指示に従いその操作を停止し、同じ操作・別経路によるプロセス調査を再試行していない。親工程から、通常serverは対象外として確認不能を記録し、独立したローカルQA/docs/checkpointを続ける指示を受けて再開した。通常serverの起動・停止・restartは行っておらず、現在のpair/PID/8000 listenerの状態は未確認である。

共有PostgreSQLの実並行競合、公開DB既存行保全、共有migration、公開Guest GET、通常server確認/切替は未検証。全域反復、削除参照とMute件数の最終UXは後続へ残す。機能の直接QAに未解決の失敗はない。ローカルcheckpointはこの結果記録を含むcommitとし、完成SHAは完了応答で報告する。

保護対象 `docs/memo/inbox.md` は読取・編集・stageしない。root README、秘密、backup、既存userchanges、生成artifactsはcommit対象外。通常serverと共有DBを保全する。

## AccountPage内のタブ配置訂正

List専用一覧へ置換した当時の記述を訂正する。固定タブを残してユーザーListを保存相当の位置へ接続する。[確認した旧UIと修正要件](account-list-tabs.md)を参照する。Listモデル・参照・認可は保持する。
