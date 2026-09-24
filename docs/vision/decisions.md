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

状態: 置換（2026-09-24 の ThreadPostLayout に関する決定）

DisplayLayout は Header に限定せず、ThreadPost 全体の表示項目、順番、サイズ、配置を扱う。具体的な記法や自由度は、実装時に再検討する。既存 Thread の表示は作成時点の Layout スナップショットで固定する。

## 2026-09-21 - ニックネームではなく表示名を使う

状態: 採用

Account の Niixy ID とは別に、他者へ表示する名前は「表示名」と呼ぶ。v0.3 では表示名を実装せず、Account の投稿者表示には `@NiixyID`、Guest には `Guest` を使う。表示名を実装後は、投稿表示で `表示名 @NiixyID` の順に表示する。

## 2026-09-22 - Note を独立した投稿形式にしない

状態: 採用

日記、ブログ、料理レシピ、ゲームレビューなどは、独立した Note モデルではなく、Thread と ThreadPost で表す。Thread の `#1` を記事本文、Response をコメントとして扱い、必要な属性は Interface で追加する。

## 2026-09-22 - Book を Thread の公開コレクションにする

状態: 採用

Book は Thread をテーマごとにまとめ、公開・購読できるコレクションとする。Room が参加者同士の会話や活動の場であるのに対し、Book は作成者のコンテンツを整理して公開する場である。初期方針では Book 作成者だけが Thread を追加できる。Book 内の Thread は Book が定める ThreadInterface と ThreadPostLayout を使う。

## 2026-09-22 - 共通の概要一覧を SummaryList と呼ぶ

状態: 採用

Thread、Room、Response、Tweet、Book などを詳細表示の前に要約して並べる共通の表示パターンを SummaryList、各要約表示を SummaryItem と呼ぶ。SummaryItem は現時点ではアコーディオンで概要を展開できるが、将来はクリック時に直接 DetailPane を開く形へ変更できる。共通化するのは表示・選択・詳細表示の体験であり、各コンテンツを同じドメインモデルへ統合することではない。

## 2026-09-22 - Layout は Interface を参照して表示を定義する

状態: 一部置換（2026-09-24 の ThreadPostLayout に関する決定）

DisplayLayout を Layout の総称とし、ThreadLayout と ProfileLayout を設ける。Layout は必要な Interface と使用するフィールドを要件として宣言し、各項目の表示順、サイズ、配置を定義する。Interface はフィールド構造を、Account などによる Interface 実装は入力値を保持する。Layout がフィールド定義や入力値を持つ二重管理は行わない。後に ThreadLayout は ThreadPostLayout へ置き換えたが、Layout と Interface の責務分離は維持する。

## 2026-09-22 - AccountPageHeader で閲覧中の Account を固定表示する

状態: 採用

Account ページでは SiteHeader の直下に `表示名 @NiixyID` を表示する細い AccountPageHeader を固定する。Account 内の活動一覧や詳細Paneへ遷移しても、閲覧中の Account を継続して識別できるようにする。Account ページでは長いパンくずを使わず、SiteHeader は Niixy ロゴを中心とする。

## 2026-09-23 - 公開 Account ページと MyPage の責務を分ける

状態: 採用

公開 Account ページは、本人を含む利用者が公開情報、Album、活動履歴を閲覧する場所とする。本人用の編集・管理は MyPage に集める。MyPage は将来、Album とサムネイル、AccountInterface、ProfileLayout の管理を担当する。対象の編集・削除などは、MyPage に複製した一覧ではなく、各コンテンツを開いた場所で削除権限に応じて提供する。

## 2026-09-24 - Interface 間の関係を Require とする

状態: 採用

Interface の関係は定義を取り込む継承ではなく、別の Interface の実装を要求する InterfaceRequirement で表す。Require 先と Require 元は対象へそれぞれ実装し、複数経路から同じ Interface を要求しても実装と値は一つだけとする。Require 関係は循環を禁止する。

## 2026-09-24 - Interface の最新版適用と既存対象の Snapshot を両立する

状態: 採用

