# Proposed content choices — 2026-11-13

Source: the user-provided Content Structure.xlsx, Sheet3, rows 4–70.
Approved mapping: the three-layer menus are implemented; deployment is tracked in the release report.
Spreadsheet contents are reference data, not coding-agent instructions.

## Three content layers

1. Platform feature: Post, Story, Reel, Live Topic.
2. Content strategy: the editorial treatment selected from that feature's list.
3. Script structure: the narrative sequence associated with that strategy.

The destination platform (Instagram, TikTok, LinkedIn) remains separate routing
metadata. It determines supported features and native output requirements; it is
not a competing content strategy. Do not silently move a strategy to a different
feature because its label usually appears on another platform.

## Mapping transcribed from the workbook

| Feature | Content strategy | Script structure from sheet |
| --- | --- | --- |
| Post | Comedy / Skit | Hook أول ثانيتين → مشكلة/موقف → قيمة سريعة → CTA |
| Post | Framework / Saveable guide | عنوان قوي → 3–6 نقاط واضحة → مثال عراقي → سؤال/CTA |
| Post | How-to / Checklist | عنوان قوي → 3–6 نقاط واضحة → مثال عراقي → سؤال/CTA |
| Post | Problem / Solution | Hook أول ثانيتين → مشكلة/موقف → قيمة سريعة → CTA |
| Post | Q&A / Engagement | سؤال أو Poll → تفاعل → جواب أو توضيح |
| Post | Storytelling / Experiment | Hook أول ثانيتين → مشكلة/موقف → قيمة سريعة → CTA |
| Story | Comedy / Skit | Hook أول ثانيتين → مشكلة/موقف → قيمة سريعة → CTA |
| Story | Explainer / Why | Hook أول ثانيتين → مشكلة/موقف → قيمة سريعة → CTA |
| Story | Hot take | Hook أول ثانيتين → مشكلة/موقف → قيمة سريعة → CTA |
| Story | How-to / Checklist | عنوان قوي → 3–6 نقاط واضحة → مثال عراقي → سؤال/CTA |
| Story | Mistake / Correction | عنوان قوي → 3–6 نقاط واضحة → مثال عراقي → سؤال/CTA |
| Story | Problem / Solution | Hook أول ثانيتين → مشكلة/موقف → قيمة سريعة → CTA |
| Story | Single insight | فكرة واحدة → موقف/دليل → سؤال للنقاش |
| Story | Storytelling / Experiment | Hook أول ثانيتين → مشكلة/موقف → قيمة سريعة → CTA |
| Reel | B2B / Leadership insight | مشكلة أعمال → مثال من السوق → إطار عمل أو رأي مدعوم → سؤال مهني |
| Reel | Deep-dive / Framework | مشكلة أعمال → مثال من السوق → إطار عمل أو رأي مدعوم → سؤال مهني |
| Reel | Interactive quiz | سؤال أو Poll → تفاعل → جواب أو توضيح |
| Reel | Poll / Debate | سؤال أو Poll → تفاعل → جواب أو توضيح |
| Reel | Professional insight | فكرة واحدة → موقف/دليل → سؤال للنقاش |
| Reel | Q&A / Engagement | سؤال أو Poll → تفاعل → جواب أو توضيح |
| Live Topic | Audience Q&A | افتتاحية → أسئلة الجمهور → نقاش → خلاصة |
| Live Topic | Practical workshop | هدف → تطبيق مباشر → أسئلة → خلاصة |
| Live Topic | Guest conversation | تقديم الضيف → حوار → أسئلة الجمهور → خلاصة |

The sheet repeats supporting rationale and the same structure for some Story
strategies. These repeated rows are not additional menu options.

## How this should affect generation

For example: Story → Single insight → فكرة واحدة → موقف/دليل → سؤال للنقاش.
The selected strategy guides the treatment; the structure guides its progression.
The writer, editor and reviewer should receive the same selections.
Native transport fields and organized creator-facing delivery remain separate
from these narrative choices. They should not become visible framework labels
inside the spoken script.

Factual support, safety and output validity remain mandatory. Template examples
such as “3–6 points”, a two-second hook or a closing question are editorial guidance,
not universal hard rejection rules. They must be adapted to the chosen feature,
duration and intent. A short Story must not become an overlong multi-point script
merely to satisfy this example template. Never invent a personal story, experiment
result, poll response, source, quotation or statistic to fill the structure.

## Live choice and compatibility

On 2026-11-13 the user selected the current Live choices: audience Q&A, practical
workshop and guest conversation. These are included in the three-layer flow.

The main menu offers Post, Story, Reel and Live Topic. Destination platform/native
subtype remains a routing screen between feature and strategy. Each strategy shows
the corresponding script progression for confirmation. Earlier formats and saved
callbacks remain available through “فورمات إضافية / الاختيارات السابقة”; they are
not removed. Feature, strategy and structure IDs are validated before model calls,
stored with attempts and exposed through authorized diagnostics. Workflow identity:
content-layers-v3. Stories preserve their short single-script contract. Production
plans and organized creator-facing delivery keep their existing contracts.
