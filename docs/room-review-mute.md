# Room Review / Mute

Status: 実装・隔離QA完了、ローカルcheckpoint。共有DB migration / 通常server restart / push / public反映は未実施。Version番号は未割当。

2026-10-06の承認済み範囲。開始基準は親工程から引き継いだ `209c6eff8a6c1202fdf3c8da66a179f6aec0c114`（local / remote / public一致、interfaces0011共有反映済み）。この工程ではremote/public/共有DBへ接続して再確認していない。[Account Review](account-review.md)と[Account Mute](account-mute.md)の動作をRoomへ揃える。

## 確定仕様

RoomPageとWorkspaceのRoom概要にReviewを表示する。ログインAccountが1 Roomへ1件、必須の紹介文と排他的なLove / Hateを同じ行に保存する。評価だけ、紹介文だけ、空白だけの本文は拒否する。紹介文は10,000文字まで、前後の空白を除き、内側の改行を保持してHTMLをescapeする。ブラウザmaxlengthとフォーム・モデルvalidatorを使う。紹介文の削除はReview行全体の削除で、評価・件数も同時に消える。

RoomOwnerも自分のRoomを評価できる。RoomはAccount本人と別の対象であり、自己Account Review禁止をRoomOwnerへ拡張しない。親からの確認に対するユーザー本人の承認（`Sentinel_f85d057d93948191bb5e3c748605876f`、確認 `Sentinel_35435c24c3b88191ae021653c1fd830a`）を受けて確定した。Ownerも他Accountと同じ本人CRUDのみで、他者の紹介文編集・削除権は持たない。Guestは閲覧のみ。Room参加・Ownerだけに限定する追加ゲートを入れない。

RoomMuteは紹介文不要の独立した公開意思表示。`RoomMute(muter, room, created_at)`を公開Muter一覧で表示する。Review削除でMuteを消さず、Mute解除でReviewを変えない。RoomOwner AccountへのAccountMuteとは別の対象・行で、同じOwnerの他RoomやOwner自身の投稿をRoomMuteだけで隠さない。ログイン本人だけが追加・解除でき、RoomOwnerにも独自の禁止を加えない。GuestはMuter閲覧のみ。

Review作成・更新・削除、Mute登録・解除はPOST / CSRFで行う。本人はrequest.user、RoomはURLを使い、POSTされた別の作者・Room指定を採用しない。Reviewはauthor + target一意、Love / Hate限定、空本文禁止のDB制約を持つ。作成競合は409で暗黙更新しない。更新・削除はreview_id / author / target / revisionを照合し、保存ごとにrevisionを増やす。古い版・二重送信・古い削除は409。RoomMuteはmuter + room一意、enabled=true / falseの明示状態で重複POSTを冪等にする。

## 表示・draft・Account Roomタブ

Reviewヘッダは差（Lover − Hater）とLove / Hate件数、保存済み選択、Mute状態。本文は全紹介文 / Lover / Hater / Muterタブ。Reviewの順序は更新日時降順、同時刻はID降順。初期紹介文3件、Muter8件、もっと見るは10件単位、前へ / 次へ / 畳む。畳む・タブ変更は先頭へ戻る。差・count・公開Muterには本人のMute表示filterを適用しない。

Love / Hateを押すと既存の共通Workspace Review Paneで本文を編集する。保存前に既存評価・本文・countを変更しない。Close / Cancelの本文はWorkspace内のメモリに保持し、永続storageへ書かない。リロードで破棄する。サーバーの行ID / revisionが変わった場合は古い本文を自動復元しない。Account / Roomのdraftと送信guard・再表示更新はactor + target種別 + targetをkeyにするため、Room PKと同じ文字列のNiixyIDでも混ざらない。

Muteの変更時はWorkspace全体の未保存Review / AccountListを確認する。CancelではPOST・reload・入力破棄を行わない。承認した場合だけMuteをPOSTし、成功時に現在URLをreloadして既存一覧・検索・markerを再取得する。送信中の入力・新規編集を固定し、通信失敗時は元のdisabled状態とdraftを復元する。Reviewは送信中Close後に開き直すと送信完了後の最新revisionを読む。閉じたPaneや古いタブGETの応答で新しいPaneを復活・上書きしない。

