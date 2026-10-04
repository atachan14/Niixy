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

状態: 置換済み（2026-10-04 の「配置と参照を分離する」を採用）

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

状態: 置換済み（2026-10-03 の「Book を Board へ統合する」を採用）

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

状態: 置換済み（2026-09-29 の「Field を Interface から独立させる」を採用）

Interface の関係は定義を取り込む継承ではなく、別の Interface の実装を要求する InterfaceRequirement で表す。Require 先と Require 元は対象へそれぞれ実装し、複数経路から同じ Interface を要求しても実装と値は一つだけとする。Require 関係は循環を禁止する。

## 2026-09-24 - Interface の最新版適用と既存対象の Snapshot を両立する

状態: 一部置換済み（2026-09-29 の「Field を Interface から独立させる」を採用）

公開済み InterfaceVersion と Field 定義は変更しない。新規実装では各 Interface と Require 先の最新版だけを使用し、利用者に Version を選ばせない。InterfaceRequirement は特定 Version を固定せず、新規実装時に Require 先の最新版との互換性を検証する。互換性を失った依存元 Interface は、作成者が新 Version で対応するまで新規利用できない。既存 Thread は適用時点の Version 構成を維持し、作成者が差分を確認して最新版へ更新できるようにする。Field 定義を変更する場合は新しい Field とし、未変更の Field だけ同じ Field ID と値を引き継ぐ。旧 Version は過去ログ維持のために残し、新規投稿を最新版へ集約して検索対象の分散を抑える。

## 2026-09-24 - Interface は Draft を経て公開し Soft Delete する

状態: 一部置換済み（2026-09-29 の「Field を Interface から独立させる」を採用）

新規 Interface と公開済み Interface の次回 Version は、作成者だけが扱う Draft として途中保存する。Draft は公開済み InterfaceVersion ではなく、公開時に検証を通過した定義だけを変更不能な v1 または次の Version として作成する。Version 番号は公開時に確定し、現在 Version は公開完了後に切り替える。削除は Interface を `deleted` にする Soft Delete とし、定義を空にした新 Version は作らない。削除済み Interface は一覧から隠して新規実装・新規 Require を禁止するが、既存対象は解決済み Version を継続利用する。削除済み Interface と同名で作成しようとした場合は既存 Interface の復元として扱い、定義も変える場合だけ新 Version を作る。Version は定義変更だけを表し、公開済み Version と Field は削除しない。

## 2026-09-24 - ThreadInterface は作成後も変更可能にする

状態: 一部置換済み（2026-09-29 の「Field を Interface から独立させる」を採用）

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

## 2026-09-29 - Field を Interface から独立させる

状態: 採用（2026-09-24 の InterfaceRequirement と Interface 内 Field 定義を置換）

Field は InterfaceVersion の内部定義ではなく、作成者と安定 ID を持つ独立した再利用可能な定義とする。Field は対象種別を持たず、Account、Room、Thread、ThreadPost などへの実装時に対象ごとの Value と接続する。InterfaceVersion は FieldVersion を参照し、必須・任意と表示順を保持する。

Field は Version を持つ。公開済み FieldVersion は変更せず、新規 InterfaceVersion は各 Field の最新版だけを参照できる。既存対象は実装時の InterfaceVersion と FieldVersion を継続利用する。Field の意味または値型を変える場合は新しい Field とし、同じ値を安全に引き継げる変更だけを同じ Field の新 Version とする。

FieldVersion は別の Field を片同義として参照できる。片同義の検索展開は参照元から参照先への片方向とするが、同じ対象へ両 Field が実装された場合は一つの Value を共有する。複数の既存 Value が片同義によって接続される場合は、対象へ最初に実装された Field の Value を維持し、Interface 実装前に変更内容を示す。

Field の再利用を InterfaceRequirement で表現しない。InterfaceRequirement は廃止し、Field、将来の ComputedField、Action、Layout の依存は Field 参照または RequireField で表現する。複数 Interface の同時実装は維持し、各 Interface は用途ごとの意味のあるまとまりとして表示する。

## 2026-09-29 - Layout を Interface と独立させる

状態: 採用

Layout は複数 Interface の Field、ComputedField、Action を横断して配置するため、InterfaceVersion の内部には置かず独立した定義とする。対象は用途に対応する Layout を一つ使用し、通常利用者には Niixy の標準 Layout を自動適用する。ThreadPost 作成時の Layout Snapshot と、本文などの固定領域を Layout から削除できない方針は維持する。

当時はField、ComputedField、Action、Interface、Layoutのユーザー向け総称を「定義（Definition）」としていた。この名称判断は、2026-10-02の「Moduleをユーザー向け総称とする」により置き換えた。

