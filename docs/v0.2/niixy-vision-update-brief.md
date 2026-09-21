# Niixy Vision 更新指示書

## 0. この文書の目的

この文書は、Niixy v0.2完了後に行った構想整理を、既存の `docs/vision/` へ反映するための差分資料である。

会話中には採用後に撤回された案が多く含まれるため、過去の会話ログではなく、本書を今回の構想整理における最新判断として扱う。

本書は完成した仕様書ではない。既存Visionを更新・分割するときの入力資料であり、記載内容をそのまま一括実装してはならない。

### 状態の表記

- **確定**：現時点のVisionとして採用する。
- **将来構想**：方向性は残すが、直近バージョンへの実装を意味しない。
- **保留**：構想はあるが、詳細や採否を今後決める。
- **廃止**：今回の整理で採用しない旧案。

---

## 1. 全体コンセプト

### 1.1 Niixyにおける主な概念【確定】

Niixyでは、次の概念を組み合わせて利用する。

- **Account**：利用者の主体。
- **Room**：利用者が作成・管理する場所。座標を持つことも、持たないこともできる。
- **Thread**：RoomまたはNiiMap上で共有される話題・掲示板。
- **ThreadPost**：Thread内の投稿。先頭投稿とResponseを内部的に統一して扱う。
- **Interface**：Account、Room、Thread、ThreadPostに構造化された情報や機能を追加する仕組み。
- **NiiMap**：座標付きRoomと、NiiMapへ直接配置されたThreadを地図上で発見するサービス。

旧称 `Community` / `NiiRoom` は、概念名・画面上の名称ともに **Room** へ変更する。

### 1.2 NiiMapとRoomの位置づけ【確定】

- NiiMapは、座標によって場所を提供する。
- Roomは、Room作成者・管理者によって場所を提供する。
- 同じThreadをNiiMapと複数Roomから共有できる。
- どの入口から開いても、Thread本体・ThreadInterface・ThreadPostは同一である。
- NiiMapではRoomを利用せず、Threadを直接配置することもできる。

---

## 2. ThreadとThreadPost

### 2.1 Threadの役割【確定】

Threadは、雑談、質問、募集、告知、Eventなどを載せられる共通の掲示板単位とする。

Eventや店舗情報そのものを独立した投稿エンティティとして固定せず、必要に応じてInterfaceで構造化する。

- Event：Event用ThreadInterfaceを実装したThread。
- 募集：募集用ThreadInterfaceを実装したThread。
- 投票：投票用ThreadInterfaceを実装したThread。
- 何も実装しないThread：通常の掲示板・雑談Thread。

地図上のMarkerまたはPinは表示上の表現であり、Threadと別のコンテンツ本体にはしない。

### 2.2 ThreadのTitle【確定】

- Thread Titleは作成後に編集できない。
- NiiMapへThreadが直接表示される場合、PinのラベルにはThread Titleを使用する。
- ThreadInterfaceのフィールドをPinラベルの代わりに使用しない。
- Event名や店舗名など、更新が必要な名称はInterface側に持たせられるが、Thread Titleそのものは変更しない。
- Title変更機能は、実際に需要が生じた場合に将来再検討する。

### 2.3 Thread本文とResponse【確定】

Thread本文は、内部的には1番目のThreadPostとして扱う。

- `#1`：Thread作成時の先頭投稿。UI上は「本文」と呼んでもよい。
- `#2`以降：UI上のResponse。
- `>>1`など、投稿番号を利用したアンカーを実装可能にする。
- Thread作成時には、Thread本体、`#1`、初期配置を同一トランザクションで作成する。

内部モデル名は `ThreadPost` を想定する。UIでは必要に応じて「本文」「Response」と呼び分ける。

### 2.4 編集原則【確定】

Niixyに投稿された発言は、投稿後に編集できず、削除のみ可能とする。

- Thread Title：編集不可。
- ThreadPost本文：編集不可。
- Response：編集不可。
- ResponseInterfaceの実装値：編集不可。
- ThreadのPolicy：作成後は編集不可。
- ThreadのDisplayLayout：作成後は編集不可。

一方、現在状態を表す次の情報は更新可能とする。

- AccountInterfaceの実装値。
- RoomInterfaceの実装値。
- ThreadInterfaceの実装値。
- ThreadおよびRoomの配置・座標。

投稿後に編集できないことを理由とした、確認画面、警告ダイアログ、投稿UI付近の常時注意書きは設けない。問題がある場合は投稿を削除できる。

### 2.5 ThreadPostの削除【確定】

削除されたThreadPostは、投稿番号と削除済み表示だけを残す。

例：

```text
#18 削除されました
```

削除後は、次の情報を表示しない。

- 本文。
- 投稿者情報。
- 投稿時Snapshot。
- Thumbnail。
- Interfaceの入力値。

