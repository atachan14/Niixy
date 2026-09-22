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

公開 AccountPage と、Account が作成・返信した Thread を閲覧する ThreadPane を追加する。Account の公開情報と活動履歴を載せる基盤を作り、NiiMap と共通する SummaryList / DetailPane の体験を Account 側へ広げる。

主な対象:

* Guest を含む AccountPage の公開閲覧
* ThreadPost の投稿者から AccountPage への導線
* 固定 AccountPageHeader
* Account が作成・返信した Thread の一覧
* Account 側の Thread 閲覧と返信

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

* Account Profile
* Account情報管理
* Password Recovery
* Social Login
* My Page

### Interface

* Interface作成
* Interface編集
* EventとInterfaceの連携
* CommunityとInterfaceの連携

### Community

* Community作成
* Community参加
* Member管理
* Community内Communication

### Service Integration

* NiiMapとCommunityの連携
* EventからCommunityへの接続
* Niixy Accountによる各Serviceの共通利用

実装順序は、各Versionの開発経験と必要性を基に決定する。
