# Niixy v0.2 Decisions

v0.2の実装中に確定した設計判断と、その理由を記録する。

---

## Account Does Not Replace Guest Usage

Accountを作成・Loginしなくても、NiiMapの閲覧とEvent投稿は利用できる状態を維持する。

### Reason

Niixyは、AccountをService利用の入口ではなく、利用できる機能を増やす手段として扱う。

---

## Niixy ID and Password Authentication

v0.2ではEmail Addressを要求せず、Niixy IDとPasswordだけでAccount登録・Loginを提供する。

### Reason

登録時の入力と認証を減らし、Guest利用からAccount利用への移行障壁を低くするため。

Emailを登録しないため、v0.2ではPassword Recoveryを提供しない。

---

## Niixy ID Is Public

Niixy IDはLogin IDであると同時に、Eventの投稿者名として公開する。

### Reason

v0.2では表示名を別に持たず、Account登録時の入力項目とData Modelを最小限にするため。

将来表示名を追加する場合は、表示名が未設定のAccountではNiixy IDを表示する。

---

## Guest Events Remain Unowned

Guestが作成したEventを、後から作成またはLoginしたAccountへ紐付ける機能は提供しない。

### Reason

Guestを継続的に識別しない方針のため、AccountとGuest投稿の作成者が同一人物かを確認できない。

---

## Event Management Stays in NiiMap

v0.2では、投稿済みEventの編集・削除はNiiMap上で行う。投稿したEventの専用一覧やMy Pageは作成しない。

### Reason

My Pageは将来、Profile、Community、InterfaceなどNiixy全体の情報を扱う場所になる。目的が固まっていない段階で画面構造を先行して固定しないため。

---

## Django Authentication

v0.2ではDjango標準のAuthenticationとUser Modelを使用する。

### Reason

Niixy IDとPasswordによる基本的なSession Authenticationに、追加のAuthentication Serviceは必要ないため。

Social LoginやService分離が必要になった時点で拡張方法を再検討する。

