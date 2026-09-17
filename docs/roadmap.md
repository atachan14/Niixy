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

Niixy IDとPasswordによるAccount登録・Loginを追加し、Loginした利用者が自身のEventを管理できる状態を完成させる。

主な対象:

* Niixy ID / PasswordによるAccount登録
* Login / Logout
* LoginしたAccountとEventの紐付け
* 作成者表示
* 自身が作成したEventの編集・削除
* 自身が作成したEventでのNiiMap Filter

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
