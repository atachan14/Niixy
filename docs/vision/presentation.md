# 表示パターン

## SummaryList と SummaryItem

SummaryList は、詳細表示の前に対象を要約して並べる一覧の表示パターンである。Thread、Room、Response、Tweet、Book など、異なる種類の対象に使える。SummaryItem は SummaryList 内の一件の要約表示である。

各 SummaryItem は、対象ごとに異なる Header と概要情報を持つ。Item を選択すると、対応する DetailPane を直接開く。SummaryList 内で概要を展開するアコーディオンや、追加の「詳細を見る」操作は設けない。

SummaryList はコンテンツの上位ドメイン概念ではない。Thread、Room、Response、Tweet、Book を同じデータモデルへ統合することを意味せず、一覧・選択・詳細表示という体験を共通化するための名称である。

## DetailPane

DetailPane は、SummaryItem で選択した対象の内容を閲覧し、対象に許可された操作を行う領域である。ThreadDetailPane では ThreadPost の閲覧と Response 投稿を扱い、InterfaceDetailPane では Interface の閲覧、Draft 編集、対象への実装値入力を扱う。NiiMap の Thread 新規作成は Map との同時操作を必要とするため、ThreadDetailPane ではなく Thread 一覧Paneで扱う。対象の種類ごとに内容と操作は異なるが、SummaryList から詳細へ進む導線は共通の表示パターンとして扱う。
