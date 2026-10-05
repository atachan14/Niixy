# コンテンツモデル

## Thread

Thread は Niixy 上の会話の単位である。NiiMap に直接、または Board の中で作成できる。Thread は Event や Pin ではない。

Thread はタイトル、作成者、作成日時、更新日時、`last_activity_at`、必須の開始 ThreadPost（`#1`）を持つ。作成時にはタイトルと開始本文を同時に入力する。Thread Title は作成後に編集しない。

開始本文の単独削除は許可しない。開始投稿を削除する場合は Thread 全体を削除する。Thread 削除時は Title と `#1` を削除済み表示へ置き換え、既存の返信は残す。

## ThreadPost

ThreadPost は開始投稿と返信の両方を表す。投稿は時系列順に表示し、Thread 内で変わらない投稿番号を持つ。

返信はフラットな時系列の一覧とする。`>>1` のような参照は別の投稿へのリンクであり、ネストした返信ツリーを作らない。将来は参照先を hover で表示する UI を検討する。

ThreadPost の本文と ThreadPostInterface の実装値は、投稿後に編集しない。ThreadPostInterface は `#1` と返信の両方へ適用できる。削除済みの返信は、投稿番号を維持したまま、当面は「削除されました」と表示する。削除済み表示のレイアウトや文言は将来の DisplayLayout と合わせて再検討する。

## ThreadInterface の更新

Threadには複数のDirectFieldとThreadInterfaceを適用できる。DirectFieldはFieldを個別に追加する経路、ThreadInterfaceは複数Fieldや機能を用途ごとにまとめる経路とする。作成後も新規Field・Interfaceの追加、既存実装の削除、値の編集、最新版への更新を許可する。同じFieldまたは片同義で接続されたFieldは、実装経路にかかわらずThread内の一つのValueを共有する。

Version 更新では、旧 Version の削除と新 Version の追加を利用者に個別操作させず、一つの更新操作として扱う。両 Version で継続する同一 Field の値は引き継ぎ、追加 Field は入力を求め、使用されなくなる Field は差分確認に表示する。片同義によって複数の既存Valueが統合される場合は、最初に実装されたFieldのValueを維持し、保存前に影響を示す。

Interface の追加、削除、実装値編集、Version 更新は構造化された履歴として保持する。Thread の時系列上で変更時点を示すシステム Response として表示し、`#1` の ThreadInterface 領域から更新履歴を一覧できるようにする案を有力とする。具体的な表示と、システム Response の投稿番号・Response 数への扱いは実装時に決める。

## Collection

Collection は Board を掲載する一覧であり、一つの Account または Room に配置する。Collection 自体は NiiMap へ配置しない。Account と Room には初期 Collection として `Main` を用意するが、通常の Board 作成時には配置先 Collection を利用者が選ぶ。

Collection は Board と別の Collection を参照できる。参照先を複製せず、参照解除によって対象本体を削除しない。Collection 間の循環参照は禁止し、複数経路から同じ Board に到達した場合の表示規則は Collection 管理機能の実装時に確定する。

Collection を削除する場合、その Collection に配置されている Board は、同じ Account または Room に属するシステム Collection「未分類」へ移す。「未分類」がなければ自動作成し、既にあれば再利用する。表示名ではなくシステム上の役割で通常の Collection と区別する。Collection が参照している Board や Collection は、対象本体を変更せず参照だけを解除する。

## Board

Board は Thread をテーマや用途ごとにまとめるコンテナである。会話、告知、日記、ブログ、料理レシピ、ゲームレビューなどを、独立した投稿モデルではなく Board 内の Thread として表す。用途ごとの差は BoardPolicy、ThreadPostLayout、Board の表示方法で表現する。

Board は独立した Owner を持たず、一つの配置先を持つ。配置先は Account または Room に属する Collection、もしくは NiiMap の座標とする。Collection に配置された Board は、その Collection が属する Account または Room の管理者が管理する。NiiMap に直接配置された Board には配置先管理者が存在せず、配置後の編集と削除を認めない。Guest／Accountとも直接作成でき、初期BoardPolicyは閲覧／Thread作成がGuest OR NiixyAccount、deny空とする。共通4欄のAccount条件は作成時に変更でき、保存後のBoardPolicyも変更不可とする。

Room 作成時には、Room の Main Collection 内に `最初のBoard`を自動作成する。Board を使用しない Room も認め、Board 管理機能の実装後は最後の Board も削除できるようにする。Account の初期 Main Collectionにはブログ用 Board を用意する方向とするが、Account側の導入時期と詳細は実装時に決める。

Board の配置先変更は後続 Version で扱う。主用途は、異なる管理者間での移動申請と承認である。NiiMap へ直接配置した Board は、それ以降の配置先変更、未配置化、編集、削除を認めない。

Board の削除は物理削除とし、復元機能や削除済み一覧を設けない。削除された Board に配置されていた Thread は未配置になるが、Thread 本体、Response、ThreadPolicy、Field、Interface、その Thread への外部参照は残す。Board が保持していた参照は Board とともに削除する。削除後も ThreadPolicy に従って Response 投稿と編集可能な Thread 情報の変更を認める。

削除された Board を参照していた Collection では、参照 Item を対象なしの状態で残せるようにする。「削除されました」と表示し、Collection 管理者が参照 Item を取り除ける。参照時点の名称などを Snapshot として残すかは、参照機能の実装時に決める。

## 配置と参照

Thread、Board、Room などの対象は、同時に最大一つの配置先を持つ。別の Board、Collection、Account の List、fav、bad などから共有する場合は、対象自身の配置を増やさず、共有する側が独立した参照を持つ。参照の追加や解除によって対象本体、配置先、ほかの参照を変更しない。

Thread の配置先は作成時に確定し、作成後に変更しない。NiiMap への配置は座標を、Board への配置は Board との関係を保持する。配置先の Board が削除された場合は未配置となる。未配置 Thread も、Account の活動履歴、fav、bad、List、別の Board が保持する参照、Thread 固有 URL などから継続利用できる。

Board 詳細の Thread 一覧には、その Board に配置された Thread と、その Board が参照する Thread の両方を表示できる。参照は閲覧権限を付与せず、利用可否は参照先 Thread の ThreadPolicy に従う。

Room は Room 管理者による NiiMap 座標の変更、未配置化、再配置を認める。対象ごとに配置変更の可否は異なるため、「配置先は一つ」と「配置先は変更不能」を同じ規則にはしない。

## 活動日時

`last_activity_at` は Thread、Board、Collection、Room に対する最後の意味のある操作日時である。活動中のコンテンツの並び順に使い、Thread 作成、ThreadPost 作成、関連する Interface の更新、掲載先変更、再掲載などで更新する。上位対象へどこまで活動を伝播するかは、各対象の実装時に確定する。

## 投稿時点のスナップショット

投稿者が後からニックネーム、サムネイル、Interface の情報を変更しても、ThreadPost の表示は安定している必要がある。そのため長期的には、投稿時点の投稿者表示情報をスナップショットとして持つ。具体的な項目とサムネイルの保存は、最小構成の v0.3 より後で決める。