## 2026-10-02 - Moduleをユーザー向け総称とする

状態: 採用

Field、ComputedField、Action、Interface、Layoutのユーザー向け総称は「Module」とする。MyPageとProfileではModuleを一つの入口とし、Module種別、対象種別、検索・自作・保存済み・削除済みの順に一覧を絞り込む。Draftを持つInterfaceとLayoutでは、自作の隣に編集中を加えて公開済みModuleとDraftを分離する。

Module一覧の最上位分類はElement、Interface、Layoutとする。ElementはInterfaceなどを構成する単位を表し、Field、ComputedField、Actionを分類する。

ProfileでもMyPageと同じModule一覧・詳細Paneを使用する。Profileでは、Profile本人が公開した自作ModuleとProfile本人が保存したModuleだけを扱う。保存済みは閲覧者自身の保存先ではない。新規作成、検索、編集中、削除済みは表示しない。実装済みAccountIFはAccountInterface実装時に分類を追加する。

画面、URL、画面制御など上位概念を扱う内部名称にも`module`を使用する。一方、`FieldDefinition`のように具体的な定義データを表す既存モデル名は維持する。ModuleはUIとドメイン上の分類であり、共通の親データモデルを必須としない。

## 2026-10-02 - ThreadへのDirectField実装を認める

状態: 採用

Thread作成時には、FieldをThreadInterface経由だけでなくDirectFieldとして個別に追加できる。DirectFieldは作成時の入力を必須とし、追加時点の最新FieldVersionを固定する。DirectFieldとThreadInterface内のFieldは共通のValue解決処理を使い、同一Fieldまたは片同義Fieldであれば一つのThreadFieldValueを共有する。UIでは同じValueを参照するFieldへホバーまたはフォーカスした際、関連するFieldまたは収納中の親アコーディオンを強調する。

## 2026-10-02 - Threadの発見制限を廃止する

状態: 採用（2026-09-20の最小制限と、発見・閲覧を分離する方針を一部置換）

Threadがどこに現れるかは配置先と参照が決める。Thread固有のPolicyは閲覧制限と書込制限を持ち、発見制限は持たない。

閲覧できないThreadも掲載先の一覧、Map、検索、Profileには存在を表示する。本文とThreadPostはサーバー側で返さず、詳細では閲覧できないことを案内する。存在自体を隠す必要が生じた場合は、公開範囲を持つRoomなど掲載先側の仕様として実装時に再設計する。

## 2026-10-02 - Account条件を再利用可能な一覧として扱う

状態: 採用

作成者検索とPolicyで使うAccount条件は、Default、Account、AccountIF、Field、Roomを同じ一覧から選択する。Accountごとに一覧と使用順を保持し、既存条件の再追加では重複させず先頭へ移動する。削除したDefault条件はDefault一覧から復元できる。

呼び出し元に追加した条件Item同士はOR、ANDグループ内の条件同士はANDとして評価する。ANDグループは条件種別をまたいで作成でき、成立不能な組み合わせも当面は利用者の判断に委ねる。

## 2026-10-03 - SummaryListの取得形式を共通化する

状態: 採用

SummaryListのページネーションUIとAjax差し替え処理を共通化し、標準表示数を20件とする。一覧固有の事情がある場合だけ内部的に上書きできる余地を残す。NiiMapのように表示範囲と連動する一覧では、同じSummaryListを使いながらページ送り以外の取得方法を採用できる。

検索条件、権限、ソートが異なるため、Field、Interface、Accountなどを一つの巨大な検索処理へ統合しない。検索処理は対象種別ごとに分け、検索結果の表示形式とページネーション契約を揃える。Thread、Room、Book、Timeline、TweetはNiiMapへ並ぶSpotという共通用途を持つため、Spot検索として横断的に扱う。

Account条件一覧のItemは検索元のAccountやFieldそのものではなく、再利用可能なAccountConditionとする。新しい条件を探す導線では対象別検索を利用し、履歴へ追加した時点で条件定義として扱う。

## 2026-10-03 - Book を Board へ統合する

状態: 一部置換（2026-10-04 の「Policy Templateは作成時に確定する」を採用）

Thread をまとめるコンテナは Board に統一し、Book を独立したコンテンツ種別として実装しない。会話用、告知用、ブログ用などの用途差は、BoardPolicy、ThreadPostLayout、Board の表示方法によって表現する。ブログでは、Thread のタイトル、`#1` の一部、続きを開く導線を一つの Item として縦に並べる表示を標準候補とする。