投稿番号は詰めず、アンカーの参照先を維持する。

### 2.6 Thread本体の削除【確定】

Thread作成者がThreadを削除しても、既に利用している他ユーザーの会話まで一括消去しない。

削除時は次の扱いとする。

- Thread Titleを削除済み表示へ置き換える。
- `#1`本文を削除する。
- Thread作成者の情報および投稿時Snapshotを非表示にする。
- 実装済みThreadInterfaceをすべて解除する。
- Thread作成者の管理権限を失わせる。
- 既存ThreadPostは、個別に削除されていない限り残す。
- Policyが許可していれば、新しいResponseも引き続き投稿できる。
- NiiMap上の直接配置は解除する。
- Roomへの既存配置は自動解除しない。
- `last_activity_at`は以後更新しない。

Thread削除によって、削除前に他Accountが持っていた権限を自動的に奪わない。ただし、もともと「Thread作成者のみ書き込み可能」だった場合、作成者削除後に誰も書き込めなくなることは許容する。Policyの自動緩和や特別な警告は行わない。

### 2.7 `last_activity_at`【確定】

Threadが現在も利用・管理されていると判断できる操作で更新する。

対象例：

- Thread作成。
- 新しいThreadPostの投稿。
- ThreadInterfaceの更新。
- 掲載先の設定・変更。
- NiiMapへの掲載・再掲載。
- Roomへの共有配置。
- Roomからの配置解除。

活動種別を保持できる設計が望ましい。

例：

- `created`
- `post_created`
- `interface_updated`
- `publication_moved`
- `shared_to_room`
- `removed_from_room`
- `republished`

一文字Responseや配置変更を利用した意図的な浮上は、当面許容する。実害が表面化した場合にクールダウン等を検討する。

Threadが配置されているRoom自体の座標変更では、そのRoom内にある全Threadの `last_activity_at` を一斉更新しない。

---

## 3. Room

### 3.1 Roomの基本【確定】

- RoomはAccountが作成・管理する場所である。
- Roomは座標を持つことも、持たないこともできる。
- 座標付きRoomはNiiMapへ表示できる。
- Roomの座標は後から設定・変更・解除・再設定できる。
- 座標を解除してもRoomおよび内部Threadは削除されない。
- Room内には複数Threadを配置できる。
- 同じThreadを複数Roomで共有できる。

店舗、施設、団体、ゲームコミュニティなど、一つの場所に複数の話題や機能が必要な場合はRoomを使用する。

### 3.2 Room管理者の役割【確定】

Thread本体はThread作成者の管轄とし、Room管理者はRoomという場所を提供・管理する。

- Room管理者は、自分のRoomへのThread配置を管理できる。
- Room管理者は、RoomからThreadの配置を解除できる。
- Room管理者は、共有されているThread本体を編集・削除しない。
- Room管理者の詳細権限は今後詰める。

Room設定により、Thread配置を次から選べる構想とする。

- 自由配置。
- Room管理者による承認制。

Room内から作成されたThreadについても承認を必須にできる。逆に、誰でも自由にThreadを配置できるRoomも作成可能とする。

### 3.3 Roomの制限【確定】

Roomは少なくとも次のPolicyを持つ。

- **発見制限**：Roomの存在、Marker、名称などを発見できる条件。
- **閲覧制限**：Room概要およびRoom内にどのThreadが存在するかを閲覧できる条件。
- **参加制限**：Roomへ参加できる条件。自動承認または管理者承認などを含む。

Roomの閲覧が禁止されている場合、Room内Threadの一覧も表示しない。

### 3.4 Roomの `last_activity_at`【確定】

Roomも `last_activity_at` を持つ。

更新対象の例：

- Room作成。
- RoomInterfaceの更新。
- RoomへのThread配置。
- RoomからのThread配置解除。
- Room内Threadへの新しいThreadPost。
- Room内ThreadInterfaceの更新。
- Room本体の座標変更。

共有Threadに別の入口からThreadPostが追加された場合も、同じ内容がRoom内で更新されるため、そのRoomの活動として扱う。

Room内からThreadが解除されても、Roomの過去の `last_activity_at` を巻き戻さない。これは「現在含まれるThreadの最大日時」ではなく、「そのRoomで最後に観測された活動日時」とする。

### 3.5 Roomからの通知【将来構想】

- Room管理者から参加者へAnnouncementを配信できるようにする。
- Room参加と通知購読は分離する。
- 参加者は「すべて」「重要のみ」「なし」などの通知設定を選べる構想とする。
- 初期段階ではRoom内のお知らせ一覧だけを実装し、外部通知やPush通知は後回しにできる。

---

## 4. Threadの掲載先と共有先

### 4.1 ユーザー向け概念【確定】