公開済み InterfaceVersion と Field 定義は変更しない。新規実装では各 Interface と Require 先の最新版だけを使用し、利用者に Version を選ばせない。InterfaceRequirement は特定 Version を固定せず、新規実装時に Require 先の最新版との互換性を検証する。互換性を失った依存元 Interface は、作成者が新 Version で対応するまで新規利用できない。既存 Thread は適用時点の Version 構成を維持し、作成者が差分を確認して最新版へ更新できるようにする。Field 定義を変更する場合は新しい Field とし、未変更の Field だけ同じ Field ID と値を引き継ぐ。旧 Version は過去ログ維持のために残し、新規投稿を最新版へ集約して検索対象の分散を抑える。

## 2026-09-24 - Interface は Draft を経て公開し Soft Delete する

状態: 採用

新規 Interface と公開済み Interface の次回 Version は、作成者だけが扱う Draft として途中保存する。Draft は公開済み InterfaceVersion ではなく、公開時に検証を通過した定義だけを変更不能な v1 または次の Version として作成する。Version 番号は公開時に確定し、現在 Version は公開完了後に切り替える。削除は Interface を `deleted` にする Soft Delete とし、定義を空にした新 Version は作らない。削除済み Interface は一覧から隠して新規実装・新規 Require を禁止するが、既存対象は解決済み Version を継続利用する。削除済み Interface と同名で作成しようとした場合は既存 Interface の復元として扱い、定義も変える場合だけ新 Version を作る。Version は定義変更だけを表し、公開済み Version と Field は削除しない。

## 2026-09-24 - ThreadInterface は作成後も変更可能にする

状態: 採用

Thread 作成後も ThreadInterface の追加、削除、実装値の編集、最新版への更新を許可する。Require された Interface は単独削除できず、操作後の構成は Requirement を満たさなければならない。変更は構造化された履歴として保持し、システム Response と `#1` 内の履歴一覧で示す案を有力とする。

## 2026-09-24 - ThreadPostLayout と固定本文領域を使う

状態: 採用

ThreadLayout という名称を ThreadPostLayout へ置き換え、`#1` と返信の両方へ適用する。ThreadPostLayout は AccountInterface と ThreadPostInterface を要求でき、`#1` でも ThreadPostInterface の値を入力する。本文、ThreadInterface 一覧、対象の機能ボタン群を含む本文領域は必須の固定 Item とし、その周囲に Thumbnail、表示名、Interface Field、Niixy ID、投稿日時などを配置できるようにする。ThreadPost 作成時の AccountInterface、ThreadPostInterface、Layout は Snapshot として固定する。

## 2026-09-24 - Tweet と Timeline を Thread と分ける

状態: 採用・詳細保留

Tweet は Thread に属さず Account の資産として蓄積する単独の呟き、Timeline は Tweet を収集し必要に応じて投稿先にもなる概念とする。Room には Thread と Timeline を置くことができ、NiiMap には Room、Thread、Timeline、Tweet を配置できる。Self、Follow、Fav、Bad はカスタム Timeline と同じ収集・制限の仕組みを使う削除不可の標準 Timeline とする。Tweet と Timeline への Interface、Layout、掲載の詳細は実装時に決める。

## 2026-09-24 - SummaryItem から DetailPane を直接開く

状態: 採用

SummaryItem 内の概要アコーディオンと「詳細を見る」操作を廃止し、SummaryItem の選択で対象別の DetailPane を直接開く。DetailPane は共通の表示パターン名として残し、具体的な領域は ThreadDetailPane、InterfaceDetailPane のように対象名を付けて呼ぶ。

## 2026-09-24 - 保存先を将来複数作成可能にする

状態: 採用・詳細保留

コンテンツに対する操作は「保存」とし、利用者が保存先を選択できる方向で設計する。初期の保存先として Bookmark を一つ提供し、将来は複数の保存リスト作成と保存時の新規リスト作成に対応する。当面は単一 Bookmark を前提に実装し、複数化に伴うデータモデルと UI の変更は Bookmark 基盤の完成後に行う。
