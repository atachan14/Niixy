# AccountIF適用エラーとSummary Color

2026-10-06。基準local checkpointは`dfcec6681f0fcd14aa7943401381afea975e3f28`。ユーザーのAccountIF適用エラーとInterface周辺のColor欠落を優先し、Thread / Response fav・bad・ユーザーListの追加機能を混ぜず修正した。

## 公開済み状態と作業境界

前releaseの公開SHAは`d5b53a8073e3e6b992b43fa946fe21df27acc169`。Vercelの同SHA deploymentはsuccessで、Room Review / Mute `9011a00`、`rooms.0012_room_review_mute`適用済み。記録は`.artifacts/private-release-d5b53a8/release-report.md`。

通常serverは`30348 → 5452`（venv launcher → base Python child）、127.0.0.1:8000 listenerは5452の1つ。起動時刻UTCはそれぞれ`2026-10-06T06:15:49.806733Z` / `2026-10-06T06:15:49.883879Z`。今回の開始時にExecutablePath、CommandLine、parent、start、全runserver数とlistenerを再照合し、進行中QAなしを確認した。

今回の書込みはlocalコード・docs・tests・隔離QAだけ。共有Neonの接続・テスト適用・migration、通常serverのGET / restart、push / 公開反映は行わない。READMEとdocs/memo/inbox.mdは開始時hashを保持し、stageしない。新migrationはない。

## JSONエラーの根本原因

