# NiiMap Vision

## Overview

NiiMapは、現実世界の「場所」と「時間」を基点として、人とEventを接続するNiixyのMapサービスである。

Mapを中心としたUIによって、「どこで・いつ・何が起きているか」を視覚的に発見できることを目指す。

NiiMap単体でも利用価値を持つサービスとし、Niixy AccountへのLoginを利用開始の条件としない。

---

## Basic Experience

NiiMapへアクセスした利用者には、LoginやAccount作成を要求せずMapを表示する。

利用者はMap上からEventを探し、詳細を確認できる。

GuestもEventを投稿できる。

Niixy AccountでLoginすることで、自身が作成したEventの管理やInterfaceなど、追加機能を利用できるようにする。

---

## Event

NiiMapでは、Map上に表示される出来事をEventとして扱う。

Eventは主に以下の情報を持つことを想定する。

* 場所
* 開始日時
* 終了日時
* Event名
* Event詳細
* Event作成元

正確なData Modelは各VersionのRequirementsで決定する。

---

## Event Creator

NiiMapでは、GuestとAccountのどちらから作成されたEventも、同じEventとして扱う。

将来的にはEventに`creator_account_id`を持たせ、Accountに紐づくEventと、Accountに紐づかないEventを区別できる構造を目指す。

* Guestが作成したEvent：`creator_account_id`を持たない
* Accountが作成したEvent：作成したAccountのIDを持つ
* 運営Accountが作成したEvent：運営Interfaceを実装したAccountのIDを持つ

Eventの表示やFilterでは、Eventを別種類に分けるのではなく、creator AccountやAccountInterfaceの情報を参照する。

---

## Search and Filter

将来的には、以下の条件によるEvent検索を想定する。

* Date
* Time
* Location
* Distance
* Category
* Keyword
* creator Accountの有無
* 運営Interfaceの有無
* その他のTrust Level

Guestが作成したEventを禁止するのではなく、利用者がcreator AccountやAccountInterface、Trust Levelによって表示対象を選択できる設計を目指す。

---

## External Events

将来的に外部Event ServiceのAPI等からEventを取得し、NiiMap上へ表示することを検討する。

外部Eventは、必要に応じて運営Accountが投稿するEventとしてNiixy内部で扱う。

Concept:

External Source
→ Normalized Event
→ Database
→ NiiMap

想定Dataには以下が含まれる。

* title
* description
* starts_at
* ends_at
* latitude
* longitude
* source_url

外部サービス由来であることを別途保持する必要が生じた場合は、Eventのcreator Accountとは別の情報として追加する。

具体的なAPI、同期方式、Data Modelは実装Versionで決定する。

---

## Account Integration

NiiMap独自のAccount Systemは作成しない。

Niixy Accountを共通Accountとして使用する。

将来的にはLoginによって以下の機能を利用可能にすることを想定する。

* 自身のEvent管理
* Event編集
* Event削除
* Event保存
* Event参加
* Interface利用
* Communityとの連携
* その他Account固有機能

---

## Future Architecture

NiiMapはNiixyのServiceとして設計する。

将来的にSubdomainや独立したApplicationとして提供する可能性は残す。

例:

* niixy.com/map/
* map.niixy.com

ただし、Service境界とSystem境界は分けて考える。

将来の分離を想定して、現在のVersionから不要なMicroservice化や認証基盤の分離を行わない。