Threadは、一つの **掲載先** と、複数の **共有先** を持てる。

掲載先は次のいずれか。

- NiiMap上の座標。
- Room。
- なし。

掲載先は、NiiMap検索でそのThreadを提示するときに使用する一つの表玄関である。掲載先以外のRoomへの配置は共有先として扱う。

ユーザーへ「直置き座標」「代表座標」「本体位置」「代替表示先」などの内部概念を並べない。Thread詳細では「掲載先」と「共有先」を表示する。

例：

```text
掲載先：NiiMap 東京都○○
共有先：
- LOL Club
- 初心者交流Room
```

または：

```text
掲載先：LOL Club
共有先：
- 初心者交流Room
- 深夜勢Room
```

### 4.2 掲載先の変更【確定】

Threadの掲載先は後から変更できる。

例：

```text
NiiMap上の座標
→ Room A
→ 掲載先なし
→ 別のNiiMap上の座標
```

これにより次を可能にする。

- NiiMapから一時的に取り下げる。
- Room内だけで利用する。
- NiiMap検索上の掲載先を持たない状態にする。
- 後からNiiMapへ再掲載する。
- 掲載するRoomを変更する。

ThreadとRoomのどちらも移動可能とし、「Roomだけ移動可能、Threadは移動不可」という非対称な仕様にはしない。

### 4.3 NiiMapでの表示規則【確定】

- 掲載先がNiiMap上の座標：ThreadのPinを表示する。
- 掲載先が座標付きRoom：RoomのPinを表示し、条件に一致したThreadとして扱う。
- 掲載先が座標なしRoom：NiiMapへは表示しない。
- 掲載先なし：NiiMapへは表示しない。
- 共有先Room：そのThreadを理由としてNiiMap検索結果を増やさない。

同一Threadは、NiiMapの一回の検索結果に最大一つの入口しか作らない。

### 4.4 掲載先を利用できない場合【確定】

掲載先であるRoomを発見または閲覧できず、NiiMap検索の入口として利用できない場合でも、別の共有先へ自動的にフォールバックしない。

- その利用者のNiiMap検索結果にはThreadを出さない。
- 発見・閲覧可能な共有先Roomを直接訪れれば、そのRoom内からThreadを発見できる場合がある。
- NiiMapで発見されたい場合は、発見・閲覧可能なRoomまたはNiiMap上の座標を掲載先として選ぶ。

掲載先は、Threadがどこを表玄関にするかという作成者の意思として扱う。

### 4.5 配置履歴【確定】

掲載先および共有先の変更履歴を残す。

例：

```text
2026-09-20 掲載先が変更されました
大阪府大阪市 → 北海道札幌市
```

- 配置履歴はThread詳細から確認可能にする。
- 配置履歴は削除不可とする方向で扱う。
- 配置変更はThreadの `last_activity_at` を更新する。
- 過去のThreadPost本文そのものは変更しない。

### 4.6 概念モデル【確定】

UIでは「掲載先」と「共有先」だけを見せる。

DBでは、RoomとThreadが多対多であり、配置ごとに承認状態や日時等を持つため、中間テーブルまたは配置テーブルを使用する。

概念例：

```text
ThreadPlacement
- id
- thread_id
- placement_type: map / room
- room_id: nullable
- latitude: nullable
- longitude: nullable
- is_publication
- approval_status
- placed_by_account_id
- created_at
- removed_at
```

RoomにThread IDの配列を直接保存する設計は採用しない。PostgreSQLでは配列自体は使用可能だが、外部キー整合性、逆引き、承認状態、重複禁止、削除処理、配置履歴などを扱いにくいためである。

このテーブル構造をそのままUI用語として露出させない。

---

## 5. NiiMapの一覧・検索・絞り込み

### 5.1 Pin一覧の表示単位【確定】

NiiMapのPin一覧へ直接並ぶものは次の二種類。

- 掲載先がNiiMap上の座標であるThread。
- 座標付きRoom。

Room内Threadを一件ずつPin一覧へ展開しない。Room内ThreadはRoomを開いて確認する。

### 5.2 Room内Threadも検索対象にする【確定】

ThreadInterface等を利用した検索・絞り込みでは、Room内Threadも対象とする。

ただし、検索結果の表示単位は掲載先に従う。

- Threadの掲載先がNiiMap上の座標：Threadとして表示。
- Threadの掲載先がRoom：そのRoomを表示し、一致したThreadを示す。

例：

```text
こあたみ商店
一致したThread 2件
- 秋のセール
- カード交換会
```

同じRoomに複数の一致Threadがある場合はRoom単位にまとめる。

同じThreadが複数Roomへ共有されていても、共有先すべてを検索結果へ出さない。掲載先だけをNiiMap上の入口とする。

### 5.3 Room内Threadを検索へ利用できる条件【確定】

