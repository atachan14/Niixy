# AccountList 作成・参照追加

Status: 公開済み（最新公開基準 `e17e00e188e6863914a0863dc33c67f19cf85e6f`、親工程からの引き継ぎ）。新しいVersion番号は未割当。以下の実装開始時の基準・公開計画・隔離QAの「未実施」は当時の記録として保持する。accounts0003～0005、rooms0010～0011、interfaces0010は共有環境に適用済み。[最新状態と検証境界](qa-status-2026-10-06.md)を参照する。

2026-10-05承認済みの次工程。リリースversionは未割当。local HEAD 5030762（Review / Mute / draft保護）の上に実装する。公開80a39cf（v0.16）へのpush、共有DB migration、通常server restartはこの工程に含めない。

## 要件と操作

AccountListはAccountを自由に参照する名前付きList。`owner` AccountがList本体を管理し、Guestを含め誰でも閲覧できる。将来ListPolicyを追加できるが、今回は制限を設けない。Account自身や既存BoardCollectionを移動・改名しない。

AccountPageの既存Peopleから、そのAccountが所有するListのSummary一覧を共通Workspace Paneで開く。owner本人にだけ新規作成を表示する。List詳細にはAccountSummary、追加日時、参照解除、URL共有、URLから追加、List名変更・削除を表示する。owner以外には書込みformを返さない。APIでもrequest.userとList.ownerを照合し、POSTのowner/target ID指定を信頼しない。全書込みはPOST / CSRFを必須とする。

Reviewの［追加］は閲覧者本人が対象AccountへLove / Hateと紹介文を保存済みの場合だけ表示する。押すと「追加先を選択」Paneを開き、本人所有の既存Listへ対象Accountを追加するか、新規Listを作成して同時に追加できる。Picker GETでも保存済みReviewを再確認する。一般のList詳細のURL追加は、Review有無を要求しない自由参照とする。Reviewを削除しても既存参照は残る。Account評価は引き続きLove / Hateと紹介文のReviewだけで、新しいAccount fav / badを設けない。

List名は前後空白を除去し1〜80文字。初期Listは自動作成しない。List一覧/Pickerは作成日時昇順・ID昇順、参照は追加日時降順・ID降順。共通Summary paginationの20件を使用し、空状態を用意する。手動並び替え、評価sort、Listネスト、他List参照、Board / Interface参照は対象外。

## 保存・重複・削除

`AccountList(owner, name, submission_id, created_at, updated_at)`と`AccountListReference(account_list, target, created_at)`を追加する。List作成はowner + submission UUIDをuniqueにし、同じ送信の再試行でListを増やさず、既存名を暗黙改名しない。参照はList + targetをDB uniqueにしてget_or_createする。二重追加・二重解除を安全に扱い、参照解除は対象Accountや他Listの参照を変更しない。List削除も参照だけをcascade削除する。

参照先Account削除については、自然な参照解除と非機密placeholderを比較し、今回はnullable target / SET_NULLで参照行を残す最小案を採用した。名前・NiixyID等のsnapshotは保存せず、表示は「削除されました」と追加日時だけ。ownerが参照を解除できる。List owner削除時はその所有Listと参照をcascade削除する。この削除表示の最終仕様は親工程へ報告し、後続対象との共通化時に再確認する。

Muteはアクセス認可に使用しない。List詳細のAccountSummaryは閲覧者本人のMute対象をpagination前に除外し、Guestには全参照を表示する。直接Account URLは従来通り公開、参照行自体は維持する。List一覧/Pickerの件数はListに保存された参照総数（削除済みplaceholderとMute非表示分を含む）。Mute非表示対象の管理UIを別途設けるか、件数表示をvisible countへ変更するかは後続のUX判断とする。

## URL共有とサーバー解決

Account正規URLは`/accounts/<NiixyID>/`、List正規URLは`/accounts/lists/<id>/`。Picker内の「URLを共有」で対象Account URLをコピーでき、List詳細でもList URLをコピーできる。コピー時に現在originを付けた絶対URLにする。clipboardが使えない場合は文字列を選択し、手動コピーできる。ブラウザに貼るとAccountまたはListを直接表示する。List URL reloadはownerのAccountPage上でList詳細Paneを復元する。

