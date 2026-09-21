# Vision の決定記録

Niixy 全体に影響する設計・プロダクト上の決定を時系列で残す。後から置き換えられた決定も削除せず、状態を更新して残す。

## 2026-09-20 - Thread を基礎コンテンツにする

状態: 採用

Niixy の会話モデルは Thread と ThreadPost を使う。Event と Pin は基礎モデルにせず、Event は将来の ThreadInterface とする。

## 2026-09-20 - Community と NiiRoom を Room に統一する

状態: 採用

Account が作成・管理する場所の名称は Room に統一する。Community と NiiRoom は旧用語とする。

## 2026-09-20 - 開始投稿を必須にする

状態: 採用

Thread はタイトルと開始本文を同時に入力して作成する。開始投稿は常に `#1` であり、単独では削除できない。削除時は Thread 全体を削除する。

## 2026-09-20 - 掲載先を独立モデルにする

状態: 採用

Thread の掲載と共有は ThreadPlacement 型の中間モデルで表現する。これにより、主掲載先、共有、移動、掲載履歴を Thread の複製なしに扱える。

## 2026-09-20 - 返信は時系列のフラットな構造にする

状態: 採用

返信は時系列順のフラットな並びとする。`>>1` のような投稿参照はリンクであり、ネストした返信ツリーは作らない。

## 2026-09-20 - v0.3 は最小の制限を含める

状態: 採用

v0.3 は Guest / NiixyAccount を条件にした発見制限・閲覧制限・書込制限を実装する。汎用 Policy、Room、汎用 Interface、DisplayLayout、Album、アカウントページは後続バージョンへ回す。

## 2026-09-21 - `#1` は Thread と ThreadPost の両方として扱う

状態: 採用

`#1` は Thread の開始投稿であり、Thread の一部として表示する。同時に ThreadPost でもあるため、投稿番号、アンカー、DisplayLayout は `#1` にも適用する。Thread を対象にする操作は `#1` の操作領域に置き、Response を対象にする操作とは区別する。

## 2026-09-21 - DisplayLayout は ThreadPost 全体を対象にする

状態: 採用

DisplayLayout は Header に限定せず、ThreadPost 全体の表示項目、順番、サイズ、配置を扱う。具体的な記法や自由度は、実装時に再検討する。既存 Thread の表示は作成時点の Layout スナップショットで固定する。

## 2026-09-21 - ニックネームではなく表示名を使う

状態: 採用

Account の Niixy ID とは別に、他者へ表示する名前は「表示名」と呼ぶ。v0.3 では表示名を実装せず、Account の投稿者表示には `@NiixyID`、Guest には `Guest` を使う。表示名を実装後は、投稿表示で `表示名 @NiixyID` の順に表示する。
