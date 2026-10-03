# v0.5 Interface Foundation 要件

## 目的

Account が再利用可能な Field と ThreadInterface を定義し、Thread 作成時にDirectFieldまたはInterfaceを実装して、構造化された値を `#1` に表示できる最小基盤を作る。

## 先行する画面整理

- SummaryItem のアコーディオンを廃止し、選択時に対象の DetailPane を直接開く。
- NiiMap の一覧Paneでは「新規作成」を選んでMap上の地点を指定し、対象種別を選んだ後に作成フォームをDetailPaneとして開く。Mapと一覧Paneを画面内に残しながら作成Paneへ遷移する。
- Thread 作成成功後は再読み込み先で、作成した Thread を通常選択時と同じスライドアニメーションによって ThreadDetailPane に自動表示する。送信前や作成失敗時には DetailPane を開かない。
- Account 新規登録時に表示名を任意入力できるようにする。
- DetailPane は共通パターン名とし、具体的な領域を ThreadDetailPane、InterfaceDetailPane と呼ぶ。Threadの閲覧と新規作成は同じDetailPane領域を切り替えて使用する。

## NiiMap の検索と作成

NiiMapの一覧Paneは「検索」と「新規作成」を入口とし、両方を同時には開かない。一覧には常にMapの表示範囲内に配置された対象だけを表示する。現行の対象種別はThreadのみとし、Room、Book、Timeline、Tweetは各機能の実装時に追加する。

検索条件はソート、基本情報、Policy、Moduleに分ける。基本情報では対象種別、作成者、更新日、タイトルと本文を対象にしたフリーワードを扱い、Policyでは指定した利用者に対する閲覧・書込の実効的な許可結果を扱う。ModuleではFieldの型に応じた値とThreadIFの有無を条件にできる。複数条件はANDとし、片同義Fieldは参照元から参照先へ検索対象を展開する。

Policyは閲覧可能、閲覧不可、書き込み可能、書き込み不可の4枠を常設し、それぞれでAccount条件を追加する。Guestとログイン済みAccountのどちらでも初期条件は空とする。検索窓は常設のカード型アコーディオンとし、収納しても入力中の条件を保持する。リセットでは空の初期条件へ戻す。

ログイン中に検索を実行した場合、Policyを含むすべての検索条件をAccountごとに保存する。次回NiiMap表示時はデフォルトの検索結果を表示し、保存条件は検索窓へ入力値として復元するだけで自動適用しない。再度「検索」を実行した時点で適用する。Guestの検索条件は保存しない。

Spot一覧PaneはHeader、新規作成アコーディオン、検索アコーディオン、SummaryListの順に配置する。Headerは「Spot一覧」だけを表示し、閉じる操作を持たない。新規作成も検索と同じカード型アコーディオンとし、収納中も入力値、選択地点、仮Markerを保持する。収納中はMapクリックによる地点変更だけを停止し、再展開時に再開する。入力途中の状態はPage遷移時に破棄する。

作成者とPolicyでは、再利用可能なAccount条件を共通して使用する。Account条件の種類はDefault、Account、AccountIF、Field、Roomとし、Accountごとに使用履歴と並び順を保持する。呼び出し元へ追加された条件Item同士はOR、ANDグループとしてまとめた一つのItemの内部はANDとして評価する。成立不能なANDグループの作成も当面は制限しない。

Account条件一覧では通常クリックで単独条件を追加し、ANDグループモードでは種類をまたいで複数選択して一つの条件Itemとして追加する。追加後も一覧Paneを閉じず、連続追加できるようにする。DefaultとAccountを先行して実動作させ、AccountIF、Field、Roomは各機能のデータ基盤に合わせて拡張する。

Account条件一覧には「新しい条件を探す」を置き、SummaryListにはAccountが保持する全種類の使用履歴を並び順どおり表示する。遷移先の一覧PaneではDefault、Account、AccountIF、Field、Roomを上段Tabで切り替える。Fieldは検索・自作・保存Tab、Accountは検索・Follow・Mute・Love・Hate Tab、AccountIFは検索・自作・保存Tab、Roomは検索・参加・保存Tabを下段に持ち、Defaultでは下段Tabを表示しない。

FieldのSummaryItemを選ぶと定義確認Paneを開き、Actionの「Account条件を編集」から条件編集Paneへ切り替える。値を空欄にした場合はFieldの実装有無だけを条件とし、値を指定した場合は型に応じた比較方法と値を保存する。「条件一覧に追加する」でAccount条件一覧へ追加する。

値を持つField条件はAccount条件履歴のSummaryItem右端に「編集」と「×」を表示し、編集後は同じ履歴Itemを置き換える。Defaultなど編集余地のない条件は「×」だけを表示する。呼び出し元へ追加済みの条件Itemは追加時点のSnapshotとして扱い、履歴Itemを編集しても変更しない。