`accounts/internal_urls.py`はAccount / AccountListを型付きで返す内部resolver。URL入力からの追加はAccount型だけを許し、List型は拒否する。現在request originと設定`NIIXY_REFERENCE_ORIGINS`の明示した追加originだけを認める（既定は空、comma区切り）。originのscheme / host / portを比較し、credentials、不明origin、不明ID、別種類、非正規path、query / fragment、encoded path、private Draftなどの内部管理URLを拒否する。相対の正規pathも許す。外部HTTP fetch、DNS照会、redirect追跡は行わない。将来のBoard / InterfaceListでも同じresolverとWorkspace Pane起点を拡張できるが、他対象の認可を今回緩めない。

## Workspaceと未保存入力

共通Trailの起点Pane以降置換、右Pane追加、Close、親DOM/scroll保持を使用する。List入力は同一Workspaceメモリに保持し、Close後の再表示と通信失敗時に復元する。submission UUIDも保持し、結果不明の作成を再試行して重複Listを作らない。Page遷移/reloadでは破棄する。

GETはno-store、AbortControllerとPane接続・request一致で遅い応答を無視する。POSTは送信単位のpending guardを使い、Closeで中断せず、再表示時は送信完了後に保存済み状態を読み直す。閉じた送信の応答で新しいPaneを閉じない。入力中のfocus位置補正は末尾Paneに限定する。保存結果の名称・参照件数は背後のSummary DOMにも反映し、Close時の再取得に依存しない。GET再読込失敗時も既存formを残してalertを表示する。

Muteによるreloadの前に、既存Review draftとAccountList draft双方の破棄確認を行う。Cancel時はPOST/reloadしない。List書込み中はMuteを送信せず、Mute送信中はList入力・新規操作を固定する。Mute失敗時はdisabled状態と入力を復元する。Mute待機中に遅いGETで新しいformが生成された場合も、元のdisabled状態に戻す。

## 隔離検証

- `manage.py test accounts.tests_lists accounts.tests_list_migration accounts.tests_reviews accounts.tests_mutes accounts.tests.AccountPageTests --noinput`：52件成功（AccountList 15件、migration 1件、Review 10件、Mute 11件、AccountPage 15件）。API応答による保持件数修正後もAccountList 15件を絞って再確認し成功。
- 新migrationの検証は0004→0005移行前後で、全既存SQLiteテーブルのschema/全行が同一で、追加2テーブルが空であることを確認した。
- `scripts.account_list_browser_tests`：Edge headlessのPC 1280px / mobile 390pxで、Picker・URL共有・既存追加・重複追加・作成・通信失敗/再試行・Close/input保持・二重送信・AccountSummary子Pane・URL追加・改名・解除・List削除・直接URL/reload・Guest・遅いGET・nested People・送信中Close/再表示・Mute Cancel/失敗を検証する。同じ隔離LiveServerで変更していない`browser_smoke.py`のentry pointを実行し、両画面各17check、warnings / browser_errorsとも0。
- `scripts.mute_browser_tests.MuteBrowserTests.test_unsaved_review_mute_confirmation_pc_mobile`：既存Review draft保護のPC/mobile回帰成功。
- Django check / makemigrations --check --dry-run / JavaScript構文検査 / 指定コード範囲git diff --check成功。全域の反復は実施しない。

画像は`.artifacts/account-lists/`と`.artifacts/browser-smoke/`にuntrackedで保存する。desktop/mobile List・Workspaceとbrowser-smokeの画像を目視確認した。途中で見つけた古いfocus位置補正、保持Summary件数、スタイル適用時の重複classは修正し、関連ケースを再実行した。

## 公開前と後続

追加migrationは`accounts/0005_accountlist_accountlistreference_and_more.py`。0003 Review / 0004 Mute / rooms0010 creatorと既存interfaces0009が共有環境に未反映であるため、公開前に親工程が適用順・backup・公開scope・versionを確定する。共有Neonへのmigration・テスト書込み、通常runserverの起動/停止/restart、public pushは未実施。共有PostgreSQLでの実並行競合と公開Guest GETは未検証。コードを公開する前に必要migrationを適用し、AGENTSに従ってverified pairをrestartしてasset marker `20261005-account-lists`と代表GETを確認する。

rollbackはコードを先に戻し、List/参照データを保存する。0005逆適用は保存したList/参照を削除するため自動実行しない。BoardCollection改名、BoardList / InterfaceListの実装、ListPolicy、他種類/ネスト参照、並び替え、DM、評価sortは親の後続工程へ引き継ぐ。

保護指定の`docs/memo/inbox.md`は未読・未変更・未stage。root READMEは不変更。secret / backup / 既存userchanges / artifactsはcommit対象外にする。
