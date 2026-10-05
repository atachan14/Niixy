# v0.9 BoardPolicy Foundation 要件

Status: Complete

## 目的

Account条件を用いた共通Policy評価の基盤を作り、Boardの閲覧とThread作成をBoardPolicyで制御できるようにする。

v0.9ではBoardPolicyを最初の利用対象とする。RoomPolicy、ThreadPolicyの新基盤への移行、Template、Layoutは後続Versionで扱う。

## 共通評価

Policyは操作ごとに許可条件と不可条件を持つ。

- 許可条件のItem同士はORで評価する。
- 一つのANDグループに含まれる条件はすべて成立した場合に、そのItemが成立する。
- 許可条件が一つ以上成立し、不可条件が一つも成立しない場合だけ操作を許可する。
- 不可条件は許可条件より優先する。
- 許可条件が空の場合は、誰にも操作を許可しない。

条件はAccountConditionと同じ`kind`、`definition`、表示LabelをSnapshotとしてPolicyへ保存する。v0.9の画面から選べる条件はGuest、NiixyAccount、自分のNiixyID、特定Account、選択したRoomへの参加とする。自分のNiixyIDは保存時に操作したAccountのIDへ確定し、Room条件はBoardの配置先以外のRoomも選べる。モデルと評価器はOR ItemとANDグループを表現できる構造にする。

## BoardPolicy

BoardPolicyは次の操作を制御する。

- 閲覧
- Thread作成

RoomOwnerだけがBoard詳細の編集からBoardPolicyを変更できる。画面上で操作を隠すだけでなく、Board詳細取得とThread作成POSTでも同じPolicyを評価する。

既存挙動を維持するため、新規Boardと既存Boardには次の初期条件を設定する。

- 閲覧可能: Guest OR NiixyAccount
- Thread作成可能: 配置先Roomへ参加
- 閲覧不可、Thread作成不可: 条件なし

RoomOwnerは、閲覧条件を誤って外してもPolicyを修正できるようにBoard管理画面を開ける。Thread作成POSTではBoardの閲覧可否とThread作成条件の両方を再評価する。RoomOwnerは閲覧条件にかかわらずBoardを開けるが、Thread作成条件は通常どおり適用する。

## 閲覧不可UI

閲覧できないBoardもCollection内のSummaryListから消さない。

- SummaryItem上段に`閲覧不可`と表示する。
- Board名と最終更新日時は表示する。
- Thread数は表示しない。
- ItemをクリックしてBoardPaneを開ける。
- BoardPaneには不足している許可条件と、該当した不可条件だけを表示する。
- Boardの詳細、Policy全体、Thread一覧、Thread作成UIは返さない。

サーバー側でも閲覧不可利用者向けResponseへBoard詳細とThreadデータを含めない。

## 親子Policy

各Policyは自身の対象と、その対象から提供する導線だけを制御する。

- RoomPolicyはRoomPageとRoomからの導線を制御する。
- BoardPolicyはBoardPaneとBoardからの導線を制御する。
- 別の導線から直接Threadへ到達した場合はThreadPolicyで判定する。
- 親Policyを子へ動的に重ねない。

将来のTemplateは、子の作成時または編集時に設定値を確定する仕組みとして扱う。既存対象へ親の変更を一括反映しない。

## 関連するWorkspace遷移

Account・Room・Board・ThreadのPane遷移は共通の起点保持・子孫置換として扱う。

- 操作の起点Paneとそれ以前を保持し、後続Paneを閉じて新しい遷移先へ置き換える。末尾Paneからの操作は追加になる。
- 保持するPaneのDOM、スクロール、入力、Tabの状態を維持し、破棄済みPaneへの遅い応答を新しい枝へ反映しない。
- Account条件・Account選択・Field選択の補助Paneも同じ枝として扱う。
- 末尾PaneのCloseは直前へ戻り、途中PaneのCloseはその後続も閉じる。
- 通常設定では既存の展開・Closeアニメーションを使い、prefers-reduced-motionを尊重する。
- Page遷移、ブラウザ履歴、URLからの再読み込み復元との区別を維持する。

## Templateの確定方針

Templateは基本情報を対象に含めない。Fieldは実装有無だけを指定し、値は指定しない。Interface、Policy、Layout、子Templateを指定対象にできる。

- 推奨値は作成時の初期値で、利用者が変更できる。
- 強制値は作成時に変更できない。
- 編集可能な設定を後から編集する場合、その編集時点の親Templateの強制値を適用し、該当Controlを無効表示にする。
- 編集操作を行わない既存対象は変更しない。
- 作成後に変更できないThreadPolicyなどには、作成時だけTemplateを適用する。
- 強制値は画面だけでなくサーバー側でも上書きを拒否する。

Template自体の保存と適用はv0.9に含めない。

## 完了条件

- 共通評価器が許可OR、ANDグループ、不可優先、空の許可条件を扱える。
- 既存Boardと新規Boardに従来挙動を保つ初期BoardPolicyが存在する。
- RoomOwnerが閲覧条件とThread作成条件を編集できる。
- 閲覧不可BoardがSummaryListに残り、BoardPaneで理由だけを確認できる。
- 閲覧不可利用者へBoard詳細とThread一覧を返さない。
- Thread作成POSTがBoardPolicyを再評価する。
- BoardPolicyが別導線から開いたThreadへ動的に影響しない。

## 完了確認（2026-10-05）

実装確認の基準はcc58188（Boardの閲覧・Thread作成判定修正を含むdd4cc3dの後続）とする。

- 共通評価器、初期Policyの生成・既存Boardへの移行処理、RoomOwner限定の編集処理を完了条件と照合した。
- 既存Djangoテスト138件が成功した。Policy評価、閲覧不可Responseの情報非表示、Ownerの編集、閲覧・作成条件の組み合わせとThread作成POSTの再評価を含む。
- 隔離SQLiteで `manage.py test scripts.workspace_browser_tests --noinput` が成功した。PC・スマートフォンの両画面で子孫置換、遅い応答の破棄、補助Pane、復元を確認し、展開・Closeはtransitionイベントとフレームごとの位置変化で検証した。
- `scripts/browser_smoke.py` のPC・スマートフォン確認は警告・ブラウザエラーなしで成功した。ユーザーによるブラウザ動作確認も完了した。

Ownerが閲覧条件を外した後も編集できること、非OwnerのPolicy編集POSTを拒否すること、別導線のThreadへBoardPolicyを重ねないことは実装の読取も含めて照合した。すべての完了条件を専用の自動テストで網羅したという意味ではない。稼働中の共有DBへの操作や追加のデプロイはこの確認に含めない。

## v0.9に含めないもの

- RoomPolicy
- 既存ThreadPolicyの共通Policyモデルへの移行
- BoardTemplate、ThreadTemplate、ResponseTemplate
- Layoutの作成・適用
- AccountIF、Fieldを使った条件の実評価
- Policy編集画面からのANDグループ作成
