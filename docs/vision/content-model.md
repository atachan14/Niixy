# コンテンツモデル

## Thread

Thread は Niixy 上の会話の単位である。NiiMap に直接、または Room や Book の中で作成できる。Thread は Event や Pin ではない。

Thread はタイトル、作成者、作成日時、更新日時、`last_activity_at`、必須の開始 ThreadPost（`#1`）を持つ。作成時にはタイトルと開始本文を同時に入力する。Thread Title は作成後に編集しない。

開始本文の単独削除は許可しない。開始投稿を削除する場合は Thread 全体を削除する。Thread 削除時は Title と `#1` を削除済み表示へ置き換え、既存の返信は残す。

## ThreadPost

ThreadPost は開始投稿と返信の両方を表す。投稿は時系列順に表示し、Thread 内で変わらない投稿番号を持つ。

返信はフラットな時系列の一覧とする。`>>1` のような参照は別の投稿へのリンクであり、ネストした返信ツリーを作らない。将来は参照先を hover で表示する UI を検討する。

ThreadPost の本文と ThreadPostInterface の実装値は、投稿後に編集しない。ThreadPostInterface は `#1` と返信の両方へ適用できる。削除済みの返信は、投稿番号を維持したまま、当面は「削除されました」と表示する。削除済み表示のレイアウトや文言は将来の DisplayLayout と合わせて再検討する。

## ThreadInterface の更新

Thread には複数の ThreadInterface を適用できる。作成後も新規 Interface の追加、既存 Interface の削除、実装値の編集、最新版への更新を許可する。Require された Interface は単独で削除できず、追加・削除・更新後の構成は InterfaceRequirement を満たさなければならない。

Version 更新では、旧 Version の削除と新 Version の追加を利用者に個別操作させず、一つの更新操作として扱う。両 Version で継続する同一 Field の値は引き継ぎ、追加 Field は入力を求め、使用されなくなる Field は差分確認に表示する。更新により他の Interface が成立しなくなる場合は、保存前に影響を示し、更新の中止、依存する Interface の同時更新、または削除を選べるようにする。

Interface の追加、削除、実装値編集、Version 更新は構造化された履歴として保持する。Thread の時系列上で変更時点を示すシステム Response として表示し、`#1` の ThreadInterface 領域から更新履歴を一覧できるようにする案を有力とする。具体的な表示と、システム Response の投稿番号・Response 数への扱いは実装時に決める。

## Book

Book は Thread をテーマや用途ごとにまとめ、公開・購読できるコレクションである。日記、ブログ、料理レシピ、ゲームレビューなどは、独立した Note モデルではなく、Book に配置した Thread として表す。`#1` が記事本文、Response がコメントとして機能する。

Book は作成者、タイトル、説明、公開条件、購読者、Book 内の Thread に適用する ThreadInterface と DisplayLayout を持つ。Book 内の Thread は同じ表示ルールを使う。初期方針では Book 作成者だけが Thread を追加できるものとし、共同投稿や投稿権限の拡張は後続で検討する。

新規 Account には「日記」という空の Book を初期作成する。不要な場合は削除できる。Account の Book 一覧では、作成した Book と購読中の Book を区別して表示する。

## ThreadPlacement

ThreadPlacement は Thread の掲載先または共有先を表す。主掲載先、Room や Book への共有、掲載先の移動、掲載履歴を扱うため、Thread から独立したモデルにする。

NiiMap への配置は地図表示に必要な地点情報を持つ。Room や Book への配置は、それぞれのコンテナと Thread を結ぶ。v0.3 は NiiMap への配置のみを実装し、Room と Book に対応するためのモデル境界は維持する。

## 活動日時

`last_activity_at` は Thread または Room に対する最後の意味のある操作日時である。活動中のコンテンツの並び順に使い、Thread 作成、ThreadPost 作成、関連する Interface の更新、掲載先変更、再掲載などで更新する。

## 投稿時点のスナップショット

投稿者が後からニックネーム、サムネイル、Interface の情報を変更しても、ThreadPost の表示は安定している必要がある。そのため長期的には、投稿時点の投稿者表示情報をスナップショットとして持つ。具体的な項目とサムネイルの保存は、最小構成の v0.3 より後で決める。
