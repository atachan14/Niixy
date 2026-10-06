# Thread / Responseの公開評価とユーザーList

前checkpoint `46d31cd`から継続。AccountPageのThread / Responseに残っていたfav・bad・bookmarkの「未実装」表示を、共通の評価とユーザーListへ接続する。bookmarkは旧称であり、独立した保存機能は作らない。

## 変更と共通経路

- `ThreadRating` / `ResponseRating`はBoard / Moduleと同じ公開・排他的なfav / bad。紹介文は持たない。同じ操作の再クリックで解除し、APIは希望する状態を受け取る。対象行のlockとauthor / targetのunique制約で重複送信を処理する。
- `ThreadList` / `ResponseList`と参照modelを追加。所有者ごとのsubmission UUIDで作成を再送可能にし、同じList / targetの参照は一つ。元のThread / Response、placement、Policyは変更しない。
- ListのPicker、追加して作成、URL追加、改名、参照解除、削除、URL共有、取得失敗時の表示、送信中の制御は既存の`accounts/content_lists.py`と`NiixyAccountLists`を拡張して使う。AccountPageにはList作成ボタンを追加しない。
- AccountPageは「作成｜fav｜bad｜各実在ユーザーList」。全List名を同段tabに保持する。Thread / Responseの本文一覧は従来の10件単位、汎用List管理の参照一覧は共通の20件単位を保持する。独立bookmark tabは置かない。
- Threadの最初の本文下、各Responseの本文下とAccountPageのResponse本文下に小さい「fav｜bad｜追加」を表示する。評価人数と正規URL共有も共通部品を使う。touch環境では操作領域を44px以上に保つ。
- 評価 / List変更後は該当種別の一覧を再取得し、選択分類を保持する。native AccountPageのHTML cacheを無効にし、nested Paneでも親のtab / URL bindingを保持する。遅い取得の結果は切断済みPaneに戻さない。

## 正規URLと閲覧条件

| 対象 | 正規URL | 意味 |
| --- | --- | --- |
| Thread | `/threads/<Thread.pk>/` | 既存Threadの詳細 |
| Response | `/responses/<ThreadPost.pk>/` | 同じThread内の対象Responseを表示位置として指定 |
| ThreadList | `/thread-lists/<pk>/` | 公開Listの管理・共有 |
| ResponseList | `/response-lists/<pk>/` | 公開Listの管理・共有 |

Responseは`ThreadPost.number > 1`。#1をResponseとして閲覧 / 評価 / Picker追加するAPIは404。PickerやURL追加は正規URLの種別と同一originを確認し、外部URL・query / fragment・Pane URL・異種Listへの追加を拒否する。

Threadの本文と返信は既存のThreadPolicyに従う。Boardへの参照や評価は閲覧権を与えず、Thread自身の閲覧条件が判定元である。評価、評価者一覧、Picker、参照追加は対象を閲覧可能なAccountだけが操作できる。所有者の閲覧救済も既存のThread.allowsをそのまま使う。Guestには評価・追加をdisabledで表示し、POSTは401。List管理は所有者以外404、CSRF検証は既存middlewareを通る。

AccountPageから他者作成の評価済み / List追加済みThreadを開くため、Accountとの関係判定にrating / List参照を追加する。関係のないThreadのAccount固有詳細URLは404を保ち、関係があってもPolicyは別途検証する。

閲覧不可の詳細は本文、投稿数、対象投稿番号、評価操作を出さない。Response履歴 / 評価 / List tabでは同じ閲覧不可Threadを一度だけ表示し、投稿時刻をThreadの最終活動時刻へ置き換える。共通List管理の参照summaryも閲覧不可時はResponse番号と本文を出さない。List自身の参照件数・追加時刻は既存の公開List仕様を保持する。

## Muteと削除

Muteは表示フィルターであり、閲覧権限を変えない。Threadの各分類と自由参照は既存のAccountMute / 原配置RoomMuteを使う。Responseの履歴は従来のAccountMute-only規則を保持する。Thread作者のMuteは履歴から除外し、Response作者のMuteは本文の折り畳み表示を保持する。自由参照summaryは共通List同様にMute作者を除外する。折り畳み本文には評価操作を付けない。

対象を物理削除した場合、ratingはCASCADEで消し、List参照のtargetはSET_NULLで残す。削除済み表示と所有者の参照解除を維持する。Listを削除しても元のThread / Responseは残る。既存Thread削除やsoft-deleteの仕様は拡張しない。