Room内Threadを検索判定へ利用するには、少なくとも次を満たす必要がある。

- Roomを発見できる。
- Roomを閲覧できる。
- Threadを発見できる。
- 指定されたInterfaceおよびフィールド条件に一致する。

Roomの閲覧制限は「Room内にどのThreadがあるか」を隠すため、Roomを閲覧できない利用者の検索に、内部Threadを一致理由として使用しない。

Threadを閲覧できることは常時必須にしない。検索者は「閲覧可能のみ」のFilterで、閲覧できないThreadを含めるか選択できる。既定では「閲覧可能のみ」を有効にする。

発見条件を満たさないRoomまたはThreadは、Filter設定にかかわらず検索判定へ含めない。

### 5.4 既定フィルターと並び替え【確定】

- Threadに有効期限は持たせない。
- NiiMapの既定フィルターは、原則として `last_activity_at >= 現在日時 - 7日` とする。
- 7日という値は後から容易に変更できる設定値として扱う。
- 古いThreadは削除せず、条件変更によって閲覧できる。
- 現在のMap表示範囲内を一覧対象とする。
- 並び替えは少なくとも次を用意する。
  - 更新が新しい順（既定）。
  - 距離が近い順。
- Roomと直接表示Threadを同じ一覧で並べる。
- RoomはRoomの `last_activity_at` と座標を使用する。
- ThreadはThreadの `last_activity_at` と掲載先を使用する。

### 5.5 掲載期限案【廃止】

以下は採用しない。

- 掲載終了日時。
- 有効期限。
- 24時間後を既定とする掲載期間。
- 最大30日で延長更新する仕組み。
- `waiting / active / closed` を全投稿へ共通化する仕組み。

古いThreadの表示抑制は、削除や期限切れではなく、`last_activity_at` の既定フィルターで行う。

---

## 6. Access Policy

### 6.1 Policyの種類【確定】

#### Room

- 発見制限。
- 閲覧制限。
- 参加制限。

#### Thread

- 発見制限。
- 閲覧制限。
- 書き込み制限。

ThreadPostごとの表示制限は持たせない。Threadを閲覧可能なら、削除済みまたはPlatform Moderation対象でない `#1` およびResponseを閲覧可能とする。

### 6.2 共通条件モデル【確定】

各Policyは、共通の条件部品を組み合わせて表現する。

条件候補：

- Guest。
- NiixyAccount。
- 指定Account。
- 指定Roomへの参加。
- 指定AccountInterfaceの実装。
- 評価値等の将来条件。
- 将来のRoleや承認状態。

例：

- `[Guest] + [NiixyAccount]`：本人確認に関する制限なし。
- `[NiixyAccount]`：ログインAccountのみ。
- `[参加Room: LOL Club]`：LOL Club参加者のみ。
- `[AccountInterface: LOL]`：LOL用AccountInterface実装者のみ。

Threadに、Policyとは独立した包括的な `Required Account Interface` は持たせない。AccountInterfaceの要求は、必要な各Policyの条件として直接設定する。

### 6.3 AND / OR【確定】

初期の分かりやすい規則として、次を想定する。

- Guest、NiixyAccount、指定Account、指定Room参加などのAudience候補：OR。
- 複数の指定AccountInterface：AND。

将来的には、作成者が条件をAND／ORグループとして組み合わせ、入れ子にできるようにする。

当面は浅い構造や固定規則による仮実装でもよい。ただし、任意のAND／ORグループへ拡張する方向性は確定とする。具体的な編集UIと初期バージョンで対応する深さは実装時に決める。

### 6.4 上位・下位Policyの関係【確定】

Room内Threadへのアクセスは、RoomとThread双方のPolicyを満たす必要がある。

例：

```text
Roomを閲覧可能
AND Threadを発見可能
AND Threadを閲覧可能
```

Threadを閲覧可能なら、ThreadPostは一律に閲覧可能とする。ThreadPost固有の表示Policyは持たない。

### 6.5 発見不可・閲覧不可の表示【確定】

発見制限と閲覧制限は次のように扱う。

| 発見 | 閲覧 | 表示 |
| --- | --- | --- |
| 不可 | 不問 | 検索、一覧、Bookmarkに表示しない |
| 可能 | 不可 | Filter設定に応じて検索へ表示し、開くと必要条件を案内する |
| 可能 | 可能 | 通常表示する |

発見条件を満たさないURLへ直接アクセスされた場合は、存在の有無を確定させない共通文言を表示する。

例：

```text
このThreadは存在しないか、発見条件を満たしていません。
```

発見可能だが閲覧できないRoomまたはThreadは、Locked画面を表示し、閲覧できない原因と解消条件を示す。RoomのLocked画面では、内部Threadの一覧や内容を表示しない。

例：

