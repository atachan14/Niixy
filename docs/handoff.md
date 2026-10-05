# 開発引き継ぎメモ

更新日: 2026-10-05
確認基準: `27d806b`（v0.9完了）。このメモ作成前の作業ツリーはクリーン。

仕様の大枠とv0.9完了は既にdocsへ反映済み。このメモは、次のAIが作業を再開するための実装・検証上の補足であり、仕様書の代わりではない。

## 最初に確認するもの

1. [AGENTS.md](../AGENTS.md): 開発サーバーの起動・再起動とブラウザ検証のルール。
2. `git status`と直近の差分: このメモ以後の変更を保持し、過去の会話時点へ戻さない。
3. [Roadmap](roadmap.md)、[v0.9要件](v0.9/requirements.md)、[Vision](vision/README.md)、[決定記録](vision/decisions.md)。

`docs/memo/inbox.md`はユーザー専用。明示的な方針変更がない限り、読み取り・編集・削除・ステージングをしない。docs配下の一括検索や一括ステージングにも注意する。

## 現在地

- `dd4cc3d`: Board投稿権限とAccount起点のPane遷移の修正。
- `cc58188`: Workspace共通の起点保持・後続置換、補助Pane、遅い応答の対策、展開アニメーションの修正とブラウザ回帰テスト。
- `27d806b`: v0.9完了のdocs更新。

ユーザーは直近のWorkspace修正を画面で確認済み。現在の依頼は引き継ぎメモ作成であり、次Versionの実装範囲はまだ指示されていない。RoomPolicy、ThreadPolicyの共通基盤への移行、Templateなどの候補は既存docsを参照し、実装順を勝手に確定しない。

## Workspaceの実装入口

「起点Pane以前を保持し、後続Paneを閉じて遷移先へ置き換える」という仕様自体は[決定記録の2026-10-05項](vision/decisions.md)とv0.9要件に反映済み。追加実装では以下の既存処理を使う。

| ファイル | 役割と注意点 |
| --- | --- |
| `static/shared/workspace_trail.js` | 動的なPaneの追加・後続破棄・Close・通信処理。`prepare(source)`と`push({after: origin, ...})`で起点を扱う。公開APIの`open(url, source)`にも操作元を渡せる。 |
| `templates/shared/ui_script.html` | 既存Page側の`NiixyUI.createWorkspace`。`retain(source)`、`onRetain`、`track.niixyWorkspace`で動的Paneの共通処理と接続する。 |
| `static/accounts/account.js`、`static/rooms/room.js`、`static/events/map.js` | 各Page固有のPane・キャッシュ・通信世代の整理。共通化後もこれらの制御は残っている。全画面が単一レンダラーへ移行済みという意味ではない。 |
| `static/accounts/account_conditions.js`、`static/rooms/forms.js` | Account条件・Field/Interface選択などの補助Pane。呼び出し元の破棄に合わせて後片付けし、遅い応答で再表示しない。 |
| `static/events/styles.css` | Workspaceや補助Paneの共通スタイル。ファイル名がeventsでも他Pageが利用する。 |

- 遷移先を単にtrack末尾へappendすると、以前の「途中Paneから開いても後続が残る」問題が再発する。操作元を共通処理へ渡す。
- `fetchInto`はAbortControllerだけでなく、Paneの接続状態と現在のrequestも検査する。通信完了直後に閉じた場合や、同じPaneの再取得競合にも必要なため、この検査を省略しない。
- 遅延した位置合わせも世代で無効化する。通常の展開で`align(entry, true)`を使うとアニメーションを消してしまうため、起点置換だからという理由では即時位置合わせにしない。
- Account条件のクリックが呼び出し元Pageのハンドラーまで二重に届かないこと、補助Paneを閉じた後に別の呼び出し元で再表示できることも確認する。
- Thread詳細の対象Responseへのスクロールは、Pane内の縦スクロールに限定する。`scrollIntoView()`でWorkspace全体の横スクロールが発生しないよう注意する。
- Room経由のThread URLではBoard・Collectionの文脈も保持する。再読み込み時の復元に必要。

## 検証方法

通常のDjangoテストとWorkspaceブラウザ回帰テストは別コマンド。

```powershell
.\.venv\Scripts\python.exe manage.py test --noinput
.\.venv\Scripts\python.exe manage.py test scripts.workspace_browser_tests --noinput
```

後者は隔離SQLiteへテストデータを作り、空きポートの一時テストサーバーとPlaywrightのEdgeでPC・スマートフォンを検証する。普段の8000番runserverを追加起動する必要はない。スクリーンショットは`.artifacts/workspace-regression/`へ出力する。

既存開発サーバーに対するスモークテストは、AGENTS.mdに従ってサーバーを確認したうえで実行する。

```powershell
.\.venv\Scripts\python.exe scripts\browser_smoke.py
```

- 開発用依存関係は`requirements-dev.txt`。ブラウザはローカルのMicrosoft Edgeを使う。
- 地図ライブラリは外部取得する。サンドボックスで`ERR_NETWORK_ACCESS_DENIED`、続いて`geolonia is not defined`が出た場合、サーバーの多重起動で解決しようとしない。ネットワーク実行権限を確認する。
- `config/settings.py`は`manage.py test`ではSQLiteを選ぶが、通常起動は`DATABASE_URL`があればそのDBを使う。localhostだからローカルDBとは限らない。通常の`manage.py shell`などで検証データを作らない。
- 直近の修正・検証では共有DBへ投稿・設定変更をしていない。次の作業でもテストは隔離し、共有DBへのmigrationや更新は対象と指示を別途確認する。
- v0.9完了時の成功記録は通常テスト138件、隔離ブラウザテスト、既存サーバー向けスモークテスト。詳しい確認範囲・限界は[v0.9要件の完了確認](v0.9/requirements.md)にある。今回のメモ作成では再実行していない。

## 保留と文書上の注意

- Thread詳細の座標行が巨大化する現象は、前の引き継ぎ時点では再現せず調査保留。今回の確認でも新たな再現報告はない。確定済みの原因・修正待ちタスクとして扱わず、再発時に導線、画面幅、スクロール位置、DOMを記録する。
- v0.9要件の対象外項目に「Policy編集画面からのANDグループ作成」が残っている。一方、現在の共通Account条件UIには複数選択から`addGroup(activeTarget, selectedConditions())`を呼ぶ処理があり、BoardPolicyもこのUIを使用している。専用のPolicy画面を指すのか、古い対象外記述なのかは次回Policy作業時に照合する。今回、この点の動作確認や仕様変更はしていない。
- `docs/structure.md`のディレクトリ一覧やRoadmapのFuture欄には古い記述が残る。FutureにBoardPolicyがあることだけを理由に、v0.9の実装を未着手と判断しない。Version要件の完了範囲、最新の決定記録、実コードを照合する。

このメモ作成ではアプリコード・DB・開発サーバーを変更せず、commit・pushも行っていない。