`change_application`はFieldDefinitionを行lockし、nullableな`current_version`を`select_related`でLEFT JOINしていた。対象を限定しない`FOR UPDATE`がLEFT JOIN側の公開版もlockしようとするため、PostgreSQLは`NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join`を返す。Fieldを持つAccountIF、または既存適用Fieldがある変更経路で発生する。SQLiteの行lock省略では再現しない。[Djangoの行lockとnullable relationの仕様](https://docs.djangoproject.com/en/6.1/ref/models/querysets/#select-for-update)も確認した。

PGlite 0.5.8と公式socket adapter 0.2.11をtask workspaceだけに取得し、localhostの空きport50668にin-memory PostgreSQLを用意した。Django設定ロード前にそのDSNへ固定し、vendor / host / portをassert。全migrationと架空Account / Field / AccountIFをこの隔離DBに作り、実Django APIをCSRF有効のClientで実行した。productionのDEBUG=False形式を使い、隔離HTTP用のSSL redirectとstatic storageだけQA設定で調整した。

修正前の`/accounts/pg_qa_owner/applied/change/`は正しい本人session・CSRFでも **500 / text/html / redirectなし**。本文は`<!doctype html>`のServer Error、保存はrollbackされ適用とValueは0件。この実本文をV8でJSON.parseすると、ユーザーの報告どおり`Unexpected token '<', "\n<!doctype "... is not valid JSON`になった。

修正は`select_for_update(of=('self',))`でlock対象をFieldDefinition本体へ限定する。公開版は既存のimmutableモデルであり、publisherと同じdefinition → interface → accountのlock順を保つ。lockやtransactionを外したり例外を成功扱いしたりしない。

| 同じ隔離PostgreSQLでの修正後実API | status / Content-Type / 結果 |
| --- | --- |
| 本人・正規CSRFのAccountIF適用 | 200 / application/json、適用と共有Value各1件 |
| 同じ適用を再送 | 400 / application/json、各1件を保持 |
| CSRFなし | 403 / application/json、csrf_failed |
| Guest・正規CSRF | 401 / application/json |
| 他者・正規CSRF | 403 / application/json |
| AccountIF更新、共有Field編集、IF取外し、直接Field追加・取外し | 5操作とも200 / application/json、最終取外し後Binding / Valueは0件 |

全応答でredirectなし。`postgres-before.json` / `postgres-after.json` / `postgres-operations.json` / `json-symptom.json`を`.artifacts/account-if-fix/`へ保存した。隔離Node DBプロセスはidentityを照合して停止し、50668 listener消失を確認した。通常serverを停止していない。

## 失効・誤応答の扱い

別のHTML応答経路として、Django標準CSRF拒否がHTML 403を返していた。Applied変更APIだけはJSONの`csrf_failed`へ接続し、CSRF検証自体は保持する。通常のフォームのCSRF拒否は既存HTMLのまま。消えたAccountの保存先はJSON 404になる。

AppliedとLayout RequireのJSON clientは共通`NiixyUI.readJsonResponse`でcontent-type / redirectを確認する。HTMLやJSON破損をparser例外のまま表示せず、入力保持と再試行・ログイン確認を案内する。予期しないサーバーエラーは成功扱いにしない。この処理に加え、上記のPostgreSQL 500の原因を修正した。

catalog取得前にsessionが失効または他者へ変わった場合、公開Applied JSONの値は既存仕様どおり返るが、本人用catalogは返らない。Pickerを開かずログイン状態の確認を案内する。元の入力・Paneを保ち、本人sessionへ戻すと正規のPicker / 保存が通る。

## Colorの欠落経路

既存色契約は`data-summary-kind`から共通styles.cssのField / Interface / Layout色を使う。同じ色の新定義やserializerの色値を追加しない。

| 確認した欠落 | 最小修正 |
| --- | --- |
| MyPage Applied / Thread作成 / Board Thread作成で共有するField / Interface Picker | `rooms/forms.js`のsummaryItemへkind属性 |
| 公開AccountPage・MyPageのApplied Field / AccountIF Summary | templateへfield / interface属性 |
| AccountLayoutのRequire Field / AccountIF Summary | require種別からfield / interface属性 |

定義管理・Field検索 / 追加、公開Moduleの自作 / fav / bad / 実List、List詳細の参照、MapのField / Interface Picker、Account条件候補は既存属性を保持していた。保存枠の未実装empty表示や追加先List名ボタンには、今回のコンテンツSummary欠落を認めていない。

ユーザーの「どこかで見た」画面そのものは特定できていないが、上記3経路で欠落をコードと実描画により確認した。PC / mobileでcomputed colorが既存色tokenに一致し、背景がtransparentでないことを検証した。本人 / 他者 / Guestの公開Applied・Moduleと、List参照・Requireも確認した。

## QA

隔離SQLite runnerは`C:/Users/user/Documents/Codex/2026-10-06/task-10/run_account_qa.py`。共有DBへ接続せず、StaticLiveServerの空きportとローカルEdge headlessを使う。

関連 **68件の異なるテストは各最終実行で成功**。一度の68件runが全成功したという意味ではない。初回68件は64件成功、cache marker assert1件とbrowser3件が失敗。前checkpointのLayout DOM selector、今回のbrowser fixture内の同期ORMを訂正し、4件の集中再実行が成功した。新規失効testをcatalog取得前の他者 / Guestへ拡張した最終再実行も成功。同じテストの再実行を件数へ足していない。

| 確認 | 結果 |
| --- | --- |
| AccountIF APIの認可・CSRF・不正入力・重複・rollback、PG lock SQL compile | 新規直接3件成功。PG compilerは接続せず実APIからのqueryを検証 |
| Applied・最新版更新 / pending / frozen / preview・Layout / renderer | 既存直接回帰成功 |
| Applied追加 / 編集 / 解除、merge確認と遅い応答、Layout Require適用、共有作成Picker | PC / mobileの既存browser回帰成功 |
| Color実描画 | PC / mobile、本人 / 他者 / Guest、26記録。`colors.json` |
| 認証 / CSRF失効・HTML 500・302からHTMLへの誤redirect・本人への復帰・連打 | PC / mobile、入力保持、余分な適用 / Valueなし、最後の連打はPOST1回。`errors-and-retry.json` |
| browser_smoke.py CLI | 隔離LiveServerでPC / mobile各17 checks、warning 0 / browser error 0 |
| 構文・schema | 変更Python AST、変更JS / inline UI node --check、Django check、makemigrations --check --dry-run成功 |

負のHTTPテストでは意図して401 / 403 / 500を発生させ、Chromeが出す対応するresource errorを証拠に記録した。page errorは0、予期しないconsole errorは0。正常操作とsmokeはconsole error 0。失敗応答を隠して正常と数えていない。

smokeのdesktop-workspace / mobile-workspace / desktop / mobileの4画像と、新しいApplied owner・Layout RequireのPC / mobile画像4枚を目視確認した。SummaryのField黄 / Interface緑と罫線が既存paletteで表示される。smokeの最終2画像はstandalone Room Thread状態。

生成artifact・失敗を含むQAログはignored / task workspaceに保持する。Gitへ追加するのは修正・tests・docsだけ。変更した3 JS assetのcache markerは`20261006-account-if-fix`。通常反映にはPython / template変更としてAGENTSどおり明示restartが必要で、次の反映承認まで保留する。

## 保全した後続作業

Thread / Response fav・bad・ユーザーListは既存モデル・docs・Board / Module共通処理を調査した段階で未編集。独立bookmarkモデルを作らず、同じ排他的公開評価・既存Picker / CRUD / 正規URL・Policy / Mute契約へ拡張する方針を確認済み。今回の差分・checkpointに追加機能は含めない。