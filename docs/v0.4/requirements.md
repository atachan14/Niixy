# Niixy v0.4 要件

## 目的

公開 AccountPage と、Account が作成した Thread の一覧・閲覧導線を追加する。Guest を含む利用者が Account を確認し、その Account の公開範囲にある Thread を SummaryList / DetailPane の共通パターンで閲覧・返信できる状態をつくる。

v0.4 では Account 情報そのものを充実させない。将来のサムネイル、紹介文、プロフィール、Book、フォローなどの完成形を想定した枠と動線だけを用意する。

## 用語

- **AccountPage**: ある Account の公開情報と履歴を表示するページ。
- **AccountPageHeader**: SiteHeader の直下に固定する細い Account 専用ヘッダー。
- **ThreadPane**: Account に関連する Thread を表示する領域。
- **SummaryList / SummaryItem**: 対象を概要として一覧化し、展開して概要を確認できる UI パターン。
- **DetailPane**: 選択した Thread の ThreadPost と返信フォームを表示する領域。

## スコープ

- Guest とログイン中 Account のどちらも AccountPage を閲覧できる。
- ThreadPost の Account 投稿者表示 `@NiixyID` から、その AccountPage へ移動できる。Guest 表示はリンクにしない。
- AccountPage にサムネイル、紹介文、プロフィール、将来機能ボタンのプレースホルダーを表示する。
- Account が作成した Thread を ThreadPane で表示する。
- ThreadPane の SummaryItem と DetailPane では、既存 NiiMap と同じ Thread 閲覧・返信の基本動作を使う。
- Discover / View / Write 制限を AccountPage 側でもサーバー側で適用する。

## AccountPage

### 公開と URL

- URL は `/accounts/<NiixyID>/` とする。
- 自分の AccountPage と他者の AccountPage は同じ画面構成とする。自分専用操作は将来のマイページに置く。
- フォロー中の Account だけに公開するなどの AccountPage 自体の閲覧制限は将来対応とする。
- AccountPage、ThreadPane、DetailPane の表示状態は v0.4 では URL に反映しない。URL 設計は NiiMap の Thread 詳細 URL とまとめて将来整理する。

### Header

- AccountPage の SiteHeader は `Niixy` ロゴだけを表示し、長いパンくずは置かない。
- SiteHeader の直下に AccountPageHeader を置く。
- 通常時は `@NiixyID` を表示する。
- ThreadPane 表示中は `@NiixyID > Thread` を表示する。
- `@NiixyID` 部だけを押すと Account 概要へ戻る。`> Thread` は現在地を示すだけで操作不可とする。

### 概要画面

- 概要画面の上部は、左にサムネイルのプレースホルダー、右に機能ボタン群を置く二列レイアウトとする。
- 機能ボタンは `フォロー / フォロワー / Thread / Response / Tweet / Book / Room / Interface` を並べる。
- v0.4 で有効なのは `Thread` のみ。他は `未実装` 相当の無効ボタンとして表示する。
- 上部の下に、紹介文とプロフィールの将来用プレースホルダーを通常の縦並びで置く。サムネイル側へ押し込まない。
- サムネイル、紹介文、プロフィールは v0.4 では `未実装` と表示する。

## ThreadPane

### レイアウトと切替

- `Thread` ボタンで Account 概要から Account Thread 表示へ切り替える。
- PC では `ThreadPane | DetailPane` の二列を表示する。
- DetailPane の初期状態は `Threadを選択してください` とし、Thread を自動選択しない。
- SP では Account 概要から ThreadPane へ切り替え、ThreadPane と DetailPane は横スライドで切り替える。
- SP の DetailPane には閉じるボタンを置き、ThreadPane へ戻れるようにする。

### タブと一覧

ThreadPane は次のタブを持つ。

1. `作成`
2. `fav`
3. `bad`
4. `bookmark`

- `作成`: 対象 Account が作成した Thread。作成日時の新しい順。
- `fav`、`bad`、`bookmark` は v0.4 では空の未実装状態だけを表示する。
- 一ページ最大 10 件とし、必要ならページネーションを表示する。
- 将来の更新順、フィルタ、並び替えは v0.4 の対象外とする。

### SummaryList と DetailPane

- SummaryItem の Header は `ThreadTitle (Response数)` とする。
- Header を押すと `#1` の本文全体と `詳細を見る` ボタンをアコーディオンで表示する。
- `詳細を見る` を押すと対象 Thread を DetailPane に表示する。
- DetailPane では ThreadPost 全件と、書込制限を満たす場合の返信フォームを表示する。
- DetailPane の閉じる操作は選択を解除し、空状態に戻す。

### 制限

- Thread の一覧には Discover 制限を満たすものだけを含める。
- Discover できても View 制限を満たさない場合は、概要に閲覧不可状態を表示し、本文や DetailPane の内容を渡さない。
- Write 制限を満たす場合だけ返信フォームを表示する。
- これらは見た目だけでなく、ビュー側の取得・判定でも適用する。

## 表示名

v0.4 では Account の表示名を追加しない。既存 Account は表示名なしとして、画面上では `@NiixyID` を表示する。

表示名は v0.4.1 以降で任意入力として追加する予定。空文字を許可し、絵文字は許可しない。表示幅は全角 12 文字相当、半角 24 文字相当を上限の目安とする。重複は許可し、識別は重複不可の NiixyID で行う。

## 対象外

- マイページ、自分専用操作、アカウント設定
- Album、サムネイル画像、紹介文、プロフィールの編集・表示
- フォロー、フォロワー、DM、ミュート
- fav、bad、bookmark の保存・一覧
- Tweet、Book、Room、Interface の作成・詳細・一覧
- Book 固有の Thread 運用
- ProfileLayout、ThreadLayout、DisplayLayout と Interface の連携
- Thread / ThreadPost の編集・削除
- AccountPage・Thread 詳細を表す URL 設計

## 完了条件

- Guest とログイン中 Account のどちらも `/accounts/<NiixyID>/` を開ける。
- ThreadPost の Account 投稿者表示から AccountPage を開ける。
- AccountPage に将来機能のプレースホルダーと、Thread への動線がある。
- 作成 Thread を表示できる。
- SummaryItem の展開、DetailPane での閲覧、許可された返信が動作する。
- Account 概要と Thread 表示の往復、SP の ThreadPane と DetailPane の往復ができる。
