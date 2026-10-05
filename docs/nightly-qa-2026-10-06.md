# Niixy 夜間広域QA — 2026-10-06 JST

対象: local `436aa0afb4cec509a7c2d2c0b6dd871518ca5063`。公開基準は v0.16 / `80a39cf`。実行日は2026-10-05 UTC（翌6日JST）。Versionは変更しない。

**未公開Review / Mute / AccountList / BoardList / InterfaceList / fav・badの今回の接続回帰は成功。広域ブラウザsuiteには、公開済みv0.15由来のGuest条件候補に関する1テストの不一致が残る。全件greenとは報告しない。** 製品コード・migration・asset markerは変更せず、接続回帰4件とこの結果文書を追加した。

## 実行境界と保全

- [AGENTS](../AGENTS.md)、[開発引き継ぎ](handoff.md)、[Policy詳細](codex-handoff/README.md)、[Review](account-review.md)、[Mute](account-mute.md)、[AccountList](account-lists.md)、[Board/InterfaceList](board-interface-lists.md)、[Layout](account-layout.md)、[版更新](interface-version-foundation.md)、[NiiMap/Panes](niimap-boards-and-pane-ui.md)と関係する既存テスト・コードを照合した。
- 実行入口で `DATABASE_URL=sqlite:///:memory:` を指定し、`sys.argv`に`test`を設定してからsettingsを読み、ENGINEがSQLite / NAMEが`:memory:`であることをassertした。通常の`.env`がNeonを設定していてもこのQAのDBには選ばれない。ブラウザは空きポートの`StaticLiveServerTestCase`とローカルEdge headlessのみ。
- 通常server、8000、共有DB、公開サイトへの操作・GET・migration・pushは行っていない。拒否済みの`Get-CimInstance`や別経路のprocess調査は実施しない。通常serverの現在の状態は未確認のまま。通常serverを起動/停止/restartする必要もない。
- 開始時のdirtyはユーザー専用inboxのみ。内容の読取・編集・stageは行わず、root README・秘密・private backup・ユーザー差分も保全した。検索・読取は指定したコード/テスト/許可docsに限定した。
- 前回QA生成物は許可task workspaceの`nightly-qa/prior-artifacts/`へ複製してから、今回の生成先を利用した。private/public release directoriesは対象外。今回の画像・ログはgitignore済み`.artifacts/`に保持し、commit対象にしない。
- 既存venvの開発用依存とローカルEdgeを再利用した。アプリ実装キュー完了後の承認済み広域QAとして、以前の直接151件+Browser4を同じ組合せで繰り返さず、全Djangoを一度実行して接続・保留領域を追加確認した。

## 実測結果

| 実行 | 結果 | 対象 / 証拠 |
| --- | --- | --- |
| `test accounts events interfaces rooms --noinput` | **292件成功**、214.184秒 | 4app全域、Review/Mute/Lists/評価/URL/CSRF/Policy/Field/IF/Applied/Layout/既存migration。`django-suite.log` |
| 既存代表ブラウザ8module | **16件中15件成功、1件失敗（PC/mobileの2subtest）**、278.214秒 | Workspace、ThreadPolicy、Applied、Layout、Interface編集/公開、Module選択、NiiMap Board、Board作成。`browser-broad.log` |
| `test scripts.nightly_qa_tests --noinput` | **追加4件成功**（直接2 + ブラウザ2）、28.623秒 | 今回の接続回帰。`nightly-integration.log` |
| Policy後続の診断run | **1件成功**、24.216秒 | 下記のGuest候補数assertだけを実行時に回避。元suiteの成功扱いには加算しない。`policy-diagnostic.log` |
| 同じ隔離LiveServerへの既存`browser_smoke.py` CLI | PC/mobile各**17check、warning 0、browser error 0** | Workspace suite内で実行。`.artifacts/browser-smoke/run.log` |
| Django check / makemigrations check dry-run | 問題0 / `No changes detected` | SQLite memoryをassertして実行。`checks.log` |

既存ブラウザmoduleは`workspace_browser_tests`、`thread_policy_browser_tests`、`account_applied_browser_tests`、`account_layout_browser_tests`、`interface_browser_tests`、`module_selector_browser_tests`、`map_board_browser_tests`、`board_creation_browser_tests`。いずれも`scripts.`配下。成功済みmoduleの広域反復は行っていない。

今回追加した[接続テスト](../scripts/nightly_qa_tests.py)で確認したこと:

