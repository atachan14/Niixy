# Interface

## 目的

Interface は Niixy の概念に付与する構造化・再利用可能な情報と機能である。基礎モデルを変えずに、Event、募集、質問などの専用形式を表現できるようにする。

Interface は Field の入力値を表示するだけでなく、Field を参照した自動計算、Niixy が提供する Action、通知、応募、参加、承認などの機能を宣言できる方向で設計する。利用者が任意のプログラムを実行する方式にはせず、Niixy が安全に提供する処理を組み合わせる。

## 分類

- AccountInterface: アカウントのプロフィールや資格情報
- RoomInterface: Room の設定やアイデンティティ情報
- ThreadInterface: 将来の Event 情報を含む、Thread 用の専用情報
- ThreadPostInterface: `#1` と返信を含む ThreadPost に付与する専用情報

Interface は作成した Account と名称を名前空間として持つ。Tweet と Timeline に Interface や Layout を適用する可能性はあるが、分類と適用範囲は実装時に決める。

Interface の新規作成と Version 更新には、作成者だけが扱う編集途中データとして Draft を設ける。Draft は何度でも保存・破棄でき、利用者が実装できる InterfaceVersion には含めない。新規 Interface の Draft を初めて公開した時点で v1 を作成し、公開済み Interface の Draft は公開した時点で次の Version を作成する。Version 番号は公開時にだけ確定し、公開されなかった Draft に欠番を生じさせない。

Interface は現在利用する公開済み InterfaceVersion を一つ参照する。Draft の公開時には参照する FieldVersion と機能を一括検証し、変更不能な InterfaceVersion を作成して現在 Version を切り替えた後、Draft を削除する。InterfaceVersion と Draft は保存先を分け、Draft 自体に公開・非公開などの状態を持たせない。

公開済みの Interface は `active` と `deleted` の状態を持つ。削除は DB からの物理削除や空の新 Version の作成ではなく、Interface 自体を `deleted` にする Soft Delete とする。削除済み Interface は通常の一覧から隠し、新規実装に利用できなくするが、既存対象は固定済みの InterfaceVersion を継続利用する。まだ v1 を公開していない Draft は Interface の削除ではなく Draft の破棄として扱う。

Version は Field参照・機能などの定義変更だけを表し、削除・復元では増やさない。削除済み Interface と同じ名前で作成しようとした場合は新しい Interface を作らず、既存 Interface の復元として案内する。定義を変えずに復元する場合は現在の Version のまま `active` に戻し、定義も変更する場合は新 Version を作成してから復元する。公開済み InterfaceVersion と FieldVersion は削除せず、名前空間も再利用しない。

削除により参照元 Interface が新規利用できなくなる場合は、削除前に影響範囲を表示する。本人用一覧の整理だけを目的とする非表示機能を削除と分けるかは、管理 UI の実装時に検討する。違法・悪意・脆弱性などへの強制停止は、通常の削除状態とは分けて将来の運営機能として扱う。

## Field と片同義

Field は Interface の内部ではなく、作成者、安定 ID、現在 Version を持つ独立した定義とする。Field 自体は Account、Room、Thread、ThreadPost などの対象種別を持たず、用途の異なる Interface から再利用できる。InterfaceVersion は FieldVersion を参照し、その Interface 内での必須・任意と表示順を保持する。

対象は Field を直接値として保持せず、対象に属する Value と、Field から Value への接続を保持する。同じ Field を複数 Interface が使用する場合は同じ Value を参照する。Account と Thread のように対象が異なる場合は、同じ Field を使用してもそれぞれ別の Value を持つ。

Threadには、FieldをInterface経由だけでなくDirectFieldとして個別に実装できる。DirectFieldとInterface内のFieldは同じValue解決処理を使用し、同一Fieldまたは片同義Fieldであれば実装経路にかかわらず一つのValueを共有する。DirectFieldは軽量な個別追加、Interfaceは複数Fieldや機能を用途ごとにまとめる単位として使い分ける。

