# Niixy Roadmap

公開基準: `e17e00e188e6863914a0863dc33c67f19cf85e6f`（2026-10-06 JST、親工程からの公開完了引き継ぎ）。v0.16公開と後続の公開済み追加機能を区別し、後続には新しいVersion番号を割り当てない。[最新状態・限定QA](qa-status-2026-10-06.md)を参照する。

## v0.1 - NiiMap / Event

Status: Complete

最初のVersionでは、NiiMapの最小構成を完成させる。

Account登録やLoginを必要とせずMapを利用でき、Eventを閲覧・投稿できる状態を目指す。

主な対象:

* Map表示
* Event表示
* Event詳細
* GuestとしてEvent投稿
* Database保存
* Admin管理

---

## v0.2 - Account Core

Status: Complete

Niixy IDとPasswordによるAccount登録・Loginを追加し、Loginした利用者が自身のEventを管理できる状態を完成させる。

主な対象:

* Niixy ID / PasswordによるAccount登録
* Login / Logout
* LoginしたAccountとEventの紐付け
* 作成者表示
* 自身が作成したEventの編集・削除
* 自身が作成したEventでのNiiMap Filter

---

## v0.3 - Thread Foundation

Status: Complete

暫定的な Event モデルを、`docs/vision/` で定義する Thread / ThreadPost の基盤へ置き換える。NiiMap に配置する Thread、時系列の返信、Guest / NiixyAccount による最小の制限を対象にする。

---

## v0.4 - AccountPage Foundation

Status: Complete

公開 AccountPage と、Account が作成・返信した Thread を閲覧する ThreadPane を追加する。Account の公開情報と活動履歴を載せる基盤を作り、NiiMap と共通する SummaryList / DetailPane の体験を Account 側へ広げる。

主な対象:

* Guest を含む AccountPage の公開閲覧
* ThreadPost の投稿者から AccountPage への導線
* 固定 AccountPageHeader
* Account が作成・返信した Thread の一覧
* Account 側の Thread 閲覧と返信

---

## v0.4.1 - MyPage / Account Basic Information

Status: Complete

本人用の最小 MyPage と、Account 基本情報としての表示名編集を追加する。

主な対象:

* MyPage と SiteHeader の Account メニュー
* 表示名の保存と Validation
* Profile、MyPage、ThreadPost 投稿者表示への反映

---

## v0.5 - Interface Foundation

Status: Complete

最初の ThreadInterface 作成・適用基盤を追加する。独立した Field と FieldVersion、InterfaceVersion と編集途中の Draft を分離し、複数 Interface を一つの Thread に適用できる状態を目指す。

主な対象:

* Interface の新規作成、Draft 保存、v1 公開
* 独立した Field の作成、Version 公開、片同義
* Interface から FieldVersion を参照する構造
* 複数 ThreadInterface の同時適用
* Thread 作成時の Interface 選択と値入力
* `#1` での ThreadInterface 表示
* Interface の Soft Delete

---

## v0.6 - Room Foundation

Status: Complete

NiiMapへRoomを配置し、AccountがRoomへ参加して、Room内のBoardでThreadとResponseをやり取りできる最小の共同利用を完成させる。

主な対象:

* Roomの作成、基本情報編集、NiiMap配置
* RoomPageとNiiMapでのRoom表示・検索
* Main Collectionと「最初のBoard」の自動作成
* ログイン済みAccountの即時参加・退出
* RoomOwnerと参加者の区別
* 参加者によるBoard内Thread作成・Response投稿

---

## v0.7 - Board Management

Status: Complete

RoomのMain Collection内でBoardを追加・編集・削除できるようにし、複数Boardを用途ごとに使い分けられる状態を完成させる。

主な対象:

* RoomOwnerによるBoardの新規作成と基本情報編集
* Boardの物理削除と、未配置で存続するThread
* 配置先から解決するBoard管理権限
* 複数BoardでのThread作成・閲覧・Response投稿

---

## v0.8 - Collection Management

Status: Complete

RoomOwnerがRoom内のCollectionを追加・編集・削除し、Boardの配置先をCollection単位で管理できる状態を完成させる。

主な対象:

* RoomOwnerによるCollectionの新規作成と名称編集
* 選択中CollectionへのBoard作成
* 通常Collectionと常設のシステムCollection「未分類」の識別、およびCollection削除時の配置Board退避
* 通常Collection、未分類、管理のTab構成
* Collectionの詳細確認と、管理者向け編集・削除導線

BoardおよびCollectionの参照機能と、Account側のCollection管理への展開は後続段階で扱う。

---

## v0.9 - BoardPolicy Foundation

Status: Complete

Account条件を使う共通Policy評価の基盤を追加し、Boardの閲覧とThread作成をBoardPolicyで制御できる状態を完成させる。

主な対象:

* 許可OR、ANDグループ、不可優先を扱う共通Policy評価
* Boardの閲覧制限とThread作成制限
* 共通Account条件選択によるRoomOwner向けBoardPolicy編集
* 閲覧不可BoardのSummary表示と理由だけを返すBoardPane
* 既存Boardの固定ルールを明示的な初期Policyへ移行
* 起点Paneとその前を保持するWorkspace遷移、子孫Paneの置換、展開・Closeの動作確認

RoomPolicy、既存ThreadPolicyの共通基盤への移行、TemplateとLayoutは後続段階で扱う。

---

## v0.10 - ThreadPolicy Foundation

Status: Complete (implementation / isolated verification / published)

Threadの閲覧とResponse投稿を共通Account条件・Policy評価器へ移行し、条件設定と不可表示を各導線で揃える。Templateは別Versionで扱う。移行、初期値、閲覧不可時のメタ情報公開範囲は合意済み。必要migrationは公開工程で反映済み。

詳細: [v0.10要件](v0.10/requirements.md)

---

## v0.11 - Room初期Board / Board作成Policy

Status: Complete (implementation / isolated verification / published)

新規RoomのMainに「お知らせ」「掲示板」を生成し、手動Board作成で共通Account条件UIによる4欄Policy設定を可能にする。既存Roomの移行・Template・動的RoomOwnerは対象外。

詳細: [v0.11要件](v0.11/requirements.md)。関連: [Backlog BL-001 / BL-003](backlog.md)。

---

## v0.12 - Account Applied

Status: Complete (implementation / isolated verification / published)

MyPageでAccountへ直接Field／AccountIFを適用・値編集・取外しできるようにし、公開AccountPageのApplied一覧にField／AccountIFを表示する。固定版とAccount内共有Valueを扱い、Value更新日時で一覧を並べる。Moduleと将来ProfileLayout欄は別機能として維持する。

詳細: [v0.12要件](v0.12/requirements.md)。schema migration 0007は共有Neonへ適用済み。公開済み。公開状態と今回の検証境界は冒頭の最新状態リンクを参照する。

---

## v0.13 - Account Board / Collection

Status: Complete (implementation / isolated verification / published)

AccountのBoard一覧Pane、本人向けCollection／Board管理、Main／日記／未分類の初期生成とBoardからThread投稿までをRoom共通処理で実装する。v0.13時点のfav／badはTab枠。現在の公開fav／badは後続の追加機能を参照する。返信は各ThreadPolicyで決める。

詳細: [v0.13要件](account-boards.md)。既存Accountへのrooms 0009はCollectionを一つも持たないAccountだけを対象とする一度限りのデータ追加。自動migrationを行うVercel本番buildでは、新コード公開後に0009を追加する二段階で反映した。

---

## v0.14 - Interface / Field版更新・凍結／復帰

Status: Complete (implementation / isolated verification / published)

Accountの最新版編集・保存前確認、IF定義の対応可否とAccount適用状態の分離、凍結中の共有Field更新、条件付き復帰を実装する。Threadの既存表示を維持し、新規作成の最新版解決を継続する。Threadの適用済み編集・投稿Snapshot・AccountIF条件の実評価は後続。AccountLayout初期実装はv0.16で公開済み。v0.14と共有interfaces0008の反映は完了した。

詳細: [v0.14要件と移行影響](interface-version-foundation.md)。続くUI／NiiMap調整とAccountLayout初期実装も公開済み。

---

## v0.15 - Pane UI / NiiMap Board

Status: Complete (implementation / isolated verification / published)

