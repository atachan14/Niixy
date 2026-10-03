# Room と NiiMap

## NiiMap

NiiMap はコンテンツを発見・作成する地図上の入口である。現行の地図マーカーは独立した Pin ではなく、ThreadPlacement を表す。

現行の NiiMap は地図に直接掲載された Thread を表示する。将来は Room、Board、Thread、Timeline、Tweet を NiiMap の座標へ配置できるようにする。Room や Timeline の内部にあるコンテンツを NiiMap でどのように表示するかは、それぞれの公開範囲と掲載関係を踏まえて実装時に決める。

一覧PaneにはMapの表示範囲内にある対象だけを表示する。「検索」では基本情報、実効Policy、Field、Interfaceを組み合わせて絞り込み、「新規作成」では先に地点と対象種別を選び、対象の作成Paneへ遷移する。検索窓は実行後も条件を保持したままアコーディオンとして収納する。

## Room

Room は Account が作成・管理する場所である。Collection と Timeline を置くことができ、固有の設定、所属、制限、Interface を定義できる。Room 自体も NiiMap へ配置できる。

Community と NiiRoom は Room に置き換えられた旧名称である。

## RoomOwner と参加者

Room は常に一人の RoomOwner を持つ。Room作成時には作成AccountをRoomOwnerかつ参加者とする。RoomOwnerはOwnerである間は退出できず、将来は別の参加者へOwnerを譲渡できるようにする。Room内Tagと複数管理者はOwnerとは別の権限として扱う。

Guestは継続的な参加状態を保持するAccountを持たないため、Roomへ参加できずRoomOwnerにもなれない。RoomPolicyは閲覧や参加条件を定義できる方向で設計するが、Guest参加を許可する設定は持たない。

## Collection と Board

Room作成時にはMain Collectionと、その中の`最初のBoard`を自動作成する。RoomPaneへ表示するBoardはMain固定ではなく、Room管理者が選択したCollectionから取得できるようにする。Boardを一つも持たないRoomも認める。

Room内の会話はBoardに配置したThreadで行う。BoardPolicyと個別ThreadPolicyはANDで評価する。v0.6ではBoardPolicyを編集できず、Room参加者だけがBoard内でThread作成とResponse投稿を行える固定ルールから始める。

## 掲載と共有

Thread は一つの主掲載先を持ち、追加の共有先を持てる。NiiMapとBoardはThreadの掲載先になり得る。BoardはCollectionまたはNiiMapへ、CollectionはAccountまたはRoomへ配置する。TimelineもRoomまたはNiiMapに置くことができる。移動は主掲載先の変更、共有は参照の追加として扱い、対象自体を複製しない。

## v0.6 の範囲

v0.6ではRoomの作成とNiiMap配置、RoomPage、Main Collectionと`最初のBoard`、ログイン済みAccountの即時参加、参加者によるThread作成とResponse投稿を実装する。参加申請、参加条件、Owner譲渡、Room内Tag、BoardPolicy、Collection管理、ProfileAreaは後続Versionへ回す。

NiiMapではRoom自体をSpotとして表示・検索する。Room内部のThreadを検索一致理由として利用する機能は後続Versionへ回す。
