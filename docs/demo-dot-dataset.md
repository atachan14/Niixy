# Dot架空デモデータ（2026-10-07）

ユーザーの明示承認により、公開版と共有するNeonへ架空デモセット `niixy-demo-dot-20261007-v1` を追加した。既存データの編集・削除、schema/migration、設定、通常server、push、deployment変更は行っていない。

実行前HEADは `0d889fb9e10d0856016c477f51c3edca41c82892`、GitHub master/追跡ref Niixy/master/公開済みコードは `ddef8887100d93aa435d2e0eb506eef6689ddf2a`。accounts/events/interfaces/rooms/templates/configは両HEADで一致し、working treeにも差分がないことをguardした。READ ONLY inventoryで64テーブルの列とmigrationを確認し、未適用migrationは0だった。

## 見本用Account

IDの制約は小文字英数字・アンダースコア3〜20文字、表示名は表示幅24まで。Dot系5 IDが未使用であることをcase-insensitiveに確認した。全て `is_active=False`、unusable password、email空、staff/superuser=False。固定password・認証Session・認証鍵・admin権限を作らず、メール/OAuth/通知/Webhookも実行していない。

| Account | 見どころ |
| --- | --- |
| [読書会サンプル @dot](https://niixy-psi.vercel.app/accounts/dot/) | 読書会の案内、公開AccountList、AccountIF適用とProfileカード。 |
| [共同制作デモ @dot2](https://niixy-psi.vercel.app/accounts/dot2/) | 共同制作Room、制作の流れをまとめるThreadList、Field/IF定義。 |
| [作品紹介サンプル @dot3](https://niixy-psi.vercel.app/accounts/dot3/) | Accountの初期Boardでの架空作品紹介、共通部品を集めるModuleList。 |
| [学習記録デモ @dot4](https://niixy-psi.vercel.app/accounts/dot4/) | AppliedのDirectFieldとAccountIF併用、整数Field・振り返り、ResponseList。 |
| [イベント見本 @dot5](https://niixy-psi.vercel.app/accounts/dot5/) | 日程に依存しない架空展示案内、BoardListで複数のBoardを参照。 |

## 件数と内容

| 追加対象 | 件数 |
| --- | --- |
| Account | 5 |
| Room / RoomMembership | 2 / 10 |
| Board | 11（Account初期5、Room初期4、用途別1、地図上1） |
| Thread / Response | 9 / 12（冒頭Post9を含めPost計21） |
| 公開List | Account / Board / Thread / Response / Module各1、計5 |
| 公開Field / IF | 5 / AccountIF1・ThreadIF1 |
| Account IF適用 / Account DirectField | 5 / 1 |
| Thread IF適用 / Thread DirectField | 4 / 5 |
| AccountLayout公開 / 適用 | 1 / 5 |
| 新規地図マーカー | 4（Room2・Board1・Thread1） |
| Review / fav / bad / Mute | 0 |

全投稿に架空デモの説明を入れ、架空の作品・読書・共同制作・学習・展示案内で機能を見せる。イベント日時や住宅/個人所在地は使わない。公共空間付近の仮の地図配置は実際の施設・開催場所を表さないとRoom/Board/Thread本文で明記した。未実装のRoomIF/ResponseIF適用、Album、Template、Timelineは動作するものとして扱っていない。

## 入口と機能の組合せ

| 入口 | 内容 |
| --- | --- |
| [読書と学びのデモRoom](https://niixy-psi.vercel.app/rooms/3/) | 読書会と学習記録。初期のお知らせ/掲示板を使う。 |
| [共同制作のデモRoom](https://niixy-psi.vercel.app/rooms/4/) | 構成相談と用途別の制作ノートBoardを使う。 |
| [デモの案内役](https://niixy-psi.vercel.app/accounts/lists/1/) | デモの案内役4 Accountを参照する。 |
| [会場と作品の棚（デモ）](https://niixy-psi.vercel.app/board-lists/37/) | 異なる所有/配置の3 Boardへ案内する。 |
| [制作の流れ（デモ）](https://niixy-psi.vercel.app/thread-lists/1/) | Room内とAccount内の3 Threadを一つにまとめる。 |
| [振り返りの例（デモ）](https://niixy-psi.vercel.app/response-lists/1/) | 会話の中の3 Responseを個別に参照する。 |
| [使える部品（デモ）](https://niixy-psi.vercel.app/interface-lists/1/) | AccountIF/ThreadIF/Field5/Layout1の8部品を同じModuleListにまとめる。 |
| [【デモ】架空の短編集を持ち寄る](https://niixy-psi.vercel.app/threads/41/) | 読書のThreadIFと3 Response。 |
| [【デモ】学びの一巡を記録する](https://niixy-psi.vercel.app/threads/42/) | 整数と複数行テキストのDirectField。 |
| [【デモ】架空ZINEの構成相談](https://niixy-psi.vercel.app/threads/44/) | ThreadIFに制作段階を固定し、役割別にResponseを足す。 |
| [【デモ】色と余白の制作ノート](https://niixy-psi.vercel.app/threads/45/) | ThreadIFとDirectFieldを併用した制作ノート。 |
| [【デモ】架空作品・月のしおり](https://niixy-psi.vercel.app/threads/46/) | Account初期Boardでの作品紹介。 |
| [【デモ】観察から始める学習メモ](https://niixy-psi.vercel.app/threads/48/) | NiiMapに直接配置した学習メモ。 |
| [デモ活動カード（AccountLayout）](https://niixy-psi.vercel.app/layouts/1/) | RequireAccountIFとItemの版を固定して公開し、5つのAccountの異なる現在値を表示する。 |

## 保存・冪等性・保全

[seed script](../scripts/demo_dot_seed.py) の既定actionはDB未接続のplanのみ。共有保存は明示action・対象公開SHA・既存private inventoryを要求し、public backend一致、Neon PostgreSQL、未適用migration0を再確認する。batch UUIDからRoom/Board/Thread/Response/Listのsubmission_idを決定し、主Roomのbatch markerを既存schemaへ保持する。再実行は完全な既存デモを検証して返すだけで、名前衝突や不完全な既存セットは無変更で停止する。

User標準managerと初期Board signal、Room/Boardサービス、join/Thread/Response/Listの標準view、Field/IF公開、Applied変更、Layout preview/publish/applyを再利用した。新規デモActorを直接サービスへ渡し、ログインや認証Sessionを発行しない。公開版と同じ認可・Policy・型検証・公開版固定・初期生成・container activity更新を通す。

共有保存はrepeatable-read transactionとbatch限定advisory lockで一度実施した。既存行のID/行hashを保存前後で比較し不変をassert、全作成IDをprivate manifestへ保存した。既存本文・認証情報を含む全文dumpは作らず、限定保全記録はID/schema/migration/件数/行hashであり全文復元用backupではない。auth.Userのpassword/email/氏名/usernameは保全snapshotの読取り対象から除外した。private inventory・preapply witness・intent・manifestはGit外の共有task-10/privateへ保存し、秘密/backup/artifactsをstageしない。rollbackや他データ削除は実施していない。

Threadの閲覧PolicyはGuest/Accountへ公開、書込みPolicyは今回の5デモAccountだけ。Boardの既存初期Policyは保持しGuest閲覧を確認した。見本用Accountはログイン不可なので、公開閲覧のサンプルとして扱う。

## QAと証跡

[専用QA](../scripts/demo_dot_tests.py) をdotenv無効の隔離SQLiteで実行し、**2テスト / 10.871秒成功**。既存大文字Dot衝突時に全行不変、初回作成差分が見積り通り、完全再実行時は全行無変更、Guest53 GETが200、全新Thread/Boardの閲覧PolicyとGuest書込禁止、PC/mobileのProfile/Applied/Thread/ModuleList/Room、横overflow 0、page/console error 0を確認した。初期試行のLayout border shorthand拒否とGuest AppliedのQA locator不一致はseed/testだけで調整し、既存製品制約は変更していない。

追加後の公開確認開始UTCは `2026-10-07T14:36:08.516722+00:00`。匿名GETのみで**53 URLすべてHTTP200**、新規4マーカーを公開rootで確認。PC/mobile各5代表画面とAppliedのField/AccountIF切替を確認し、browser errorと横overflowは0。公開Profileカード・Applied・Thread・ModuleList・AccountListの画像を目視確認した。

ignored `.artifacts/demo-dot-2026-10-07/sqlite/summary.json` と `public/summary.json`、PC/mobile画像に証跡を保持する。外部runner/公開GET専用script/過去試行ログ/共有applyログはtask-10 workspaceへ保存した。通常serverのPID/開始時刻、root README/inboxのhash、開始時の他差分は保持する。

全browser/mobile幅/全利用方法の網羅ではない。新機能・schema・公開コード変更を追加せず、既存機能のデータ充実だけで区切る。