1. AccountList削除がAccount本体、別AccountList参照、Review、Mute、BoardPlacement、Board/Interface参照、fav/bad行を変更しないこと。削除前後の対象全行を比較した。
2. Board参照を持つList ownerにも元Boardの編集・閲覧権限が付与されないこと。閲覧不可本文/評価UIは露出せず、編集/評価POSTを拒否すること。Muteは3種類のListの表示filterだけで、参照行・配置・Reviewを消さず、直接公開IF/Accountへのアクセス認可を変えないこと。Guestの参照は表示でき、owner formやIF Draftは返さないこと。
3. 3種類のListから子Account/Board/IFを開き、Closeで同じ親DOMへ復帰すること。別ページからのBack/Forward、再reloadで正しいListとkindを復元し、Guestへ切替えてもowner formやDraftを出さないこと。公開参照不能になったIFもDraft/旧非公開説明を露出せず、正規URLは404になること。
4. 閉じたReviewとListの両draftに対してMute CancelがPOSTを発行しないこと。Mute待機中に遅いGETで届いたList formをdisabledに保ち、失敗時に元の入力と操作を復元すること。遅いReview GETもMute完了まで入力を有効にせず、失敗後に保持本文を表示すること。
5. Review保存中はMuteを送らず、保存済み応答を遅延してからReview PaneをCloseし、新しいIF Paneを開いても、その応答が新しいPaneを閉じないこと。再編集では保存済み本文を読むこと。各ブラウザケースのpage/console errorは0。

全Djangoは既存の新規SQLiteテストDBへmigration graphを適用した。Review（0002→0003）、Mute/Board.creator、AccountList（0004→0005）、Board/InterfaceList（rooms0010/interfaces0009→最新）の保持テストも成功した。既存tableの全行/schema（Collectionは追加nullable token以外）、既存creator unknownのNULL保持、新table空、Layout/Account版基盤の既存migration保持を、用意されたfixtureの範囲で確認した。共有DBの実データを復元・移行した検証ではない。

## 残った失敗と切り分け

`scripts.thread_policy_browser_tests.ThreadPolicyBrowserTests.test_pc_mobile_policy_forms_and_denied_detail`の両viewportで、`check_editor`の61行目が失敗した。Guestの候補を1件と期待するが、実際は`['Guest', 'NiixyAccount']`の2件。HTTP失敗やJS例外ではなく、明示的な候補数assertの不一致。

- [v0.10要件](v0.10/requirements.md)はGuestのDefault候補をGuestのみとし、既定PolicyのGuest OR Accountとは区別する。一般Account条件APIもGuestのみを返す（今回の292件内で成功）。
- [v0.15要件](niimap-boards-and-pane-ui.md)はGuestの**Board**作成でNiixyAccount候補を追加することを明記する。公開済み`28e9de6`で`extraDefaultCodes`が入り、`static/events/map.js:112`はBoardだけでなくThreadのPolicyにも`guest/account`を追加する。
- このselector・Map側条件追加・ThreadPolicy・失敗testは`80a39cf..436aa0a`の未公開変更で変わっていない。今回のReview/Mute/Lists追加に起因する回帰ではない。
- **既存の仕様文書とUI/テスト前提の不一致。製品バグかfixture陳腐化かの最終判断は保留。** Threadの候補をGuestのみへ戻すか、Threadにも拡張した仕様としてtest/docsを更新するかを親工程で確認する。承認済みBoard候補の変更を戻したり、期待件数だけ変えてgreenにする修正はしていない。

後続検証をこのassertで止めないため、許可workspaceに置いた診断runnerがGuest候補**数**のassertだけを一時的に省き、元のPolicyテストを隔離再実行した。他のassertは維持。PC/mobileで4欄、reset、Guest条件選択、拒否Threadの本文/投稿欄/件数/座標行非露出、Header/Closeの画面内表示、6回reload後の復元、console/page error 0を確認した。runner・ログを`.artifacts/nightly-qa/`に残す。元test/製品は未変更で、通常suiteの1件失敗は解消していない。

今回、未公開承認機能の明確な製品バグや環境起因のテストブロッカーは見つからなかった。新規テスト4件は初回実行で成功。通常process確認を省いたことは今回の隔離QAの失敗原因ではない。

## 画像と未実施

`.artifacts/browser-smoke/desktop-workspace.png`、`mobile-workspace.png`、`desktop.png`、`mobile.png`を目視確認した。今回のsmoke末尾画像はstandalone Room Thread状態。さらに`.artifacts/nightly-qa/`の3種類List Guest/History各PC/mobileと保持Review入力、`.artifacts/account-layout/`のdesktop Profileとmobile長文末尾を確認した。Workspace端、Close、mobile幅、入力/参照内容、自然高さの末尾表示に異常は見られなかった。Applied/版更新/条件UIの生成画像も保持する。