## schemaと反映範囲

`events/0018_responselist_responselistreference_responserating_and_more.py`は6つの新規model / tableと、その新規tableの8制約のみを追加する。既存Thread / ThreadPost、RoomReview / Mute、AccountIFの保存データを更新するdata migrationはない。

共有Neonへのmigration・書込、通常runserverの再起動、push / public反映は今回の作業範囲外。通常反映時には新migrationの適用と、Python / template変更に伴うAGENTSどおりの明示restartが必要。cache markerは`20261006-conversation-feedback`。隔離SQLite LiveServerとheadless EdgeだけでQAを行う。

## QA

81件の各最終結果が成功（76件の初回回帰 + 修正・追加後のfocused runの各最終結果を統合）。新規12件、既存AccountPage / ThreadPolicy / pagination、共通Board / Module / PeopleのList操作を含む。単一81件runではなく、各成功logの対応は`.artifacts/conversation-feedback/qa-summary.json`に保存した。

| 検証 | 結果 |
| --- | --- |
| 評価 / List API | 排他fav→bad→解除、希望状態の再送、作成UUID / 参照重複、正規URL / 種別、所有者 / Guest / CSRF、Policy、削除済みtarget / rating CASCADE、List削除で元target保持 |
| Response privacy / Mute | 閲覧不可の本文・番号・投稿数を非表示、同じThreadのdenied履歴を重複排除。AccountMuteと原配置RoomMuteの既存規則を確認 |
| 本人 / 他者 / Guest × PC / mobile × native / nested | 12組でThread / Responseのfav / bad / List分類、詳細、Close、native Back / Forward、owner評価変更後の親分類保持。page / console error 0 |
| 実操作 | PC / mobileの評価切替・解除、double clickのPOST 1回、追加Pickerから両Listを作成、共通List表示、正規URLコピー、Guest disabled / 閲覧不可表示、canonical Response Paneから返信成功 |
| mobile寸法 / 描画 | coarse pointerのfav / bad / 追加は幅・高さ44px以上。画像は共通Workspaceの350msのalign待ちと表示領域判定後に取得 |
| browser_smoke.py CLI | 隔離LiveServerでPC / mobile各17 checks、warning 0 / browser error 0。map / Account / Room / 両Boardの代表fixtureを用意して省略なし |
| 構文 / schema | Python AST、JS node --check、Django check、makemigrations --check --dry-run。events0018は隔離SQLiteのtest DBだけに適用 |

初回の8件direct runはMute本文をACLと混同したtest assertionを既存折り畳み契約へ訂正。以後の初回76件runは74件成功と、古いasset marker assertion / hidden tabにも同じThreadがあるlocatorの2件を訂正。分類更新後の新tabを親のhistory callbackでbindする順序も確認して修正した。role matrixの旧testはvisible overviewへCloseせず操作していたため、実際のClose経路へ訂正。RoomMute / smokeのfixtureは初期Boardが2件あることを反映し、代表ケース不足によるsmoke省略を許容しないassertionを追加した。失敗logも保持する。

smokeのdesktop-workspace / mobile-workspace / desktop / mobile、会話のPC native / mobile nested・canonical Response・Guest denied・List管理画像を目視確認した。通常server `30348 → 5452`とlistener5452、起動時刻は開始時のまま。初回通常権限のCIM process読取はアクセス拒否となったが、許可済みの読取を承認審査付きで再実行して成功。自動承認レビューによる拒否や残るアクセスblockerはない。
生成画像・JSON・試験logは`.artifacts/conversation-feedback/`とtask-10に保持し、Gitには追加しない。

## 未解決の製品判断

- ThreadとResponseでRoomMuteの適用範囲が異なる点は、既存コードに明示された規則として保持する。Responseも原配置RoomMuteで隠す変更は今回採用しない。
- Accountの会話一覧10件と汎用List管理20件の差も既存契約を保持する。全種別を同じ件数へ統一する要件は未確定。
- 多数のユーザーList tabの別UI化 / lazy loading、Thread / Responseのsoft-delete、削除前の本文snapshot、bookmark旧URLからの移行は追加しない。旧bookmarkには保存model / 正規URLがなかったため移すデータはない。

root READMEと`docs/memo/inbox.md`の編集・stageは行わず、開始時hashと既存差分を保持する。