```text
このThreadを閲覧するには、次の条件を満たす必要があります。

すべて満たす：
- AccountInterface「LOL@AccountA」
- Room「Room A」への参加

いずれかを満たす：
- 評価10以上
- 指定Account
```

条件の内部式をそのまま露出せず、人間が理解できる文言へ変換する。具体的な文言はUI設計時に再検討する。

発見不可になったThreadやRoomはBookmark一覧から隠すが、Bookmarkデータ自体は削除しない。後から発見条件を再び満たした場合は再表示できる。

非表示の本文、ThreadPost、Interface値等をクライアントへ送ってCSSだけで隠す実装にはしない。

### 6.6 Policyテンプレート【確定】

- Roomは、Room内から作成するThreadのPolicyおよびDisplayLayoutの初期テンプレートを持てる。
- Threadは、新しいThreadPostで使用するResponseInterface等の初期テンプレートを持てる。
- テンプレートは作成時にコピーするSnapshotであり、作成後に親設定を変更しても過去データへ自動反映しない。
- ThreadのPolicyとDisplayLayoutは作成後に編集不可。
- ResponseInterface実装値は投稿後に編集不可。

RoomからThreadを作成する場合、Room参加条件で要求されるAccountInterface等をThreadの初期Policyへ反映できる。ただし、Thread側では各Policy条件として明示的に保持する。

### 6.7 Policy変更履歴【保留】

Thread Policyを作成後編集不可としたため、Threadについての変更履歴要件は縮小する。

Room Policyや将来変更可能になるPolicyについて、監査履歴をどこまで保持するかは実装時に決める。

---

## 7. Interface

### 7.1 Interfaceの種類【確定】

Interfaceは対象ごとに別種として扱う。

| 種類 | 対象 | 主な用途 | 実装値の更新 |
| --- | --- | --- | --- |
| AccountInterface | Account | Rank、プロフィール、参加資格 | 可能 |
| RoomInterface | Room | 店舗情報、施設情報、団体情報 | 可能 |
| ThreadInterface | Thread | Event、募集、投票、営業告知 | 可能 |
| ResponseInterface | ThreadPost | 回答、申請、定型投稿 | 不可 |

AccountInterfaceとThreadInterfaceは、同名の概念を共有するものではなく、別のInterfaceである。

正式名称は省略せず `AccountInterface`、`RoomInterface`、`ThreadInterface`、`ResponseInterface` とする。画面上では文脈が明確な場合のみ「Interface」と短く表示できる。

### 7.2 Interfaceの作成者と名前空間【確定】

Interfaceは作成者Accountへの参照を保持する。

Interfaceの名前空間には少なくとも次を使用する。

```text
作成者Account ID + Interface名
```

- Account Aが作成した `LOL` とAccount Bが作成した `LOL` は共存できる。
- 同じ作成者Accountが、Interface種別をまたいで同名Interfaceを複数定義することは禁止する。
- 内部的な識別には変更されないAccount IDを使用する。
- 表示上は `LOL@AccountA` のように作成者を併記する案を検討する。
- 作成者のNickname変更によってInterfaceの識別が変わらないようにする。
- Interface作成者Accountが削除された場合の所有権、表示名、保守方法は今後決める。

### 7.3 Interfaceの継承【確定・詳細保留】

Interfaceは同じ種類のInterfaceを継承できる。多重継承も可能とする。

例：

```text
プロフィールA
├─ 誕生日A
└─ 血液型A

プロフィールB
├─ 誕生日A
└─ 血液型A
```

Accountが `プロフィールA` を実装済みで、その後 `プロフィールB` を実装する場合、共通の継承元である `誕生日A` と `血液型A` の値を再入力させない。

これは値を別フィールドへコピーするのではなく、継承元のField IDと実装値を共有・再利用するものとして設計する。

少なくとも次の規則を設ける。

- 同じInterface種別間だけ継承可能。
- 多重継承可能。
- 循環継承は禁止。
- 同じ祖先へ複数経路から到達しても、一つの継承元として扱う。
- 表示名が同じでも、異なるInterfaceが定義したFieldはField IDが異なれば別物として扱う。
- Interface定義と継承関係をバージョン管理する。

継承先独自Fieldと継承Fieldの名前衝突、祖先Interfaceの更新が子孫へ与える影響、Interface実装済みとみなす範囲などの詳細は保留する。

### 7.4 RoomInterface【確定】

店舗や施設など、Room自体の現在情報はRoomInterfaceへ持たせる。

例：

- 店舗名。
- 営業時間。
- 営業状態。
- 施設情報。
- 団体情報。

営業時間から営業中／営業時間外などを自動計算する仕組みも、RoomInterface側の機能として将来実装できる。

### 7.5 ThreadInterface【確定】

Event等、一つの出来事や募集に紐づく情報はThreadInterfaceへ持たせる。

