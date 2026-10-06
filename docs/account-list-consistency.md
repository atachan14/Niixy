# AccountPage一覧・分類tabの整合

> 一覧整合のlocal checkpointは`dfcec66`。続いて優先した[AccountIF適用エラーとSummary Color](account-if-implementation-fix.md)は別checkpoint。Thread / Response評価・ユーザーListは[後続checkpointで実装](conversation-feedback.md)。以下は一覧整合checkpoint時点の記録。

2026-10-06。公開済み `d5b53a8073e3e6b992b43fa946fe21df27acc169`を基準とする後続local修正。Room Review / Mute `9011a00`とrooms0012は公開済み。通常server pair `30348 → 5452`、8000 listenerは5452の1つ。この後続工程では通常serverのrestart / GET、共有Neonの書込み、push / public反映を行わない。

## 今回の変更

- 公開ModuleのInterface subtypeにRoomIFを追加。既存room kindの公開済みInterfaceと評価・List参照を使い、モデルやAPIは増やさない。ComputedField / Action / ThreadPost / Room Layoutの将来tabは保持する。
- 分類tabは共通の`NiixyWorkspaceTrail.selectCategory`を通す。起点以降の子Paneを閉じ、nativeの詳細stage・共有Pane・保留requestを整理し、起点をalignして選択URLを保存する。分類は既存Board / People / Moduleに合わせてreplaceState。機能ボタン・詳細の既存history経路は保持する。
- Thread / Responseは`tab`、Roomは`room_tab`、Appliedは`tab`、Peopleは`people_tab`、Boardは`tab / collection`、Moduleは`type / subtype / collection`を使う。既存の名前を維持し、再読込・Back / Forward・Closeで選択が落ちないようにした。hydrateはclickを発火しないので、一覧の保存後refreshが開いている子Paneを勝手に閉じない。
- Summary一覧は共通`paginate_summary_list`の20件。Thread / Responseの既存10件は維持する。新しい独自page sizeやList名tabの上限は作らない。
- PeopleのLove / Hateと各Listの参照、Moduleの各分類・subtype内、自作 / fav / bad Board、各BoardListの自由参照と配置、公開AppliedのField / AccountIF、Account配下BoardのThread一覧をページ分割する。List名tabは全件の作成順・同段配置を保つ。
- Boardの自由参照`page`、配置`boards_page`、Board内Thread`thread_page`を分ける。互いのpageと選択分類をURLに保持し、Board数は表示中件数でなく総数を示す。pagination / refreshではSummary領域だけを更新し、Board作成・編集の未送信入力とaccordionのDOMを保持する。
- MyPageのApplied編集用payload・既存List作成API / Picker・Review / Mute・List / 配置 / 評価データは保持する。

## nested paginationの再現と修正

旧`d5b53a8`のworkspace_trail.jsをbrowser routeで読み込み、隔離fixtureで21 Threadを用意した。旧query-only `?created_page=2`リンクはdocumentのentity captureにAccountリンクとして認識され、paginationのbubble handlerより先に別のAccount Paneを追加した。PC / mobileとも再現した。懸念されていた「partialのfetch先だけ」の差に加え、captureでの競合が原因だった。

Thread / Responseのリンクを明示的な専用pane URLにし、entity captureからpagination属性を除外した。nestedのhandlerも元の一覧取得先にqueryを付け、canonical AccountPage URLの保存とpartialの取得先を分ける。修正後はquery-onlyを人工的に残しても余計なAccount Paneを開かず、元の一覧のpage 2を取得する。同じbefore / after 4組を`.artifacts/account-list-consistency/nested-pagination-before-after.json`に記録する。

## QAと境界

実行runnerは `C:/Users/user/Documents/Codex/2026-10-06/task-10/run_account_qa.py`。設定ロード前にDATABASE_URLをin-memory SQLiteへ固定し、ENGINEとNAMEをassertする。browserは空きportのStaticLiveServerとローカルEdge headlessを使う。AGENTSのbrowser_smoke.py CLIも同じ隔離LiveServerで実行する。

新規集中QAでは21件の参照・Module・Applied・Board Thread、22件の配置、25個のPeople / Module Listを使う。GET前後の関連モデル全行比較、Muteの表示filterとデータ保持、page 1 / 2、invalid page、公開と編集payloadの区別を確認する。本人 / 他者 / Guest × PC / mobile × native / nested、分類変更で子Paneが閉じること、選択のreload / Back / Forward、入力DOM保持、deep Board URLとClose、実HTTPの本文deliveryを保留したpaginationの破棄を確認する。

