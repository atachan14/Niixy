# AccountLayout初期実装

Version: v0.16
Base: `28e9de67bf6d65149467fc9345fd183a18c34871`（v0.14版更新基盤 / v0.15 UI・NiiMap）
Status: 実装・隔離SQLite / Edge検証完了。v0.16公開・共有Neon migration・通常runserver切替はユーザー承認済み。以下に公開前の記録と公開工程を残す。

## 今回の終点

MyPageのModule一覧 → Layout / AccountからDraftを作り、RequireField / RequireAccountIFを先に選ぶ。Require範囲のFieldだけをItemに追加し、変数名を付ける。RequireAccountIF内のFieldもItem候補になるため、同じFieldのRequireを別に追加する必要はない。

HTML / CSS / プレビューの3タブで編集する。プレビューは本人の現在のApplied値を使い、未適用Fieldは一時的なサンプル値を表示する。サンプルはDBへ保存しない。内容と最新版依存をプレビュー確認して公開し、公開版詳細のRequireから定義確認Paneを開いて不足Modを適用・更新してからLayoutを適用する。RequireAccountIFはそのIFの実際の適用が必要で、Fieldだけでは代替できない。

AccountLayoutはRoomLayoutとは独立した型。Accountの適用はOneToOneで最大1つ。公開版・Require・Itemは不変で、適用した公開版を固定する。編集は別Draftを作り、次の公開版を発行する。Layout切替・取り外しでField / IF / Valueは削除しない。未適用時のAccountPage下部Profileは既存の「未実装」表示を維持する。AppliedのField / AccountIF一覧とModule定義ライブラリの役割は変えない。

本人の編集・適用はMyPageで行う。公開AccountPageのModule詳細は、本人も含め閲覧用。Guestは定義・適用済みProfileを閲覧するだけで、Draftを読めず、変更APIを使えない。変更APIはログイン・CSRF・URLの対象Account本人を検査し、payloadの他Account指定を受け入れない。

## 表示言語と安全境界

- bindingはHTML本文テキスト中の `{{alias.name}}` / `{{alias.value}}` だけ。変数名は英字から始まる英数字・アンダースコア、32文字以内。重複alias・未定義参照・任意式・Django template構文をvalidationで拒否する。属性 / CSS内では使えない。Field名・現在値を必ずtextescapeし、Django template engineやuser JavaScriptで評価しない。
- HTMLは標準ライブラリHTMLParserで解析し、許可タグ・属性だけを新しく再構築する。div / section / article / span / p / 見出し / 強調 / リスト / br / hrなどと、class / title / lang / aria-labelを許可する。script / event属性 / style属性 / URL属性 / link / img / svg / form / iframe / embed / object / meta / base / コメント / 宣言は拒否。タグ対応、量、深さも検証する。入力をregex置換して通すsanitizeではない。
- CSSは公式PyPIの `tinycss2==1.5.1` で解析し、selector・property・value・function・nested ruleをallowlistで検証する。class / 要素名 / 子孫 / `>` / カンマselector、flex / grid、文字・背景・border色、余白、角丸、幅、高さ、generic fontなどを許可する。値は非負・上限付きpx/em/rem/%、grid用fr、列数上限付きrepeat/minmaxなど。色はCSS Color parserでも検証する。
- @mediaはmin-width / max-widthの160〜2000pxに限定し、3段以内。@import / @font-face / URL / var / attr / expression / calc / pseudo / 属性selector / ID selector / 任意CSS入れ子 / custom property / position / transform / z-index / overflow / 負の余白 / viewport単位 / !importantは拒否する。文字列・コメントは今回は扱わず、閉じ括弧不正はCSS parserのEOF補完で黙って修復せずvalidationにする。
- HTMLは20,000文字・300要素・20段、CSSは10,000文字・100 rule、Requireは種類ごと32件、Itemは32件、詳細は2,000文字。JSON requestは300KB以内。parser例外も入力エラーとして扱い、途中出力を表示しない。
- HTMLのbinding参照はname / valueを合算して128個以内。プレビュー・公開validation共通で検査する。renderer document全体はescape後のUTF-8で256KiB以内、各bindingの表示は同じ基準で64KiB以内。巨大値は文字・HTML entityの途中で切らず、末尾へ「表示上限のため省略」を付ける。HTML/CSS、通常テキスト、全閉じタグと各参照の省略表示を先に予約し、総量が不足した後続参照は残量に応じたprefixまたは省略表示だけにする。構造自体が予約上限を超える入力は公開前にvalidationで拒否する。全Layoutの破棄・default切替は行わず、保存値・timestampは変更しない。巨大値を一括escape・連結してから切る処理もしない。この表示省略はユーザー承認済み。

