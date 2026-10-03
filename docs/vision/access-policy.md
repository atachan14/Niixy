# 制限と Policy

## 方向性

Thread は、誰がコンテンツを閲覧・返信・編集・管理できるかを定義できるようにする。将来の条件には Guest 状態、特定 Account、Room の所属やロール、AccountInterface の値、評価値などが含まれる。Room 自体の公開範囲は Room 実装時に設計する。

Thread の発見制限は持たない。Thread がどこに現れるかは ThreadPlacement と掲載先が決め、閲覧 Policy は本文と投稿一覧を開けるかだけを決める。閲覧できない Thread も掲載先の一覧や検索には存在を表示し、開いた先で必要条件を案内できるようにする。

## v0.3 の最小実装

画面の見出しは「Policy」とし、その中に「閲覧制限」「書込制限」を置く。現在設定できる条件は Guest と NiixyAccount のみである。

これは汎用 Policy エンジンの先行実装ではない。現在は固定された二条件だけを確実に保存・判定する。Thread の制限は作成時に確定し、作成後に編集しない。特定 Account、Room、ロール、Interface、評価値などを組み合わせる Policy の設計は、それらを利用する機能と合わせて後続バージョンで行う。

ログイン済み Account の作成者は、自分の Thread を管理するための閲覧・削除権限を常に持つ。各制限に条件が一つもない場合、ログイン済みの作成者以外にはその操作を許可しない。Guest は継続して識別しないため、Guest が作成した Thread を後から削除できない。

## 実装上の原則

閲覧制限は Thread 本文と投稿一覧に、書込制限は返信作成に適用する。すべてサーバー側で再判定するため、URL を直接開いた場合や画面を改変した場合にも制限を回避できない。

編集可能なRoomPolicyとBoardPolicyを実装する前に、条件、継承、監査履歴を設計する。

## Room と Board

Roomは閲覧条件と参加条件をRoomPolicyとして持てる方向で設計する。Guestは参加状態を保持できないため、RoomPolicyにかかわらずRoomへ参加できない。Room参加を必要としない閲覧やGuest投稿の可否は別のPolicyとして扱う。

BoardPolicyとBoard内の個別ThreadPolicyはANDで評価する。v0.6ではRoomPolicyとBoardPolicyの編集を実装せず、ログイン済みAccountはRoomへ即時参加でき、Room参加者だけがBoard内でThread作成とResponse投稿を行える固定ルールを使用する。非参加者とGuestの閲覧可否は個別ThreadPolicyに従う。

## Account条件

作成者検索と将来の汎用Policyでは、Accountを直接指定するだけでなく、Default、Account、AccountIF、Field、Roomから再利用可能なAccount条件を作る。条件はAccountごとの一覧に保存し、使用した条件を先頭へ移動する。一覧からの削除は定義の削除ではなく、そのAccountの一覧から非表示にする操作とする。

呼び出し元に並ぶ条件Item同士はORで評価する。複数条件をANDグループとして追加した場合は、そのグループ内部だけをANDで評価し、グループ全体を一つのItemとして扱う。成立不能な組み合わせの検証は当面行わない。
