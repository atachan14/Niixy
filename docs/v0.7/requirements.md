# v0.7 Board Management 要件

Status: Complete

## 目的

RoomのMain Collection内でBoardを追加・編集・削除できるようにし、RoomOwnerが用途ごとに複数のBoardを使い分けられる状態を完成させる。

v0.7ではRoom配下のBoard管理を対象とする。Collectionの追加・編集・削除・参照、Boardの参照や配置先変更、BoardPolicy、NiiMapへ直接配置するBoardは後続Versionへ回す。

## 対象範囲

- RoomOwnerによるBoardの新規作成
- RoomOwnerによるBoard名と詳細の編集
- Boardの物理削除
- 複数BoardでのThread作成、閲覧、Response投稿
- Board削除後も存続するThreadとResponse
- RoomPageとBoard一覧の更新
- Board操作の権限、Validation、二重送信防止

## Board

BoardはThreadをまとめるコンテナであり、安定したIDと変更可能なBoard名および詳細を持つ。

Boardは独立したOwnerや作成者を持たない。管理権限は配置先から解決する。v0.7でRoomから作成するBoardはRoomのMain Collectionへ配置し、そのRoomのRoomOwnerだけが管理する。Board名を変更してもBoard IDと配置先は変更しない。

## Board作成

RoomのBoard一覧に、RoomOwnerだけが利用できる`Board作成`を配置する。

作成時にはBoard名を必須入力とし、作成したBoardをRoomのMain Collectionへ配置する。RoomOwner以外の参加者、非参加Account、Guestからの作成要求はサーバー側でも拒否する。

作成処理は二重送信によってBoardまたはBoardPlacementを重複作成しない。作成成功後はBoard一覧を更新し、作成したBoardのThread一覧Paneを開く。

## Board編集

RoomOwnerだけがBoard名と詳細を変更できる。編集操作はBoard内Thread一覧Paneの`詳細情報`から開く。

Board名や詳細の変更は既存Thread、ThreadPlacement、URLへ影響させない。Board名の空文字や各項目の文字数超過など、不正な入力は保存しない。

Board内Thread一覧Paneでは、`詳細情報`と`Thread作成`を排他的に展開する。`詳細情報`にはBoard名、詳細、将来のPolicy、Layout、ThreadTemplateの確認領域を配置し、RoomOwnerにだけ編集への導線を表示する。編集時には同じ領域を入力状態へ切り替え、保存と物理削除を行えるようにする。

v0.7ではBoardの配置先変更、NiiMap配置、BoardPolicy、Layout、Templateを提供しない。

## Board削除

Boardは復元を前提としない物理削除とする。`Active / Deleted`などの状態、削除済み一覧、復元機能は設けない。

- RoomOwnerだけがBoardを削除できる。
- 最後のBoardも削除でき、Boardを一つも使用しないRoomを認める。
- 削除前に、操作を取り消せないことと、Board内のThreadおよびResponseは削除されないことを案内する。
- Board本体、BoardPlacement、そのBoardが保持する参照は削除する。
- Boardに配置されていたThreadは削除せず、ThreadPlacementだけを削除して未配置にする。
- Thread本体、ThreadPost、ThreadPolicy、Field、Interface、そのThreadへの外部参照は保持する。
- Board削除後も、ThreadPolicyが許可するResponse投稿と編集可能なThread情報の変更を認める。
- 未配置ThreadはNiiMapとRoomの通常導線には表示せず、AccountPageなどの履歴や将来のList、fav、bad、Thread固有URL、別Boardからの参照で利用できる。

## Board一覧

RoomのBoard一覧PaneではCollection TabとBoardのSummaryListを表示する。

- v0.7ではCollection TabにMainだけを表示する。
- `Board作成`はMainのSummaryList先頭に表示する。
- Boardは最終活動日時が新しい順に表示する。
- BoardのSummaryItemは既存の三行構造を使用する。
- Room自身のCollectionへ配置されたBoardでは上段を空欄とする。
- 将来の参照Boardでは、本体の配置元であるAccountまたはRoomを上段へ表示できる構造を維持する。

## Board内Thread

Boardが存在する間はv0.6の固定ルールを継続する。

- Room参加者だけがThreadを作成できる。
- Room参加者かつThreadPolicyで許可された利用者だけがResponseを投稿できる。
- Thread詳細、DirectField、ThreadInterface、ThreadPolicyは既存の共通実装を使用する。
- どの導線から開いても同じThread詳細を表示する。

Boardを削除するとRoom参加状態によるBoard経由の制限は消え、以後はThreadPolicyだけでThreadを判定する。

## Data Model

Boardへ作成の二重送信を防止する`submission_id`を追加する。Boardの管理主体はBoard上のOwner列ではなく、`BoardPlacement -> Collection -> Room`から解決する。

Board削除時にThreadまで削除されないことをDB関係とService Testの両方で保証する。NiiMapのThread取得処理は、未配置Threadを含めず、NiiMap配置を持つThreadだけを対象とする。

## Security

- Board作成、編集、削除にはLoginを必要とする。
- すべての管理操作でRoomOwnerかをサーバー側で再確認する。
- 対象Boardが指定RoomのCollectionへ配置されていることを確認する。
- 不正なBoard IDや別RoomのBoardを利用した操作を拒否する。
- Board削除後のThread操作では、残存するThreadPolicyをサーバー側で再判定する。

## 完了条件

- RoomOwnerがMain Collectionへ複数のBoardを作成できる。
- 作成した各BoardでRoom参加者がThreadとResponseをやり取りできる。
- RoomOwnerがBoard名と詳細を変更できる。
- RoomOwnerがThreadの有無にかかわらずBoardを物理削除できる。
- Board削除後もThread、ThreadPost、ThreadPolicy、Field、Interfaceが残る。
- Board削除後のThreadへ、ThreadPolicyで許可された利用者がResponseを投稿できる。
- 未配置ThreadがNiiMapのSpot一覧や検索へ表示されない。
- 最後のBoardを削除してもRoomPageが破綻しない。
- RoomOwner以外はBoard管理操作を実行できない。
- 既存Roomの`最初のBoard`とBoard内Threadを壊さない。
- Board一覧、Thread一覧、Thread詳細のWorkspace遷移で余分なPaneや空白を作らない。

## v0.7に含めないもの

- Collectionの新規作成、編集、削除、並び替え
- システムCollection「未分類」
- BoardとCollection、BoardとThreadの参照
- BoardのCollection間移動と管理者間の移動申請・承認
- NiiMapへ直接配置するBoard
- BoardPolicy
- BoardLayoutとTemplate
- Account向けMain CollectionとブログBoard
- Room内部BoardやThreadを利用したNiiMap検索
- 配置先に依存しないThread固有URL

## 実装順序

1. 要件、Vision、Roadmapの整合
2. Ownerと削除状態を持たないBoard Data Model、Migration、Model Test
3. Board作成、名称編集、物理削除のServiceと権限Test
4. Board一覧と作成・編集・削除UI
5. Board削除後のThread存続、Response投稿、NiiMap除外Test
6. Workspace、既存Room、既存Threadを含む回帰Test
