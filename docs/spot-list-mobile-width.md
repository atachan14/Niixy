# スマホSpot一覧幅の回帰修正

基準: `f0ec1d8864da13856c76c400be53b0786bcbfeed`（親工程でlocal/remote/public一致と引継ぎ）。2026-10-06のローカル修正。新Version、migration、asset markerの変更はない。公開と通常server restartは行っていない。

## 原因と最小変更

既存のスマホ仕様は地図の下に画面幅のSpot一覧を置く（`docs/v0.3/requirements.md`）。`bf7039c`で追加された`.thread-track > .thread-map-list-pane > .thread-list-pane`の`width: var(--list-width)`（360px）が、後方のスマホ用`.thread-list-pane { width: 100vw; }`より詳細度が高く、初期画面から上書きしていた。最近のborder/sticky/focus修正に新たな原因は見つからなかった。

修正前390px画面では一覧360px・右空白30px。375/430/768/780pxでも一覧360pxで再現し、320pxでは一覧がrootの幅を超えた。360px画面とPCでは幅の不一致が現れず、既存390px QAもSpot幅自体はassertしていなかった。

変更は`static/events/styles.css`のスマホルールのセレクター1行のみ。共通ルールと同じ詳細度にして、既存の100vw指定を適用する。PC固定幅、gutter、border、sticky、Paneの幅種類、ナビゲーションコードは変更していない。

## 隔離ブラウザーQA

`scripts/spot_width_browser_tests.py`を追加。SQLite `:memory:`、SharedSQLiteStaticFilesHandler、StaticLiveServerTestCaseの一時port、ローカルEdge headlessで検証する。共有DBと通常8000 serverを使用しない。

正式コマンド: `.\.venv\Scripts\python.exe manage.py test scripts.spot_width_browser_tests`。

- mobile 320/360/375/390/430/768/780 × height 844、desktop 781/1280 × height 720。
- 初期表示、Room→Board一覧→Close、Room URL復元→Close、history戻る/進む、reload、Thread URL復元→Close。各復元状態で一覧幅・地図幅・document幅・一覧内部横scroll・root.scrollLeft・Summary端を確認し画像保存。Room Closeではroot DOM同一性とスマホscrollTopも確認する。
- 直接Thread復元では詳細Paneの幅と画面右端を確認。各contextでJS pageerrorとconsole errorを失敗扱いにする。
- 既存`WorkspaceBrowserTests`の2 test、`ModuleSelectorBrowserTests`の4 testを継承し、BASE_DIRの画像出力先だけをtask専用に向けたハーネスで実行。起点からの右側置換、補助Pane、Close、遅延応答、reduced-motion、focus native scrollを含む。指定`browser_smoke.py --base-url <isolated-LiveServer> --output-dir <task専用出力>`も実行。
- 新規contextでCSSを再取得し、PC／mobileの初期Spot画像と指定desktop-workspace/mobile-workspace画像を目視確認。

結果: 正式Spot回帰 **1 test pass（9 viewport × 6 root復元状態＝54測定）**、既存Workspace/selector **6 test pass**。指定smokeはdesktop/mobileともwarnings・browser_errorsが空。代表PC/mobileのSpot、Workspace、補助Pane画像を目視確認した。320pxを含め、修正後のfixtureではdocument幅は指定viewportと一致し、rootの横overflowもない。

既存画像を上書きしないため、今回の証跡は `C:\Users\user\Documents\Codex\2026-10-06\task-7\spot-width-evidence\`（before/final）、`spot-impact-evidence\.artifacts\`、同taskのQAログに保存した。テストdefaultの新規出力先は未追跡`.artifacts/spot-width/after/`。

## 反映境界

CSS内容のみの変更なので通常serverのrestartは不要。手元確認ではbrowser cacheを迂回して再読込する。通常serverへの今回のGET確認と本番公開は親工程に保留した。root README、inbox、秘密、既存artifactに変更・stageを行っていない。RoomReview/RoomMuteは別工程で、今回実装していない。
