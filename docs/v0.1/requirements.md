# NiiMap v0.1 Requirements

## Goal

Account登録やLoginを必要とせずNiiMapを利用でき、Map上のEventを閲覧し、匿名のGuestとしてEventを投稿できるWeb Applicationを完成させる。

---

## Technology

v0.1では以下を基本構成とする。

* Python
* Django
* PostgreSQL
* Django Template
* HTML
* CSS
* Vanilla JavaScript
* Geolonia (MapLibre GL JS)

開発環境ではLocal PostgreSQLを使用する。

Production環境のDatabaseとしてSupabase PostgreSQLを候補とする。

HostingはKoyebを第一候補とする。

具体的なProduction構成はDeploy時に決定する。

---

## NiiMap

### Map

* NiiMapへアクセスするとLoginを要求せずMapを表示する。
* Databaseに保存されたEventをMap上へMarkerとして表示する。
* MarkerまたはEvent一覧から、Eventの概要を確認できる。
* 開始・終了日時と開催状態を条件に、表示するEventを絞り込める。

### Event Information

EventごとのDetail Pageは持たず、Map右Paneのアコーディオンで内容を確認する。

最低限、Eventを識別し内容を確認できる情報を表示する。

具体的な表示項目はEvent Data Model決定時に定義する。

---

## Event Creation

GuestはNiixy Accountを作成せずEventを投稿できる。

投稿されたEventはPostgreSQLへ保存し、NiiMap上へ表示する。

Event作成に必要なFieldは実装開始前に決定する。

候補:

* title
* description
* capacity
* starts_at
* ends_at
* latitude
* longitude
* created_at
* updated_at

候補はRequirements確定時に追加・削除できる。

---

## Time Filter

初期状態では、開始日時が現在以降のEventを表示する。

終了日時が空欄のEventは、開始日時を実質的な終了日時として扱う。

期間指定と開催状態はOR条件で評価する。

* 期間指定: 開始日時以降、終了日時以前
* 真っ最中: 開始済みかつ実質終了日時が現在以降
* 今日: 今日の時間帯に重なるEvent
* 明日: 明日の時間帯に重なるEvent
* 終了済み: 実質終了日時が現在より前

期間指定の終了日時が空欄の場合は、上限を設けない。

---

## Guest

GuestとはNiixy AccountにLoginしていない利用者を指す。

GuestとしてLoginする仕組みは作成しない。

v0.1ではGuest識別を目的とした以下を実装しない。

* Guest Account
* Guest ID
* Guest Token
* Guest識別目的のCookie
* Guest固有の保存状態

Guestが作成したEventのOwnershipは管理しない。

そのためGuestは投稿後に自身のEventを編集・削除できない。

---

## Event Creator

v0.1では、Guestが作成したEventもAccountが作成したEventも、同じEventとして扱う。

v0.1ではAccount機能を実装しないため、すべての投稿EventはAccountに紐づかない。

将来Account機能を追加する際は、Eventにnullableな`creator_account_id`を持たせ、作成したAccountと関連付けられる構造を選択する。

---

## Admin

Django AdminからEventを確認できる。

AdminはEventを編集・削除できる。

Guestが作成したEventもAdmin管理対象とする。

---

## Out of Scope

以下はv0.1では実装しない。

* Niixy Account
* Login / Logout
* Interface
* Community
* AccountによるEvent管理
* Event参加
* Comment
* Follow
* Direct Message
* Notification
* 外部Event API連携
* 高度なEvent検索
* 高度なFilter
* PostGIS
* Guestが作成したEventのAccount移行
* GuestによるEvent編集・削除
* 本格的なSpam Prevention
* Native Mobile Application
* Service分離
* Microservice Architecture
* SSO

---

## Completion Flow

以下のFlowが成立すればv0.1の基本要件を満たす。

1. 利用者がNiiMapへアクセスする。
2. Account登録やLoginを要求されずMapが表示される。
3. Map上のEventを確認する。
4. Map右PaneでEventの概要を確認する。
5. Guestとして新しいEventを作成する。
6. 作成したEventがDatabaseへ保存される。
7. 作成したEventがNiiMap上へ表示される。
8. AdminがDjango AdminからEventを確認・管理できる。

---

## Undecided

実装開始前または実装中に以下を決定する。

* Production構成
