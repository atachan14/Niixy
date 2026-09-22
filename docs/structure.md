# Project Structure

## Purpose

このDocumentでは、Niixy Repository全体のDirectory StructureとNaming Policyを管理する。

全Fileの一覧を管理することを目的としない。

「どの種類のDataやCodeを、どこが所有するか」を明確にすることを目的とする。

---

## Naming Policy

### External Documents

Repositoryを外部から閲覧する利用者を主な対象とする標準Documentは、大文字のFile Nameを使用する。

Examples:

* README.md
* LICENSE
* CONTRIBUTING.md

### Internal Files

Niixyの開発内部で使用するFileおよびDirectoryは、原則として小文字を使用する。

Examples:

* docs/
* concept.md
* roadmap.md
* structure.md
* vision/
* requirements.md

ただし、Programming Language、Framework、Tool等に一般的なNaming Conventionが存在する場合は、それを優先する。

---

## Current Structure

```text
manage.py
requirements.txt

config/
├─ settings.py
├─ urls.py
├─ asgi.py
└─ wsgi.py

events/
├─ admin.py
├─ apps.py
├─ forms.py
├─ models.py
├─ tests.py
├─ urls.py
├─ views.py
└─ migrations/

templates/
└─ events/

static/
└─ events/

docs/
├─ concept.md
├─ roadmap.md
├─ structure.md
│
├─ vision/
│  ├─ README.md
│  ├─ content-model.md
│  ├─ room-and-niimap.md
│  ├─ access-policy.md
│  ├─ interfaces.md
│  ├─ account-and-history.md
│  ├─ presentation.md
│  ├─ decisions.md
│  └─ archive/
│     ├─ niimap.md
│     ├─ community.md
│     ├─ interface.md
│     ├─ account.md
│     └─ guest.md
│
├─ memo/
│  └─ inbox.md
│
├─ v0.1/
   ├─ requirements.md
   ├─ decisions.md
   └─ backlog.md

├─ v0.2/
│  ├─ requirements.md
│  ├─ decisions.md
│  └─ backlog.md
│
├─ v0.3/
│  └─ requirements.md
│
└─ v0.4/
   └─ requirements.md
```

---

## docs/

ProjectのConcept、Vision、Requirements、Decision等のDocumentを管理する。

### concept.md

Niixy全体のConceptと基本思想を管理する。

### roadmap.md

今後実装する領域と、大まかなDevelopment Directionを管理する。

### structure.md

Repository StructureとNaming Policyを管理する。

### vision/

`README.md` is the entry point for the canonical Niixy Vision. The authoritative documents are `content-model.md`, `room-and-niimap.md`, `access-policy.md`, `interfaces.md`, `account-and-history.md`, `presentation.md`, and `decisions.md`. Older Event-centered vision files remain historical references only.

将来的に実現したいConceptやServiceごとのVisionを管理する。

現在のVersionで実装することを保証するものではない。

### memo/

未整理のIdeaや検討事項を一時的に記録する。

ここに書かれた内容はSpecificationではない。

### v0.x/

各Versionの実装対象に関するDocumentを管理する。

#### requirements.md

そのVersionを完成させるために必要なRequirementsを管理する。

#### decisions.md

ArchitectureやProduct Design等の重要なDecisionと、そのReasonを記録する。

#### backlog.md

そのVersionで検討可能なFeature、Improvement、Bug、Technical Task等を管理する。

Backlogに存在すること自体は、そのVersionでの実装を必須としない。

---

## Source Directories

### config/

Django Project全体のSettings、Root URLConf、ASGI / WSGI Entry Pointを管理する。

### events/

NiiMap v0.1のEvent Model、View、Form、URL、Admin、Testを管理するDjango Application。

### templates/

Django Templateを管理する。

### static/

CSS、JavaScript等のStatic Assetsを管理する。

---

## Adding Directories

新しいTop-Level Directoryや主要なClassificationを追加する場合は、既存Directoryの責務と重複しないか確認する。

新しいDirectoryには明確なResponsibilityを持たせる。

単一Fileのためだけに不要なDirectoryを追加しない。

Project Structureに影響する重要な変更を行った場合は、このDocumentを更新する。

通常のSource File追加など、Structure Policyに影響しない変更については更新を必要としない。
