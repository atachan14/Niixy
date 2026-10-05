# Review 初期実装

Status: 公開済み（最新公開基準 `e17e00e188e6863914a0863dc33c67f19cf85e6f`、親工程からの引き継ぎ）。新しいVersion番号は未割当。以下の実装開始時の基準・公開計画・隔離QAの「未実施」は当時の記録として保持する。accounts0003～0005、rooms0010～0011、interfaces0010は共有環境に適用済み。[最新状態と検証境界](qa-status-2026-10-06.md)を参照する。

2026-10-05の承認済み範囲。AccountPageの評価欄をReviewにする。リリース番号は未確定で、v0.17として扱うかは公開時に決める。

## 保存と権限

ログインAccountが別Accountに一件のReviewを作る。Love / Hateは排他的で、必須の紹介文と同じ行に保存する。紹介文だけ、評価だけ、自己評価は認めない。Guestは閲覧だけできる。作成・編集・削除は作者本人だけに許可し、対象Accountに他者のReviewの削除権を追加しない。作者の認証情報とURLの対象Accountを使い、POSTされた作者や対象の値を採用しない。紹介文削除はReview行全体を削除するため、Love / Hateとcountも同時に消える。

`AccountReview`にauthor / target / sentiment / body / revision / 作成日時 / 更新日時を持つ。DBのauthor + target一意制約、自己評価禁止、Love / Hate限定、空本文禁止を使う。紹介文は既存Response (`ThreadPostForm`) と同じ上限10,000文字を採用する。フォームとモデルで長さを検証し、前後の空白を除去した後に空なら拒否する（改行、タブ、全角空白だけも拒否）。内側の改行・空白は保持する。HTMLとして実行せずエスケープして改行を表示する。ブラウザにもmaxlengthを付ける。DB checkだけでは空白本文・TextFieldの長さは保証しないため、アプリの全書込み入口は検証済みフォームを通す。

新規作成競合は一意制約を捕捉して409を返し、既存行を暗黙更新しない。編集と削除はreview_id、作者、対象を検証し、revision一致を条件に更新・削除する。保存ごとにrevisionを増やし、別窓の古い内容、二重送信、古い削除は409にする。CSRF middlewareとPOST限定を維持する。実際のPostgreSQL並行書込み試験は今回の隔離SQLite検証には含めない。

## 表示と編集

ヘッダはReview、差（Lover − Hater）、Love / Hate件数とする。正の差はLove色、負の差はHate色、ゼロは中立。自分の保存済み選択を色とaria-pressedで表す。Guestと自分のAccountでは投稿ボタンをdisabledにする。Mute / Muterなどの未実装controlを追加しない。

BodyのTabは全紹介文(count) / Lover(count) / Hater(count)。初回sortは更新日時降順、同時刻ではID降順だけとする。紹介文はdefaultResponseの投稿構造を再利用し、表示名 @NiixyIDの右にLove / Hate、更新日時、作者本人だけの編集ボタンを置く。最初は3件、もっと見るで1ページ10件、前へ / 次へ、畳むで選択中Tabの最初3件に戻る。Tab変更はページ1へ戻る。countと差はTabやページによらず対象Account全体を集計する。

Love / Hateを押すと共通Workspace Paneで紹介文を編集する。既存Reviewの場合も本文を読み込み、押した評価を編集窓だけで選択する。保存前には既存評価、本文、ヘッダ、countを変えない。Cancel / Closeでも保存済み内容は保持する。未保存本文は同じWorkspace内のメモリに保持し、Closeや通信失敗後に開き直せる。永続ストレージには保存せず、リロードでは破棄する。サーバーの行ID / revisionが変わっていれば最新本文を表示し、古い入力を自動復元しない。

共通PaneのClose・元DOM保持・レスポンシブ幅・遷移を使い、Accountを入れ子で開いた場合も同じ編集窓を使う。GETはno-store、AbortControllerと接続状態の照合で閉じた窓や古いTab応答の反映を抑止する。送信は共通pending controlに加えて作者＋対象単位のguardを使う。保存中は入力を固定し、失敗時は本文と操作可能状態を復元する。Closeは送信済み書込みを取消す操作ではなく、完了した書込みの応答は閉じた窓を再生成しない。

## migration と公開順序

