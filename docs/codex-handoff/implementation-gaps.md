# 現行実装との差分

確認日: 2026-10-05 / HEAD: `27d806b`

この文書はコード読取による現状記録。新たにブラウザ再現やDB操作はしていない。以下の仮実装は、次のAIが誤って最終仕様として継承しないために記載する。今回その場で修正する依頼ではない。

## 1. Threadへの返信にはまだ親Room参加チェックがある

根拠:

- [events/services.py](../../events/services.py) の `prepare_thread_for_view`: ThreadPolicyの書込許可と、`room_for_thread`で解決したRoomの `has_member` をANDで評価して `thread.can_write` を設定する。
- [events/views.py](../../events/views.py) の `thread_post_create`: POST側でもRoom非参加者を403にする。
- [rooms/views.py](../../rooms/views.py) の `board_threads`: 一覧準備時にも `room.is_member and thread.allows(...)` が残る。

これはv0.6の「Room内の書込は参加者のみ」という固定ルールが残ったもの。v0.9でBoardのThread作成Policyを共通化しても、**既存ThreadへのResponse投稿はまだ完全にThread自身の条件だけでは決まらない**。

将来方針では、Room参加必須にしたいThreadは自身のPolicyにRoom参加条件を持つ。親を暗黙に毎回チェックする方式とは異なる。

移行時の注意:

- UI側だけ親チェックを消してもPOSTで拒否される。逆にPOSTだけ消すと表示と認可が食い違う。
- 親チェックを単純削除すると、既存のRoom内Threadで非参加者の書込が新たに可能になる場合がある。
- 旧固定制限を既存Threadの明示的条件へ移すか、どの既存挙動を維持するかは移行要件として確定する必要がある。今回の合意だけでデータ一括変更を承認されたとは扱わない。
- 現行ではBoard削除後に `room_for_thread` がRoomを解決できなくなると、この暗黙の参加制限も外れる。将来の明示的なRoom参加条件なら親Boardが消えても残る。

## 2. ThreadPolicyは旧二条件方式のまま

[events/models.py](../../events/models.py) の `ThreadAccessRule` は閲覧 / 書込とGuest / NiixyAccountのみ。`Thread.allows` は該当audienceの有無で判定し、ログイン済み作成者の閲覧を例外許可する。

一方、BoardPolicyは [accounts/policies.py](../../accounts/policies.py) の `evaluate_policy` を使う。Threadがこの共通評価器へ移行済みという理解は誤り。

- Threadの不可条件、Room条件、特定Account条件、OR / AND構造は新基盤へ未移行。
- [events/services.py](../../events/services.py) の `matched_write_denials` は現状常に空。不可条件表示用の受け口があっても、Threadの不可条件を保存・評価できる意味ではない。
- Threadの作成後Policy編集は許可していない。移行を機に編集可能へ変える合意はない。
- Board編集とThread作成が同じAccount条件・同じフォーム構造へ全面統一済みというわけでもない。

## 3. 閲覧不可Threadの存在表示が全導線で揃っていない

[rooms/views.py](../../rooms/views.py) の `board_threads` は `threads = [thread for thread in board_threads if thread.can_view]` として閲覧不可Threadを一覧から除外する。

これは「存在をSummaryItemに残し、閲覧不可とTitle・更新日時を表示する」将来方針と異なる。Board自身の閲覧不可Summary表示が完成したことと混同しない。

[templates/events/partials/thread_detail_content.html](../../templates/events/partials/thread_detail_content.html) は、閲覧不可なら投稿本文を描画せず「このThreadは閲覧できません。」と表示する。ただし、不足条件・該当不可条件の詳細案内にはなっていない。配置行は `thread.can_view` の条件分岐より前にあるため、閲覧不可でも配置情報が描画される構造。

[templates/accounts/partials/response_pane.html](../../templates/accounts/partials/response_pane.html) はThreadが閲覧不可なら投稿本文を出さないが、Threadタイトルと投稿件数を表示する構造。件数などの公開範囲は今後整理する。

今後は一覧・詳細・検索・Response履歴を別々に確認すること。ある導線で非表示だから全APIも同じ、とは判断しない。

## 4. RoomPolicyとResponsePolicyは未実装

根拠:

- [rooms/models.py](../../rooms/models.py): RoomとRoomMembership、BoardPolicyConditionはあるが、上記構想のRoom参加・閲覧Policyを保存するモデルはない。
- [rooms/views.py](../../rooms/views.py): `room_join` はログイン済みなら参加。`room_leave` は現Ownerの退会を拒否。Room詳細・Member一覧・Board一覧はまだRoomPolicyを評価しない。
- [templates/rooms/partials/room_overview.html](../../templates/rooms/partials/room_overview.html): Policyボタンは未対応でdisabled。Guest参加Dialogには「Room独自の参加条件はありません」と固定表示。
- [events/models.py](../../events/models.py): ThreadPostに個別ResponsePolicyはまだない。

Guest参加不可のプラットフォームルールは現行でもサーバー側で実施している。RoomPolicy未実装だからGuest参加まで未制限という意味ではない。

Room閲覧不可のPopup、Thumb / Feedback / Profileの非表示、閲覧不可RoomのSummary表示は、Boardの完成済み表示から自動的に実現されるわけではない。

## 5. BoardPolicyで既にできること

実装入口:

