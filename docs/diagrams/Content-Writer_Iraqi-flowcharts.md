# Content-Writer_Iraqi — repository flowcharts and database structure

Snapshot: `main` at `fceebf5` · 16 November 2026 (Baghdad).

## How to use these files

- This `.md` file contains all three diagrams as editable Mermaid source. GitHub and Mermaid-compatible Markdown viewers can render them.
- For tldraw, download **Content-Writer_Iraqi.tldr** and use the app menu **Open / Open file**. Menu wording may vary. The companion file contains three named pages with editable shapes, text and arrows.
- A Markdown file alone does not guarantee conversion of Mermaid into tldraw shapes. The native companion avoids that conversion.
- The SVG companions can also be dragged onto a canvas as images; their individual boxes will not be native editable shapes.

## Legend

Blue: current interfaces/storage. Green: accepted delivery or explicit owner approval. Yellow: decisions, repair or review. Grey/dashed: future design. No diagram claims a live production deployment has passed acceptance.

## 1. Content request workflow

Current implementation | main fceebf5 | 16 November 2026 | Publication is manual.

```mermaid
flowchart TD
    creator(["Creator enters a topic"])
    web["Web interface<br/>web/"]
    api["Sign-in + validation + admission<br/>bot/webapp.py"]
    demo{"Demo mode?"}
    sample["Return labelled sample<br/>No model or research calls"]
    adapter["Build web request context<br/>bot/web_service.py"]
    telegram["Telegram commands + access checks<br/>bot/bot.py"]
    brief["Topic + selected treatment<br/>Brief / content settings"]
    knowledge["Owner voice + dialect + examples<br/>knowledge/ + guidelines/"]
    prompt["Build system prompt<br/>bot/prompts.py"]
    engine["Shared writing engine<br/>pipeline.py -&gt; revision.py"]
    route{"Clarify, research or write?"}
    clarify["Ask for missing information"]
    research["Research and evidence validation<br/>bot/research.py"]
    write["Optional planning + writer draft<br/>via bot/llm.py"]
    check["Format checks + independent review<br/>quality.py + reviewer.py"]
    pass{"All required checks pass?"}
    repair["Repair / regenerate<br/>within remaining budgets"]
    block["Withhold draft + explain reason<br/>No unapproved script delivered"]
    delivery["Revalidate exact reviewed artifact<br/>Render copy + separate source links"]
    owner(["Owner edits or copies script<br/>Publishes manually"])
    creator --> web
    creator --> telegram
    web --> api
    api --> demo
    demo -->|"Yes"| sample
    demo -->|"No"| adapter
    adapter --> brief
    telegram --> brief
    brief --> prompt
    knowledge -->|"Style / rules"| prompt
    prompt --> engine
    engine --> route
    route -->|"Missing context"| clarify
    clarify -->|"Creator answers"| brief
    route -->|"Evidence needed"| research
    route -->|"Direct writing"| write
    research -->|"Evidence ready"| write
    research -->|"Unsupported / unavailable"| block
    write --> check
    check --> pass
    pass -->|"Yes"| delivery
    pass -->|"Repairable + budget"| repair
    repair -->|"Fresh checks"| check
    pass -->|"Otherwise"| block
    delivery --> owner
    classDef blue fill:#dbeafe,stroke:#2563eb,color:#172033
    class web,api,adapter,telegram,brief,prompt,engine,research,write,check blue
    classDef green fill:#dcfce7,stroke:#16a34a,color:#172033
    class creator,delivery,owner green
    classDef yellow fill:#fef3c7,stroke:#d97706,color:#172033
    class demo,route,clarify,pass,repair yellow
    classDef red fill:#fee2e2,stroke:#dc2626,color:#172033
    class block red
    classDef violet fill:#ede9fe,stroke:#7c3aed,color:#172033
    class knowledge violet
    classDef grey fill:#f1f5f9,stroke:#64748b,color:#172033
    class sample grey
```

## 2. Storage and human-approved learning

Current stores are separate | Feedback does not automatically train a model.

