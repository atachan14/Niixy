# Niixy Concept

## Overview

Niixyは、Interfaceを介して人と場を接続するサービス群である。

Niixy AccountとInterfaceを共通基盤とし、その上に目的の異なる複数のサービスを提供する。

主要なサービスとして、現実世界の場所と時間を基点とする「NiiMap」と、継続的な人間関係を基点とする「Community」を構想する。

---

## Service Structure

Niixyは単一機能のSNSではなく、共通のAccountとInterfaceを利用する複数のサービスから構成する。

### NiiMap

現実世界の「場所」と「時間」を基点として、人とEventを接続するサービス。

Mapを中心としたUIを持ち、現在地や任意の場所からEventを発見できることを目指す。

NiiMapはNiixy Accountを持たない利用者でも使用できる。

ログインしていない状態でもMapやEventを閲覧でき、GuestとしてEventを投稿できる。

Niixy Accountでログインすることで、自身のEvent管理やInterfaceなど、より多くの機能を利用できるようにする。

### Community

継続的な人間関係を基点として、人と人を接続するサービス。

一時的なEventとは異なり、特定の目的・趣味・活動などを共有する人々が継続的に関係を持つ場として構想する。

### Interface

利用者がEventやCommunityなどの「場」と接続する際に使用する情報の集合。

一般的なProfileが「私はこういう人です」を表すのに対し、Interfaceは「この場では、この情報を使って接続します」を表す。

Interfaceの内容は利用するEventやCommunityなどの文脈によって変化し得る。

---

## Account

Niixy Accountは、Niixyの各サービスで共通して使用するAccountである。

Accountの作成やログインは、Niixyのすべての機能を利用するための入口とはしない。

各サービスは可能な範囲でAccountなしでも利用できるようにし、Accountを作成することで利用可能な機能が増える設計を基本とする。

> まず使える。Accountを作成すると、できることが増える。

---

## Guest

NiixyにおけるGuestとは、Guest AccountやGuest Sessionにログインした利用者ではない。

**Niixy Accountにログインしていない利用者をGuestとして扱う。**

Guestを識別するためのGuest ID、Guest Token、Guest Accountなどは原則として作成しない。

Guest固有の状態を保存することも基本的には行わない。

ただし、Webサーバーやホスティング基盤などがHTTP通信の過程でIP Address等を処理・記録することは、Niixy自身によるGuest識別とは分けて考える。

---

## Principle

Niixyでは、Account作成をサービス利用の前提にしない。

利用者がまずサービスそのものを体験でき、その後必要に応じてAccountを作成する設計を基本とする。

NiiMapであれば、URLへアクセスした時点でMapを表示し、Eventの探索を開始できる状態を目指す。

Loginはサービスへの入口ではなく、機能を拡張するための手段として扱う。
