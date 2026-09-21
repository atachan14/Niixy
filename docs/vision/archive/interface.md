
# Interface Vision

## 概要

Interface は、Event や Community などの「場」で必要となるプロフィール情報の構造を定義する仕組み。

ユーザーは接続先に応じた Interface を実装し、その場に適した情報を持った状態で参加・交流する。

---

## EventInterface と AccountInterface

`EventInterface` と `AccountInterface` は、同じ Interface を使い回すものではなく、異なる対象に紐づく仕組みとして扱う。

### EventInterface

`EventInterface` は Event に紐づき、その Event が扱う情報や参加条件、検索・フィルタリング項目などを定義する。

例：

* 出会いを目的とした Event
* 企業説明会
* ゲームの募集

EventInterface は、Event がどのような情報を求め、どのような条件で参加者を扱うかを表現する。

### AccountInterface

`AccountInterface` は Account に紐づき、ユーザーが自分の属性、目的、立場などを表現するための仕組みとする。

AccountInterface は特定の Event や Community への参加を前提としない。Event や Community で利用できるほか、Interface を条件とした Account の検索や表示にも利用する。

EventInterface や Community が、必要に応じて AccountInterface の情報を参照・要求する関係を想定する。

---

## 例

### Player Interface

ゲーム Community などで利用する。

* プレイヤー名
* メインキャラクター
* ランク
* 使用デバイス
* 活動時間
* VC 可否

### Company Interface

企業 Event などで利用する。

* 企業名
* 業種
* 募集職種
* 企業 URL
* 対象者

### Participant Interface

交流 Event などで利用する。

* 年齢
* 趣味
* 参加目的
* 希望する交流内容

---

## 今後検討すること

* Interface の作成方法
* フィールドの定義方法
* 必須項目 / 任意項目
* Interface の再利用
* Interface の編集
* Interface と Account の関係
* Event / Community が Interface を要求する仕組み
* 一人のユーザーが複数の Interface をどのように管理するか

具体的なデータ構造については未確定。
