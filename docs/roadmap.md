# Niixy Roadmap

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

Status: Complete (local implementation / isolated SQLite verification)

Threadの閲覧とResponse投稿を共通Account条件・Policy評価器へ移行し、条件設定と不可表示を各導線で揃える。Templateは別Versionで扱う。移行、初期値、閲覧不可時のメタ情報公開範囲は合意済み。共有DBへのmigrationは未実施。

詳細: [v0.10要件](v0.10/requirements.md)

---

## v0.11 - Room初期Board / Board作成Policy

Status: Complete (local implementation / focused verification)

新規RoomのMainに「お知らせ」「掲示板」を生成し、手動Board作成で共通Account条件UIによる4欄Policy設定を可能にする。既存Roomの移行・Template・動的RoomOwnerは対象外。

詳細: [v0.11要件](v0.11/requirements.md)。関連: [Backlog BL-001 / BL-003](backlog.md)。

---

## v0.12 - Account Applied

Status: Complete (local implementation / focused verification)

MyPageでAccountへ直接Field／AccountIFを適用・値編集・取外しできるようにし、公開AccountPageのApplied一覧にField／AccountIFを表示する。固定版とAccount内共有Valueを扱い、Value更新日時で一覧を並べる。Moduleと将来ProfileLayout欄は別機能として維持する。

詳細: [v0.12要件](v0.12/requirements.md)。schema migration 0007は共有Neonへ適用済み。公開版の確認結果は別途確認する。

---

## v0.13 - Account Board / Collection

Status: Complete (implementation / isolated verification; release approved)

AccountのBoard一覧Pane、本人向けCollection／Board管理、Main／日記／未分類の初期生成とBoardからThread投稿までをRoom共通処理で実装する。fav／badは未実装Tab枠に揃える。返信は各ThreadPolicyで決める。

詳細: [v0.13要件](account-boards.md)。既存Accountへのrooms 0009はCollectionを一つも持たないAccountだけを対象とする一度限りのデータ追加。自動migrationを行うVercel本番buildでは、新コード公開後に0009を追加する二段階で反映する。

---

## Version未割当 - Interface / Field版更新・凍結／復帰

Status: Local implementation / isolated verification; shared migration and release pending

Accountの最新版編集・保存前確認、IF定義の対応可否とAccount適用状態の分離、凍結中の共有Field更新、条件付き復帰を実装する。Threadの既存表示を維持し、新規作成の最新版解決を継続する。Threadの適用済み編集・Layout本体・投稿Snapshot・AccountIF条件の実装は後続。まとめ番号候補はv0.14だが未確定とする。

詳細: [未割当要件と移行影響](interface-version-foundation.md)。基盤の一区切り後は承認済みUI／NiiMap調整を挟み、その後AccountLayoutへ進む。

---

## Future

v0.1以降のVersion番号や実装順序は固定しない。

将来的な候補として以下を想定する。

### NiiMap

* Event検索
* Event Filter
* Current Location
* Distance Search
* Category
* 外部Event API連携
* Event Source / Trust Filter

### Account

* ProfileArea / ProfileLayout
* Account情報管理
* Password Recovery
* Social Login
* MyPageの拡張

### Interface

* AccountInterface / ResponseInterface
* ComputedField / Action / Layout
* EventとInterfaceの連携
* RoomとInterfaceの連携

### Room / Board / Collection

* RoomPolicyと参加申請
* Room内Tagと複数管理者
* BoardPolicy
* BoardとCollectionの管理・参照
* Room内部コンテンツを対象にしたNiiMap検索

長期構想は[Vision: Account条件のRoom関係・選択UI](vision/access-policy.md#account条件のroom関係選択uiの長期構想)と[Vision: RoomTag](vision/room-and-niimap.md#roomtagの長期構想)で、Version未割当・未確定事項として管理する。

### Service Integration

* 外部Serviceとの連携
* Niixy Accountによる各Serviceの共通利用

実装順序は、各Versionの開発経験と必要性を基に決定する。