Board は安定 ID と変更可能な名称を持つ。BoardPolicy と Board 内の個別 ThreadPolicy は AND で評価し、双方を満たす利用者だけが対象 Thread を利用できる。Board の表示方法、Policy、管理操作の詳細は Board 実装時に確定する。

## 2026-10-03 - Collection を Account または Room に配置する

状態: 一部置換（2026-10-04 の「Boardの管理主体は配置先から決める」を採用）

Collection は Board を掲載する一覧であり、必ず一つの Account または Room に配置する。Collection 自体を NiiMap の座標へ直接配置しない。Account と Room には初期 Collection として `Main` を作成する。通常の Board 新規作成時には配置先 Collection を利用者が選択し、Main へ自動掲載しない。

Board は一つの主配置先を持ち、主配置先には Collection または NiiMap の座標を指定する。Account や Room を Board の直接の配置先にはせず、Collection を介して掲載する。これにより、Board から Collection、その配置先である Account または Room へ掲載経路を辿れるようにする。

Account の初期状態では、Main Collection 内にブログ用 Board を用意する方向とする。初期 Collection と初期 Board の削除、再作成、名称変更などの詳細は Account と Board の実装時に確定する。

Room の初期状態では、Main Collection 内に `最初のBoard`を自動作成する。Board を使わない Room も認め、Board 管理機能の実装後は最後の Board も削除できるようにする。

## 2026-10-03 - RoomPane に表示する Collection を選択する

状態: 置換済み（2026-10-04 の「RoomPageではBoardボタンから一覧Paneを開く」を採用）

RoomPane に表示する Board は、Main 固定ではなく、Room 管理者が選択した一つの Collection から取得する。初期状態では Main を表示用 Collection とするが、公式情報や交流などの運用に応じて別の Collection へ変更できるようにする。

RoomPane では表示用 Collection から更新の新しい Board を最大三件表示し、`もっと見る`から Collection ごとの Board 一覧へ遷移する案を初期方針とする。Account と Room の Board 一覧では、Main とカスタム Collection をタブで切り替える。表示件数とタブ構成の具体的な UI は Room 実装時に調整する。

## 2026-10-03 - Collection は Board と Collection を参照できる

状態: 一部置換（2026-10-04 の「Boardの管理主体は配置先から決める」を採用）

Collection は、自身を主配置先とする Board に加えて、別の Board および別の Collection を参照できる。参照先は複製せず、参照元から解除しても対象本体を削除しない。参照先 Collection の内容が変わった場合は参照元の表示にも反映する。

Collection 間の循環参照は禁止する。複数経路から同じ Board に到達した場合の重複排除、参照 Collection の見出し表示、並び順などは Collection 実装時に確定する。DB では Collection が対象 ID の配列を直接持つ形ではなく、掲載順や関係種別を保持できる中間モデルで表現する。

Board の Owner は Account または Room とし、主配置先や参照先とは分離する。別の Collection から参照されても Owner は変わらない。Board を作成した実 Account は監査用情報として内部に保持する方向とし、管理権限の追加は BoardPolicy で表現する。Owner の移譲と複数管理者の詳細は実装時に確定する。

## 2026-10-03 - Profile を Account と Room の共通表現領域とする

状態: 採用・詳細保留

Profile は Account の公開ページ全体を指す名称ではなく、Account と Room が自身の情報やコンテンツを表現する共通領域とする。この領域を ProfileArea と呼び、ProfileLayout によって内容と配置を定義する。

Account と Room は、Niixy の独立した Field ではない基本情報として自由記述の Description を持つ。ProfileLayout は Description の表示を任意とし、ほかの Field、Timeline、Thread、Board なども縦横に配置できるようにする。ProfileArea は Layout によってページの主要コンテンツにも補助的な領域にもなり得るため、About や Overview とは呼ばない。

画面全体の内部名称は、対象 Account を閲覧する画面を AccountPage、対象 Room を閲覧する画面を RoomPage とする。MyPage はログイン中 Account が情報や機能を管理する本人用画面として区別する。利用者向けの導線では、AccountPage を従来どおり `Profile` と表示してもよい。

## 2026-10-03 - Room は一人の Owner と Account の参加者を持つ

状態: 採用・詳細保留

Room 作成時には、作成した Account を参加者かつ RoomOwner とする。存在する Room は常に一人の RoomOwner を持ち、RoomOwner は Owner である間は退出できない。将来は RoomOwner を別の参加者へ譲渡できるようにし、譲渡後の旧 Owner は通常の参加者として退出可能にする。