例：

- 開催日時。
- 終了日時。
- 募集人数。
- 募集状況。
- 申込状態。

Thread共通のTitleをEventTitleとして利用し、重複したEventTitle共通フィールドは設けない。

Roomが複数Eventを開催する場合は、EventごとにThreadを作成し、それぞれへEvent用ThreadInterfaceを実装する。これにより、終了したEventも過去Threadとして残せる。

募集人数など、全Threadに必要ではない項目はThread共通フィールドにせず、ThreadInterface側で定義する。

### 7.6 ResponseInterface【確定・詳細保留】

ResponseInterfaceは、旧来の掲示板で投稿テンプレートをコピーして回答していた文化を、構造化された入力として扱うための仕組みとする。

例：

- 質問者用ResponseInterface。
- 回答者用ResponseInterface。
- 申請用ResponseInterface。
- アンケート回答用ResponseInterface。

Threadの書き込み条件として特定ResponseInterfaceの使用を要求したり、必須ではなく推奨として提示したりできる構想とする。

ResponseInterfaceの実装値はThreadPostの一部であり、投稿後に変更できない。自由記述欄を編集可能な本文代わりに利用できないようにする。

Interface定義自体が後から更新された場合でも、過去ThreadPostは投稿時のInterfaceバージョンと入力値を保持する。

ResponseInterfaceを一つのThreadPostへ複数実装可能にするか、初期段階では一つに限定するかは保留する。

### 7.7 DisplayLayout【確定・詳細保留】

RoomやThreadは、ThreadPostの表示項目と順番を宣言的に設定できる構想とする。

`ThreadPost` は、`#1`のThread本文と`#2`以降のResponseをまとめた内部名称である。DisplayLayout、投稿時Snapshot、Thumbnail表示は、Responseだけでなく`#1`を含むすべての投稿へ適用する。

使用候補：

- 投稿時Nickname。
- Niixy ID。
- Thumbnail。
- ThreadPost番号。
- 投稿日時。
- Policyによって実装が保証されるAccountInterfaceのフィールド。

例：

- LOL用Room：名前とRankを表示。
- Pokémon用Room：通常名の代わりに好きなPokémonを表示。

任意HTMLは許可せず、用意されたSlot・Itemを並べる宣言的なLayoutとする方向で検討する。

Policyによって実装が保証されていないAccountInterfaceフィールドを必須表示へ設定しない。依存条件を外した場合にLayout Itemも削除するUI等は、実装時に詰める。

---

## 8. 投稿時SnapshotとThumbnail

### 8.1 投稿時Snapshot【確定】

ThreadPostには、投稿時点の表示情報をSnapshotとして保持する。

同じAccountによる投稿でも、投稿時期によってNickname、Thumbnail、Interface値等が異なる状態を許容する。

候補：

- 投稿時Nickname。
- 投稿時Niixy ID。
- 投稿時ThumbnailVersion。
- DisplayLayoutで利用されたAccountInterfaceフィールド値。
- 使用したInterface定義のバージョン。

現在値を参照して過去ThreadPostの見た目を一括変更する方式にはしない。

### 8.2 AlbumとThumbnail【確定】

NiixyにAvatar機能は設けない。

- AccountはAlbumへ自由に画像を投稿できる。
- Album画像から一つをAccountのThumbnailとして選択できる。
- ThreadPostではAccountのThumbnailを表示に利用できる。

AlbumとThumbnail履歴は分離する。

概念例：

- `MediaImage`：画像資産。
- `AlbumItem`：Albumへの掲載。
- `ThumbnailVersion`：Thumbnailとして利用した画像と担当期間。

新しいThumbnailを登録するときは、同じ画像をAlbumにも追加することを既定とする。

Albumから画像を削除してもThumbnail履歴は残る。Thumbnail履歴はAccount本人のみが管理・閲覧できる想定とするが、過去ThreadPostはそのThumbnailVersionを参照して表示できる。

各ThreadPostへ画像バイナリを複製せず、ThumbnailVersionまたは画像資産を参照する。

### 8.3 過去Thumbnailの削除【確定】

- Account本人は過去Thumbnailを削除できる。
- 削除されたThumbnailVersionを使用していた過去ThreadPostではPlaceholderを表示する。
- ThreadPost自体を削除した場合は、Thumbnailを含む投稿者Snapshot全体を表示しない。

### 8.4 投稿履歴の一括削除【将来構想】

将来的に次の一括削除を検討する。

- 指定ThreadPost以前をすべて削除。
- 期間で絞り込んで削除。
- DisplayLayoutやInterfaceで絞り込んで削除。

投稿時Snapshotの一部だけを後から書き換えるのではなく、問題がある投稿はThreadPost単位で削除することを基本とする。

---

## 9. Accountページ【将来構想】