| ファイル | 主な内容 |
| --- | --- |
| [accounts/policies.py](../../accounts/policies.py) | 許可OR、グループ内AND、不可優先、空の許可は不許可。現在状態を条件定義で判定 |
| [rooms/models.py](../../rooms/models.py) | `BoardPolicyCondition`、`Board.evaluate_policy` |
| [rooms/services.py](../../rooms/services.py) | 初期条件、Snapshot検証、グループ保存、表示用行の生成 |
| [rooms/views.py](../../rooms/views.py) | Board閲覧・作成POSTの評価、RoomOwner限定編集 |
| [board_threads.html](../../templates/rooms/partials/board_threads.html) | 不可理由のみのBodyと、許可時の詳細・編集・作成フォーム |
| [board_list.html](../../templates/rooms/partials/board_list.html) | 閲覧不可BoardのSummary表示 |

初期値は閲覧 `Guest OR NiixyAccount`、Thread作成 `配置先Roomへの参加`、不可条件なし。これは現行Board生成の固定初期値であり、RoomのBoardTemplateから生成しているわけではない。

RoomOwnerはBoardの閲覧を救済されるが、Thread作成には通常の作成条件が必要。非OwnerのThread作成にはBoardの閲覧と作成の両方をチェックする。BoardPolicy変更が別導線のThread閲覧へ動的に重なる実装ではない。

Board管理はRoomOwner限定。編集 / 削除を任意のAccount条件へ委譲できるPolicyはまだない。

閲覧許可・Thread作成不可のBoardでは、現在は `Thread作成` ボタンをdisabledで残す。ユーザーは以前「作成不可ならボタン非表示でもよい、後で詰める」としているので、この差はUI再検討事項。閲覧不可Boardでは作成UI自体を返さない。

## 6. Account条件UIとPolicyの対応種類は違う

[static/accounts/account_conditions.js](../../static/accounts/account_conditions.js) が共通履歴・複数選択・追加を担当する。`loadCatalog` は履歴APIから取得し、`addGroup(activeTarget, selectedConditions())` が選択した条件をまとめて追加する。

[rooms/services.py](../../rooms/services.py) の `_board_policy_condition_snapshot` がPolicy保存時に受け入れるのは次:

- DefaultのGuest / NiixyAccount / 自分のNiixyID。
- 特定Account。
- 特定Roomへの参加。配置先Roomだけに限定しない。

`self` は保存者の固定Account IDへ変換する。表示Labelはサーバー側で生成し、送られた文字列を認可条件そのものにはしない。

Field / AccountIFの条件編集用画面や履歴の仕組みがあっても、Policyで実評価できるわけではない。現行Board保存処理は未対応種類を拒否し、共通評価器の未対応条件はfalseになる。UIの候補数を、認可の対応範囲だと数えない。

`update_board_policy` はグループのJSON配列を受け取り、同じgroup_keyの条件として保存する。このため、v0.9要件に残る「Policy編集画面からのANDグループ作成は対象外」は現コードと照合が必要。少なくとも接続・保存のコードは存在する。ただし今回の文書作成でその組み合わせのブラウザ再検証はしていない。

## 7. TemplateとLayoutは見出しだけの箇所がある

Board詳細のLayout / ThreadTemplateアコーディオンは「未実装」。FieldやThreadIFを選んで実装する処理があっても、それを親Templateが推奨・強制する基盤があるわけではない。

RoomProfileLayout、BoardLayout、ThreadPostLayout等の型・名前の構想と、保存・選択・適用エンジンの完成状況を分けて扱う。今回、Module全種別の実装状況を網羅監査したわけではない。

## 既存docsとの照合表

| 参照 | 読取時の状態 | 次のAIへの注意 |
| --- | --- | --- |
| [Vision / access-policy](../vision/access-policy.md) | Templateは作成時だけ作用する旧説明 | 編集可能な対象設定の編集時にも強制を適用する合意へ照合 |
| 同上 | 「編集可能なRoomPolicyとBoardPolicyを実装する前に…」 | BoardPolicyはv0.9で実装済み。Room / Boardを未着手として一括扱いしない |
| [Vision / decisions](../vision/decisions.md) | 旧AND継承案、旧BoardOwner案なども履歴として残る | 「置換済み」「一部置換」と後の決定を読む。検索で最初に出た段落だけを採用しない |
| [v0.9 requirements](../v0.9/requirements.md) | Boardの細かな不可表示・Templateの新方針は記載済み | Room / Threadの全UIが実装済みという意味ではない |
| 同上 | ANDグループ作成を対象外に列挙 | 共通UIとBoard保存処理にはグループ対応あり。意図・実動作を照合 |
| [Roadmap](../roadmap.md) | FutureにBoardPolicy、既に実装した検索に重なる旧Event項目等が残る | 未着手リストとしてそのまま使わない。Versionの完了範囲で判断 |

別AIが既存docsを変更中のため、上表はこの時点の観測記録。既に修正された項目を再び変更する必要はない。

## 次回修正時の回帰確認候補

以下は推奨テスト項目であり、今回実行済みの結果ではない。

- Guest / Account / Owner / 非参加者 / 参加者での各操作。
- RoomやBoardを閲覧できなくても、別導線のThreadは自身のPolicyどおりに判定されること。
- 閲覧不可レスポンスのHTML / JSONに、保護本文や子一覧が混入しないこと。
- Account条件履歴の削除で保存済みPolicyが変わらないこと。
- 親Template変更だけでは既存子が変わらず、編集可能項目の編集時だけ新しい強制が働くこと。
- ThreadIF編集で変更不可のThreadPolicyを書き換えないこと。
- Board削除後もThreadに保存済みのRoom参加条件が残ること。
- 条件編集の補助Paneが起点の右に開き、遅い応答で破棄済みPaneが復活しないこと。

テスト環境と実行手順は[既存引き継ぎ](../handoff.md)を参照。通常のlocalhostサーバーが共有Neonを使う場合があるため、検証データは隔離SQLiteに置く。
