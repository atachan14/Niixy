# v0.6 Room Foundation 要件

## 目的

AccountがNiiMapへRoomを作成し、別のAccountがRoomへ参加して、Room内のBoardでThreadとResponseをやり取りできる最小の共同利用を完成させる。

v0.6ではRoom、Collection、Boardの基礎モデルを導入するが、自由なBoard・Collection管理や汎用Policyは実装しない。Room作成時に用意されるMain Collectionと`最初のBoard`を使って、Roomの基本導線を先に検証する。

## 対象範囲

- Roomの作成、基本情報編集、NiiMap配置
- NiiMapでのRoom表示と基本検索
- RoomPage
- Main Collectionと`最初のBoard`の自動作成
- RoomOwnerと参加者
- ログイン済みAccountの即時参加・退出
- Room参加者によるBoard内Thread作成
- Room参加者によるBoard内ThreadへのResponse投稿
- 既存のThread、DirectField、ThreadInterface、ThreadPolicyとの接続

## Room

RoomはAccountが作成・管理し、参加者が継続的に活動する場所である。Roomは次の情報を持つ。

- 変更可能なRoom名
- Description
- RoomOwnerであるAccount
- 監査用の作成Account
- 作成日時、更新日時、最終活動日時
- NiiMap上の配置座標

Roomは常に一人のRoomOwnerを持つ。Room作成時には、作成AccountをRoomOwnerかつ最初の参加者とする。RoomOwnerはv0.6では退出できない。

将来のOwner譲渡に備え、RoomOwnerは作成Accountから独立して変更可能な関係として保存する。ただし、Owner譲渡UIと譲渡処理はv0.6に含めない。

## Guestの扱い

GuestはRoomへ参加できず、RoomOwnerにもなれない。これはPolicyではなく、永続的なAccountを持たないGuestに対するNiixy共通の制約とする。

- Guestには参加・退出操作を表示しない。
- Guestから参加URLへ直接POSTされてもサーバー側で拒否する。
- GuestがRoom内Threadを閲覧できるかはThreadPolicyに従う。
- Guestはv0.6のRoom内ThreadへResponseを投稿できない。
- NiiMapへ直接配置された既存Threadに対するGuest利用は変更しない。

## Room参加

v0.6では参加申請と参加条件を設けず、ログイン済みAccountは参加操作によって即時参加できる。

- 同じAccountが同じRoomへ重複参加できない。
- 参加操作は二重送信されても一つの参加関係だけを作る。
- RoomOwner以外の参加者は退出できる。
- 未参加Accountの退出要求は状態を壊さない。
- RoomOwnerの退出要求は拒否し、Owner譲渡が必要であることを案内する。
- RoomPageから参加者数と参加者一覧を確認できる。

参加関係はRoomとAccountを結ぶ独立したモデルとして保持し、参加日時を記録する。Guestを表すNULL参加者は作成しない。

## CollectionとBoard

Room作成時の同一Transaction内で、次を自動作成する。

1. Room
2. RoomOwnerの参加関係
3. Roomに配置された`Main` Collection
4. Main Collectionを主配置先とする`最初のBoard`
5. RoomのNiiMap配置

いずれかの作成に失敗した場合は、途中状態を残さず全体を取り消す。

Collectionは将来AccountまたはRoomへ配置できる共通概念とする。Boardは将来CollectionまたはNiiMapへ配置できる共通概念とするが、v0.6で新規作成するCollectionとBoardはRoomのMain Collectionと`最初のBoard`だけとする。

自動作成するMain Collectionの配置先と`最初のBoard`のOwnerはRoomとし、実際に作成操作をしたAccountはBoardの監査用作成者として保持する。`最初のBoard`の主配置先はMain Collectionとする。

v0.6では次の管理操作を提供しない。

- Boardの追加、名称変更、削除、移動
- Collectionの追加、名称変更、削除、並び替え
- BoardまたはCollectionの参照追加
- RoomPaneへ表示するCollectionの変更
- Account向けMain CollectionとブログBoardの作成