Accountページは、本人専用の管理画面ではなく、他ユーザーへ公開するプロフィール・活動ページとする。

ただし、NiiMapとRoomの関係が変更されたため、Accountページ全体の情報設計とLayoutは改めて構想し直す。

現時点で維持する候補：

- Thumbnail。
- NicknameとNiixy ID。
- 実装中のAccountInterface。
- 作成したInterface。
- 他Accountからの紹介文。
- 代表として選択したAccountInterface一つ。

次の旧案は、Accountページへ載せるかを含めて再検討する。

- 作成したThread。
- 投稿したThreadPost／Response。
- Event参加および参加申請。
- Tweet。
- Note。
- NiiMap上の活動とRoom上の活動の分類。

NiiMapとRoomを別軸として活動表示を分割する方針は撤回する。Event参加、Tweet、Noteをどこへ配置するかもAccountページ全体の再設計時に決める。

### 9.1 Account評価と紹介文評価【将来構想】

- Accountへの評価：`love / hate`。
- 紹介文が参考になったか：`helpful / unhelpful` 等。
- Accountページには、`helpful - unhelpful` が高い紹介文を上位三件まで代表表示する案。
- 紹介文一覧では次を用意する案。
  - 参考度順。
  - 新着順。
  - love評価のみ。
  - hate評価のみ。

PinやThreadへの評価、および評価に応じた色の薄化は保留する。

---

## 10. 旧Eventモデルからの変更

### 10.1 Event中心モデル【廃止】

v0.2までのEventをNiiMapの唯一の投稿単位とする構造は廃止し、Threadを中心に再構成する。

廃止対象：

- 全投稿で必須の開始日時。
- 全投稿で共通の募集人数。
- Eventだけを前提にした一覧・詳細・絞り込み。
- EventをPinへ単純リネームするだけの案。
- PinをThreadと別のコンテンツ本体にする案。

開始日時、終了日時、募集人数などは、必要なThreadInterfaceへ持たせる。

### 10.2 Event参加【将来構想】

Eventへの参加はThreadへの参加ではなく、Event用ThreadInterface固有のActivityまたはRelationshipとして残す。

将来的に次を扱えるようにする。

- 参加予定。
- 参加申請中。
- 承認済み。
- 却下。
- キャンセル。

Accountページへどのように表示するかは、Accountページ全体の再設計時に決める。

具体的なAccountInterfaceとの接続、DBモデル、承認フローも保留する。

---

## 11. v0.3との関係

### 11.1 方針【確定】

- v0.3では既存Eventのテストデータを削除して構わない。
- Event中心のモデルを無理に互換維持せず、Thread中心へ再構築できる。
- ただしVision記載内容をv0.3ですべて実装しない。
- 先にVision文書を更新し、その後v0.3の最小実装範囲を別途決める。

### 11.2 再利用候補【確定】

既存実装から、汎用的に利用できる部分は残す。

- Map表示。
- Marker表示。
- 位置検索。
- 現在地取得。
- 一覧Pane。
- 認証。
- Account／Guestの作成者識別。
- フィルター設定の保持。
- 二重送信防止・Submission ID等の仕組み。

既存Event固有の開始・終了日時、募集人数、Event用Filter等は、Thread中心設計に合わなければ破棄してよい。

### 11.3 v0.3候補【保留】

過去の会話では、v0.3の最小候補として次が挙がっている。

- Thread。
- ThreadPost／Response。
- NiiMapへのThread配置。
- 編集不可・削除可能。
- 削除済み表示。
- `last_activity_at`。
- 過去7日を既定とする絞り込み。
- 更新順／距離順。

ただし、その後Room、配置、Policy、InterfaceのVisionが大きく拡張されたため、v0.3へどこまで含めるかは改めて決定する。Codexは本書だけを根拠にv0.3実装を開始してはならない。

---

## 12. 明示的に廃止・撤回する案

既存文書内に以下が残っている場合、最新Visionとの整合を確認し、旧案として削除または履歴へ移す。

- `Community` または `NiiRoom` を現在の概念名として使う。
- EventをNiiMapの共通投稿単位とする。
- PinをThreadと独立したコンテンツ本体にする。
- 全投稿へ開始日時・終了日時・募集人数を共通必須項目として持たせる。
- 掲載終了日時、有効期限、最大30日の掲載期間。
- 全投稿へ `waiting / active / closed` を共通状態として持たせる。
- Thread Titleを編集可能にする。
- Thread Title以外をPinラベルとして使用する。
- ThreadまたはResponse本文を編集可能にする。
- ResponseInterfaceを投稿後に編集可能にする。
- Policyと独立した `Required Account Interface` をThreadへ持たせる。
- Room内の共有ThreadをすべてNiiMap検索結果へ重複表示する。
- 掲載先を発見できない場合、別の共有先へ自動フォールバックする。
- ThreadPostごとに表示Policyを持たせる。
- NiiMapとRoomの活動をAccountページで別軸として固定表示する。
- Threadの座標だけを変更不可にする。
- Thread削除時にすべてのRoom配置を自動解除する。
- Thread削除時に既存ThreadPostもすべて消去する。
- Room管理者が共有Thread本体を編集・削除する。
- 投稿時Snapshotを常にAccountの現在値で表示する。
- Album画像を削除したらThumbnail履歴からも自動削除する。

