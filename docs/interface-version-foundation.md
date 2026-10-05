# Interface / Field版更新・凍結／復帰基盤

Version: v0.14
Status: Complete (implementation / isolated verification; release approved, migration pending)
Base: `fc94013`（v0.13）。既存inbox差分は保護。v0.12の実績・READMEは変更しない。

## 共通方針と今回の範囲

Interface・Field・Layoutは、既存内容の旧版表示を維持し、新規作成・適用・編集を最新版へ揃える。適用済みFieldの値編集も対象。同一定義の複数版を同一対象へ併用せず、版・依存・影響値の差分と必要な確認を保存前に提示する。Field型変更は同一定義では引き続き禁止し、破壊的な型変換は追加しない。

今回の実装対象はAccountのField／IF更新、凍結／復帰、共有値の確認付き統合、状態表示と隔離回帰。Threadは現在、新規作成時だけ最新Field／IFを解決し、既存IFのVersionと値表示を保持する。適用済みThreadの版／値編集APIはまだないため、Accountだけで共通の編集対応が完了したとは扱わない。Thread編集導入時は同じ最新版・preview契約を実装する。

Layout本体はこのv0.14基盤の対象外で、後続の[AccountLayout初期実装](account-layout.md)で扱う。依存IFが凍結しても適用済みLayout表示を継続し、新規適用／編集には最新版条件を要求する。非表示や標準Layoutへの自動差替えは行わない。投稿時SnapshotはThreadPostの`#1`・Response側に、当時の表示名／表示値と不変FieldVersion／LayoutVersion参照を保持する契約とし、defaultLayoutにも適用する。Snapshotは引き続き別の将来要件。

## 判定表

| 最新IF定義／Accountの状態 | 適用状態 | 表示と操作 |
| --- | --- | --- |
| 最新公開IFが依存Field最新版に未対応 | 凍結 | 既存IF名・構成・適用記録と値を保持。新規IF適用／IF経由値編集不可 |
| 対応IF版公開済み、Accountの必要なField版が古い | 復帰待ち | Field更新またはIF更新のpreview・確認が必要 |
| 対応IF版公開済み、不足Field／追加入力／矛盾／別Value統合あり | 復帰待ち | 本人が必要事項を揃える。初期値があってもFieldを自動追加しない |
| 凍結後、対応IF版と既存最新版Field・現値だけで確認不要に要件を満たす | 有効へ自動復帰 | IF参照を対応版へ接続し直す。Field追加・値変更・別Value統合をしない |
| 通常のIF公開更新で既存適用にFieldの不整合がない | 有効のまま旧版表示 | IF編集時に最新版へ更新・確認する |
| 本人がIFを取り外した | 適用記録なし | 後の公開更新で自動適用しない |

定義全体の互換性は`interface_availability()`、Account適用状態は`application_state()`で分離する。機能／実装済み条件が必要な呼出側には`active_account_interfaces()`を用意し、凍結・復帰待ちを除外する。現在のAccount条件APIはAccountIF／Field条件をまだ評価していない。今回、権限条件や情報公開範囲は追加しない。v0.12と同じくApplied項目は公開する。

## Accountの版と共有値

`AccountFieldBinding.version`をAccount内の一つの適用Field版とする。新規適用／値編集では、影響する共有ValueのField定義を最新版へ揃えて検証し、版の変更をpreviewへ含める。直接Field参照も同じ版へ同期する。公開済みIFの不変Field参照や旧IF版を変更せず、IF表示値は現在のAccount共有Valueを参照する。

凍結・復帰待ちIFの古い制約は共有値更新を妨げない。直接Fieldと他の有効IFの制約は引き続き守る。凍結IFだけから実装されたFieldもFieldタブから単独で編集できる。IF更新で構成から外れたFieldは、Binding／ValueとField一覧・単独編集を保持する。凍結／復帰判定では孤立データを削除しない。明示的な取り外しでは、その取り外しが対象とした参照だけを解除し、他の参照が残るField／値は保持する。

片同義はAccount内共有Valueを使い、既に共有しているValueを同義語削除で自動分割しない。複数の既存Valueを接続する場合は最初に適用されたFieldの値を保持し、変更前後／版／統合を本人が確認してから保存する。他Account／Threadの値は共有しない。

## 保存前確認と再検証

版更新、Field構成差分、制約・同義語差分、共有Value統合と影響値をpreviewへ含める。IF編集の入力欄は最新IF版で構成する。凍結IFはIF編集欄を無効にし、Fieldタブへの更新導線を示す。

確認tokenはAccount、操作payload、対象版、Field最新版、適用IF版・状態・最新公開版、Binding版・共有値・参照状態に結び付け、有効時間は10分。確定時に再解決・再検証し、版／値／依存／参照が変わっていたら再確認または入力修正を求める。別の確認済み編集で版差分がなくなった場合も、古いpreviewでその新しい値を上書きしない。

Field定義→IF定義→Accountの順で行lockを取得し、保存をtransactionで行う。公開処理もField依存をlockして最新版を解決し、凍結／復帰判定を同じtransactionで更新する。初期値や矛盾を解決する任意プログラム・自動変換は追加しない。公開GETは状態を計算するだけで書き込まない。

確認が必要なAPI応答は`200 + needs_confirmation: true`で、保存成功の`ok: true`とは区別する。期待されたpreviewをHTTPエラーとしてブラウザconsoleへ出さない。新JSは旧409確認応答も扱い、旧payloadへのfallbackも維持する。新JSのcache識別子は`20261005-application-versions`。

