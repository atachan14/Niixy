# Room と NiiMap

## NiiMap

NiiMap はコンテンツを発見・作成する地図上の入口である。地図マーカーは独立した Pin ではなく、NiiMap へ直接配置された対象を表す。

NiiMapは地図に直接配置されたThread、Room、Boardを表示する。Guest／Accountとも地点を選んでBoardを直接作成できる。Timeline、TweetのNiiMap配置は後続実装で扱う。Room や Timeline の内部にあるコンテンツを NiiMap でどのように表示するかは、それぞれの公開範囲と掲載関係を踏まえて実装時に決める。

一覧PaneにはMapの表示範囲内にある対象だけを表示する。「検索」では基本情報、実効Policy、Field、Interfaceを組み合わせて絞り込み、「新規作成」では先に地点と対象種別を選び、対象の作成Paneへ遷移する。検索窓は実行後も条件を保持したままアコーディオンとして収納する。

## Room

Room は Account が作成・管理する場所である。Collection と Timeline を置くことができ、固有の設定、所属、制限、Interface を定義できる。Room 自体も NiiMap へ配置できる。

Community と NiiRoom は Room に置き換えられた旧名称である。

## RoomOwner と参加者

Room は常に一人の RoomOwner を持つ。Room作成時には作成AccountをRoomOwnerかつ参加者とする。RoomOwnerはOwnerである間は退出できず、将来は別の参加者へOwnerを譲渡できるようにする。Room内Tagと複数管理者はOwnerとは別の権限として扱う。

Guestは継続的な参加状態を保持するAccountを持たないため、Roomへ参加できずRoomOwnerにもなれない。RoomPolicyは閲覧や参加条件を定義できる方向で設計するが、Guest参加を許可する設定は持たない。

## Collection と Board

Room作成時には`Main`という名称の通常Collection、システムCollection`未分類`、Main内の`最初のBoard`を自動作成する。RoomPageにはBoardを直接表示せず、`Board`ボタンからCollection Tabを備えたBoard一覧Paneを開く。Tabは作成順の通常Collection群、`未分類`、Room管理者だけに表示する`管理`の順とする。`Main`は初期名称であり、通常Collectionと同様に名称変更と削除を認める。Boardを一つも持たないRoomも認める。

各Collection Tabでは詳細確認とBoard作成を排他的に展開する。詳細確認にはCollection名とBoard数を表示し、通常CollectionではRoom管理者だけが名称編集と削除へ進める。Boardは選択中Collectionへ作成する。Collectionの新規作成は管理Tabで行い、並び替えは後続Versionで扱う。

Room内の会話はBoardに配置したThreadで行う。Boardは独立したOwnerを持たず、配置先Collectionが属するRoomの管理者が管理する。Collectionを削除した場合、そこに配置されているBoardは同じRoom内のシステムCollection「未分類」へ移す。「未分類」は固定名、削除不可、並び替え不可とするが、Boardの作成先には指定できる。Collectionのうちシステム上の特別な識別を持つのは「未分類」だけとする。

RoomPolicyはRoom自体の閲覧、参加、管理を制限する。BoardPolicyはBoard自体の閲覧やThread作成を制限する。RoomのBoardTemplateとBoardのThreadTemplateは子対象の作成時に推奨値または強制値を確定保存し、作成後も編集可能な設定を編集する場合はその時点の強制値を再適用する。対象が親Templateを継続参照する構造にはしない。ThreadPolicyは作成後変更不可なので作成時にだけ確定し、親の変更や削除の影響を受けない。Templateは後続Versionで実装する。

## 配置と参照

対象は同時に最大一つの配置先を持ち、共有する側が別に参照を持つ。ThreadはNiiMapまたはBoardへ配置でき、作成後に配置先を変更しない。BoardはCollectionまたはNiiMapへ配置できる。RoomはNiiMap座標の変更、未配置化、再配置を認める。TimelineもRoomまたはNiiMapに置くことができる。

Boardの配置先変更は、異なるRoomやAccountの管理者間で申請・承認する用途を中心に後続Versionで実装する。NiiMapへ直接配置したBoardは、配置後の移動、編集、削除ができない。Collectionから参照されたBoardは配置先や管理主体を変更せず、参照解除によって本体を削除しない。

## v0.6 の範囲

v0.6ではRoomの作成とNiiMap配置、RoomPage、Main Collectionと`最初のBoard`、ログイン済みAccountの即時参加、参加者によるThread作成とResponse投稿を実装する。参加申請、参加条件、Owner譲渡、Room内Tag、BoardPolicy、Collection管理、ProfileAreaは後続Versionへ回す。

NiiMapではRoom自体をSpotとして表示・検索する。Room内部のThreadを検索一致理由として利用する機能は後続Versionへ回す。

## RoomTagの長期構想

状態: 長期構想 / Version未割当 / 未確定設計。v0.10・v0.11では実装しない。

Room管理者らが自由にRoomTagを作成し、Memberへ適用してAccount条件に利用する案を保存する。初期作成され削除不可のTag「管理者」も構想する。

Tagの付与・剥奪権限、Ownerとの関係、「管理者」Tagが与える権限は未設計である。自由なTagと管理権限を同一視しない。Owner変更操作、複数管理者、既存データ移行の詳細も未設計であり、既存構想を確定・置換するものではない。

Room参加者・Room管理者・RoomOwner・各RoomTag適用者をAccount条件として選ぶ導線は、[Account条件の長期構想](access-policy.md#account条件のroom関係選択uiの長期構想)と合わせて検討する。
