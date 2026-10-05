# 制限と Policy

## 方向性

Thread は、誰がコンテンツを閲覧・返信・編集・管理できるかを定義できるようにする。将来の条件には Guest 状態、特定 Account、Room の所属やロール、AccountInterface の値、評価値などが含まれる。Room 自体の公開範囲は Room 実装時に設計する。

Thread の発見制限は持たない。Thread がどこに現れるかは配置先と参照が決め、閲覧 Policy は本文と投稿一覧を開けるかだけを決める。閲覧できない Thread も配置先や参照元の一覧と検索には存在を表示し、開いた先で必要条件を案内できるようにする。

## v0.3 の最小実装

画面の見出しは「Policy」とし、その中に「閲覧制限」「書込制限」を置く。現在設定できる条件は Guest と NiixyAccount のみである。

これは汎用 Policy エンジンの先行実装ではない。現在は固定された二条件だけを確実に保存・判定する。Thread の制限は作成時に確定し、作成後に編集しない。特定 Account、Room、ロール、Interface、評価値などを組み合わせる Policy の設計は、それらを利用する機能と合わせて後続バージョンで行う。

ログイン済み Account の作成者は、自分の Thread を管理するための閲覧・削除権限を常に持つ。各制限に条件が一つもない場合、ログイン済みの作成者以外にはその操作を許可しない。Guest は継続して識別しないため、Guest が作成した Thread を後から削除できない。

## 実装上の原則

閲覧制限は Thread 本文と投稿一覧に、書込制限は返信作成に適用する。すべてサーバー側で再判定するため、URL を直接開いた場合や画面を改変した場合にも制限を回避できない。

編集可能なRoomPolicyとBoardPolicyを実装する前に、条件、継承、監査履歴を設計する。

## Room と Board

Roomは閲覧条件、参加条件、管理条件をRoomPolicyとして持てる方向で設計する。Guestは参加状態を保持できないため、RoomPolicyにかかわらずRoomへ参加できない。Room参加を必要としない閲覧やGuest投稿の可否は別のPolicyとして扱う。

BoardPolicyはBoard自体の閲覧、編集、Thread作成などを制限する。Threadの閲覧とResponse投稿は、作成時に確定した個別ThreadPolicyで判定する。BoardPolicyとThreadPolicyを作成後も永続的にAND評価する構造にはしない。

RoomのBoardTemplateとBoardのThreadTemplateは、子対象を作成するときのField、Interface、Policy、Layout、子Templateの初期値を定める。推奨値は変更でき、強制値はUIとサーバーで変更を拒否する。作成後も編集可能な設定を編集するときは、その時点の親Templateの強制値を再適用する。ThreadPolicyは作成後変更不可なので作成時にだけ確定保存し、親Templateの後日変更や親Boardの削除で変えない。Template自体はv0.10の実装範囲に含めない。

## Account条件

作成者検索と将来の汎用Policyでは、Accountを直接指定するだけでなく、Default、Account、AccountIF、Field、Roomから再利用可能なAccount条件を作る。条件はAccountごとの一覧に保存し、使用した条件を先頭へ移動する。一覧からの削除は定義の削除ではなく、そのAccountの一覧から非表示にする操作とする。

呼び出し元に並ぶ条件Item同士はORで評価する。複数条件をANDグループとして追加した場合は、そのグループ内部だけをANDで評価し、グループ全体を一つのItemとして扱う。成立不能な組み合わせの検証は当面行わない。

## Account条件のRoom関係・選択UIの長期構想

状態: 長期構想 / Version未割当 / 未確定設計。動的RoomOwner条件・RoomTag条件・以下の選択UIはv0.10・v0.11では実装しない。

### 動的RoomOwner条件

現在のRoomOwnerを評価するAccount条件を将来追加し、Owner変更に追従させる。現行のRoom管理操作にあるowner_idの直接判定と、Account条件としての動的RoomOwner評価は別である。

初期「お知らせ」BoardのThread作成条件には当面、Room作成時の作成者のNiixyID（特定Account Snapshot）を固定保存する方針。初期Board構成自体はv0.10後の別作業である。両初期Boardの公開閲覧、新規Room限定、通常の作成後管理などの具体要件は[BL-003](../backlog.md#bl-003---新規roomの初期board構成をお知らせ掲示板にする)へ記録する。動的RoomOwner条件へ移す際はこの固定Account条件の扱いを検討する。Owner変更操作そのもの、複数管理者、既存データの移行詳細は未設計とする。

### Account条件のRoom選択パネル

Account条件追加Pane → 新しい条件を探す → RoomTab → RoomSummaryItemをクリックした際、即座にRoom参加者条件を追加する代わりに、アコーディオン状のPanelを展開する案。

Panel内でRoom参加者・Room管理者・RoomOwner・各RoomTag適用者を選ぶ。RoomTagの意味と管理権限は[RoomTagの長期構想](room-and-niimap.md#roomtagの長期構想)で未確定事項として扱う。

現在のRoomItem選択はRoom参加者条件を履歴へ保存し、Policyへの条件グループ追加は別操作である。将来Panelの詳細挙動、履歴保存タイミング、グループ追加導線は未確定とする。

### その他の条件選択UI

さらに将来、Account条件のField選択も似たPanel方式を検討する。入力が多いAccountIF条件はWorkspaceのPaneを展開する案とする。条件選択の既存AccountTabをIDTabへ改称する案も保存する。いずれも時期、改称範囲、既存構想との整合は未確定である。

これは将来の検討事項であり、今回の実装範囲拡大や通常DBmigrationを承認するものではない。
