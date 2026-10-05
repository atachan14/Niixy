# 確定仕様と構造

状態: 会話の最終合意を整理。すべて実装済みという意味ではない。

## 設定全体の構造

最初に出た「RoomPolicyの中へRoomProfileLayoutとBoardTemplateを入れる」案は、その後変更された。FieldやInterfaceもTemplateで指定するため、**Policy / Layout / 子Templateは設定全体の下に並ぶ別項目**とする。

```text
Room設定
  Room基本情報: Title / Desc
  Field
  RoomIF
  RoomPolicy: 参加制限 / 閲覧制限
  RoomProfileLayout
  BoardTemplate

Board設定
  Board基本情報: Title / Desc
  BoardPolicy: Thread作成制限 / 閲覧制限
  BoardLayout
  ThreadTemplate

Thread設定
  Thread基本情報: Title / 本文
  Field
  ThreadIF
  ThreadPolicy: 書き込み制限 / 閲覧制限
  ThreadPostLayout
  ResponseTemplate

Response設定
  Response基本情報: 本文
  Field
  ResponseIF
  ResponsePolicy: 閲覧制限
```

- 「設定」は構造を説明する呼称。新しいSettingsモデルや画面名まで確定したわけではない。
- ここでのFieldには、Interfaceを経由せず直接追加するFieldの構想がある。現行ThreadのDirectFieldと整合させる。
- LayoutをInterface内に埋め込む案は過去に撤回している。Layoutを独立させ、上記各対象の設定として選ぶ方向。
- Room管理制限やBoard編集制限も将来構想にはある。ただし上記の最終ツリーには含まれず、具体的な権限委譲・編集UIは別途詰める。現行のRoomOwner限定管理を「汎用管理Policy実装済み」と解釈しない。
- ResponsePolicyに書き込み制限を独断で足さない。Response投稿の許可はThreadPolicyの役割。

## Policyの影響範囲

| Policy | 対象 | 親から子へ持ち越さないもの |
| --- | --- | --- |
| RoomPolicy | Room自体の閲覧・参加、Roomが提供する導線 | 個別Board / Threadを他の導線から利用する際の追加権限判定 |
| BoardPolicy | Board自体の閲覧・Thread作成 | 既存Threadの閲覧・返信への動的な上乗せ |
| ThreadPolicy | 当該Threadの閲覧・Response投稿 | 別Threadへの制限 |
| ResponsePolicy | 当該Responseの閲覧という将来構想 | 未確定の親子判定まで推測して実装しない |

Roomを閲覧できないならRoomPaneから次のコンテンツへ進めない、という意味で「導線を制限」する。**一度Roomを経由したからといって、そのRoomのPolicyがThread利用中に付きまとうわけではない。**

例:

- RoomAは参加者だけ閲覧可能でも、ThreadBのPolicyがNiixyAccountを許可するなら、非参加AccountがThread固有URLや保存済み参照からThreadBへ到達した場合はThreadBのPolicyで判定する。
- RoomA内のThreadを参加者限定にしたい場合、RoomのBoardTemplateからBoardのThreadTemplateを設定し、ThreadPolicyへ「RoomAに参加」を強制して保存する。
- この場合はThread自身がRoomA参加条件を持つため、親Boardがなくなっても条件は残る。Room参加条件をチェックすること自体が禁止なのではなく、**Threadに保存していない親由来の制限を暗黙に足すことが違う**。

APIも同じ境界で認可する。単独URLだから無条件許可するのではない。親の一覧・子一覧取得には親の閲覧判定、独立した子詳細取得には子自身の判定、親で子を新規作成する操作には親の作成権限が必要。

Response個別の閲覧不可表現と、Thread閲覧不可時のResponse単独表示をどう扱うかは詳細未決。上の「親を動的に重ねない」を、その未決部分の完成仕様だと広げない。

## 許可・不可とAccount条件

操作ごとに許可条件と不可条件を持つ。

```text
許可 = 許可Itemのいずれかが成立 AND 不可Itemが一つも成立しない
Item = 一つのAccount条件、または複数Account条件のANDグループ
```