最後のBoardを削除してBoardなしのRoomを作れる最終方針は維持するが、その操作はBoard管理機能を実装する後続Versionで提供する。

## Board内のThread

RoomPageから`最初のBoard`を開くと、Board内ThreadのSummaryListを表示する。Room参加者にはThread新規作成操作を表示し、非参加AccountとGuestには表示しない。

Board内Threadの作成フォームは、NiiMap上の既存Thread作成フォームから座標入力だけを除いた共通フォームとする。次の既存機能を維持する。

- Threadタイトルと`#1`本文
- DirectField
- 複数ThreadInterface
- ThreadPolicy
- 二重送信防止

作成したThreadはNiiMap座標ではなくBoardを主配置先とする。NiiMapへ直接配置された既存Threadは移行せず、従来の座標を主配置先として継続する。

Threadの主配置先は一つとし、NiiMapまたはBoardのどちらかを持つ。将来の共有先追加に備えて、配置はThread本体へ座標やBoard IDを直接埋め込まず、独立した配置関係として扱う。

## 固定の書込ルール

BoardPolicyはv0.6で実装しない。Room内の共同利用を確認するため、次の固定ルールを適用する。

- Board内でThreadを作成できるのはRoom参加者だけ。
- Board内ThreadへResponseを投稿できるのはRoom参加者だけ。
- Response投稿には、参加状態に加えて既存ThreadPolicyの書込条件も満たす必要がある。
- Board内Threadの閲覧可否は既存ThreadPolicyで判定する。
- RoomOwnerも参加者として同じ書込判定を受ける。

後続VersionでBoardPolicyを導入した際は、この固定ルールを標準BoardPolicy相当へ置き換える。

## RoomPage

RoomPageはAccountPageと同じWorkspaceの考え方を使用するが、ProfileAreaとProfileLayoutはまだ実装しない。少なくとも次を表示する。

- Room名を表示する固定Header
- NiiMap座標へ戻る導線
- サムネイルの未実装表示
- Description
- RoomOwner
- 参加者数と参加者一覧への導線
- 参加または退出Action
- Main Collection内のBoard一覧

RoomPageではMain Collection内のBoardを更新が新しい順に最大三件表示する。v0.6では`最初のBoard`だけが存在するが、後続のBoard管理を前提としたSummaryListを使用する。

Boardを選択するとBoard内Thread一覧Paneを開き、Threadを選択すると既存のThreadDetailPaneを開く。Pane追加と読み込み表示には既存のWorkspace共通処理を利用する。

## Room作成

NiiMapの新規作成アコーディオンで、地点選択後にRoom作成を選べるようにする。Room作成にはLoginを必須とする。

作成フォームではRoom名とDescriptionを入力し、Header直下の座標行で選択地点を確認できるようにする。地点を変更する場合はNiiMapへ戻り、既存の地点選択導線を利用する。

作成成功後は作成したRoomPageへ遷移する。作成中は共通の送信状態を使用し、二重送信によってRoom、参加関係、Collection、Board、配置を重複作成しない。

## Room編集

RoomOwnerだけがRoom名、Description、NiiMap座標を編集できる。編集後はRoomPageとNiiMapのMarker・SummaryItemへ反映する。

次はv0.6に含めない。

- RoomOwnerの譲渡
- Roomの削除
- ProfileAreaとProfileLayout
- サムネイルとAlbum
- 表示用Collectionの変更
- RoomInterface

Room削除は、内部BoardとThreadを削除・移動・存続のどれとして扱うかをBoard管理機能と合わせて決める。

## NiiMap表示と検索

NiiMapのSpot一覧とMarkerへRoomを追加する。SummaryItemとMarkerはThreadとRoomの種別を識別できる表示にする。具体的な色は意味を持つCSS tokenとして定義し、カード全面ではなく種別表示や左端など限定した箇所へ使用する。

Room検索では少なくとも次を扱う。

- Mapの表示範囲
- 距離順または更新順
- 対象種別のRoom
- Room名とDescriptionを対象にしたフリーワード
- RoomOwner