FieldVersion は、同じ意味と値型を持つ別の Field を「片同義（One-way synonym）」として参照できる。検索時は参照元から参照先だけへ候補を展開する。同じ対象へ片同義で接続された Field が実装された場合は、方向にかかわらず一つの Value を共有する。

片同義によって既存の異なる Value が接続される場合は、その対象へ最初に実装された Field の Value を維持する。変更される値は Interface の実装前に表示し、利用者の確認を得る。片同義Targetは同じ型の Field に限定する。

Field の再利用に InterfaceRequirement は使用しない。将来の ComputedField、Action、Layout が入力を必要とする場合は、Interface 全体ではなく必要な Field を RequireField として参照する。ComputedFieldへ片同義を適用する詳細は、ComputedField実装時に決める。

## Version と Field

Interface と Field はそれぞれ Version を持ち、公開済み Version は変更しない。新規 InterfaceVersion は各 Field の最新版だけを参照し、新規実装時は Interface の最新版を使う。利用者に Version を直接選択させず、実際に適用した InterfaceVersion と FieldVersion を対象へ固定する。

旧 Version は既存対象の意味と表示を維持する過去ログのための資産とし、新規対象へ直接選択・適用させない。新規投稿を最新版へ集約することで、検索対象が旧 Version ごとに分散し、抽出精度と検索体験が低下することを避ける。

旧 Version を使う対象は当時の InterfaceVersion と Field による表示・動作を継続する。最新 Version の内部に、使用されなくなった Field を historical field として重複保持しない。

Field の意味または値型を変更する場合は、新しい Field として定義する。同じ値を安全に引き継げる説明、表示名、Validation、片同義Targetなどの変更は、同じ Field の新しい FieldVersion とする。これにより、たとえば「好きなポケモン」を「嫌いなポケモン」へ変更し、既存値の意味を反転させることを防ぐ。

通常の検索候補には最新版の Field を提示する。利用者が望む場合は、過去 Version の Field を選び、最新版へ更新されていない対象を検索できるようにする。検索 UI の詳細は検索機能の実装時に決める。

既存の Thread は、適用中 Interface または Field が旧 Version であることを作成者へ示し、変更内容を確認したうえで最新版へ更新できる。更新は参照するFieldとValueの統合を含めて一括検証し、壊れた実装構成を保存しない。

依存先の変更や Field の置換が必要な更新では、Interface 作成者が安全な値の対応関係を MigrationPlan として提示できる方向で設計する。Thread 作成者は更新時に、引き継ぐ値、失われる値、新たに必要な入力、無効になる Interface を確認して同意する。任意プログラムによる移行は許可せず、同じ型の値のコピー、安全な型変換、固定値、再入力、破棄などの宣言的な操作に限定する。

## ThreadInterface の表示

ThreadInterface の実装値は、`#1` の本文直下に置く必須の固定領域で表示する。外側の ThreadInterface 一覧は初期状態で収納し、展開後は最新版の実装と更新履歴を分ける。各 Interface も個別に収納できるアコーディオンとし、初期状態では展開する。

```text
ThreadInterface（初期状態: 収納）
  最新（初期状態: 展開）
    Interface A（初期状態: 展開）
      Field
    Interface B（初期状態: 展開）
      Field
  更新履歴（初期状態: 収納）
```

## DisplayLayout

DisplayLayout は、Interface の実装値や共通 Item をどのように表示するかを定める独立した Layout の総称である。Layout は必要な Field、ComputedField、Action を宣言し、項目の順番、サイズ、配置を定義する。複数の Interface を横断して配置でき、通常利用者には Niixy の標準 Layout を自動適用する。

### ThreadPostLayout

ThreadPostLayout は、`#1` と返信を含む ThreadPost 全体の表示項目、順番、サイズ、配置を定める。Thread は内部で使用する ThreadPostLayout を設定できる。