初回browser QAではApplied初期URLのtab / pageを渡していない経路を検出し訂正した。nested再現の初期assertは「AccountPage全体挿入」を想定していたが、実際はcaptureによる別Account Pane追加だったため、実症状を確認してassertを訂正した。後続fixture追加ではRoomReviewの`room`引数を`target`へ訂正した。旧AccountBoard testの「Board List管理」assertは前checkpointの撤去済みUIを指していたため、残すべき「Listの詳細・管理」へ更新した。

関連 **61件の異なるテストについて、各最終実行の成功を確認**した。一度の61件runが全成功したという意味ではない。既存回帰52件（module API・AccountPage・AccountBoard・People・Applied、既存browser操作・smoke）は最終core変更後のrunで成功。新規9件は追加fixture / locator訂正後の集中runで8件成功、Room / Responseを含むmatrixを最後に1件成功（143.027秒）した。遅延pageのassertをDOM全体・console監視まで強めた再runも成功（20.166秒）。同じテストの再実行を件数へ加算していない。

| 検証 | 最終結果・証拠 |
| --- | --- |
| 本人 / 他者 / Guest × PC / mobile × native / nested | 12組。People / Module / Board / Thread / Response / Room / Appliedの分類・ページ・子Pane・reload、native Back / Forward、owner入力DOM保持。`matrix.json` |
| 保留した実HTTP page本文の解放 | People / Module / Board × PC / mobile × native / nestedの12組。分類変更後、DOM全体・URLを保持し、page / console error 0。`delayed-pages.json` |
| nested query-only pagination | 旧JSの誤ったAccount Pane追加がPC / mobileで再現し、修正後は同じquery-only条件でも元のThread一覧page 2。before / after 4組。`nested-pagination-before-after.json` |
| deep Board URL | PC / mobileで参照page 2・配置page 2・Thread page 2、詳細CloseとBoard Closeの復元に成功。 |
| 既存browser操作 | Moduleの評価・作成Picker・改名・削除・Guest、PeopleのList管理・入力・保留子Paneは成功。 |
| browser_smoke.py CLI | 隔離LiveServerでPC / mobile各17 checks、warning 0 / browser error 0。`.artifacts/browser-smoke/run.log` |
| 構文・schema | 変更PythonのAST、変更JSとinline UI scriptのnode --check、Django check、makemigrations --check --dry-runは成功。新migrationなし。 |

`.artifacts/account-list-consistency/qa-summary.json`に61件の各最終成功logを紐づけた。ログはtask-10の`list-qa-final.log` / `list-focused-final.log` / `list-matrix-final.log` / `list-delayed-verified.log`。fixture訂正前の失敗logも保持している。Roomが複数tabに現れるfixtureではvisibleな分類へlocatorを絞った。また遅延testへ追加したconsole監視の初期化漏れを訂正し再実行した。

RoomIFのPC owner nativeとmobile Guest nested画像、smokeのdesktop-workspace / mobile-workspace / desktop / mobileの4画像を目視確認した。RoomIFのpage 2、4 subtype、全List名tabの横scroll、単一Headerと描画が成立する。smoke最終2画像はstandalone Room Threadの状態。生成物は全てignoredのまま。

変更した5 assetのcache markerは`20261006-account-list-consistency`。共有UI scriptもtemplate変更を含むため、通常反映時の明示restartは必須。

生成物とログはignored artifact / task workspaceに保持し、Gitへ追加しない。

## 次checkpoint・残る判断

Thread / Responseのfav・badと本文下の小さい操作、ユーザーList（bookmarkは旧名）の実装は[後続checkpoint](conversation-feedback.md)へ分けた。この一覧整合checkpointでは、将来用の空tabや独立bookmark機能を変更していない。

List名tabの全件表示は今回の依頼どおり保持し、参照本文のpaginationとは分ける。大量tabの別UIへの置換やlazy loadingは新しい製品判断として採用していない。Room / NiiMap自身のBoard Thread全件表示、MyPageの編集・検索catalogはAccountPage公開一覧の今回の範囲外で変更しない。

新migrationはない。Python / template変更を含むため通常環境への反映にはAGENTSに従う明示restartとcache bypassが必要。次の反映承認まで保留する。root READMEとdocs/memo/inbox.mdの開始時hashと未commit差分を保持し、編集・stageをしない。
