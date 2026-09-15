# Guest Vision

## Overview

Niixyでは、Accountを持たない利用者でも可能な限りServiceを利用できる設計を目指す。

Guestとは特別なAccount種別ではなく、Niixy AccountにLoginしていない利用者を指す。

GuestとしてLoginする仕組みは作成しない。

---

## Identification

Niixy自身は、Guestを継続的に識別するための仕組みを原則として持たない。

Guest識別を目的とした以下の仕組みは使用しない。

* Guest Account
* Guest ID
* Guest Token
* Guest識別目的のCookie
* Guest固有の保存状態

GuestはNiixyから見て匿名の利用者として扱う。

---

## Infrastructure

HTTP通信やHosting Infrastructureの性質上、Web Server、Hosting Provider、Security Service等がIP AddressやRequest情報を処理・記録する可能性がある。

これはNiixy Application自身がGuestを識別する仕組みとは分けて考える。

Niixyとして「通信上あらゆる情報が一切処理されない」ことを保証するものではない。

---

## Guestが作成したEvent

NiiMapではGuestもEventを作成できる。Guestが作成したEventも、Accountが作成したEventと同じEventとして扱う。

Guestを識別しないため、Guestが作成したEventに対するGuest本人のOwnershipは管理しない。

その結果、Guestは投稿後に以下を行えない。

* Event編集
* Event削除
* Ownership確認
* AccountへのOwnership移行

Guestが作成したEventはAdminによる管理対象とする。

---

## Trust

Eventの作成者に関する情報は、Eventの種類を分けるのではなく、creator Accountの有無やAccountInterfaceによって確認できるようにする。

将来的には利用者がEvent SourceやTrust Levelによって表示対象をFilterできるようにする。

例:

* Accountに紐づかないEventを含む
* Accountに紐づかないEventを除外
* creator AccountのあるEventのみ
* 運営Interfaceを実装したAccountが作成したEventのみ

Guest投稿自体を禁止するのではなく、閲覧者側が情報の性質を判断・選択できる仕組みを目指す。

---

## Abuse Prevention

Guest投稿によるSpamやAbuseが問題になった場合、必要に応じて以下を検討する。

* Rate Limit
* CAPTCHA
* Report
* Moderation
* Adminによる削除
* その他のAbuse対策

初期Versionでは、実際に必要になる前から複雑なAbuse Prevention Systemを構築しない。