Defaultのself条件は「自分のNiixyID」ではなく、実際の `@NiixyID` を表示する。値を指定した条件のSummaryItemでは、上段に値と比較方法、中段にModule名と作成者、下段にModule種別を表示する。AccountIF条件でも複数Fieldの条件値を上段に要約する方針とし、連結方法と省略規則はAccountIF実装時に決める。

Guestが利用できるDefault条件はGuestだけとする。selfやFollowなどAccountに紐づくDefault条件は、ログイン済みAccountにだけ表示する。

作成者とPolicyでは、再利用可能なAccount条件を共通して使用する。Account条件の種類はDefault、Account、AccountIF、Field、Roomとし、Accountごとに使用履歴と並び順を保持する。呼び出し元へ追加された条件Item同士はOR、ANDグループとしてまとめた一つのItemの内部はANDとして評価する。成立不能なANDグループの作成も当面は制限しない。

Account条件一覧では通常クリックで単独条件を追加し、ANDグループモードでは種類をまたいで複数選択して一つの条件Itemとして追加する。追加後も一覧Paneを閉じず、連続追加できるようにする。DefaultとAccountを先行して実動作させ、AccountIF、Field、Roomは各機能のデータ基盤に合わせて拡張する。

## Module 管理画面

Profile と MyPage では Field、ComputedField、Action、Interface、Layout を「Module」としてまとめる。Module一覧Paneの最上位分類は Element、Interface、Layout とし、ElementにはField、ComputedField、Actionを含める。その下で種別に応じた対象、検索・自作・編集中・保存済み・削除済みの順に絞り込み、SummaryListを表示する。「編集中」はDraftを持つInterfaceとLayoutだけに表示する。各Moduleの管理画面は、左側のSummaryListと右側のDetailPaneで構成する。SPでは既存のThreadPaneと同様に横スライドで切り替える。

ProfileのModule一覧では、Profile本人が作成したModuleを「自作」、Profile本人が保存したModuleを「保存済み」として切り替える。閲覧者自身の保存内容は表示しない。新規作成、検索、編集中、削除済みは表示しない。AccountInterfaceの実装機能を追加した段階で、実装済みAccountIFの分類も追加する。MyPageでは検索、自作、編集中、保存済み、削除済みを切り替え、自作のSummaryList先頭に新規作成を置く。

Interfaceの自作一覧には公開済みInterfaceを表示する。v1公開前の新規Draftと公開済みInterfaceの次回Version Draftは編集中一覧に表示する。

SummaryListのページネーションは共通UIとして扱い、標準表示数を20件とする。一覧固有の事情がある場合だけ内部的に表示数や取得方法を変更し、利用者が表示件数を設定する機能は設けない。Field検索フォーム、検索結果、ページ送りはModule管理、InterfaceへのField追加、片同義Field追加で共用する。

SummaryListのページネーションは共通UIとして扱い、標準表示数を20件とする。一覧固有の事情がある場合だけ内部的に表示数や取得方法を変更し、利用者が表示件数を設定する機能は設けない。Field検索フォーム、検索結果、ページ送りはModule管理、InterfaceへのField追加、片同義Field追加で共用する。

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

Thread作成時には、FieldをInterface経由だけでなくDirectFieldとして個別に追加できる。DirectFieldは作成時の入力を必須とし、追加時点の最新FieldVersionを固定する。DirectFieldとThreadIF内で使用される同一Fieldまたは片同義Fieldは、Thread内の一つのValueを共有する。

## Thread 作成時の適用

Thread作成画面では本文欄の下にDirectField、ThreadIF、Policyを置く。DirectFieldとThreadIFの追加操作ではそれぞれのSummaryListとDetailPaneをスライドインし、定義内容と入力欄を確認してから作成画面へ反映する。

「このFieldを追加する」または「このThreadIFを実装する」でThread作成画面へ戻る。同じFieldや片同義FieldはDirectFieldとThreadIFのどちらから実装されても同じValueを参照し、片方の入力変更を他方へ即時反映する。適用済みFieldとInterfaceは再度開いて値を編集できる。

## Thread Policy

Thread固有のPolicyは閲覧制限と書込制限を持つ。発見制限は廃止し、Threadがどこに現れるかはThreadPlacementと掲載先が決める。

閲覧できないThreadも掲載先の一覧、Map、検索、Profileには存在を表示する。本文とThreadPostはサーバー側で返さず、詳細では閲覧できないことを案内する。

## v0.5 に含めないもの

- InterfaceとFieldの更新を既存Threadへ適用するMigrationPlanの実動作
- Thread 作成後の Interface 追加、削除、Version 更新履歴
- 計算 Field、Action、通知、応募・承認機能
- ThreadPostInterface と ThreadPostLayout
- Tweet と Timeline
- 複数の保存リスト
