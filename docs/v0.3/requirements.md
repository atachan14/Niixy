# Niixy v0.3 要件定義

## 目的

暫定的な Event 中心のモデルを、Thread を中心とした NiiMap の基盤へ置き換える。利用者は地図上の地点を選び、本文を持つ Thread を作成・発見・閲覧・返信できる。

v0.3 では汎用化を急がず、Thread と最小限の制限を一貫して扱える状態までを完成条件とする。

## 用語

- Thread: Niixy 上の会話の単位。Event や Pin ではない。
- ThreadPost: Thread の開始投稿（`#1`）または返信。
- ThreadPlacement: Thread を掲載または共有する先を表す中間モデル。v0.3 では NiiMap への配置だけを扱う。
- 制限: Thread を発見・閲覧・書き込みできる利用者の条件。画面上では「発見制限」「閲覧制限」「書込制限」と表記する。

## スコープ

- Thread と返信の作成
- Thread 作成時に必須となる開始 ThreadPost（`#1`）の同時作成
- 時系列順に表示する返信 ThreadPost と、Thread 内で不変の投稿番号
- NiiMap 上の ThreadPlacement と地点選択
- 地図マーカー、一覧Pane、詳細Pane、地点検索、現在地への移動
- Guest / NiixyAccount を条件にした発見制限・閲覧制限・書込制限
- Account / Guest の投稿者としての扱いを v0.2 から引き継ぐ
- Event のテストデータモデルから Thread モデルへの移行

## Thread 作成

NiiMap の作成導線は、v0.3 では `Threadを作成` とする。Room 作成は対象外のため、Room と Thread を選ばせるメニューは設けない。

作成を開始すると、既存の Event 投稿と同じく地図が地点選択モードになる。地図をクリックまたはタップして Pin を置き、その座標を Thread の NiiMap 配置に使う。

フォームには次を置く。

- タイトル: 必須
- 本文: 必須。開始 ThreadPost（`#1`）の本文になる
- `内容` タブと `制限` タブ
- 地点選択の状態

Thread Title、`#1` を含む本文、返信、制限は作成後に編集できない。`#1` を削除する操作は Thread 全体の削除として扱い、返信を削除しても残る投稿の番号は変えない。この削除操作の UI と実装は v0.3 の対象外とする。

## 制限

制限タブには、次の三つを独立した項目として置く。

- 発見制限: NiiMap の一覧・マーカー・検索結果で見つけられる条件
- 閲覧制限: Thread 本文と投稿一覧を開ける条件
- 書込制限: 返信を投稿できる条件

各項目は、現在設定されている条件を一行ずつ表示する。条件は `×` で削除でき、`条件を追加` から追加する。v0.3 で選べる条件は次の二つだけとする。

- Guest: 未ログインの利用者
- NiixyAccount: ログイン済みの Niixy アカウント

新規 Thread の三つの制限は、いずれも Guest と NiixyAccount を設定した状態を初期値とする。これは現在の公開状態と同じ意味になる。

同じ制限内に複数の条件がある場合は OR とする。条件が一つもない制限は、ログイン済みの作成者以外には許可しない。ログイン済み Account の作成者は、自身の Thread を常に閲覧・削除でき、制限の条件から除外しない。Guest は継続して識別しないため、Guest が作成した Thread は投稿後に削除できない。

発見・閲覧・書込の判定は画面だけで済ませず、一覧取得・Thread 表示・返信投稿の各サーバー処理でも適用する。直接 URL などで到達した場合も閲覧制限を満たさなければ内容を返さない。

v0.3 の `条件を追加` ポップアップには Guest と NiixyAccount を候補として表示する。特定 Account、Room、ロール、Interface、評価値を検索・指定する UI は後続バージョンで扱う。

## 一覧Pane と詳細Pane

一覧Pane は Thread の一覧と概要確認に使う。Item の Header には、当面 `Thread Title (Response数)` を表示する。Item を選択すると Header の下に開始投稿（`#1`）の全文と `詳細を見る` を展開する。将来は Interface に応じた要約情報を Header に追加でき、右端には fav 数・bad 数を表示する予定である。

地図マーカーまたは一覧 Item の Header を選択した場合は、対応する一覧 Item を選択・展開するだけで、詳細Pane の表示対象は変えない。`詳細を見る` を選択したときだけ、その Thread を詳細Pane に表示する。初期表示と地図移動後の一覧は、Map の中心から近い順に並べる。

