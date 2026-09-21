# Room と NiiMap

## NiiMap

NiiMap は Thread を発見・作成する地図上の入口である。地図マーカーは独立した Pin ではなく、ThreadPlacement を表す。

NiiMap は地図に直接掲載された Thread を表示する。将来は、Room 側の制限が発見を許可する場合に Room から共有された Thread も表示できるようにする。

## Room

Room は Account が作成・管理する場所である。Thread を含められ、固有の設定、所属、制限、Interface を定義できる。

Community と NiiRoom は Room に置き換えられた旧名称である。

## 掲載と共有

Thread は一つの主掲載先を持ち、追加の共有先を持てる。移動は主掲載先の変更、共有は掲載先の追加として扱う。両者は履歴上で区別でき、Thread 自体を複製しない。

## v0.3 の範囲

Room の作成、所属、掲載、共有、発見は v0.3 の対象外である。初期実装では NiiMap に直接配置する Thread を扱う。