`accounts/0003_accountreview.py`はReviewテーブル・制約・indexの追加だけで、既存Account、Profile、Condition、InterfaceやLayoutの値を書き換えない。標準post_migrateでReviewのcontent type / permissionが追加される。既存interfaces/0009はそのまま前提にする。

1. 親taskが公開するcommitと反映scope、リリース番号を確定する。今回の実装担当はpublic pushしない。
2. 共有Neonの既存行とschemaをread-onlyで確認し、必要なprivate backupをgitの対象外に保全する。現在の通常serverのverified pairと8000 listenerを再確認する。
3. 0003を適用してから新コードを公開・通常serverを再起動する。Vercel buildがmigrationを担う運用なら手動migrationを重ねない。旧コードは追加テーブルがあっても稼働できるが、新コードは0003適用前には表示APIで失敗する。
4. AGENTS.mdの手順で確認したNiixy pairだけを止め、runserver processと8000 listener両方が0なのを確認してからHiddenで通常コマンドを一組起動する。
5. 一組・単一listener、代表GETの`20261005-review` asset markerとReview markupを確認し、共有DBへのテスト書込みなしでPC/mobileのGuest閲覧を確認する。通常serverにはPython / template変更の明示restartが必要。

rollbackはコードを先に戻し、Reviewテーブルと作成されたReviewを保全する。Review作成後の0003逆適用はデータを削除するため自動で行わない。migration適用前後の公開DB確認と公開GET確認は親調整の公開工程として残す。

## 検証

`manage.py test accounts.tests_reviews accounts.tests_review_migration scripts.review_browser_tests`はsettingsのtest分岐と明示SQLite assertionを使う。共有Neonや通常serverにデータを作らない。直接試験は認証・作者/対象認可・自己評価・一意/DB check・CSRF・CRUD・空白/上限・既存評価保持・古い版拒否・件数・更新順・Tab・3/10件ページ分割・escapeを確認する。migration試験は0002から0003へ移行し、既存テーブルのschemaと全行の不変、新Reviewテーブルが空であることを確認する。

Edgeの隔離LiveServerでdesktop1280px / mobile390pxを確認する。新規/編集/削除、保存前の評価不変、Cancel / Closeの本文保持、通信失敗と再送、二重submit、Tab・pagination・畳む、古いGET、作者への入れ子Account、自分/Guest制限を確認する。同じLiveServerで既存`scripts/browser_smoke.py`のentry pointを両viewport実行する。画像は`.artifacts/review/`と`.artifacts/browser-smoke/`に生成し、untrackedのまま保管する。

送信中Closeから再度編集を開くと、送信完了を待ってから最新本文とrevisionを取得する。古い送信応答で新しい編集窓を閉じない。編集Paneではfocus / inputに共通trail再整列を使い、ブラウザの自動横scrollがtransformと二重に適用されるのを防ぐ。画像は遷移完了後に取得する。

2026-10-05の結果: Review直接10件、migration既存schema/全行保全1件、PC/mobile Review browser1件、既存AccountPage15件が成功（計27件）。Browser内の既存smokeは両viewportそれぞれ17check成功、warnings / browser_errorsとも0。画像でReview本文・色・Tab・編集窓とdesktop/mobile Workspaceを確認した。初回のTextFieldモデル単体長さ検証不足に明示validatorを追加し、編集Paneのfocus時の横ずれを修正して直接/ブラウザを再実行した。`makemigrations --check --dry-run`は追加差分なし、Django checkも問題なし。全域testは繰り返していない。

通常serverの事前確認はvenv launcher37132 → base Python34712、開始2026-10-05 21:48:11、127.0.0.1:8000 listener owning34712の一組。通常serverは再起動していない。共有Neonへのmigration・テスト書込み、public push、production GETは未実施。公開DB上の既存行保全、PostgreSQL実並行競合、公開後Guest表示は公開工程で確認する。inboxは読取・編集・stageの対象外、root READMEは不変更。secret / backup / artifactsをcommitしない。

## 対象外

Mute / Muter（将来の公開意思表示とfilter）、AccountList、DM / AccountPolicy送信条件、紹介文への評価、作者評価sort、ProfileLayout変更、List renameは今回含めない。将来PCの紹介文 / Timeline / Boardの3列も別工程とする。
