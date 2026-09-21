# コンテンツモデル

## Thread

Thread は Niixy 上の会話の単位である。NiiMap に直接、または Room の中で作成できる。Thread は Event や Pin ではない。

Thread はタイトル、作成者、作成日時、更新日時、`last_activity_at`、必須の開始 ThreadPost（`#1`）を持つ。作成時にはタイトルと開始本文を同時に入力する。Thread Title は作成後に編集しない。

開始本文の単独削除は許可しない。開始投稿を削除する場合は Thread 全体を削除する。Thread 削除時は Title と `#1` を削除済み表示へ置き換え、既存の返信は残す。

## ThreadPost

ThreadPost は開始投稿と返信の両方を表す。投稿は時系列順に表示し、Thread 内で変わらない投稿番号を持つ。

返信はフラットな時系列の一覧とする。`>>1` のような参照は別の投稿へのリンクであり、ネストした返信ツリーを作らない。将来は参照先を hover で表示する UI を検討する。

ThreadPost の本文と ResponseInterface の実装値は、投稿後に編集しない。削除済みの返信は、投稿番号を維持したまま、当面は「削除されました」と表示する。削除済み表示のレイアウトや文言は将来の DisplayLayout と合わせて再検討する。

## ThreadPlacement

ThreadPlacement は Thread の掲載先または共有先を表す。主掲載先、Room への共有、掲載先の移動、掲載履歴を扱うため、Thread から独立したモデルにする。

NiiMap への配置は地図表示に必要な地点情報を持つ。Room への配置は Thread と Room を結ぶ。v0.3 は NiiMap への配置のみを実装し、Room 対応のためのモデル境界は維持する。

## 活動日時

`last_activity_at` は Thread または Room に対する最後の意味のある操作日時である。活動中のコンテンツの並び順に使い、Thread 作成、ThreadPost 作成、関連する Interface の更新、掲載先変更、再掲載などで更新する。

## 投稿時点のスナップショット

投稿者が後からニックネーム、サムネイル、Interface の情報を変更しても、ThreadPost の表示は安定している必要がある。そのため長期的には、投稿時点の投稿者表示情報をスナップショットとして持つ。具体的な項目とサムネイルの保存は、最小構成の v0.3 より後で決める。
