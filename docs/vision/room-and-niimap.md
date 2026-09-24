# Room と NiiMap

## NiiMap

NiiMap はコンテンツを発見・作成する地図上の入口である。現行の地図マーカーは独立した Pin ではなく、ThreadPlacement を表す。

現行の NiiMap は地図に直接掲載された Thread を表示する。将来は Room、Thread、Timeline、Tweet を NiiMap の座標へ配置できるようにする。Room や Timeline の内部にあるコンテンツを NiiMap でどのように発見させるかは、それぞれの発見制限と掲載関係を踏まえて実装時に決める。

## Room

Room は Account が作成・管理する場所である。Thread と Timeline を置くことができ、固有の設定、所属、制限、Interface を定義できる。Room 自体も NiiMap へ配置できる。

Community と NiiRoom は Room に置き換えられた旧名称である。

## Book との役割の違い

Room は参加者同士の継続的な会話や活動の場である。対して Book は、作成者のコンテンツをテーマごとに整理し、継続して公開するコレクションである。どちらも Thread を含められるが、Room では会話や参加が中心であり、Book では `#1` のコンテンツが中心になる。

## 掲載と共有

Thread は一つの主掲載先を持ち、追加の共有先を持てる。NiiMap、Room、Book は掲載先または共有先になり得る。Timeline も Room または NiiMap に置くことができる。移動は主掲載先の変更、共有は掲載先の追加として扱う。両者は履歴上で区別でき、対象自体を複製しない。

## v0.3 の範囲

Room の作成、所属、掲載、共有、発見は v0.3 の対象外である。初期実装では NiiMap に直接配置する Thread を扱う。
