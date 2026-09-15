# Account Vision

## Overview

Niixy Accountは、Niixyが提供する各Serviceで共通して使用するAccountである。

Account作成やLoginはNiixyを利用するための必須条件とはしない。

> まず使える。Accountを作成すると、できることが増える。

この考え方をNiixy全体の基本方針とする。

---

## Shared Account

NiiMap、Community、Interfaceなどで個別のAccount Systemを作成せず、Niixy Accountを共通して使用する。

利用者は一つのNiixy Accountで各Serviceを利用できることを目指す。

---

## Guest to Account

Guestとして利用した後、必要に応じてNiixy Accountを作成できる。

ただし、Guestを識別・追跡しない方針のため、Guest状態で作成したDataを後からAccountへ自動的に紐付けることは原則として行わない。

特にGuestが作成したEventについては、後から作成したAccountへの所有権移行を行わない。

---

## Account Features

将来的にAccountによって利用可能になる機能として、以下を想定する。

* Login / Logout
* Account情報の編集
* Interfaceの作成・編集
* 自身が作成したEventの管理
* Event保存
* Event参加
* Community作成
* Community参加
* その他、User固有のDataを必要とする機能

具体的な機能は各Versionで決定する。

---

## AccountInterface

AccountInterfaceはAccountに紐づき、ユーザーが自分の属性、目的、立場などを表現するための仕組みとする。

AccountInterfaceは特定のEventやCommunityへの参加を前提としない。EventやCommunityで利用できるほか、Interfaceを条件としたAccountの検索や表示にも利用する。

運営Accountは、運営Interfaceを実装したAccountとして扱う。運営InterfaceはEventの作成者表示やFilterなどに利用できるが、Django Admin等の管理権限とは別に管理する。

---

## Authentication Architecture

具体的なAuthentication方式は、Account機能を実装するVersionで決定する。

将来的にNiiMap等をSubdomainまたは別Applicationへ分離する可能性は考慮するが、初期VersionからSSOや分散Authentication等を先行実装しない。
