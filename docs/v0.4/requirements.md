# Niixy v0.4 要件定義

## 目的

公開 AccountPage と Account が関係する Thread の一覧・閲覧導線を追加する。Guest を含む利用者が投稿者の Account を確認し、その Account が作成または返信した Thread を、NiiMap と共通する SummaryList / DetailPane の体験で閲覧・返信できる状態を完成条件とする。

v0.4 は Account 情報を充実させる版ではなく、将来のプロフィール・活動履歴・Book・フォロー機能を載せるための画面と動線の基盤を作る版とする。

## 用語

- AccountPage: ある Account の公開情報と活動導線を表示するページ。
- AccountPageHeader: SiteHeader の直下に固定し、閲覧中の Account を示す細い見出し。
- ThreadPane: AccountPage 内で Account に関係する Thread を表示する領域。
- SummaryList / SummaryItem: 対象を要約して一覧表示し、詳細表示へ進む共通の表示パターン。
- DetailPane: 選択した Thread を閲覧し、許可されている場合は返信できる領域。

## スコープ

- AccountPage の新設と Guest を含む公開閲覧
- ThreadPost の Account 投稿者から AccountPage への導線
- AccountPageHeader の固定表示
- AccountPage の将来機能用プレースホルダーと無効ボタン
- Account が作成・返信した Thread を表示する ThreadPane
- ThreadPane 内の SummaryList と DetailPane
- Thread の発見・閲覧・書込制限を AccountPage 側でも適用

## AccountPage

### 公開と URL

- AccountPage は Guest とログイン済み Account のどちらも閲覧できる。
- URL は `/accounts/<NiixyID>/` とする。
- 自分の AccountPage と他者の AccountPage は同じ画面を使う。
- AccountPage 自体への閲覧制限、フォロー中の Account だけへの公開などは後続で扱う。
- Account 内の ThreadPane や DetailPane を開いても v0.4 では URL を変えない。NiiMap を含む詳細 URL の設計は後続でまとめて決める。

### Header

- AccountPage では SiteHeader を Niixy ロゴ中心の表示にし、長いパンくずは置かない。
- SiteHeader の直下に細い AccountPageHeader を固定する。
- v0.4 では表示名を実装しないため、AccountPageHeader の表示は `@NiixyID` とする。
- AccountPage 内で ThreadPane や DetailPane を開いても、AccountPageHeader は表示を維持する。

### 上部と将来機能の枠

- 本文上部の左側に、将来 Album の画像を選べるサムネイル領域のプレースホルダーを置く。
- 右側に次の二列の機能ボタンを置く。
  - フォロー / フォロワー
  - Thread / Response
  - Tweet / Book
  - Room / Interface
- `Thread` だけを有効にする。その他は無効状態のボタンとして表示し、リンクや操作は提供しない。
- 自分の AccountPage でも同じレイアウトを使う。将来の「フォローする」「DM」「ミュート」など、他者に対する操作は v0.4 では表示しない。
- 上部の下には、紹介文とプロフィールの領域を置く。どちらも内容は実装せず、`未実装` と表示する。

### 投稿者からの導線

- ThreadPost の投稿者が Account の場合、表示している `@NiixyID` を選択すると、その AccountPage を開く。
- Guest の `Guest` 表示は AccountPage へのリンクにしない。

## ThreadPane

### 表示する列

Thread ボタンを選択すると、AccountPage の本文を左へ退避させ、ThreadPane を右から表示する。AccountPageHeader は維持する。

ThreadPane には次の五列を置く。

1. 作成したThread
2. 返信したThread
3. favしたThread
4. badしたThread
5. ブックマーク

PC では各列に最低幅を設け、幅が足りない場合は列全体を横スクロールできる。SP では列をタブで切り替える。

`作成したThread` と `返信したThread` は実データを表示する。fav、bad、ブックマークは一覧の枠と空状態だけを表示し、データモデルや操作は実装しない。

各列は一ページにつき最大 10 件を表示し、実データを扱う列には追加ページへ進む操作を置く。

### 取得対象と初期順

- `作成したThread`: 対象 Account が作成者である Thread。
- `返信したThread`: 対象 Account が `#2` 以降の Response を投稿した Thread。同じ Thread に複数返信していても一件だけ表示し、その Account による最新 Response を代表とする。
- `作成したThread` は Thread の作成日時が新しい順、`返信したThread` は対象 Account の最新 Response が新しい順に並べる。
- 将来の履歴順、Thread の `last_activity_at` 順、検索・フィルターは後続で検討する。

### SummaryList と DetailPane

- 実データを表示する列では、NiiMap の一覧Paneと同じ SummaryItem の体験を提供する。
- SummaryItem の Header は `Thread Title (Response数)` とする。
- Header を選択すると、開始投稿（`#1`）の全文と `詳細を見る` をアコーディオンで表示する。
- `詳細を見る` を選択すると、対象列を左側へ退避させ、右側の残り幅に DetailPane を表示する。
- DetailPane では NiiMap と同じ ThreadPost 一覧と返信フォームを表示する。
- DetailPane を閉じると、元の列・選択状態・スクロール位置へ戻る。
- SP では SummaryList と DetailPane を横スライドで切り替える。

### 制限

- ThreadPane の各一覧には、閲覧者が発見制限を満たす Thread だけを表示する。
- DetailPane は閲覧制限を満たす場合だけ内容を表示する。
- 返信フォームは書込制限を満たす場合だけ表示・投稿できる。
- これらの判定は UI だけで行わず、一覧取得・詳細表示・返信投稿のサーバー処理でも適用する。

## 表示名

v0.4 では Account 名のデータ項目、登録時入力、変更画面を実装しない。既存・新規を含むすべての Account 名は空欄として扱い、Account の識別・表示には `@NiixyID` を使う。

表示名の入力と変更は、マイページを扱う v0.4.1 以降で実装する。その時点で、空欄可・絵文字不可・全角 12 文字 / 半角 24 文字相当まで・重複可の制約を適用する。

## 対象外

- マイページ、表示名の入力・変更、プロフィール編集
- Album、サムネイル画像、画像投稿、画像モデレーション
- 紹介文、紹介文への評価・アコーディオン
- フォロー、フォロワー、DM、ミュート
- Response 専用ページ
- fav、bad、ブックマークの保存・操作・実データ一覧
- Tweet、Book、Room、Interface の作成・詳細・一覧
- Book 内への Thread 配置
- ProfileLayout、ThreadLayout、汎用 Interface、DisplayLayout
- Thread / ThreadPost の編集・削除
- AccountPage と Thread 詳細を指す恒久 URL の設計

## 完了条件

- Guest とログイン済み Account のどちらも `/accounts/<NiixyID>/` を開ける。
- ThreadPost の Account 投稿者から、その AccountPage を開ける。
- AccountPageHeader がスクロール中、ThreadPane 中、DetailPane 中も閲覧中の `@NiixyID` を表示する。
- AccountPage にサムネイル、紹介文、プロフィール、将来機能ボタンのプレースホルダーが表示される。
- ThreadPane で作成した Thread と返信した Thread を区別して表示できる。
- 同じ Thread への複数 Response は、返信したThreadの一覧で重複しない。
- SummaryItem の概要展開、DetailPane での閲覧・返信、Pane を閉じた後の状態復帰が機能する。
- 発見・閲覧・書込制限が AccountPage 側でもサーバー処理を含めて維持される。
