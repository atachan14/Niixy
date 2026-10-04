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

### Service Integration

* 外部Serviceとの連携
* Niixy Accountによる各Serviceの共通利用

実装順序は、各Versionの開発経験と必要性を基に決定する。
