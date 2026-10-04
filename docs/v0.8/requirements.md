# v0.8 Collection Management 要件

Status: Complete

## 目的

RoomOwnerがRoom内のCollectionを追加・編集・削除し、Boardの配置先をCollection単位で管理できる状態を完成させる。

v0.8ではRoom配下のCollection管理を対象とする。CollectionやBoardの参照、Collectionの並び替え、Account側のCollection管理、Boardの配置先変更は後続Versionへ回す。

## 対象範囲

- RoomOwnerによるCollectionの新規作成、名称編集、削除
- 選択中CollectionへのBoard作成
- 常設のシステムCollection`未分類`
- Collection削除時の配置Board退避
- 通常Collection、未分類、管理のTab構成
- Collectionの詳細確認、編集、Board作成UI
- 管理操作の権限、Validation、既存RoomへのMigration

## Collection

CollectionはBoardをまとめるコンテナであり、AccountまたはRoomのどちらか一つに属する。v0.8ではRoomに属するCollectionだけを画面から管理する。

Room作成時には、通常Collection`Main`とシステムCollection`未分類`を作成し、`最初のBoard`をMainへ配置する。`Main`は初期名称にすぎず、通常Collectionと同じく名称変更と削除を認める。

通常Collectionは作成順に表示する。新規Collectionは通常Collection群の末尾へ追加する。

## 未分類

`未分類`はCollection削除時のBoard退避先として、すべてのRoomに一つだけ常設する。既存RoomにもMigrationで追加する。

- 名称は`未分類`で固定する。
- 名称変更と削除を認めない。
- 将来の並び替えでも移動を認めない。
- Boardの作成先に指定できる。
- 上記以外は通常Collectionと同様にBoardを保持・表示する。

通常Collectionを削除した場合、そのCollectionに配置されているBoardを同じRoomの`未分類`へ移してからCollectionを物理削除する。Board、Board内Thread、Responseは削除しない。

## Board一覧

RoomPageの`Board`ボタンからBoard一覧Paneを開く。Pane上部のTabは次の順に表示する。

1. 作成順の通常Collection
2. `未分類`
3. RoomOwnerだけに表示する`管理`

`管理`はCollection実体ではなく管理UIである。Collection作成は管理Tab内で行う。

各Collection Tabでは、そのCollectionに配置されたBoardをSummaryListとして表示する。BoardのSummaryItemはBoard名、Thread数、最終更新日時を表示し、クリックすると既存のBoard内Thread一覧Paneを開く。

## Collection操作UI

各Collection Tabの先頭には`詳細確認`と、RoomOwner向けの`Board作成`を配置する。二つの操作窓は排他的に展開し、展開中のボタンは`キャンセル`へ切り替える。

詳細確認ではCollection名とBoard数を表示する。通常CollectionではRoomOwnerだけに`編集`を表示し、同じ領域を編集状態へ切り替えて名称変更と削除を行う。`未分類`では編集を表示しない。

Board作成ではBoard名を入力し、対象Boardを現在選択中のCollectionへ配置する。`未分類`も作成先として利用できる。RoomOwner以外にはBoard作成を表示せず、直接POSTされた場合もサーバー側で拒否する。

## Security

- CollectionとBoardの管理操作にはLoginを必要とする。
- Collection作成、編集、削除とBoard作成ではRoomOwnerかをサーバー側で再確認する。
- 対象Collectionが指定Roomに属していることを確認する。
- `未分類`への編集・削除要求はUIの有無にかかわらずサーバー側で拒否する。
- Collection削除とBoard退避は同一Transactionで処理する。

## 完了条件

- RoomOwnerが複数の通常Collectionを作成できる。
- 通常Collectionの名称を変更できる。
- 選択中Collectionと`未分類`へBoardを作成できる。
- 通常Collectionを削除すると、配置Boardが`未分類`へ移る。
- `未分類`を名称変更または削除できない。
- 通常Collection、未分類、管理のTabが所定の順序で表示される。
- Collectionの詳細確認、編集、Board作成が排他的に展開する。
- RoomOwner以外に管理操作を表示せず、不正な直接要求も拒否する。
- 既存Roomと既存Boardを壊さず、各Roomに`未分類`が一つだけ存在する。
- CollectionからBoard、Thread、Responseへ進むWorkspace遷移を維持する。

## v0.8に含めないもの

- Collectionの並び替え
- BoardまたはCollectionの参照追加
- 参照Itemの削除済み表示
- Account側のCollection管理
- BoardのCollection間移動
- 異なる管理者間のBoard移動申請・承認
- NiiMapへ直接配置するBoard
- BoardPolicy、BoardLayout、ThreadTemplate
