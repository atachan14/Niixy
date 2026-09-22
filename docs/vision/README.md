# Niixy Vision

## 位置づけ

このディレクトリは、Niixy のプロダクト・設計方針における正本である。

Niixy は次の七つの概念を中心にする。

- Account: Niixy を利用する人
- Room: Account が作成・管理する場所
- Thread: NiiMap、Room、または Book で作られる会話
- ThreadPost: Thread の開始投稿または時系列の返信
- Book: Thread をテーマごとにまとめ、公開・購読できるコレクション
- Interface: Account、Room、Thread、ThreadPost に付与する構造化・再利用可能な情報
- NiiMap: コンテンツを発見・作成する地図サービス

以前の Event 中心・Pin 中心の考え方は置き換えられた。Event は基礎モデルではなく、将来の ThreadInterface の一つとする。

## 文書

- [コンテンツモデル](content-model.md): Thread、ThreadPost、掲載、スナップショット、活動日時
- [Room と NiiMap](room-and-niimap.md): Thread が存在・発見される場所
- [制限と Policy](access-policy.md): アクセス制御の方向性と v0.3 の範囲
- [Interface](interfaces.md): Interface の分類と保留する汎用機能
- [Account と履歴](account-and-history.md): アカウントページ、Book、Album、将来の履歴
- [表示パターン](presentation.md): SummaryList、SummaryItem、DetailPane の役割
- [決定記録](decisions.md): 設計判断の時系列ログ
- [v0.3 要件定義](../v0.3/requirements.md): Vision から導いた実装範囲

## 旧文書

Event 中心だった旧文書は、履歴参照用として `archive/` に残す。Event と Community の旧用語を使うため、新規実装の正本にはしない。