AccountPage > Roomは既存Owner / 参加中を維持し、対象Accountが紹介文付き評価をしたRoomのLove / Hateを追加する。Owner / 参加中は既存の最終活動順、Love / HateはReview更新日時・IDの降順。各タブ20件単位、件数は表示filter後。paginationは絶対のRoom断片URLとroom_tabを使い、native / shared Paneで選択タブを維持する。Room Review保存・削除後は当該作者のnative cacheを無効にし、表示中native / shared Room一覧を再取得する。入れ子Roomの後続Paneを他機能への切替で置換する既存Workspace契約を使う。

## 元配置による表示filter

共通 `accounts.mutes.filter_muted`で既存AccountMuteを適用した後にRoomMuteを合成する。アクセス認可には使わない。

| 対象 | 元Roomの判定 |
| --- | --- |
| Room | Room自身のPK |
| Board | `BoardPlacement(kind=collection).collection.room_id` |
| Thread | `ThreadPlacement(kind=board, is_primary=True).board.placement.collection.room_id`。Boardの配置kindもcollectionであることを確認 |
| Board自由参照 / fav・bad | 参照・評価先Boardの元配置に同じ判定を使う |

MuteしたRoom由来Boardが別AccountのListで参照・評価されても一覧では隠す。逆に、外部BoardがMuteしたRoomのCollectionに参照されただけではそのBoardやThreadをRoom所属にしない。副ThreadPlacementも元配置にしない。`muted_room_ids` / `muted_board_ids` / `muted_thread_ids` / `filter_muted_rooms`はrequest-specificで、将来の一覧・検索にも再利用できる。

適用経路はAccount Room一覧（全4タブ）、Account Thread一覧、Account / Room Board一覧（自作・評価・自由参照を含む）、Board Thread一覧、Board Thread件数、NiiMap Room一覧・検索・marker、Room条件検索候補。query / 件数・paginationは同じfilter後の対象から作る。個人化断片はprivate / no-store、Room条件検索とReview editorにもnever_cacheを付ける。保存済みAccount条件・その評価ロジックは変えない。

NiiMap Thread検索は既存の直接NiiMap配置scopeを保つ。Room内Thread検索を新設・拡張していない。直接Room / Board / Thread URLと自由参照の直接URLは従来の配置・BoardPolicy / ThreadPolicyに従って開ける。RoomMuteでResponse本文やResponse履歴を新たに隠さず、既存AccountMuteのResponse番号・折畳み・一時表示を維持する。

## Migration・反映順

`rooms/0012_room_review_mute.py`はRoomMute / RoomReviewの2テーブル・制約・index追加だけ。rooms0011とAUTH_USER_MODELを前提とし、既存Room / Board / Collection / Account / 条件 / Policy / List参照を書換えない。data backfillはない。標準post_migrateによる新content type / permissionの追加は通常のDjango動作。

共有DBへの適用・公開・通常server切替は親工程の具体承認後に行う。新コードは0012適用前には新テーブルの読取で失敗するため、追加schemaを先に用意してから新コードを有効にする。Vercel buildがmigrationを担当する場合は運用に合わせ、同じmigrationを重複実行しない。rollbackはコードを先に戻し、Review / Mute行とschemaを保全する。0012の逆適用は新規データを削除するので自動で行わない。

今回通常server `12848 → 37380`は引き継ぎ値のみ。process / port / GET / stop / restartを実施していない。Python・template変更があるため公開工程ではAGENTS.mdどおりのverified pair・8000両確認と明示restartが必要。JS cache revisionは`20261006-room-review`（reviews.js / workspace_trail.js / account.js）を使用する。これはasset markerで、新しいrelease Version番号ではない。

## 隔離QA結果

全実行は明示 `DATABASE_URL=sqlite:///:memory:`、sys.argvにtestを設定し、SQLite ENGINE・`:memory:`をassertしたrunnerを使用した。LiveServerは空きポート、Edge headlessはlocally installed msedge、標準runserver/8000/共有DBを使わない。AGENTS指定requirements-dev.txtは全項目installed済みと確認した。広域全suiteは反復していない。