```mermaid
flowchart TD
    web["Web request / edit / result"]
    sqlite[("SQLite web job history<br/>web-preview.sqlite3 / web-demo.sqlite3")]
    history["Reopen history or request edit"]
    tg["Telegram generation"]
    logs[("Post log<br/>logs/posts.jsonl")]
    feedback["Manual accept / reject / outcome<br/>Telegram editorial commands"]
    events[("Feedback and outcome records<br/>data/editorial_events.jsonl")]
    human["Owner reviews and explicitly<br/>approves a reusable example"]
    examples[("Approved example library<br/>data/reviewed_examples.json")]
    prompts["Future writing prompts<br/>bot/prompts.py"]
    voice["Shared owner voice<br/>knowledge/voice/voice.md"]
    lessons["Manually maintained source lessons<br/>knowledge/source_lessons.toml"]
    queue["Candidate dialect words<br/>knowledge/dialect/new_words.csv"]
    approval["Owner approves word changes"]
    dictionary["Approved Iraqi dictionary<br/>knowledge/dialect/iraqi_words.csv"]
    future["FUTURE DESIGN ONLY<br/>Creator accounts + private voices<br/>Consented pooled examples"]
    futuredb[("Draft Supabase schema<br/>Not applied or connected")]
    web --> sqlite
    sqlite --> history
    history -->|"Reviewed edit"| web
    tg --> logs
    logs -->|"Post ID"| feedback
    feedback --> events
    events -->|"Manual review"| human
    human -->|"Explicit promotion"| examples
    examples -->|"Style examples"| prompts
    voice --> prompts
    lessons --> prompts
    queue -->|"Manual review"| approval
    approval -->|"Approved words"| dictionary
    dictionary --> prompts
    future -. "Proposal only" .-> futuredb
    classDef blue fill:#dbeafe,stroke:#2563eb,color:#172033
    class web,sqlite,history,tg,logs,feedback,events blue
    classDef green fill:#dcfce7,stroke:#16a34a,color:#172033
    class human,examples,prompts green
    classDef yellow fill:#fef3c7,stroke:#d97706,color:#172033
    class queue,approval yellow
    classDef red fill:#fee2e2,stroke:#dc2626,color:#172033
    classDef violet fill:#ede9fe,stroke:#7c3aed,color:#172033
    class voice,lessons,dictionary violet
    classDef grey fill:#f1f5f9,stroke:#64748b,color:#172033
    class future,futuredb grey
```

## 3. Database structure

CURRENT: SQLite jobs | PROPOSED: Supabase tables below | PK = primary key, FK = foreign key.

```mermaid
flowchart TD
    sqlitejobs[("CURRENT SQLite: jobs<br/>id TEXT PK<br/>request_id TEXT UNIQUE<br/>created TEXT<br/>state TEXT<br/>payload TEXT (JSON)<br/>context TEXT (JSON)<br/>result TEXT (JSON)<br/>parent_id TEXT (logical link)")]
    sqliteinfo["CURRENT constraints / lifecycle<br/>One owner; one active job; one worker<br/>parent_id has no SQL foreign key<br/>Demo and real use separate files<br/>Sessions are in memory"]
    auth[("PROPOSED auth.users<br/>id UUID PK<br/>Managed by Supabase Auth")]
    profiles[("PROPOSED public.profiles<br/>id UUID PK, FK -&gt; auth.users.id<br/>display_name TEXT<br/>pooling_consent_at TIMESTAMPTZ nullable<br/>created_at TIMESTAMPTZ")]
    voiceprofiles[("PROPOSED public.voice_profiles<br/>user_id UUID PK, FK -&gt; profiles.id<br/>tone_summary TEXT<br/>audience TEXT<br/>platforms TEXT[]<br/>dialect_notes TEXT<br/>approved_at TIMESTAMPTZ nullable<br/>updated_at TIMESTAMPTZ")]
    voiceexamples[("PROPOSED public.voice_examples<br/>id UUID PK<br/>user_id UUID FK -&gt; profiles.id<br/>platform TEXT<br/>body TEXT (1..8000 chars)<br/>created_at TIMESTAMPTZ")]
    jobs[("PROPOSED public.jobs<br/>id UUID PK<br/>user_id UUID FK -&gt; profiles.id<br/>topic TEXT<br/>strategy_id TEXT<br/>state TEXT (default queued)<br/>result JSONB nullable<br/>created_at TIMESTAMPTZ")]
    feedback[("PROPOSED public.feedback<br/>id UUID PK<br/>job_id UUID FK -&gt; jobs.id<br/>user_id UUID FK -&gt; profiles.id<br/>rating SMALLINT (1..5)<br/>edited_copy TEXT nullable<br/>created_at TIMESTAMPTZ")]
    pool[("PROPOSED public.pooled_corpus<br/>id UUID PK<br/>contributor UUID FK -&gt; profiles.id<br/>source_kind TEXT (example/accepted_draft/edit)<br/>body TEXT<br/>created_at TIMESTAMPTZ")]
    dbnote["PROPOSAL caveats<br/>RLS enabled; pooled corpus has no client policy<br/>Foreign-key deletion cascades<br/>Consent withdrawal purges pooled rows<br/>Feedback/job same-owner check still needs review<br/>Runtime SQLite -&gt; Supabase migration not built"]
    sqlitejobs -->|"Current store"| sqliteinfo
    auth -. "1 : 0..1" .-> profiles
    profiles -. "1 : 0..1" .-> voiceprofiles
    profiles -. "1 : many" .-> voiceexamples
    profiles -. "1 : many" .-> jobs
    profiles -. "Creator reference" .-> feedback
    jobs -. "1 : many" .-> feedback
    profiles -. "1 : many" .-> pool
    pool -. "Read before applying" .-> dbnote
    classDef blue fill:#dbeafe,stroke:#2563eb,color:#172033
    class sqlitejobs,sqliteinfo blue
    classDef green fill:#dcfce7,stroke:#16a34a,color:#172033
    classDef yellow fill:#fef3c7,stroke:#d97706,color:#172033
    class dbnote yellow
    classDef red fill:#fee2e2,stroke:#dc2626,color:#172033
    classDef violet fill:#ede9fe,stroke:#7c3aed,color:#172033
    class profiles,voiceprofiles,voiceexamples,jobs,feedback violet
    classDef grey fill:#f1f5f9,stroke:#64748b,color:#172033
    class auth,pool grey
```