## Migration 0008と公開互換性

追加列は`AccountFieldBinding.version`（nullable FK、PROTECT）と`AccountInterfaceImplementation.state`（DB側にもactive defaultを保持し、旧writerのINSERTを許容）。data migrationは、各Bindingで最初の残存適用参照のFieldVersionをbackfillする。順序はv0.12の代表選択と同じ適用日時／PK／参照種別。参照がないBindingは定義の現公開版を使い、公開版が存在しない異常データは中断して確認する。

最新IFが未対応なら凍結、対応済みでも既存適用Field版との不整合があれば復帰待ちをbackfillする。既存Value、Value timestamp、公開Version、直接Field・IFの歴史参照は変更しない。移行だけでIF復帰／Field追加／値変換は行わない。

列をnullableのままにするのは、migration後も旧v0.13コードが稼働する公開切替中に旧writerのINSERTを壊さないため。新コードは必ず版を保存し、旧writerがNULL列を残した場合は読取時に最初の残存参照から解決する。公開GETでは補完書込をしない。次の本人編集で対象Bindingに版を保存する。旧コード稼働中は旧版編集ルールのままなので、ルール切替には新コード公開完了と通常開発serverのrestartが必要。

基盤checkpointは`6f68524`。v0.14基盤／v0.15 UI・NiiMap Boardの区切りと公開は承認済み。共有Neonの未適用migrationは0008だけと読取確認し、対象schema／データの限定backupをgitignore内に保存した。Account適用5テーブルは0件だった。公開手順は次の通り。

1. 保護対象を除外してreviewし、既存checkpointを保持する通常commitでv0.14 docsとv0.15実装を区切る。remote masterへ一度pushし、対象SHAを確認する。
2. `vercel.json`のproduction buildによる自動migrateで0008を適用する。手動migrateは重ねない。buildと公開切替を確認し、旧writerの稼働時間を短くする。移行後は追加列・default・migration記録・値／日時／履歴参照の保存性をbackupと読取照合する。
3. 通常runserverはAGENTS.mdどおりPID／親PID／実行パス／開始日時／8000 listenerを確認し、検証済みNiixy親子だけ停止する。残存processとlistenerがなくなってから通常コマンドで一組だけ起動する。
4. 新asset識別子と状態markupをGETで確認し、共有DBへ実験書込せずPC/mobileのread-only smokeを行う。

schema追加後は旧コードでも読書可能だが、ルールの実装は新コード公開後に有効になる。rollbackでは0008を戻して列を落とす操作より、まず旧コードへ戻して追加列を保持する方が既存Value・参照を保ちやすい。NULL列の解消やNOT NULL化は旧writer停止後の別承認で扱う。

## 検証と限界

検証はDjango test強制SQLiteに加えて`DATABASE_URL=sqlite:///:memory:`を明示し、共有DBにテストデータを作らない。ブラウザは隔離LiveServerとローカルEdgeを使用。通常runserverは共有DB未移行のため今回restartしない。

最新版編集・認可・Account分離・複数共有参照・凍結中更新・不足Field／矛盾による復帰待ち・自動復帰・解除・古いpreview・IF依存版だけの変更・migration保存性を直接検証する。既存ThreadIFの版／値保持と新規作成の最新版解決も回帰対象にする。広域全テスト、実PostgreSQLの同時公開／更新、データ量によるmigration所要時間、共有DB反映と公開版は未検証。

代表PC/mobileでは、凍結IF入力停止→Field最新版preview→確認保存→追加入力付き復帰待ちIF更新→公開表示を確認する。共通`browser_smoke.py`も隔離サーバーで実行し、Workspace配置・console／page errorとdesktop/mobileのrenderを確認する。生成画像は`.artifacts/account-versions/`、`.artifacts/account-applied/`、`.artifacts/browser-smoke/`に保存しuntrackedのままにする。

次段階は承認済みUI／NiiMap調整、その後AccountLayout本体。今回のコードはその作業へ自動でscopeを広げない。


### ローカル結果（2026-10-05）

- `manage.py test interfaces.tests_account_versions interfaces.tests_account_applications interfaces.tests_version_migration interfaces.tests --noinput`: 86件成功。SQLiteのみ。
- `manage.py test scripts.account_applied_browser_tests --noinput`: 4件成功。PC/mobileの凍結・更新・復帰待ち・追加入力・公開表示、空IF、共有値統合と遅い応答を確認。
- `scripts.account_board_browser_tests.AccountBoardBrowserTests.test_shared_browser_smoke_on_isolated_server`: 成功。`browser_smoke.py`を隔離LiveServerへ実行し、PC/mobileとも警告・ブラウザエラーなし。
- 画像QAでpreviewの長い定義JSONによるmobile横はみ出しを検出し、利用者向けの版・型・選択肢・Field構成へ変更。grid列の最小幅と折返しを修正し、横はみ出しassert・console/page error検査と代表PC/mobileを再実行して成功。Workspace／最終表示の画像も確認。
- 最終preview補強後は版更新の直接20件と変更箇所の直接／PC/mobileテストだけを再検証。`makemigrations --check --dry-run`は追加差分なし、保護対象を除く`git diff --check`は成功。

基盤の実装・migration・テストは`6f68524`へcheckpoint済み。inbox／root READMEは変更・stage対象外。上記は隔離QAの記録で、公開・共有0008・通常runserverの切替は承認された公開工程で別途確認する。