Guest は継続的な関係を保存する Account を持たないため、RoomPolicy の設定にかかわらず Room へ参加できず、RoomOwner にもなれない。これは画面上で参加操作を隠すだけでなく、サーバー側でも常に保証する。Guest の閲覧や Guest 投稿など、Account への紐付けを必要としない操作は別の Policy として扱う。

Room は参加条件を RoomPolicy として持てる方向で設計する。v0.6 では参加申請と参加条件を実装せず、ログイン済み Account が即時参加できる固定ルールから開始する。Room 内 Tag、複数管理者、Owner 譲渡は後続 Version で扱う。

## 2026-10-03 - v0.6 は Room の基本的な共同利用を成立させる

状態: 採用

v0.6 は、Room の作成と NiiMap 配置、RoomPage、Main Collection と `最初のBoard`の自動作成、Room 参加、参加者による Board 内 Thread 作成と Response 投稿を対象にする。Room は NiiMap の Spot として検索・表示するが、Room 内部の Thread は NiiMap 検索対象に含めない。

BoardPolicy と編集可能な RoomPolicy は後続 Version へ回す。v0.6 の Room 内書込は参加者だけに許可する固定ルールとし、Guest と非参加 Account は既存 ThreadPolicy が許す範囲で閲覧だけできる。ProfileArea と ProfileLayout の実装も v0.6 には含めない。

RoomOwner の譲渡操作は後続 Version へ回すが、Room は最初から変更可能な Owner を一人保持するモデルにする。v0.6 では RoomOwner は退出できない。

## 2026-10-04 - SummaryItem の上段を一覧ごとの補助表示欄とする

状態: 採用

SummaryItem の上段は、全種類に共通する種別や管理主体の表示欄として固定せず、一覧の目的に応じて内容を決める補助表示欄とする。表示する内容がない場合も空の行を維持し、SummaryItem の三行構成は変えない。

Spot 一覧では、将来、検索者が選択した Field の値を上段へ表示できるようにする。現段階では Room、Thread などの種別や管理主体を上段へ表示しない。種別は色など別の表現で識別する。

Board 一覧では、Collection が外部の Board を参照している場合に限り、参照 Board 本体の配置元である Account または Room を上段へ表示する。閲覧中の Account または Room 配下に配置された Board と、NiiMap へ直接配置された Board では上段を空にする。NiiMap は Board の参照を保持せず、Board や Collection への参照関係は Collection が保持する。

## 2026-10-04 - Boardの削除は過去ログを保持するSoft Deleteとする

状態: 置換済み（2026-10-04 の「Boardは物理削除しThreadを残す」を採用）

Boardを削除してもBoard本体、主配置先、既存Threadは物理削除しない。削除済みBoardは通常のRoomとCollectionの導線から外し、新規Thread作成と既存ThreadへのResponse投稿を禁止する。最後の使用中Boardも削除でき、Boardを一つも使用しないRoomを認める。

削除済みBoard内のThreadは過去ログとして残し、AccountPageなどの履歴や直接URLではThreadPolicyに従って閲覧できる。RoomOwnerは削除済みBoard一覧から復元でき、復元時には既存の主配置先とThreadをそのまま再利用する。

## 2026-10-04 - 配置と参照を分離する

状態: 採用（2026-09-20 の主掲載先・共有先を同じ Placement で扱う方針を置換）

Thread、Board、Roomなどの対象は、同時に最大一つの配置先を持つ。別のBoard、Collection、AccountのList、fav、badなどから対象を共有する場合は、対象自身の配置を増やさず、共有する側が独立した参照を保持する。参照の追加や解除によって対象本体、配置先、ほかの参照を変更しない。

Threadの配置先は作成時に確定し、作成後に変更しない。配置先のBoardが物理削除された場合は未配置となる。未配置ThreadもThread本体、Response、ThreadPolicy、Field、Interfaceを維持し、Accountの活動履歴、fav、bad、List、別のBoardが保持する参照、Thread固有URLなど、配置先以外の導線から継続利用できる。NiiMapのSpot一覧にはNiiMapへ直接配置された対象だけを表示する。

RoomはRoom管理者がNiiMap座標の変更、未配置化、再配置を行える。BoardはAccountまたはRoomに属するCollection、もしくはNiiMap座標のいずれか一つへ配置する。AccountまたはRoom配下に配置されているBoardの配置先変更は、異なる管理者間での移動申請と承認を主用途とし、後続Versionで実装する。NiiMapへ配置したBoardは以後配置先を変更できない。

## 2026-10-04 - Boardの管理主体は配置先から決める

状態: 採用（Board Ownerを配置先と分離する方針を置換）

