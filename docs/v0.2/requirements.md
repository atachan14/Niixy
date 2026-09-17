# Niixy v0.2 Requirements

## Goal

Niixy IDとPasswordでAccountを作成・Loginできるようにし、Loginした利用者が自分で作成したEventをNiiMap上で管理できるWeb Applicationを完成させる。

Guestは引き続きLoginなしでNiiMapを閲覧・投稿できる。

---

## Account Registration

利用者はNiixy IDとPasswordでAccountを登録できる。

### Niixy ID

* Accountごとに一意とする。
* Login IDと公開される投稿者名の両方に使用する。
* 3文字以上20文字以下とする。
* 使用できる文字は英小文字、数字、`_`のみとする。
* 大文字は使用せず、小文字として扱う。

### Password

* 8文字以上とする。
* 文字種の組み合わせは強制しない。
* Email Addressは登録時に要求しない。
* v0.2ではPasswordを忘れた場合の復旧機能を提供しない。

---

## Authentication

* 利用者はNiixy IDとPasswordでLoginできる。
* Login中の利用者はLogoutできる。
* 新規登録が完了した利用者は、自動的にLogin状態にする。
* GuestはNiiMapの閲覧・Event投稿にLoginを要求されない。

### Header

* Guestには`新規登録`と`ログイン`を表示する。
* Login中はNiixy IDを表示する。
* Niixy IDのメニューにはv0.2では`ログアウト`を配置する。
* 新規登録とLoginは、NiiMapを離れずOverlayで入力できる。

---

## Event Ownership

* EventはAccountに紐付かないGuest投稿と、Accountに紐付く投稿の両方を扱う。
* Login中に作成したEventは、作成したAccountへ自動的に紐付ける。
* Guestとして作成したEventはAccountに紐付けない。
* Guest投稿を後からAccountへ移行する機能は提供しない。
* Event一覧には投稿者としてNiixy IDまたは`ゲスト`を表示する。

---

## Event Management

* Login中の利用者は、自身が作成したEventだけを編集・削除できる。
* 編集はNiiMap右Paneの投稿フォームを編集モードとして使用する。
* 編集では既存の入力値と地点を引き継ぎ、Map上で地点を変更できる。
* 削除前には確認を求める。
* Guestは投稿後のEventを編集・削除できない。

---

## Account Filter

v0.2の最後に、Login中の利用者が自身の投稿したEventをNiiMap上で絞り込めるようにする。

* 時間条件とは別の条件として扱う。
* Filterの具体的なUIと、Guest投稿・Account投稿の表示条件は、Account機能の実装後に決定する。

---

## Out of Scope

以下はv0.2では実装しない。

* Email Addressの登録・認証
* Password Recovery
* Google、XなどによるSocial Login
* 表示名、プロフィール、画像、日記
* My Page
* 投稿したEventの専用一覧ページ
* Event参加、参加承諾、質問、参加者管理
* Interface
* Community
* Guest投稿のAccountへのOwnership移行