---

## 13. 未決事項

次の内容は、既存文書の更新時に推測で確定しない。

- v0.3へRoomを含めるか。
- v0.3へ各種Policyをどこまで含めるか。
- v0.3へInterface基盤を含めるか。
- Room管理者が持つ詳細なModeration権限。
- Room配置承認の完全な状態遷移。
- AND／OR条件グループの具体的な編集UIと初期実装範囲。
- Interface継承時のField名衝突、祖先更新の影響、実装済み判定。
- Interface作成者Account削除後の所有権、表示名、保守方法。
- ResponseInterfaceを一投稿へ複数実装できるか。
- ResponseInterfaceの要求／推奨UI。
- DisplayLayoutの具体的なSlot一覧。
- Room通知の配信方式。
- Event参加RelationshipのDBモデル。
- Thread Title変更を将来許可する条件。
- 配置履歴の保存期間と公開範囲。
- Room、Thread、ThreadPostの物理DBスキーマ詳細。
- Guestが作成したThreadの長期的な管理方法。
- Platform管理者によるModeration。
- Mute、Block、Bookmarkの詳細。
- love／hate等の評価機能を実装する時期。
- Accountページの最終レイアウト。

---

## 14. 既存Vision更新時の推奨ファイル構成

```text
docs/
├─ vision/
│  ├─ README.md
│  ├─ content-model.md
│  ├─ room-and-niimap.md
│  ├─ access-policy.md
│  ├─ interfaces.md
│  └─ account-and-history.md
└─ requirements/
   └─ v0.3.md
```

### `docs/vision/README.md`

- Niixy全体の概要。
- Account、Room、Thread、ThreadPost、Interface、NiiMapの関係。
- 用語集。
- 各詳細文書へのリンク。
- 確定事項、将来構想、未決事項の区別。

### `content-model.md`

- Thread。
- ThreadPost。
- 編集・削除原則。
- Thread削除。
- `last_activity_at`。
- 投稿時Snapshot。

### `room-and-niimap.md`

- Room。
- Thread配置。
- 掲載先と共有先。
- NiiMap表示・検索。
- 座標変更。
- Room活動。

### `access-policy.md`

- Room、ThreadのPolicy。
- 条件モデル。
- 上位・下位制限。
- TemplateとSnapshot。

### `interfaces.md`

- 四種類のInterface。
- 更新可能性。
- Event、店舗、Responseテンプレート。
- DisplayLayout。

### `account-and-history.md`

- Accountページ。
- Album。
- ThumbnailVersion。
- Account評価。
- Event参加Activity。

### `requirements/v0.3.md`

- Vision全体ではなく、v0.3で実装する範囲だけを記載する。
- Vision整理後に別途確定する。

---

## 15. Codexへの作業指示

この文書をCodexへ渡す際は、次の指示を添える。

```md
リポジトリ内の既存コードとdocsを確認し、添付した
「Niixy Vision更新指示書」を今回の構想整理における最新判断として、
docs/vision/を更新してください。

今回はドキュメントの整理のみを行い、コードは変更しないでください。

要件：
- 更新指示書と競合する既存記述は、更新指示書を優先して修正する
- 競合しない既存構想は保持する
- Visionを一つの巨大なファイルへまとめず、責務ごとに分割する
- docs/vision/README.mdを各文書への入口にする
- 「確定事項」「将来構想」「未決事項」を混同しない
- 未決事項を推測で確定しない
- Event、Community、NiiRoom、Pin等の旧名称・旧モデルの残存を検索する
- 既存コードとVisionの差異は、コードを変更せず報告する
- v0.3の実装作業はまだ開始しない
- 更新後、変更したファイル、削除・移動した記述、判断が必要な競合箇所を報告する
```

---

## 16. Codexが作業後に報告すべき内容

Codexは、Vision更新後に少なくとも次を報告する。

1. 新規作成・変更・削除した文書。
2. 旧Visionから維持した内容。
3. 本書に基づいて変更した内容。
4. 既存コードと新Visionが一致していない箇所。
5. 既存文書内で解消できなかった矛盾。
6. v0.3要件として別途決定が必要な項目。

コード変更、DB Migration、既存Eventデータ削除は、別の明示的な指示があるまで実行しない。
