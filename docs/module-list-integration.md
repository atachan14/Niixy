# AccountPage Board / Module List統合

> 2026-10-06の未公開後続修正: Board / Peopleのnative切替、People同段tab、Pane余白・Module Header、最終QAと残る仕様差は[AccountPage Paneの切替と表示統一](account-pane-consistency.md)を参照。以下は先行工程の記録として保持する。

2026-10-06の最新ユーザー訂正を実装。基準はlocal `8ae011cbf6a185f56fda315e805983af3ab7cc15`（Spot mobile幅修正を保全）。公開版・remoteの基準は`f0ec1d8864da13856c76c400be53b0786bcbfeed`。Version番号は追加していない。

## 最新の配置

- AccountPageの独立BoardList / InterfaceListボタンを撤去。List、参照、共有URLは保持。
- Board内は自作 → fav → bad → 作成順の各List → 未分類。RoomのBoard UIは変更しない。List管理はTab行の外から既存管理APIを開く。
- AccountPage Moduleの1段目Element / Interface / Layoutと2段目subtypeは維持。3段目は自作 → fav → bad → 作成順の各List。固定検索・保存済み枠を置き換える。
- List Tabは一覧を表示し、選択した1・2段目と一致する公開定義に絞る。「Listの詳細・管理」で同じ絞り込みの既存Paneを開く。List管理入口で追加・改名・削除・参照解除・URL共有を行える。
- People / AccountListは変更しない。MyPageの既存定義編集・Appliedの適用データはこの公開AccountPage整理から独立。

## 対応する実体

|分類|既存モデル|今回の参照・評価|
|---|---|---|
|Element / Field|FieldDefinition + FieldVersion|対応|
|Element / ComputedField・Action|モデルなし、未実装Tabのみ|枠を維持|
|Interface|Interface + InterfaceVersion（account / room / thread / thread_post）|全4kindをURL・List・評価で対応|
|Layout / Account|AccountLayout + AccountLayoutVersion|対応|
|Layout / ThreadPost・Room|モデルなし、未実装Tabのみ|枠を維持|

既存AccountPageのInterface subtype行にはAccountIF / ThreadIF / ResponseIFがあり、RoomIFボタンはない。1・2段目維持の指定に従いRoomIFボタンを新設していない。RoomIFモデル・保存済み参照は保持し、公開正規URLと評価APIで扱える。

## 永続構造と安全な適用

InterfaceListはAccount owner所有であり、AppliedやRoom配置ではない。既存InterfaceList、InterfaceListReference、InterfaceRatingはそのまま保持。同じListへFieldListReference / LayoutListReferenceを追加し、FieldRating / LayoutRatingを追加。複数分類の同居を内部で保ち、表示時に分類を絞る。型の置換、既存データコピーや削除は行わない。

`interfaces/0011_module_references.py`は上記4テーブルのCreateModelのみ。参照はList+target一意、target削除時はSET_NULLの残存行。評価はauthor+target一意、sentimentはfav/badのみ。クリック切替・解除は既存のdesired-state POSTとpending guardを再利用し、紹介文は要求しない。

旧`/interface-lists/<id>/`とInterface参照のIDは保持。Field / AccountLayoutの正規公開URLは`/fields/<id>/`と`/layouts/<id>/`。URL追加は既存ローカルresolverとorigin制限を拡張し、外部fetchは行わない。Listのowner権限は変わらず、typed参照解除は同IDの他種参照を解除しない。

公開対象は正しい自身のcurrent_versionがある定義のみ。Field / Interfaceはactiveも必須。未公開・deleted・不正な別定義version pointer・Draft URLを参照追加、評価、公開詳細から拒否。編集中Draftは公開済みversionと別で、一覧や本文に出さない。Guestは閲覧と公開評価者一覧のみ、操作ボタンdisabled、書込APIも拒否。他人のList管理は拒否。Muteは表示filterで、Listや参照は保持。

Boardは元配置と自由参照を分けて表示する。List参照追加・評価はBoardPlacementを書き換えず、Room所有・BoardPolicy権限を与えない。List削除時の既存配置→未分類処理だけを既存serviceに委ねる。

共有DB適用は未実施。承認後、対象schemaとbackupを確認し、既存`interfaces/0010_content_lists`を含むgraphに従って0011を先に適用し、それから新コードを通常・公開サーバーに切り替える。新コードは追加tableを参照するため、migration未適用DBへ先行切替しない。rollbackはコードを戻して追加tableと新規データを残す。0011の逆適用によるデータ削除は行わない。

## 直接QA

