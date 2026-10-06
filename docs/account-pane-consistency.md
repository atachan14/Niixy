# AccountPage Paneの切替と表示統一

2026-10-06。基準はlocal `9011a00`（`209c6ef`にRoom Review / Muteを追加）。前workerの未commit変更を保持して継続した。修正とQAはlocalのみ。通常runserver、共有Neon、push、public反映はこの工程の対象外。既存のroot READMEとdocs/memo/inbox.mdには編集・stageを行わない。

## 復旧時の状態と原因

実ファイルのstatus / diff、AGENTS、関連docs、プロセスを確認した。Board / Peopleのnative化、People同段tab、余白、Module本文抽出、関連テストの未commit変更が残っていた。通常runserverはPID `12848 → 37380`、両方の起動日時は2026-10-06 10:49:44、listenerは127.0.0.1:8000 / PID37380の1つ。関連テストの進行中プロセスはなかった。標準サンドボックスのWin32_Process読取りはアクセス拒否だったが、同じ読み取りの正規承認付き実行は成功した。通常サーバーの起動・停止・restart・GETは行っていない。

従来、Thread / Response / Room / Applied / ModuleはAccountPageのWorkspace stageを直接切り替え、Board / Peopleだけが共通trail.pushで別Paneを追加していた。後者はprepareでAccount起点をoverviewにretainしてから共有Paneをalignするため、Currentの状態、offset変更のタイミング、Close / URL / historyの経路が異なっていた。末尾Pane数の修正だけではこの差が残る。

旧比較記録 `.artifacts/account-feature-switch/before/comparison.json` では、Board / Peopleのクリック直後のstageがoverview、offsetが360px / 390pxから0pxへ戻り、historyはreplaceStateを2回使っていた。標準Response / Moduleはクリック時のoffsetを保ち、pushStateを1回使う。画像も同ディレクトリに保持した。

## 最終変更

- AccountPage直下のBoard / Peopleを専用feature workspaceとnative stageに接続した。全機能ボタンの入口を`activateProfileFeature`へまとめ、後続共有Pane、古いrequest、詳細Pane、Moduleを整理し、feature / stage / Current / URLを更新する。Closeは共通`closePane`を使う。nested Accountは既存の共有trail経路を保つ。
- BackでThread / Responseへ戻る処理とoverviewへ戻る処理も通常のopen / close入口を通す。接続されたままのnative Paneでも古いfetchをabortし、保留応答やエラーでDOMを更新しない。Boardの深いURLから復元した場合は、子PaneのClose先をBoard一覧のURLとして保存する。
- Applied / People / Thread / Response / Room / 公開Module本文に共通のgutterを適用する。PCは20px、mobileは16px。Threadのタイトルも同じ内側余白を使う。Account用のscopeで上書きし、従来の汎用summary-header CSSは保つ。
- Moduleの共有PaneではHeaderを含む外側sectionではなく`[data-module-public]`本文を取得する。本人 / 他者 / Guest、native / nestedでHeaderは1つ。MyPage用CSSを読まない他者 / Guestにもsubtypeのhiddenと単一collection表示を適用する。
- Peopleは`Love → Hate → 実在する全AccountList名`の同段tab。Love / Hateは対象Accountが書いた既存の公開Review、Listは既存参照を表示する。閲覧者のMuteは表示filterのみで、Reviewや参照を削除しない。List名tab選択は子Paneを開かず、別の「Listの詳細・管理」から従来のList詳細を開く。改名・削除・追加結果と選択tabを再取得後も反映する。
- AccountPage内のBoard / Module / PeopleからList作成の入口を除去した。作成API、追加先選択Pane、既存List詳細での追加・管理、Account Board内のBoard作成は保持する。People Summaryの時刻は実際の保存データに合わせて「Review更新」または「追加」とする。

## QA

`C:/Users/user/Documents/Codex/2026-10-06/task-10/run_account_qa.py`は設定ロード前にDATABASE_URLをin-memory SQLiteに固定し、test argvとENGINE / NAMEのassertを行う。共有DBへ接続せず、各StaticLiveServerの空きポートとローカルEdge headlessを使用する。requirements-devの全依存関係は既に導入済みだった。

最初の関連QAは **55件成功 / 308.702秒**。AccountList / content List / Moduleの直接API・保存互換migration、root切替、List tab、Account起点、Board workflow、Module / List browser、標準smokeを含む。最終変更後は **14件成功 / 159.882秒**。Feature switch 4件、People / gutter 5件、Applied操作4件、標準smoke1件を実行した。両runを合わせた異なるテストは **60件**。重複再検証9件を別の成功件数として加算していない。

Backでnative featureの保留fetchが残る問題は、修正前の追加テスト1件で **12 subcaseすべて失敗**して再現した（本人 / 他者 / Guest × PC / mobile × Board / People）。実HTTP応答を受け取ってからJavaScriptへのdeliveryを保留し、BackでThreadに戻った後に解放すると旧本文が書き換わった。共通open / closeを通す修正後は **同じ12 subcaseすべて成功**。Forward後の再取得、stage、Current、Close先も確認した。