ThreadPostLayout は AccountInterface と ThreadPostInterface が実装する Field を配置できる。`#1` にも必要な ThreadPostInterface の値を入力する。ThreadPost の作成時には、表示する AccountInterface の値、ThreadPostInterface の値、使用した ThreadPostLayout の Version を Snapshot として固定する。AccountInterface や Layout が後から更新されても既存 ThreadPost の表示を変更しない。

Layout は Thumbnail、表示名、Niixy ID、投稿番号、投稿日時、AccountInterface や ThreadPostInterface の Field などを配置できる。一方、本文と対象固有の操作を含む本文領域は必須の固定 Item とし、Layout から削除したり内部構造を変更したりできない。

`#1` の本文領域には本文、ThreadInterface 一覧、Thread を対象とする機能ボタン群を置く。返信の本文領域には本文と、その ThreadPost を対象とする機能ボタン群を置く。fav、bad などの基本機能も本文領域側で固定表示する方向とする。

### ProfileLayout

ProfileLayout は、AccountPageとRoomPageのProfileAreaを表示するLayoutである。AccountまたはRoomが基本情報として持つDescriptionのほか、必要なField、Timeline、Thread、Boardなどを配置できる。対象が必要なFieldを持たない場合は、そのFieldを含むInterfaceの実装を案内する。

ProfileLayout は Interface のフィールド定義や入力値を持たない。Interface の定義と対象ごとの実装値は Layout から独立して存在するため、Layout を変えても入力済みの情報を使い回せる。他者が作成した ProfileLayout をコピー、編集、保存、再利用できるようにする。

用意した Slot と Item を並べる宣言的な Layout は有力な案だが、自由度、実装コスト、仕様の分かりやすさを踏まえて実装時に再検討する。DisplayLayout は、誰でも簡単に編集するための機能ではなく、詳しい利用者が高い自由度でカスタマイズするための機能として想定する。

他者が作成した Layout をソースとしてコピーし、編集して別の対象で再利用したり、保存して使い回したりできるようにする。BoardはBoard内のThreadに同じThreadInterfaceとThreadPostLayoutを要求できる方向で設計する。ProfileLayoutのSnapshot、公開範囲、Version管理の詳細は後続で決める。

## 実装時に決めること

- 初期対応する Field 型、Validation、計算式、Action
- Interface と Field の作成・公開・Version 更新 UI
- FieldVersion の互換性検証と、参照元作成者への通知
- ThreadInterface の更新履歴とシステム Response の関係
- ThreadPostLayout の具体的な Slot、Item、編集形式
- Tweet と Timeline に適用する Interface と Layout

## Accountへの適用（v0.12）

Accountにも直接FieldとAccountIFを適用し、同一Field・片同義のValueはそのAccount内で共有する。追加時の公開版を固定し、編集はMyPage、公開閲覧はAccountPageのApplied一覧で行う。Module定義一覧や将来のProfileLayout欄とは統合しない。

Applied一覧はField／AccountIFタブ。Fieldは同一definitionを重複表示せず、Value更新日時の新しい順とその更新日時を表示する。AccountIFは参照Valueの最大更新日時順（値がない場合は適用日時）で表示する。参照を追加しただけでは既存Valueの更新日時を動かさない。

共有Valueの編集は関連項目へ反映する。編集欄の下に他の共有先名称を短く示し、通常編集の確認modalは設けない。既存の異なるValueを片同義で統合する際は、従来方針どおり最初の適用Valueと変更内容を確認してから保存する。direct参照の取外しはIFの固定構成を変更せず、IF由来Fieldの取外しはIF単位で行う。

## 長期構想・Version未割当

Interface定義へ入力用プレースホルダを保存できるようにし、定義確認画面のレイアウトも将来改善したい。placeholderをIF内Fieldごとの入力ヒントにするかなど、保存単位・詳細は未定。v0.12には追加せず、ずっと後の検討対象とする。