隔離SQLiteを強制assertするrunnerは`C:/Users/user/Documents/Codex/2026-10-06/task-8/run_task.py`。全域反復は行わず、関連直接テスト74件を実行して全通過（51.851秒）。対象は`accounts.tests_module_lists`（6件、うちmigration1件）、既存content_list API・migration、Account Board、AccountPage、旧Tabの直接検証。

新migration前後で、sqlite_masterの既存全table schemaと全行を比較。旧List・Interface参照・ratingを含む全行が保持され、追加4tableだけが空で増えることを確認。旧段階からList基盤までの移行テストも追加tableに合わせて確認。6種（Field、AccountLayout、Interface 4kind）の評価排他・解除・author偽装・DB一意/check制約、複数分類の同List追加・重複・typed解除、owner/Guest/CSRF、正規URL、公開版認可、分類絞込、GET非書込を直接検証。

`scripts/module_list_browser_tests.py`はEdge headless PC1280×900 / mobile390×844（touch / is_mobile）の1件2 subcase、全通過（23.996秒）。3段Tabの分類絞込・未実装枠、Field/Layout fav/bad切替解除、Picker、旧List URL/reload、List追加改名削除、後続PaneとClose、元List DOMと未送信URL入力保持、Board Tab更新とBoard作成入力DOM保持、Guest readonlyを確認。console/page errorは0。

標準`scripts/browser_smoke.py`を`WorkspaceBrowserTests.test_browser_smoke_cli`経由で同じ隔離LiveServerに実行、通過。通常8000の起動/停止/restart/GETは行っていない。

画像は`.artifacts/module-lists/`のPC/mobile three-tabs / saved-list / board-tabsと`.artifacts/browser-smoke/`に保存し、gitignoreで保全する。AccountPage起点修正・修正前再現・遅延応答と履歴のQAは[account-workspace-origin.md](account-workspace-origin.md)に記録。最終結果と目視QAは以下に追記する。

初回Browser runはPlaywright中のfixture復元にDjango同期clientを使ってSynchronousOnlyOperationになり、その影響で次viewportの名前期待値も失敗。fixture復元を認証済みHTTPへ変更し再実行で通過。Guest API直接検証の初回はdisabledの既存formまで非存在としてassertしたため失敗し、readonly/書込拒否の実際の仕様へ修正した。これらを隠さず最終結果と区別する。

root README、docs/memo/inbox.md、secret、既存user changes、Spot commitを保全。共有Neon書込、push、public反映は未実施。通常server pair `38704 → 23636`は未操作。Python/template変更のため将来の通常反映にはAGENTSの明示restartが必要。asset cache markerは今回変更せず、ブラウザcacheをbypassして検証する。


## 最終QA結果

関連API / migration / AccountPage直接テスト74件に加え、関連browserテスト6件の各最終実行が通過した。合計80件の異なるテスト。browserはすべて隔離SQLiteのStaticLiveServerで実行し、Edge headless、PC / mobileの両subcaseを使用する。

|browser対象|最終結果|
|---|---|
|AccountOriginBrowserTests 2件|2026-10-06最終再実行で成功|
|ModuleListBrowserTests 1件|成功。3段Tab・保存済List・入力保持・公開評価・Guest|
|AccountBoardBrowserTests workflow 1件|成功。既存Board管理・元配置・自由参照・List入口|
|AccountListTabBrowserTests 1件|成功。People既存Tab・入力保持・nested / 遅延応答|
|WorkspaceBrowserTests.test_browser_smoke_cli 1件|最終再実行で成功|

最終再実行はAccountOrigin 2件 + smoke 1件、`Ran 3 tests in 90.393s / OK`。smokeの`.artifacts/browser-smoke/run.log`はPC / mobileともwarnings=[]、browser_errors=[]。変更4 JavaScriptの`node --check`、Django system check、`makemigrations --check --dry-run`も成功し、migration追加漏れなし。重複実行は80件に加算していない。

最終画像を目視確認した。ModuleのPC / mobile three-tabs・saved-list・board-tabs、Account起点のPC / mobile Board・People、標準smokeのdesktop-workspace / mobile-workspace / desktop / mobileはいずれも描画が成立する。保存済ListのURL入力とBoard作成入力は残り、選択されたTabが表示範囲に入る。smokeの最終desktop / mobile画像は現行script終端のstandalone Room Thread画面であり、AccountPageはaccount-origin画像で確認した。画像は全てignored artifactとして保持し、commit対象外。

Account起点修正の途中検証で、履歴Backの期待（Thread一覧）と初期stage属性の未記入、遅延fixtureのURL取得先を修正した。その後2件ともPC / mobileで成功した。修正前の旧conversation残留の再現・修正内容は[account-workspace-origin.md](account-workspace-origin.md)を参照。