| 検証 | 最終結果・証拠 |
| --- | --- |
| 機能ボタンの即時stage / offset / history比較 | PC / mobile × Response / Module / Board / Peopleの8行。期待stage、Currentが有効、切替時offset維持、pushStateは各1回。`.artifacts/account-feature-switch/after/comparison.json` |
| 開閉motion | PC / mobile × Thread / Board / People × open / closeの12行。実transformの途中値とtransitionrun / transitionend、desktop360px / mobile390pxの移動量、scrollLeft 0、抑制classなし。`after/motion.json` |
| Close途中の再open / 同じボタン連打 / 全featureの相互切替 | PC / mobileで通過。root DOM保持、共有後続破棄、Current、Close、Back / Forward、直接URL / reloadを確認。 |
| roleとlayout | 本人 / 他者 / Guest × PC / mobile × native / nested × Thread / Applied / People / Moduleの48行。全内側余白は20px / 16px。Thread / Peopleタイトルの内側余白も同値。Module Header1つ、subtype1段、collection1面。`.artifacts/account-feature-layout/metrics.json`と同ディレクトリの画像 |
| Listと既存作成能力 | PeopleはLove / Hate / 実Listの順で25Listを表示、Muteでデータ保持、GET無書込、Picker作成API / owner認可。browserではList管理・改名・削除・選択tab維持・未送信入力・遅延子Pane・Guestと、ModuleのPicker作成・Board作成を確認。 |
| AppliedとMyPage回帰 | 追加 / 編集 / 解除、Field / AccountIF公開表示、空IFの保存制限、最新編集・pending回復、merge確認・遅延応答をPC / mobileで確認。 |
| AGENTSのbrowser_smoke.py CLI | 同じ隔離LiveServerに対するCLI実行。PC / mobile各17 checks、warning 0 / browser error 0。`.artifacts/browser-smoke/run.log` |
| 構文 / schema | 変更JavaScript3本のnode --check、変更PythonのAST parse、Django system check、makemigrations --check --dry-runは成功。migration追加なし。 |

最終smokeの`desktop-workspace.png` / `mobile-workspace.png` / `desktop.png` / `mobile.png`を目視確認した。現在のCLIの最終2画像はstandalone Room Threadの状態なので、AccountPageはfeature-layoutとfeature-switchのnative / nested画像で確認した。本人Threadの左余白、他者nested Moduleの単一Header、Guest mobileのApplied / Peopleの揃った余白と時刻表示も目視確認した。生成artifactは全てignoredのまま。

再現・実行ログは `task-10/account-qa-initial.log`、`task-10/history-before.log`、`task-10/account-qa-final.log`。`task-10/qa-evidence.json`に件数と代表数値を集約した。中断したGETに由来するserver側Broken pipe行はあるが、page error / console errorのassertは全て成功している。

## 残る仕様差・要確認事項

以下はコードと既存docsの調査結果。新しい仕様を決めて機能を追加してはいない。

| 差 | 根拠・影響 | 判定 / 次の確認 |
| --- | --- | --- |
| Thread / Responseのfav・bad・bookmarkだけ空の未実装tab | `templates/accounts/partials/thread_pane.html` / `response_pane.html`は未実装。Board / Moduleは保存済み評価、Peopleは保存済みReviewを表示する。 | 要件漏れ候補。評価API・モデル追加の合意が必要。今回の表示修正では実装しない。 |
| 公開ModuleにRoomIFの選択tabがない | `profile_module_lists.html`はAccountIF / ThreadIF / ResponseIFのみ。既存InterfaceモデルとList参照はroom kindを扱える。`module-list-integration.md`では従来の第1・第2段を維持する指示に従い未追加と記録。 | 到達できるモデルとUIが不一致。RoomIFの公開Module tabを追加するか要決定。 |
| ModuleのComputedField / Action / ThreadPostLayout / RoomLayoutは空枠 | 同テンプレートにはtabがあるが、`module-list-integration.md`では対応モデル未実装と記録。 | 既知の保留機能。空tabを残すか、未実装を選択前に示すか要決定。 |
| 分類tab選択のURL保存と子Pane整理が機能ごとに異なる | Peopleはpeople_tabとprepare、Boardはtab / collection、Moduleはtype / subtype / collection、Roomはroom_tabを使う。Thread / ResponseはbindTabsによる表示変更だけ。Board / Moduleの分類切替にもPeopleのprepareと同じ子Pane整理はない。 | 根拠が弱い挙動差。root機能ボタンは今回統一したが、分類tabの履歴・詳細Pane維持契約は別途決める必要がある。 |
| nested Thread / Responseのページ送り取得先 | `workspace_trail.js`のpagination処理はhrefをそのままfetchする。Thread / Response partialのhrefはqueryだけ。native Accountは専用pane URLにqueryを付けて取得する。 | バグ候補（コード調査、今回の複数ページnested実機再現は未実施）。canonical AccountPage全体をPaneへ挿入しないか集中QAが必要。 |
| 一覧の表示量に上限の差がある | Peopleは指定に従い全List名とinline参照を返す。Board / Moduleも全List分類を返す一方、Thread / Response / RoomやList詳細・Pickerはpaginationを使う。 | 多数List / 参照での表示・性能方針が未確定。実在Listを隠す仕様や上限は作っていない。 |

Profile / Appliedを本人も公開閲覧に限定し、編集はMyPageで行う差、Account配下Boardの本人向け管理、Guestの書込み制限、閲覧不可対象の表示は既存要件に根拠があるため統一対象にしていない。Responseが投稿本文を示しThreadがThread Summaryを示す差も活動の種類に由来する。

共有Neonの実データ・並行transaction、通常server / production、Edge以外は未検証。Python / template変更を含むため通常環境への反映にはAGENTSに従う明示restartとcache bypassが必要だが、現在の許可範囲では保留する。新しいmigrationはない。
