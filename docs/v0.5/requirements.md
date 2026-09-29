# v0.5 Interface Foundation 要件

## 目的

Account が再利用可能な Field と ThreadInterface を定義し、Thread 作成時に一つ以上の Interface を実装して、構造化された値を `#1` に表示できる最小基盤を作る。

## 先行する画面整理

- SummaryItem のアコーディオンを廃止し、選択時に対象の DetailPane を直接開く。
- NiiMap の Thread 新規作成フォームは、地点を選択する Map と同時に操作できるよう Thread 一覧Pane内に表示する。
- Thread 作成成功後は再読み込み先で、作成した Thread を通常選択時と同じスライドアニメーションによって ThreadDetailPane に自動表示する。送信前や作成失敗時には DetailPane を開かない。
- Account 新規登録時に表示名を任意入力できるようにする。
- DetailPane は共通パターン名とし、具体的な領域を ThreadDetailPane、InterfaceDetailPane と呼ぶ。Thread の新規作成は、Mapとの同時操作を優先して ThreadDetailPane の対象外とする。

## Interface 管理画面

Profile と MyPage では Field、ComputedField、Action、Interface、Layout を「定義」としてまとめる。各定義の管理画面は、左側の SummaryList と右側の DetailPane で構成する。SP では既存の ThreadPane と同様に横スライドで切り替える。

Profile の一覧には、作成した Interface、実装済み AccountInterface、保存した Interface を表示する。MyPage にはこれらに加えて、編集中の Interface、削除済み Interface、新規作成、検索を設ける。

編集中の Interface には、v1 公開前の新規 Draft と、公開済み Interface の次回 Version Draft の両方を表示する。

## Draft と公開

- Draft は InterfaceVersion とは別の変更可能な作業データとして保存する。
- 新規 Draft を初めて公開すると v1 を作成する。
- 公開済み Interface の Draft を公開すると、その時点で次の Version 番号を付ける。
- 公開時に参照する FieldVersion と機能を一括検証する。
- 公開成功後に current version を切り替え、Draft を削除する。
- 公開済み InterfaceVersion と FieldVersion は変更しない。
- 一つの Interface が同時に持つ Draft は一つとする。

## InterfaceDetailPane

作成・編集時には基本情報と、この Interface が参照する Field を編集する。Field の追加では検索、作成、保存Tabを持つ Field一覧Paneを開き、選択後にField詳細Paneを開く。InterfaceVersionは選択したFieldの最新版を参照し、必須・任意と表示順を保持する。

Field は Interface から独立した安定IDとVersionを持つ。初期 Field 型は、一行テキスト、複数行テキスト、整数、小数、日付、日時、真偽値、単一選択、複数選択とする。画像・ファイル、他対象への参照、座標、ComputedField、条件付き Field、Action は後続とする。

FieldVersionは同じ型のFieldを片同義Targetとして参照できる。検索展開は参照元から参照先への片方向とし、同じ対象へ実装された片同義Fieldは一つのValueを共有する。異なるValueを統合する場合は、最初に実装されたFieldのValueを維持し、Interface実装前に差分を示す。

## Thread 作成時の適用

Thread 作成画面では本文欄の下に Interface 欄を置き、適用済み Interface の末尾に「Interfaceを追加」を表示する。追加操作では Interface の SummaryList と InterfaceDetailPane をスライドインし、一覧から選択した Interface の説明と入力欄を確認する。

「このInterfaceを使用」で Thread 作成画面へ戻り、Interface 欄へ反映する。同じFieldや片同義Fieldを使用する複数Interfaceは同じValueを参照する。適用済み Interface は再度開いて値を編集できる。

## v0.5 に含めないもの

- InterfaceとFieldの更新を既存Threadへ適用するMigrationPlanの実動作
- Thread 作成後の Interface 追加、削除、Version 更新履歴
- 計算 Field、Action、通知、応募・承認機能
- ThreadPostInterface と ThreadPostLayout
- Interface Field を使った検索・抽出
- Tweet と Timeline
- 複数の保存リスト