v0.6ではRoom内部のBoardとThreadを検索対象に含めない。ThreadIFやFieldが一致する内部Threadを理由としてRoomを検索結果へ出す機能も実装しない。

RoomのMarkerを選択した場合は対応するSummaryItemを強調して一覧内へスクロールし、SummaryItemの選択でRoomPageを開く。既存Thread Markerの挙動は維持する。

## URLと画面遷移

RoomPageはNiiMapの一時的なPane状態ではなく、直接開ける固有URLを持つ。Page遷移でRoomPageを開いた場合は、以前のRoomまたはNiiMapのWorkspace状態を復元しない。

RoomPage内のBoard一覧、Thread一覧、Thread詳細は、既存のWorkspaceとオンデマンド取得を利用する。追加Paneは先に読み込み表示を開き、取得完了後に内容を差し替える。

## Data Modelの原則

- RoomOwnerは一つの必須Account参照として保持する。
- 作成Accountは監査用としてOwnerと分離して保持する。
- Room参加はRoomとAccountの中間モデルで表現する。
- RoomのNiiMap配置はRoom本体と分離する。
- Collectionの配置先はAccountまたはRoomのどちらか一つとする。
- BoardのOwnerはAccountまたはRoomのどちらか一つとする。
- Boardの主配置先はCollectionまたはNiiMapのどちらか一つとする。
- Threadの主配置先はBoardまたはNiiMapのどちらか一つとする。
- 配列やJSONへ関連IDを保存せず、外部キーと中間モデルを使用する。
- Owner、主配置、参照、作成Accountを同じ関係として扱わない。

v0.6では使用しない将来関係を無理にUIへ露出しない。一方で、BoardやThreadを複製しなければ参照できない構造にはしない。

## Validationと権限

すべての権限は画面表示だけでなくサーバー側で再判定する。

- Room作成、参加、退出、編集にはLoginが必要。
- Room編集はRoomOwnerだけに許可する。
- Board内Thread作成とResponse投稿ではRoom参加状態を再確認する。
- Response投稿では既存ThreadPolicyも再確認する。
- RoomOwnerの退出を拒否する。
- Room、Collection、Board、参加、配置の一意制約をDBでも保証する。

## Test

少なくとも次を自動Testで確認する。

- Room作成時にOwner参加、Main Collection、`最初のBoard`、NiiMap配置が一度だけ作成される。
- Guestと未Login利用者はRoomを作成・参加できない。
- ログイン済みAccountはRoomへ参加し、退出できる。
- RoomOwnerは退出できない。
- 同じRoomへ重複参加できない。
- RoomOwnerだけが基本情報と座標を編集できる。
- 参加者だけがBoard内Threadを作成できる。
- 参加者かつThreadPolicy許可時だけResponseを投稿できる。
- Board内ThreadはNiiMapの直接Markerとして表示されない。
- Roomは表示範囲、対象種別、フリーワード、Ownerで検索できる。
- Room内部Threadはv0.6のNiiMap検索へ混入しない。
- 既存のNiiMap ThreadとGuest利用を壊さない。
- RoomPage、Board一覧、Thread詳細のWorkspace遷移で余分なPaneや空白を作らない。

## v0.6に含めないもの

- 参加申請、招待、参加条件
- 編集可能なRoomPolicy
- BoardPolicy
- RoomOwner譲渡
- Room内Tagと複数管理者
- Room削除
- BoardとCollectionの管理UI
- BoardとCollectionの参照UI
- Account向けCollectionとブログBoard
- RoomInterface
- ProfileAreaとProfileLayout
- Room内部コンテンツを利用したNiiMap検索
- TimelineとTweet

## 実装順序

1. Room、参加、配置、Collection、Board、Thread配置のData ModelとMigration
2. Room作成と自動生成処理、Admin、Model Test
3. RoomPage、参加・退出、参加者一覧
4. Board内Thread一覧、Thread作成、Response権限
5. Room編集
6. NiiMapのRoom Marker、SummaryItem、検索
7. Workspace、SP表示、既存機能を含む回帰Test