| 対象 | 結果 |
| --- | --- |
| Room Review直接10件 + Account Review10件 + AccountPage15件 | 35件成功（17.764秒）。本文CRUD、Guest、Owner許可、他作者拒否、CSRF、長さ・空白、保存前不変、版競合、一意排他、更新順、件数、3/10件pagination、escape |
| RoomMute7件 + 新migration1件 + AccountMute11件 + content List19件 | 最終全対象成功。初回38件で新規テスト2件の期待を修正し、新規8件だけ再実行して成功（1.419秒）。既存30件は初回成功 |
| 既存Room表示3件 | 成功（8.057秒）。概要のReview置換、RoomPane endpoint、Board Thread Summary。Account代表asset marker1件も最終成功（0.958秒） |
| Room Review browser1件（両viewport） | 成功（49.118秒）。新規・編集・削除、二重submit、Close中書込と再open、通信失敗・再送、dirty本文、タブ・pagination・畳む、古いeditor/list応答、入れ子Account / Room、Guest |
| RoomMute / Account Room tabs browser2件（両viewport） | 成功（23.170秒）。同名Account/Room draft分離、両種Muteで破棄Cancel、保留Mute失敗中入力lockと復元、公開Muter8/10件・pagination、filter/unmute、Owner UI、タブ、native/shared pagination、起点DOM保持、後続置換・Close、古いRoom応答 |
| 保存後Roomタブ更新の追加browser1件（両viewport） | 成功（15.679秒）。nativeと入れ子shared一覧でLove/Hate切替の反映、選択タブ/page維持、旧branch遅延応答を再確認 |
| 最終browser_smoke.py CLI（別LiveServer fixture） | 成功（31.674秒）。PC1280 / mobile390各17 checks、warnings=0、browser_errors=0 |
| check / makemigrations --check --dry-run / 変更対象diff --check | 成功。model差分なし。inboxの既存空白差分は検査・修正対象から除外 |

直接試験の最初の2失敗は、新規試験が既存JSON検索レスポンスをHTMLとして期待していた点と、既存自由参照route名を誤っていた点。JSONのroom_ids / thread_idsと正しいboard-pane routeへ修正した。product側のfilterは該当assertion前の確認で正常だった。未解消の機能試験失敗・page/console errorは0。

Migration試験は0011へ戻した隔離DBで既存schema・全行・sequenceをsnapshotし、0012追加後に既存の全項目が一致、新規2テーブルが空であることを確認した。この結果を共有PostgreSQLの実データ保全・並行transaction検証の代わりにはしない。

画像は未追跡 `.artifacts/room-review/`、`.artifacts/room-mute/`、`.artifacts/browser-smoke/`に保存。PC/mobileのReview本文・editor・Guest、Muter、Account Roomタブ、desktop-workspace / mobile-workspace、standalone Room Threadを目視確認した。smokeのdesktop.png / mobile.pngは既存finallyのClose直後キャプチャで遷移途中のFrameを含むため、静止したThreadレイアウト確認にはdesktop-room-thread.png / mobile-room-thread.pngも併用した。新規Room UIの横幅assertion・文面escape・長いMuter省略表示は成功。

既存browser-smoke画像は変更前に `C:/Users/user/Documents/Codex/2026-10-06/task-9/prior-browser-smoke/`へ複製して保全。log / 隔離runnerは同task-9 workspaceのdirect-review-qa.log、direct-mute-migration-qa.log、room-mute-migration-final.log、room-review-browser-qa.log、room-mute-browser-qa.log、room-tabs-live-refresh-qa.log、room-existing-view-qa.log、account-assets-final-qa.log、room-final-smoke.log、run_room_qa.py、room_final_smoke.pyに保持する。これら・secret・backup・artifactsをstage / commitしない。root READMEは不変更。inboxは既存dirtyを編集・削除・stageせず保持した。

## 残る公開工程・対象外

機能仕様の未決は今回なし（RoomOwner自己評価を解決済み）。共有PostgreSQLのbackup・既存schema/row確認、0012反映、通常serverのverified restart、push/public、公開後GuestのPC/mobile読取確認は親工程へ残す。実PostgreSQL並行競合、実データ大規模性能、browser全種類・全幅、Workspace全履歴・全通信障害条件は今回の限定QAに含まない。

RoomDM、新List構造、紹介文へのクリック評価・作者評価sort、RoomPolicy / Template / RoomTag / Layout、Room内Thread検索、Response用RoomMute、Mute件数の最終UXは追加していない。