未実施・保証しない範囲:

- 共有PostgreSQLの本番並行publish/評価/Review/参照追加、lock/deadlock/同時transaction。ブラウザ用SQLite handlerはrequestを直列化する。今回の遅延は実ブラウザの非同期応答検証であり、PG並行性の代替ではない。
- 共有DBの現在schema/既存全実データ保持/backup/migration、通常server確認・切替、公開Guest GET、push/deploy。
- Edge以外のbrowser、JS無効時の完成表示、本番通信条件と大規模実データ。
- 削除済み参照の最終UX、Mute非表示の管理UI・visible count、ListPolicy、未承認の新UX。既存の暫定表示・保存参照件数は変更しない。
- 最新のReview/AccountList/ContentList等の直接成功Browser4を独立に再実行すること。既存成功記録を残し、今回追加の接続テストと広域suiteで補完した。

## 朝の手元確認

1. この文書と残件を読む。`git log -1 --oneline`と`git status --short`でQA checkpointと残dirtyを確認する。inboxのdiff/内容を開かず、stageしない。
2. 必要な手元再確認は次の隔離接続テストだけで行える。settingsの`test`分岐と各fixtureのSQLite assertを使い、通常serverは不要。UIを見たい場合は生成画像を開く。

   ```powershell
   .\.venv\Scripts\python.exe -B manage.py test scripts.nightly_qa_tests --noinput --verbosity 2
   ```

3. `.artifacts/nightly-qa/`の`desktop/mobile-*-history-guest.png`と`desktop/mobile-late-drafts-retained.png`、browser-smokeのWorkspace画像を確認する。List owner操作の実データ確認を通常serverへ持ち込まない。
4. Policy残件を再現する場合は次を実行する。現状の元testは候補数でPC/mobile両方失敗する見込み。診断runnerの成功をこの元testの成功に置き換えない。

   ```powershell
   .\.venv\Scripts\python.exe -B manage.py test scripts.thread_policy_browser_tests --noinput --verbosity 2
   ```

広域suiteを再度必要とする変更が出た時だけ、4app全Djangoと下記8moduleを実行する。`manage.py shell`や通常`migrate`でfixtureを作らない。

```powershell
.\.venv\Scripts\python.exe -B manage.py test accounts events interfaces rooms --noinput
.\.venv\Scripts\python.exe -B manage.py test scripts.workspace_browser_tests scripts.thread_policy_browser_tests scripts.account_applied_browser_tests scripts.account_layout_browser_tests scripts.interface_browser_tests scripts.module_selector_browser_tests scripts.map_board_browser_tests scripts.board_creation_browser_tests --noinput
```

## 未公開commitと必要migration

公開基準`80a39cf`以後のfeature checkpointは以下。今回のQA commitはこの上に通常のローカルcommitとして追加し、SHAは完了報告と`git log`で確認する。

| Commit | 内容 |
| --- | --- |
| `b7181b3` | Account Review、作者本人CRUD、共有Pane |
| `f2821da` | 公開Mute / Muter、閲覧者表示filter、Board.creator |
| `5030762` | Mute reload前の未保存Review保護 |
| `829f8b0` | AccountList、Account参照Picker |
| `436aa0a` | BoardList / InterfaceList参照、公開fav / bad |

共有環境へ未適用と引き継がれたmigration（今回共有状態を再照会していない）:

| App | Migration |
| --- | --- |
| accounts | `0003_accountreview` |
| accounts | `0004_accountmute` |
| accounts | `0005_accountlist_accountlistreference_and_more` |
| rooms | `0010_board_creator` |
| rooms | `0011_content_lists` |
| interfaces | `0010_content_lists` |

既存の`interfaces0009_account_layout`等を前提とし、公開工程でDjango graphに従って適用する。新templateは追加tableを読むため、未適用のまま新コードを通常/公開serverへ切り替えない。公開scope・Version・backup・migration担当と適用状況確認・AGENTSどおりの通常server切替・公開Guest確認は親工程に残す。データ作成後の逆migrationを自動実行せず、rollbackは旧コードへ戻して追加データを保持する既存方針を使う。

本工程のcommit対象はこの文書と`scripts/nightly_qa_tests.py`のみ。終了時dirtyとしてinboxだけが残ることを確認する。
