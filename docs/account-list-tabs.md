# AccountPage People / InterfaceList のタブ訂正

> 最新訂正: 独立BoardList / InterfaceList入口とModuleの固定検索・保存済み枠を撤去し、Board / Module内の各List Tabへ統合。以下の旧InterfaceList配置記録は履歴。People仕様は維持。最新仕様・非破壊migration・QAは[module-list-integration.md](module-list-integration.md)を参照。

Status: ローカル修正。基準 `590852c18a4b9668f4c038c72779d1d5859b074e` を保持し、その上に追加。公開・push・通常server restart・共有Neon書込みを行わない。Version番号は未割当。

## 訂正した要件と履歴

2026-10-06 JST のユーザー確認: People / InterfaceList の中身だけを修正する。以前の固定タブを残し、保存 / bookmark に相当する枠をユーザーが作る名前付きListのタブ・導線にする。List専用一覧への置換は誤った解釈だった。List本体、参照、URL共有、公開評価、認可を保持する。

`829f8b0^` の AccountPage People は左から **AccountListA / AccountListB / Love / Hate**。全て未実装だった。A/Bは仮のList枠であり、実ユーザーListの導線へ置き換える。People先頭のAccountListタブで一覧・作成、続いて実List名のタブで既存詳細を右Paneへ開き、その後の **Love / Hate** を元の未実装状態で残す。Love / Hateをfav / badへ改名せず、Reviewから新しい評価一覧を作らない。親工程でこの解釈を確認済み。

同じ版の **fav / bad / bookmark** は Thread / Response 内にある。今回のPeopleに保存とbookmarkの固定タブが複数存在した事実はなく、Thread / Responseのそれらは変更しない。

InterfaceListボタンは `436aa0a` で初追加されたため、「以前のInterfaceList」に完全一致するAccountPageの実装は存在しない。旧 Module の公開AccountPageは Element / Interface / Layout → subtype → **自作 / 保存済み**。MyPageには **検索 / 自作 / 編集中 / 保存済み / 削除済み** があり、Interface検索は未実装だった。さらに `fc439cb^` のMyPage Interface一覧は **作成 / 編集中 / 保存 / 削除済み**。公開AccountPageへ編集中や削除済みを移さない。

今回のInterfaceList内は **検索 / 自作 / 保存済み / 実List名…** とし、自作を初期選択する。**自作**は既存の公開済みInterface参照を使う復元部分、**検索**はユーザーの明示した希望に合わせて補う旧文言の未実装枠。検索機能は開発しない。保存済みはユーザーList一覧・作成へ接続し、実List名タブは既存List詳細を右Paneへ開く。別のModuleボタン・Element / Interface / Layout・MyPage・適用機能は変更しない。

List一覧ページ分割は従来どおり10件単位。実List名タブは表示中ページに対応し、ページ移動で残りのListを選べる。保存済みと実List名は同じデータへの一覧/直接導線であり、別の固定保存データを追加しない。

## 保持する動作と検証境界

既存List APIと共通Workspaceを使い、起点以降だけ右側を置換する。固定タブへの切替も起点右側を閉じ、親DOMと入力を残す。名前・参照件数・削除を背後の一覧と名前タブへ反映する。List入力の同一Workspace保持、結果不明送信のguard、遅いGETの破棄、URLからの直接復元は既存実装を保持する。

変更は表示・公開済み自作一覧・タブ接続だけ。モデル、migration、認可、評価、List書込みAPIは不変更。共有DBのデータ保持を実DBで書込検証せず、隔離SQLiteで直接影響と認可を検証する。Python / template変更のため手元の通常server反映にはAGENTSの明示的restartが必要。今回の工程では必要性の報告までとし、通常serverを操作しない。

## QA結果（2026-10-06 JST）

`scripts/account_list_tabs_tests.py` に旧固定タブ・公開版だけの自作一覧・GET無書込・owner formの直接3件と、EdgeのPC1280×720 / mobile390×844（touch / is_mobile）の操作1件を追加。既存 `accounts.tests_lists` / `accounts.tests_content_lists` の34件、および `WorkspaceBrowserTests.test_browser_smoke_cli` の隔離smoke 1件と合わせて、最終 **39件成功 / 66.169秒**。Django system checkは問題0。

操作QAは2 viewport × People / InterfaceListの4 subcase。固定タブ切替、名前タブから既存List選択、URL参照追加、List作成・改名・削除と背後タブ更新、起点右側置換、Closeと親DOM保持、入力保持、取得済み応答の保留→Close→解放による遅いGETの破棄、既存Summaryからの選択、Account起点のPeople→InterfaceList右置換、公開Interface詳細、Listの正規URLからowner / Guest復元を確認。新しい検索や評価一覧は実装・検証対象にしない。参照解除・owner / 他owner / Guest / CSRF・不正URL・Draft非公開・評価の保持は既存直接API suiteで確認。

初回は保存後の管理detailsをテストが開き直さずdesktopの削除クリックが失敗し、その未削除fixtureの残りでmobileのタブ数assertも失敗。管理欄の再展開と保存済み詳細の待機を修正した。また画像確認で削除後の選択タブが横scroll外に隠れることを検出し、タブ行だけのscroll補正と選択タブの表示範囲assertを追加。最終runは全件成功。page error / console errorは4 subcaseとも0、smokeは各viewport17 checks、warning / browser error 0。

`.artifacts/account-list-tabs/` のPC/mobile・固定タブ / List詳細8画像、`.artifacts/browser-smoke/` の `desktop-workspace.png` / `mobile-workspace.png` / `desktop.png` / `mobile.png` を目視確認。smoke最終2画像は既存fixtureのstandalone Room Thread状態。生成物はgitignore内、stageしない。ログとSQLite ENGINE / `:memory:`を実行前assertするrunnerは `C:/Users/user/Documents/Codex/2026-10-06/task-6/` の `tabs-qa-final.log` / `run_tabs_qa.py`。初回と再実行ログも同workspaceへ保持する。

再実行は隔離Django test経由だけで行う（通常serverは不要）。

```powershell
.\.venv\Scripts\python.exe -B manage.py test scripts.account_list_tabs_tests accounts.tests_lists accounts.tests_content_lists scripts.workspace_browser_tests.WorkspaceBrowserTests.test_browser_smoke_cli --noinput --verbosity 1
```

未検証: 共有PostgreSQL実データ・並行transaction、通常server / productionのGET、全Django / 全browser suite、追加viewport / Edge以外。今回のGET無書込・データ保持は隔離fixtureの結果であり、共有DB再確認の代わりにしない。

手元のファイル反映は済み。通常serverは起動・停止・restart・GETを行っていない。Python / template変更を含むため、親工程でAGENTSに従って明示restartした後、既存asset markerのままなのでブラウザcacheをbypassして確認する。共有migrationやschema rollbackは不要。公開・pushは別工程。`590852c`の既存修正を保全し、今回のcheckpointはその直接の子として別commitへ保存する。