## Database notes

- SQLite `payload`, `context` and `result` are JSON serialized into TEXT; the current SQL schema does not constrain job states or define a foreign key for `parent_id`.
- Telegram pilot settings, post logs, feedback and approved examples are files, not tables in the web SQLite database.
- The proposed Supabase schema has not been applied or connected to the writing engine. It does not yet implement per-creator voice use.
- Proposed relationships show foreign keys; `many` permits zero child rows. A profile can have at most one voice profile because `user_id` is its primary key.
- Before applying Supabase, validate feedback/job ownership, approved voice versions and account isolation. The diagram describes the draft as written, not a security approval.

## Learning notes

- Feedback collection does not automatically train a model, update prompts or promote examples.
- Owner-approved examples and manually curated voice/dialect/source lessons influence future prompts.
- Web history/edit requests and the Telegram feedback/example workflow currently have separate identifiers and stores. The web UI has no equivalent example-promotion interface.
- Dialect word review is a manual workflow; no automatic word extraction worker is shown.

## Configuration and development files

| Repository area | Role |
|---|---|
| `bot/llm.py` | Provider calls, fallback and usage accounting |
| `.env` / hosting settings | Private server configuration; values are excluded from this export |
| `.agents/skills/`, `.claude/` | Coding-assistant guidance and configuration; not content-engine stages |
| `tests/`, `scripts/` | Regression checks, evaluation and frontend build |
| `docs/`, `web/progress.json` | Plans and manually maintained status; not automatic project management |
| `.github/`, `render.yaml`, `vercel.json` | CI and deployment configuration |

## Source files

All links below are pinned to the reviewed revision.

- [Web API and demo](https://github.com/Marketalse/Content-Writer_Iraqi/blob/fceebf5/bot/webapp.py)
- [Web request and delivery boundary](https://github.com/Marketalse/Content-Writer_Iraqi/blob/fceebf5/bot/web_service.py)
- [Shared pipeline and bounded review/revision](https://github.com/Marketalse/Content-Writer_Iraqi/blob/fceebf5/bot/revision.py)
- [Prompt assembly](https://github.com/Marketalse/Content-Writer_Iraqi/blob/fceebf5/bot/prompts.py)
- [Manual feedback and approved examples](https://github.com/Marketalse/Content-Writer_Iraqi/blob/fceebf5/bot/editorial.py)
- [Current SQLite jobs schema](https://github.com/Marketalse/Content-Writer_Iraqi/blob/fceebf5/bot/web_store.py)
- [Proposed Supabase schema](https://github.com/Marketalse/Content-Writer_Iraqi/blob/fceebf5/supabase/migrations/0001_creator_profiles.sql)

These diagrams are a source-code snapshot and do not update automatically.