PC では、MapView・一覧Pane・詳細Pane を横一列のトラックとして持つ。MapView と詳細Pane はどちらも `画面幅 - 一覧Pane 幅` を保ち、一覧Pane は固定幅とする。

- 地図表示: `MapView | 一覧Pane` を表示し、詳細Pane は画面右外に置く。
- 詳細表示: トラック全体を左へスライドし、`一覧Pane | 詳細Pane` を表示する。MapView は画面左外に残す。
- 詳細Pane 内の地図へ戻る操作で地図表示へ戻る。戻った後も一覧の選択・展開・スクロール位置を保つ。

SP では MapView を維持し、その下の一覧Pane と詳細Pane を横スライドで入れ替える。詳細Pane には一覧へ戻る操作を置く。

## 詳細Pane の仮表示

詳細Pane の最上部には Thread Title と ThreadPost 数だけを表示する。Thread を対象にする操作は、この最上部には置かない。

`#1` は Thread の開始投稿であると同時に ThreadPost でもある。投稿番号・アンカー・DisplayLayout は `#1` にも適用する。表示上は Thread の最初の投稿として扱い、Thread を対象にする操作は `#1` の操作領域に置く。

`#2` 以降は Response として扱い、将来 ThreadPost 自体を対象にする操作は各 Response の操作領域に置く。fav、bad、bookmark のデータモデルと操作仕様は後続で決めるため、v0.3 の必須機能には含めない。

DisplayLayout 実装前の ThreadPost は、左に共通の Placeholder Thumbnail、右に投稿情報と本文を置く固定の仮レイアウトで表示する。Account の投稿者表示は `@NiixyID`、Guest の投稿者表示は `Guest` とする。表示名は後続で実装し、実装後は `表示名 @NiixyID` を同じ位置に表示する。投稿番号・投稿者・投稿日時・本文・操作領域の配置はこの仮レイアウトに従うが、`Header`、`Body`、`Footer` という固定領域を将来の DisplayLayout の前提にはしない。

返信フォームは詳細Pane の最下部に常設する。書込制限を満たす利用者だけが返信を投稿できる。投稿番号によるアンカーと、投稿番号クリックでの入力欄への自動挿入は後続へ回す。

## 絞り込み

Event に固有だった日時フィルタは削除する。v0.3 では既存の投稿者条件だけを残し、Guest の投稿を含めるか、特定の Niixy ID の投稿だけを表示するかを設定できるようにする。Guest / Account ともに、Guest の投稿を表示する状態を初期値とする。初期の並び順は `last_activity_at` ではなく、Map 中心からの距離順とする。

## データモデル

- Thread: タイトル、作成者、作成日時、更新日時、`last_activity_at` を持つ。
- ThreadPost: Thread、投稿番号、投稿者、本文、作成日時を持つ。`#1` は Thread 作成時に必ず作られる。投稿後の本文編集は行わない。
- ThreadPlacement: Thread と掲載先を結ぶ。NiiMap 配置では座標を持つ。
- 制限の保存形式: 将来の Policy 拡張を妨げない形にするが、v0.3 で実装する条件種別は Guest / NiixyAccount の固定セットに限る。

返信の追加、Thread の作成、配置変更など、会話の鮮度に関わる操作では Thread の `last_activity_at` を更新する。

## データ移行

既存の Event データはすべてテストデータとして破棄してよい。Event の日時・募集人数・会場などを Thread へ変換する処理は作らない。

以下は保持する。

- Station / Locality の地点検索データ
- Django の migration 履歴
- Account、ログインセッション、NiiMapFilterPreference などの再利用可能な基盤

## 対象外

- Room の作成、参加、掲載、共有、発見
- Thread と ThreadPost の削除操作
- 特定 Account・Room・ロール・Interface・評価値を条件にする制限
- 汎用 Policy エンジン
- 汎用 Interface スキーマ、動的表示エンジン、EventInterface、参加管理
- アカウントページ、Album、サムネイル画像、画像モデレーション
- フォロー、紹介文、評価、Tweet、Note
- ネストした返信ツリー

## 完了条件

- Thread は必ず開始 ThreadPost（`#1`）と同時に作られる。
- Thread は地点を選んで NiiMap に配置でき、マーカーと一覧から開ける。
- 返信は時系列順に表示される。
- 発見・閲覧・書込の三つの制限が UI とサーバー処理の両方で機能する。
- Thread Title、本文、返信、制限は投稿後に編集できない。
- 既存の地図操作、地点検索、NiiMap の絞り込み、Account / Guest のログイン体験が維持される。
- Event テストデータを削除しても、Station / Locality のデータは残る。