- Item間はOR、グループ内はAND。不可側も同様にグループを評価し、成立した不可Itemがあれば不可を優先する。
- 許可条件が空なら原則許可しない。「条件なし = 全員可」ではない。
- BoardのOwner管理救済や旧Threadの作成者閲覧などは明示的な例外。すべての操作へ自動的に広げない。
- Account条件履歴はAccountごとの保存・使用履歴。全員共通の使い捨て候補ではない。
- 呼び出し元へ追加する時はItemを複数選択し、件数付き追加ボタンでANDグループを追加する。別途AND選択モードへ入る旧操作は廃止。
- Policy側は条件のkind、definition、表示LabelをSnapshotで保持する。履歴の削除・並べ替えだけで、既に保存したPolicyまで変えない。
- 「自分のNiixyID」はPolicy保存者のAccount IDに確定する。閲覧者自身を毎回指す条件にしない。
- Snapshotなのは条件定義。Roomへの参加状態など、判定対象の現在状態まで保存時に固定するわけではない。
- GuestのDefault候補はGuestのみ。AccountIF・Fieldの値条件などは構想にあるが、現在のPolicyで全種類を判定できるわけではない。
- 成立しないANDの組み合わせを自動検出する機能は当面不要と合意済み。

## Templateの対象

| 設定項目 | Templateから指定 |
| --- | --- |
| Title / 本文 / Descなどの基本情報 | 対象外 |
| Fieldの実装・追加 | 対象 |
| Fieldの値 | 今回は対象外。将来必要なら拡張 |
| Interface | 対象 |
| Policy | 対象 |
| Layout | 対象 |
| 子Template | 対象 |

Field必須実装の強制と、Field値の固定は別。削除できないFieldでも値入力は必要であり、値入力欄まで一律に無効化しない。

Template編集では、対象の各設定に値と「推奨 / 強制」を指定する想定。RoomのBoardTemplate入力Paneから、BoardのThreadTemplate、さらにResponseTemplateまで辿って設定する案。Paneの細部、指定粒度、集合の追加・除外方法は未決部分が残る。

## 適用するタイミング

| 場面 | 推奨 | 強制 |
| --- | --- | --- |
| 子を作成 | 初期値に使い、利用者が変更可能 | その値・指定を適用し変更不可 |
| 親Templateだけ変更 | 既存の子へ自動反映しない | 既存の子へ自動反映しない |
| 子の編集可能な設定を編集 | 既存値を再初期化する合意はない | 編集時点の親Templateの強制を適用 |
| 子を閲覧・検索しただけ | 変更しない | 変更しない |
| 作成後変更不可のThreadPolicy | 後から変更しない | 作成時だけ適用。別設定の編集でも書き換えない |

強制されるControlはグレーアウトして変更不可にする。サーバー側でも不正な上書きを拒否する。UI上のdisabledだけを認可・整合性の保証にしない。

作成・編集時に子側へ確定した値を保存する方式であり、閲覧時に常に最新の親Templateを合成する方式ではない。ThreadIFを編集しただけで、変更不可のThreadPolicyを現在の親Templateへ置換してはいけない。

「編集時」の詳細な単位は、部分編集を実装する際に詰める必要がある。名前だけの編集で別の設定まで強制し直すなど、今回の合意から広げた動作を勝手に追加しない。

## 親削除・配置との関係

- Boardは物理削除するが、Thread・Responseは存続する。Thread自身のPolicy・Field・Interfaceも残る。
- Threadの配置先は作成後変更しない。親Board削除時は未配置になり、残った参照を新しい配置先へ昇格させない。
- 未配置Threadも固有URLやAccountの履歴、将来の保存List・参照から利用可能。ThreadPolicyが許せばResponse投稿も続けられる。
- 座標のないThreadをNiiMapのSpotへ出さない。別Boardが参照を保持する場合、そのBoardの一覧に出せないという意味ではない。
- Boardの管理主体は配置先Collectionを持つRoom / Accountから解決する。独立したBoardOwnerは置かない方向。
- NiiMap直置きBoardは将来構想で、管理者がいないため編集・削除・以後の配置変更不可と合意。Room間などのBoard移動は申請・承認を想定し後回し。
- Collection削除では配置Boardを同じRoom / Accountの「未分類」へ移す。「未分類」は常設、削除・改名・並べ替え不可。Mainは初期作成される通常Collectionであり特別な権限はない。

これらはTemplateや親Policyを永続参照しない設計と整合させる。Room削除時の参加条件など、別の未決事項まで「親が消えたら条件を許可へ変更」と推測しない。