公開Profileとプレビューは同じrendererを使う。サーバー出力はtrusted templateに包み、Niixy自身の静的JSがShadow DOMへmountする。全user selectorに毎render異なるroot prefixを付ける。trusted hostは `contain: layout style paint` / `isolation: isolate`、size containmentと固定heightは使わず自然高さにする。長文は既存のAccount概要Paneのscrollで末尾まで読め、Profile内部へ別scrollを強制しない。

Shadow DOM / containmentはscriptセキュリティ境界ではない。active contentと外部リクエストを止める根拠はサーバーのHTML/CSS allowlistとescapeであり、これを必ず通す。user CSSでhostのcontainmentや位置・overflow設定は変更できない。iframeのallow-scripts / allow-same-origin追加やinline user scriptを使わない。主ページのCSPを全面変更する実装は今回追加していない。

初期の固定32rem sandbox iframe案は二重scroll制約により採用しない。ユーザーが自然高さの限定HTML/CSS方式を承認した。JS無効時はProfileに有効化案内を表示する。SSRの完成Profileや追加ブラウザ互換性は今回対象外。

根拠: [tinycss2公式ドキュメント](https://doc.courtbouillon.org/tinycss2/stable/)はparserがCSS property/valueの意味を検証しないと明記しているため、独自allowlistを併用する。[Shadow DOM](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_shadow_DOM)と[contain](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/contain)の境界に合わせ、selector隔離と描画containmentを補助防御として使う。

## 版・依存・凍結

作成・公開・新規適用・編集は最新版依存に揃える。公開前tokenは本人・全入力・参照最新版・Item版に結び付け、有効10分。入力や公開依存が変われば再プレビューを要求する。適用APIは詳細で見たLayout版も検査し、後から新しい版が公開された場合に黙って別版を適用しない。

既存LayoutのField名・構成は固定版、表示Valueは現在のAccount共有値を参照する。依存Field更新・IF凍結・IF復帰待ちが起きても既存Profileを維持し、全体非表示やdefaultへの切替を行わない。必要Modの版が揃っていることと、表示を続けることは別。GETで復帰・値変更などの書込をしない。

使用中のRequireAccountIFの取り外し、および表示に必要なFieldを失う最後のMod参照の取り外しは、先にLayoutを変更・取り外すよう案内する。別のMod参照がFieldを保持する場合はdirect Field取り外しを許可する。Layoutの古い依存版・validationをField / IFの値更新制約に混ぜないため、凍結Layoutは依存更新を永遠に妨げない。

IFの自動復帰はv0.14基盤の無変更・追加入力不要条件をそのまま使う。不足FieldをLayout側から勝手に追加しない。Layout自身の公開版・適用版は自動で最新版に差し替えない。依存最新版へ対応した新Layout版が必要な場合は作者のDraft公開と本人の再適用で解決する。

## migration・公開順

`interfaces/0009_account_layout.py` は0008を前提とし、AccountLayout / Draft / Version / RequireField / RequireIF / Item / Applicationの7テーブルとFK・一意制約を追加する。既存AccountFieldBinding、Value、IF適用、Threadの構造・値・timestamp・版参照を変えず、Layoutを自動適用しない。Djangoの通常post_migrateによる7モデル分のcontent type・既定permission追加も想定する。共有Neonへの適用は下記の公開工程で確認する。

1. ユーザーがv0.16として今回のコード・テスト・docs・migrationを公開GitHub `atachan14/Niixy` の既存masterへcommit・pushし、DB反映と通常runserver再起動まで進めることを承認した。既存checkpoint `e9f12eb` / `4634d5f`を保持し、通常commit・pushだけを使う。inbox / root README / secret / backup / private artifactsはstageしない。
2. 共有Neonの0008適用状況と対象を確認し、必要な既存データのbackupをprivate / gitignore内に保持する。旧コードと共存できる追加migrationとして扱う。
3. 承認された公開commitをpushし、既存Vercel production buildのmigrateで0009を適用する。手動migrationを重ねない。buildと公開SHA、migration記録・追加テーブル・既存値保持を確認する。
4. 通常runserverの切替は親がAGENTS.mdどおりPythonのPID / 親PID / 実行path / commandline / start timeと8000 listenerを確認し、検証済みNiixy pairだけ停止する。process・listener両方が消えてから通常コマンドで1組起動する。今回のPython / template変更ではrestartが必要。
5. updated asset markerと代表GETを確認し、共有DBにはテストデータを書かずread-onlyでPC/mobileを確認する。

新コードは表示・Moduleで追加テーブルを読むので、0009適用前に公開切替・通常restartをしない。rollbackではコードを旧版に戻して追加テーブルと公開Versionを保持する方式を優先する。公開Layoutが作られた後に0009を逆適用するとそれらを削除するため、migration rollbackを自動で行わない。

## 検証と後続

SQLiteでHTML/CSS攻撃、量・深さ・構文、binding、owner / CSRF、IF実適用要件、公開不変性、適用版固定、切替時のValue保持、依存凍結と現在値表示、guardと依存更新、stale previewを直接検証する。0008→0009のmigrationでは既存Field定義 / Version / Value / Binding / direct適用の全行保持とLayout自動生成なしを確認する。

Edgeの隔離LiveServerでPC1280px / mobile390pxの最小一周と、長文末尾、横溢れ、page / console error、外部requestなしを確認する。既存 `scripts/browser_smoke.py` も隔離LiveServerへ実行する。画像は `.artifacts/account-layout/` / `.artifacts/browser-smoke/` に保管しuntrackedのままにする。

2026-10-05の実測: 新direct12件、追加migration保持1件、PC/mobile Layout browser1件、既存isolated smoke1件が成功。既存Interface/Account版基盤86件は85件成功と旧asset markerの個数assert1件を検出し、Applied JSそのもののmarkerを検査する形へ修正した当該1件も再実行成功。最後の変更箇所再実行（当該既存1件 + 新direct12件 + Layout browser1件）は14件成功。Draft保存/reload、Guest Module/Require readonly、Shadow DOM内外の文字色隔離を追加したbrowser再実行も成功。全領域testは行っていない。`makemigrations --check --dry-run` は追加差分なし、保護対象を除外した `git diff --check` も成功。

表示上限の承認後、巨大値・escape増幅・反復参照・UTF-8/entity境界・総量到達後の閉じ構造/末尾/省略表示・CSS prefix出力量・過大な静的構造の拒否・128参照のAPI/公開validation・DB値/timestamp不変を6件追加した。追補の最終再実行はdirect18件 + PC/mobile Layout browser1件の19件が成功。desktop ProfileとmobileのProfile末尾画像も再確認した。制限以下の長文は従来どおり自然高さで表示する。

公開前の通常serverはread-onlyにPID/親PID/path/command/starttimeを確認し、venv launcher30324 → base Python37964の1組、127.0.0.1:8000 listener owning37964を確認した。隔離実装工程では停止・追加起動・restartを行わず、0009も共有Neon未適用のまま維持した。公開工程では再度process・listenerを確認して上記手順で切り替える。inboxは未読・未編集・stage除外、root READMEも不変更。

RoomLayout、AccountIFItem、自由参照パーツ、Timeline / Boardパーツ、defaultLayout再構築、ThreadPost表示名・値Snapshot、Threadの適用済み版編集、保存ライブラリ、Layout削除 / copy、高度検索は対象外。今回はAccountLayoutの最小一周で区切り、便利機能や装飾を拡充しない。既存Profile幅を維持する。将来、PC最大幅を使う紹介文・Timeline・Boardの3列案はページ構造の改善時に別途検討する。

公開前の隔離QAには共有Neon / production / 通常serverを含めず、それらは承認された公開工程で確認する。実PostgreSQLの並行publish・apply、Edge以外のbrowser、JS無効時の完成表示、実際の大量定義は未検証。全領域の広域反復は今回後回しとする。
