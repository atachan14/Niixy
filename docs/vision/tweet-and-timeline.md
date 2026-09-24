# Tweet と Timeline

## Tweet

Tweet は Thread へ属さない単独の呟きである。Thread を立てるほどではなく、回答や続きの会話を必要としない、または会話を煩わしく感じる場合の投稿を想定する。Tweet は作成した Account の資産として蓄積し、Timeline や NiiMap から発見できるようにする。

Tweet は Timeline、NiiMap の座標、または特定の掲載先なしで作成できる方向で検討する。別の Account が管理する Timeline へ投稿した場合も所有者は投稿者 Account のままとし、その Timeline から掲載を解除されても投稿者の SelfTimeline には残す。

Tweet に Interface や Layout を適用する可能性はある。具体的な分類、返信・参照・反応機能、文字数、複数行、掲載モデルは実装時に決める。初期方針では、Thread のような Response による会話構造を持たせず、Thread との役割を分ける。

## Timeline

Timeline は Tweet を収集・表示し、設定によっては直接の投稿先にもなる。既存 Timeline、Account、Interface、その他の条件を参照して Tweet を収集できるようにする。Timeline から別の Timeline を参照する場合は循環を禁止し、複数経路から同じ Tweet が得られても一度だけ表示する。

Timeline は Room 内に置くことができ、Timeline 自体を NiiMap の座標へ配置することもできる。Room は所属と権限を持つ活動場所、Timeline は Tweet を流す場所として区別する。Timeline への投稿権限だけでは Room のような所属関係を作らない。

Timeline では次の概念を分ける。

- 収集条件: どの Tweet を表示するか
- 閲覧制限: 誰が Timeline を閲覧できるか
- 投稿制限: 誰が Timeline へ直接 Tweet を投稿できるか
- 表示設定: 並び順や Layout など

全員が直接投稿できないカスタム Timeline も許可する。この場合は保存済みの収集条件として機能する。投稿を許可する Timeline は、収集した Tweet と直接投稿された Tweet の両方を表示できる。

## 標準 Timeline

Account は Self、Follow、Fav、Bad の標準 Timeline を持つ。標準 Timeline はカスタム Timeline と同じ収集・制限の仕組みで表現するが、意味を維持するため削除、収集条件、投稿制限を変更できない。MyPage での表示・非表示、並び順、公開範囲、表示設定の変更は別途検討する。

- SelfTimeline: 所有者が作成した全 Tweet を収集する。直接投稿は受け付けない。
- FollowTimeline: 所有者がフォローしている Account の Tweet を収集する。直接投稿は受け付けない。
- FavTimeline: 所有者が fav した Tweet を収集する。直接投稿は受け付けない。
- BadTimeline: 所有者が bad した Tweet を収集する。直接投稿は受け付けない。

掲載先を指定せず作成した Tweet も、作成者条件により SelfTimeline へ自動的に表示する。

## コンテンツと掲載先の関係

- Thread は ThreadPost をまとめる会話単位である。
- Timeline は Tweet を収集し、必要に応じて投稿先になる。
- Room は Thread と Timeline を置く所属・活動の場である。
- Book は `#1` を主コンテンツとする Thread のコレクションである。
- NiiMap は Room、Thread、Timeline、Tweet を座標から発見する入口である。

Tweet と Timeline の詳細は、ThreadInterface 基盤より後の実装時に要件を確定する。