Boardは独立したOwnerを持たない。Account配下のCollectionに配置されたBoardはそのAccountが、Room配下のCollectionに配置されたBoardはそのRoomの管理者が管理する。NiiMapへ直接配置されたBoardには配置先管理者が存在しないため、配置後の移動、未配置化、編集、削除を認めない。Boardを作成した実Accountを監査情報として残すかは、監査機能の実装時に改めて決める。

Collectionを削除する場合、そのCollectionへ配置されているBoardを未配置にせず、同じAccountまたはRoom配下のシステムCollection「未分類」へ移す。「未分類」はAccountまたはRoomの作成時から常設し、固定名、削除不可、並び替え不可とする。Boardの作成先には指定でき、それ以外は通常Collectionと同様に扱う。表示名ではなくシステム上の役割で通常のCollectionと区別する。参照として掲載されているBoardやCollectionは、Collection削除時に参照だけを解除する。

参照先Boardが物理削除された場合、Collection側の参照Itemを対象なしの状態で残すことを認める。参照Itemは「削除されました」と表示し、Collection管理者がそのItemをCollectionから削除できる。参照追加時の名称などを表示し続けるSnapshotの要否は参照機能の実装時に決める。

## 2026-10-04 - Policy Templateは作成時に確定する

状態: 採用（BoardPolicyとThreadPolicyを永続的にAND評価する方針を置換）

RoomPolicyはRoom自体の閲覧、参加、管理を制限する。BoardPolicyはBoard自体の閲覧やThread作成など、Board上の操作を制限する。RoomやBoardが持つTemplateは子対象の作成時にだけ作用し、作成済み対象が親のTemplateを継続参照する構造にはしない。

RoomのBoardTemplateとBoardのThreadTemplateは、子対象を作成するときのPolicyやLayoutなどの初期値を定める。推奨値は作成時に変更でき、強制値は変更できない。いずれも作成時に子対象へ確定保存し、親のTemplateを後から変更しても既存対象へ反映しない。

たとえばRoomが、BoardのThreadTemplateにThreadPolicyの閲覧条件として「RoomAに参加」を強制すれば、その条件は各ThreadPolicyへ保存される。Boardが削除されても条件は残る。反対にThreadPolicyがNiixyAccountの閲覧や書込を許可している場合、RoomやBoardの導線を利用できないAccountでも、別の参照やThread固有URLから到達すればThreadPolicyに従って利用できる。

## 2026-10-04 - Boardは物理削除しThreadを残す

状態: 採用（同日のBoard Soft Delete方針を置換）

Boardの削除は復元を前提としたSoft Deleteではなく物理削除とする。Board本体、Board自身の配置、そのBoardが保持する参照を削除し、削除済みBoard一覧と復元機能は設けない。削除操作は取り消せないことと、Board内のThreadおよびResponseは削除されないことを実行前に案内する。

削除されたBoardに配置されていたThreadは未配置となるが、Thread本体、Response、ThreadPolicy、Field、Interfaceを保持する。Board削除後もThreadPolicyに従ってResponse投稿と編集可能なThread情報の変更を認める。別のBoard、AccountのList、fav、badなどがそのThreadへ持つ参照は維持する。

## 2026-10-04 - RoomPageではBoardボタンから一覧Paneを開く

状態: 採用（2026-10-03 の「RoomPaneに表示するCollectionを選択する」を置換）

RoomPageには特定CollectionのBoardを直接表示しない。機能ボタン群の`Board`からBoard一覧Paneを開き、一覧Pane内のTabで各Collectionを切り替える。したがって、RoomがRoomPage表示用Collectionを保持する必要はない。

`Main`はRoomまたはAccountの作成時に用意される初期Collection名にすぎず、特別な機能やシステム上の役割を持たない。通常Collectionと同様に名称変更と削除を認める。システム上の識別が必要なのは、Collection削除時のBoard退避先となる常設の`未分類`だけとする。

Board一覧PaneのTabは、作成順の通常Collection群、固定の`未分類`、管理者だけに表示する`管理`の順に並べる。`管理`はCollection実体ではなく管理UIであり、Collection作成をここへ配置する。新規Collectionは通常Collection群の末尾へ追加する。

各Collection Tabでは`詳細確認`と、Room管理者向けの`Board作成`を排他的に展開する。詳細確認にはCollection名とBoard数を表示し、通常CollectionではRoom管理者だけに編集への導線を表示する。編集領域では名称変更と削除を行う。`未分類`では詳細確認とBoard作成を利用できるが、編集への導線は表示しない。Collectionの並び替えは後続Versionで扱う。
