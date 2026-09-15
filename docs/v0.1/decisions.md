# NiiMap v0.1 Decisions

v0.1の開発中に決定した重要事項と、その理由を記録する。

---

## Python / Django

BackendにはPython / Djangoを使用する。

### Reason

Niixyは将来的にAccount、Authentication、Permission、Database、Admin等を必要とするServiceへ拡張する予定である。

小規模な構成から開始でき、これらの機能へ拡張しやすいDjangoを採用する。

---

## Web Application First

初期VersionはNative Mobile ApplicationではなくWeb Applicationとして開発する。

### Reason

URLからすぐ利用でき、Application InstallationやStore Distributionを必要としないため。

特にNiiMapでは「Loginせず、すぐMapを利用できる」ことを重視する。

---

## Niixy and NiiMap

Niixyを上位Project / Brandとし、NiiMapをNiixyが提供するServiceとして扱う。

v0.1ではNiiMapをNiixyから独立したSystemとして実装しない。

### Reason

将来的にはNiiMap、Community、Interface等がNiixy Accountを共有する構想がある。

一方で、現在から各Serviceを独立Systemとして実装すると不要なArchitecture Complexityが発生する。

Serviceとしての境界とSystemとしての境界は分けて考える。

---

## Guest Does Not Login

Guest Loginは実装しない。

Niixy AccountにLoginしていない利用者をGuestとして扱う。

### Reason

NiiMapはAccount作成を利用開始の条件とせず、URLへアクセスした時点から利用できるServiceを目指すため。

---

## Initial Map Position

初回表示時にブラウザの位置情報を一度だけ取得し、許可された場合は現在地周辺を初期表示する。

位置情報が拒否・取得失敗・未対応の場合は既定地点を表示する。Eventの分布に応じて初期表示範囲を広げない。

現在地はServerやDatabaseへ保存せず、継続的な位置追跡も行わない。

### Reason

離れた地域のEventが混在しても、利用者がまず自分の周辺を見られる状態にするため。

---

## Guest Identification

Niixy ApplicationはGuestを継続的に識別するためのGuest ID、Guest Token等を持たない。

### Reason

Guest利用をAccount Systemの簡易版として扱わず、匿名状態のままServiceを利用できることを基本方針とするため。

---

## Guestが作成したEventのOwnership

Guestが作成したEventのOwnershipは管理しない。

Guestは投稿後にEventを編集・削除できない。

### Reason

Guestを識別しない方針と、Guestが作成したEventのOwnership管理は両立しないため。

---

## Guestが作成したEventのAccount移行

Guestが作成したEventを、後から作成したNiixy Accountへ移行する機能は実装しない。

### Reason

Guestを識別しないため、Account作成者と過去にGuestとしてEventを作成した利用者が同一人物であることをNiixy側で確認できないため。

---

## Architecture

v0.1では将来的なService分離を理由としたMicroservice Architecture、SSO、独立Authentication Service等を実装しない。

必要になった時点で再検討する。

### Reason

将来の可能性だけを理由に初期Architectureを複雑化しないため。
