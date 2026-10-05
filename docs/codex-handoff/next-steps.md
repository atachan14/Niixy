# 今後の候補と未決事項

状態: v0.9完了後の引き継ぎ。以下の順番は次Versionへの正式な割当ではない。

## 以前の計画と現在地

Room基盤、Board管理、Collection管理、Policy、Roomの追加機能へ進む大まかな話があった。その後の実装でv0.6はRoom基盤、v0.7はBoard管理、v0.8はCollection管理、v0.9はBoardPolicy基盤とWorkspace共通化にまとまった。

したがって「以前v0.9あたりに回すと話した機能は全部完了」とは扱わない。特にRoomOwner譲渡、参加条件、Tagによる複数管理者はBoardPolicy実装と別。

ユーザーはここから別AIへ引き継ぐ方針。次Versionの番号・優先順位・実装範囲はまだ固定していない。「次はRoomPolicyとThreadPolicy移行が自然」は候補提示であり、確定した開発指示ではない。

## 残っている主な候補

| 領域 | 内容・境界 |
| --- | --- |
| RoomPolicy | 参加・閲覧条件、Room閲覧不可UI。管理条件はTag / 権限委譲と合わせて検討 |
| ThreadPolicy移行 | Account条件の共通評価、不可条件、親Roomへの暗黙依存解消、閲覧不可表示の統一。作成後変更不可は維持 |
| Template | Room→Board→Thread→Responseの推奨 / 強制。基本情報・Field値は対象外 |
| Room運営 | 参加申請、Room内Tag、複数管理者、参加者へのOwner譲渡。Ownerは常に一人で、譲渡後に元Ownerが退会できる構想 |
| Account条件の拡張 | AccountIF / Fieldの実評価、Room内Tag等。選択UIがあるだけでは判定可能にならない |
| Response | ResponseIF / Field / ResponsePolicy。個別閲覧制限の見せ方を詰める |
| Collection / 参照 | Account側のCollection管理、Board参照、Collection参照、Thread参照。配置は一つ、参照は共有先が持つ |
| 配置変更 | Roomの別座標・未配置への変更、管理者間Board移動の申請・承認。急いで限定的な即時移動を作らない |
| Layout | ProfileArea、RoomProfileLayout、BoardLayout、ThreadPostLayout等。単なる自由記述だけでなく他コンテンツの配置も想定 |
| その他Module | RoomIF / AccountIF / ResponseIF、ComputedField、Action等。名前や外枠と実装済み機能を区別 |
| NiiMap | Room内部のThread等を検索対象に含める仕組み。明示フラグか条件からの自動対象化かは未決 |
| Feedback | Love / Hate等や利用者からの評価文。今回のPolicy詳細化に混ぜて実装する指示はない |

Module全体や検索の細かい将来構想を今回すべて再監査したわけではない。既存Visionとこの表を合わせ、必要な領域からVersion要件へ落とす。

## Template実装前に残る確認

1. **強制の粒度**: Policy全体、許可 / 不可の各集合、条件Itemのどれを単位にするか。Field / IFは指定分の追加必須なのか、一覧全体の固定なのか。
2. **編集の単位**: 対象設定を編集した時の再適用は確定済み。部分編集で触れていない設定まで再適用するか、未送信と明示変更をどう区別するかは詳細未決。
3. **ネストの更新経路**: RoomのBoardTemplateだけ更新し、既存Boardを編集しないままThreadを作る時に、どの保存済みTemplateを使うか。上位の最新値を勝手に毎回合成すると既存子へ自動波及するため、段階ごとの確定タイミングを整理する。
4. **編集開始後の親変更**: 入力中に親Templateが変わった場合、保存を拒否して再確認するか等。最新強制を黙って適用し、別の内容を保存したと誤認させない方法が必要。
5. **対象の削除・Version**: 指定Field / IF / Layoutの削除や旧Version化、条件に指定したRoom / Accountの削除をどう扱うか。
6. **保存境界**: 管理者が作るTemplateと子作成者が編集できる範囲、強制された子Templateを書き換えられないことのサーバー検証。

これらの問いを「未確定だから基本構想も白紙」と扱う必要はない。対象外項目、推奨 / 強制、非遡及、ThreadPolicy不変という軸は既に決まっている。

## Policy移行時に残る確認

- 旧Threadの暗黙のRoom参加制限を明示条件へ移す際の既存データ方針。移行による公開範囲変更を避けること。
- RoomOwner / Thread作成者の救済権限を、どの操作へどこまで維持するか。BoardのOwner閲覧例外を汎用の不可条件無視へ拡張しない。
- ResponsePolicyとThreadPolicyの閲覧境界、不可投稿の番号・作者・件数・履歴表示。
- 不可理由のOR / AND表示、部分的に成立するANDグループの説明粒度。
- Roomの不可Popupを閉じた後の再表示、条件に含まれるRoom名などの公開範囲。
- Thread作成不可ボタンの非表示とdisabledの使い分け。現時点で全不可操作を同じDialogへ寄せる合意はない。

## 進め方の提案

まず次AIが既存Visionの更新と本資料を照合し、「次Versionに実装するもの」と「構造だけ先に決めるもの」を分ける。Policyを進めるなら、画面だけでなく共通評価・API・既存Threadの移行を一緒に計画するのがよい。

Template、Layout、全AccountIF条件を一度に完成させないとRoomPolicyを始められない、という合意はない。逆に、Templateなしの固定処理を足す場合は仮実装だと明記し、今後も固定仕様として継承されないようにする。