Account／Room作成日、細いPaneHeader／座標行、Room座標sticky、Pane端までのborder、NiiMap初期sortのloading／retryを整える。Guest／AccountによるNiiMap Board直接作成から検索・BoardPane・Thread作成・Responseまで接続する。Boardは独立Ownerなし、作成時4欄Policy、保存後変更不可。Thread閲覧／返信はThreadPolicyで判定する。

詳細: [実装と隔離QA](niimap-boards-and-pane-ui.md)。追加migrationはなく、v0.14のinterfaces0008と合わせて公開した。AccountLayout初期実装はv0.16、Thread版編集・Snapshotは後続。

---

## v0.16 - AccountLayout初期実装

Status: Complete (implementation / isolated verification / published)

RequireField／RequireAccountIFと固定版Item、Account共有値を使う自然高さの限定HTML/CSS Profile、Draft作成・公開・適用・取外しを実装した。共有interfaces0009は反映済み。公開と通常serverの読取PC/mobile確認は[v0.16実測記録](account-layout.md#v016公開後の確認2026-10-05)に残す。

RoomLayout、自由参照・Timeline／Boardパーツ、ThreadPost Snapshot等まで完成したという意味ではない。

---

## Version未割当 - Review / Mute / Lists / 公開fav・bad

Status: Complete (implementation / isolated verification / published at `e17e00e`)

[Review](account-review.md)の作者本人CRUD、[公開Mute／Muter](account-mute.md)と閲覧者の表示filter、[AccountList](account-lists.md)、[BoardList／InterfaceList参照と公開fav・bad](board-interface-lists.md)を公開済み。必要なaccounts0003～0005、rooms0010～0011、interfaces0010は共有環境へ適用済みと親工程から引き継いだ。

公開追加機能の新しいVersion番号は未割当。今回の限定QAでは共有状態や公開GETを再照会していない。削除参照・Mute件数の最終UX、ListPolicy、PostgreSQL実並行性などの未検証／未決範囲は[最新QA記録](qa-status-2026-10-06.md)を参照する。

---

## Version未割当 - Room Review / Mute

Status: Complete (implementation / isolated verification / local checkpoint, unpublished)

[Room Review / Mute](room-review-mute.md)を実装した。RoomOwnerも紹介文付きLove / Hateを作成・編集・削除でき、公開RoomMuteはReview・RoomOwner AccountへのMuteと独立する。元配置からRoom / Board / Threadを一覧・検索で隠し、自由参照と直接URL・既存ACLを維持する。AccountPage > RoomにLove / Hateタブを追加し、保存後のnative / shared一覧も更新する。

追加rooms0012は新規2テーブルのみ。開始基準は親から引き継いだ209c6ef（interfaces0011共有反映済み）。今回の共有DB migration・通常server restart・push/publicは未実施。検証結果・残る公開工程はリンク先に記録する。Version番号は割り当てない。

---

## Future

次のVersion番号や実装順序は固定しない。完了済みの基盤全体を未着手候補として扱わない。

将来的な候補として以下を想定する。

### NiiMap

* Thread／Room／Board検索・Filterの拡張（既存検索の基盤は実装済み）
* Current Location
* Distance Search
* Category
* 外部Event API連携
* Event Source / Trust Filter

### Account

* AccountLayoutの追加パーツ／ProfileArea拡張（初期AccountLayoutはv0.16公開済み）
* Account情報管理
* Password Recovery
* Social Login
* MyPageの拡張

### Interface

* AccountIF条件の実評価／ResponseIFの投稿適用など、既存定義基盤の拡張
* ComputedField / Action / 追加Layout
* EventとInterfaceの連携
* RoomとInterfaceの連携

### Room / Board / Collection

* RoomPolicyと参加申請
* Room内Tagと複数管理者
* Collection／Thread参照など、既存Board管理・Board参照の拡張
* Room内部コンテンツを対象にしたNiiMap検索

長期構想は[Vision: Account条件のRoom関係・選択UI](vision/access-policy.md#account条件のroom関係選択uiの長期構想)と[Vision: RoomTag](vision/room-and-niimap.md#roomtagの長期構想)で、Version未割当・未確定事項として管理する。

### Service Integration

* 外部Serviceとの連携
* Niixy Accountによる各Serviceの共通利用

実装順序は、各Versionの開発経験と必要性を基に決定する。
