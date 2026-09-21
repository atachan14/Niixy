# Interface

## 目的

Interface は Niixy の概念に付与する構造化・再利用可能な情報である。基礎となる Thread モデルを変えずに、Event、募集、質問などの専用形式を表現できるようにする。

## 分類

- AccountInterface: アカウントのプロフィールや資格情報
- RoomInterface: Room の設定やアイデンティティ情報
- ThreadInterface: 将来の Event 情報を含む、Thread 用の専用情報
- ResponseInterface: ThreadPost の返信に付与する専用情報

Interface は作成した Account と名称を名前空間として持つ。既存データを解釈し続けられるよう、スキーマ変更はバージョン管理する。

## DisplayLayout

DisplayLayout は、Room または Thread が ThreadPost 全体の表示項目、順番、サイズ、配置を定める仕組みである。`#1` と返信を含む、すべての ThreadPost に適用する。

対象には、投稿時のニックネーム、Niixy ID、Thumbnail、投稿番号、投稿日時、本文、Policy により実装が保証される AccountInterface のフィールドなどを含める。ThreadInterface や ResponseInterface の表示位置は未決定であり、本文後の Footer などを今後検討する。

用意した Slot と Item を並べる宣言的な Layout は有力な案だが、自由度、実装コスト、仕様の分かりやすさを踏まえて実装時に再検討する。DisplayLayout は、誰でも簡単に編集するための機能ではなく、詳しい利用者が高い自由度でカスタマイズするための機能として想定する。

他者が作成した Thread の DisplayLayout をソースとしてコピーし、編集して別の Thread で再利用したり、保存して使い回したりできるようにする。Thread に適用した DisplayLayout は作成時点のスナップショットとして固定し、後から元の Layout を変更しても既存 Thread の表示は変えない。Layout の保存形式、公開範囲、バージョン管理は後続で決める。

## v0.3 の範囲

v0.3 では汎用 Interface スキーマエンジンも DisplayLayout も作らない。Event のフィールド、募集人数、状態、ResponseInterface は後続に回す。ThreadPost は固定の仮レイアウトで表示し、このレイアウトは将来の DisplayLayout 実装時に置き換える。Thread の基礎は意図して小さく保つ。
