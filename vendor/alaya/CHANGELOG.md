# Changelog

## 3.1.0 — 2026-08-08

### Changed

- Separated the updatable skill from the user-owned `alaya/wiki/raw` knowledge base and added safe first-run path selection.
- Replaced broad automatic activation with contextual routing and one-click global persona language.
- Reworked interaction memory into per-answer/group idempotent commits, bounded shared state/history, explicit user profile consent, and bounded BI state/history.
- Unified knowledge decay around a 90-day cold threshold with daily piggyback settlement and upgrade-safe baselines.
- Rebuilt import as plan-then-commit with per-task raw-copy choice, content-hash collision handling, optional PDF support, and serialized publication.
- Made category indexing dynamic, complete after incremental updates, and protective against unconfirmed category removal.
- Made health and link checks read-only by default; automatic link edits are limited to unique case corrections.
- Made role removal recoverable and protected default-role replacement and path boundaries.
- Treated `SKILL_FULL.md` as an optional compatibility artifact; normal installation validates the multi-file package.

### Compatibility

- Legacy `hot_limit/cold_limit` fields remain readable without rewriting user configuration.
- Existing cards with the historical `half_life: 30` default follow the new global policy; explicit non-default per-card half-life values remain honored.
- Dynamic category validation supports the current 16-category knowledge base and future additions without a fixed count.

All notable changes to Alaya will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [3.0.0] - 2026-06-07

### Major Changes

- **Modular subskill architecture**: Alaya redesigned from monolithic skill (~40KB) to modular subskill system. Core functionality split into 5 independent subskills that load on-demand, reducing initial context footprint by 80%.

- **Main skill lightweight**: SKILL.md reduced from ~40KB to ~8KB. Main skill now focuses on initialization, command routing, and version coordination. Detailed protocols moved to subskills.

- **On-demand subskill loading**: Subskills automatically load based on user intent detection:
  - `alaya-retrieval` (v2.0.0): User asks questions, builds index
  - `alaya-memory` (v1.0.0): Session boundaries, "save it"
  - `alaya-persona` (v1.7.0): Persona creation, multi-persona discussion
  - `alaya-import` (v1.0.0): File imports, batch operations
  - `alaya-maintenance` (v1.0.0): Health checks, xunxi cycles

- **Subskill version management**: Each subskill has independent versioning with explicit dependency declarations. Main skill performs compatibility checks at startup.

### New Features

- **Subskill status commands**: "list loaded skills", "check subskill versions"
- **Manual subskill loading**: Users can explicitly load specific subskills
- **Intelligent command routing**: Main skill auto-detects user intent and routes to appropriate subskill
- **Version compatibility checking**: Automatic detection and reporting of version mismatches
- **Custom subskill support**: Framework for users to create their own subskills

### Performance Improvements

| Context Usage | v2.x | v3.0 | Reduction |
|:---|:---|:---|:---|
| Initial session | ~40KB | ~8KB | 80% |
| User query | ~40KB | ~15KB | 62% |
| Persona creation | ~40KB | ~18KB | 55% |
| Batch import | ~40KB | ~25KB | 37% |

### Directory Structure

```
alaya/
├── SKILL.md                    # Main skill (lightweight core)
├── skills/                     # NEW: Subskill directory
│   ├── alaya-retrieval/       # Knowledge retrieval
│   ├── alaya-memory/          # Memory management
│   ├── alaya-persona/         # Persona system
│   ├── alaya-import/          # Import functionality
│   └── alaya-maintenance/     # Maintenance tools
├── scripts/                    # Unchanged: Python utilities
├── manas/                      # Unchanged: Default personas
├── templates/                  # Unchanged: Import templates
└── config/                     # Unchanged: Default configs
```

### Documentation

- **skills/README.md**: Subskill system overview
- **MIGRATION_GUIDE.md**: Complete migration guide from v2.x to v3.0
- **Updated SKILL.md**: Lightweight main skill documentation
- **Subskill SKILL.md files**: Individual subskill documentation

### Backward Compatibility

- **100% data compatible**: All v2.x knowledge cards, personas, memories work unchanged
- **No API changes**: All scripts continue to work as before
- **Automatic migration**: Built-in migration wizard from v2.x to v3.0
- **Graceful fallback**: Subskill missing → degrade to basic functionality + install prompt

### Installation Methods

- **Full installation**: "install this skill: https://github.com/DL-LEO/alaya" → installs all subskills
- **Core-only installation**: "install alaya core only" → minimal footprint, subskills load on-demand
- **Manual subskill loading**: "load alaya-retrieval skill" → explicit subskill loading

### Migration

- **Automatic upgrade**: "upgrade alaya to v3.0" → automatic backup + migration
- **Manual migration**: Step-by-step guide in MIGRATION_GUIDE.md
- **Rollback support**: Full restore path from backups

### Added

- `skills/` directory with 5 subskills
- `skills/README.md` - Subskill system documentation
- `MIGRATION_GUIDE.md` - v2.x to v3.0 migration guide
- Subskill frontmatter with type, dependencies, triggers
- Version compatibility checking in main skill
- Command routing table in main skill

### Changed

- `SKILL.md` - Reduced from ~800 lines to ~300 lines (core only)
- `SKILL_GUIDE.md` - Moved detailed protocols to subskills
- `SKILL_REF.md` - Subskill-specific reference moved to individual subskills
- `SKILL_FULL.md` - Auto-merged for single-file platforms (Cursor, Codex)

### Technical Details

- **Main skill responsibilities**: Init detection, command routing, version coordination, error handling
- **Subskill isolation**: Each subskill owns its data directory and version
- **Shared state`: All subskills share `ALAYA_ROOT` environment variable
- **Trigger-based loading`: Keywords and signals determine when subskills load
- **Graceful degradation**: Missing subskills → fallback + install prompt

## [2.0.0] - 2026-06-02

### Changed

- **Description-driven retrieval**: Knowledge retrieval redesigned from graph-algorithm-based (tag overlap, activation spreading) to description-driven. LLM semantically matches queries against category descriptions (index.md) and card descriptions (category files), replacing explicit graph edges with natural-language semantic understanding.

- **Category file rename**: `_category.md` → `{category}_category.md`. Each category file now has a unique, Obsidian-graph-distinguishable name (e.g., `deep-learning_category.md`). Old `_category.md` files are auto-migrated on first `--full` build.

- **Simplified category format**: Removed Core/Peripheral/Dormant three-tier strength-based split. Category files now have a flat `## Cards` list with `[[CardName]] — description` entries. Strength-based filtering in retrieval is replaced by LLM semantic matching of card descriptions.

- **Card descriptions**: New `description` field in card YAML frontmatter. Auto-extracted from card body (blockquote or first paragraph) by `build_index.py` as fallback. Expected to be written at card creation time (Two-Seal).

- **index.md new format**: Category entries include descriptive paragraphs (refined from category headers) instead of a Core/Peripheral/Total table. Concept Network section removed — cross-category relationships are expressed in natural language within descriptions.

- **BI Observer expanded**: 4 new passive observation types: missing card descriptions, stale category descriptions, index-category sync, category proliferation. BI observers "hitchhike" on existing script executions (perfume --level save, build_index) rather than requiring dedicated triggers.

- **Retrieval protocol simplified**: Removed Tier 2.5 (activation spreading). Tier 2 now reads only `## Cards` section (descriptions, ~1KB) — full card content loaded only in Tier 3 for persona-selected cards (~10KB). Minimum pool size with fallback: if first pass yields < min_pool cards, additional categories are explored.

- **Maintenance model**: `build_index.py --incremental` removed from session start. BI observer monitors → natural-language suggestions → user manually triggers batch updates. Passive BI staleness check at Tier 0: if BI > 14 days stale and 3+ sessions without maintenance, gentle reminder at conversation pause.

- **Knowledge version**: `config.knowledge.version` bumped from 1.7.0 to 2.0.0. New `min_pool` config field (default 5) controls minimum candidate pool size before triggering category-expansion fallback in Tier 2.

- **Default config updated**: `config/default_config.json` bumped to v2.0.0; knowledge partition updated accordingly.

### Removed

- `compute_tag_overlaps()` and `compute_card_relations()` — tag-overlap graph computation replaced by description-driven semantic matching
- Concept Network section in index.md
- Card Relations section in category files
- Core/Peripheral/Dormant three-tier split
- `graph.json` concept (never implemented) — description text serves as the "graph"
- `build_index.py --incremental` from automatic session start

### Added

- `get_description()` / `set_description()` in `yaml_utils.py`
- `is_category_file()` / `category_file_for()` shared helpers in `yaml_utils.py`
- `extract_description_from_body()` — blockquote/paragraph extraction for card descriptions
- `generate_category_header()` — auto-generates category descriptions from card data
- `extract_index_description()` — extracts concise index entries from category headers
- `classify_card_to_category()` — tag-based card classification with ambiguity detection
- `migrate_old_category_file()` — automatic migration of `_category.md` to `{cat}_category.md`
- `build_index.py --classify-card <path>` — JSON output for Agent/LLM classification decisions
- 4 new BI health check types: `missing_descriptions`, `stale_category_descriptions`, `index_desync`, `category_proliferation`
- Passive BI staleness check in SKILL.md Tier 0
- New trigger words: "补充卡片描述", "更新类别描述", "更新索引描述", "审视分类结构"

## [1.10.0] - 2026-06-02

### Added

- **BI System Health Observer**: New `check_health()` function in `bi_observer.py` with 11 detection items across 9 domains: dirty categories, index missing/stale, orphan cards, orphan categories, mass dormancy, dormant persona cluster, knowledge gaps (interest-category alignment + thin categories), cold capacity, stale xunxi. All items include severity, data-backed detail, and natural-language suggestions.

- **Proactive health reminders**: `--level save` now runs `check_health()` alongside the existing BI pass. Findings are filtered by frequency control (24h quiet, max 3× per 7 days) and written to `bi_notes.json` as `system_health`. Output at session boundary:

  ```
  ⚠️ alaya系统提醒您：
    • 检测到 3 个脏类别（量子物理、机器学习）
      → 建议您对智能体说「重建索引」，智能体会自动全量构建知识图谱
  ```

- **Frequency control**: `config.json` gains a `reminder_tracking` section that prevents the same reminder from repeating within 24h or more than 3 times within 7 days. Counter resets after 7 days of silence.

- **Tier 0 health alert**: If a `system_health` item has `severity=high`, Agent briefly mentions it at session start (one line max).

### Fixed

- **Interest-category alignment false positive**: `_find_interest_category_gaps()` list comprehension used a leaked loop variable (`il`) from the outer `for interest in foci` iteration, causing all interests to be matched against the last processed interest's name. Rewrote as explicit for-loop with per-iteration `interest_lower` binding.

### Changed

- **`bi_observer.py`**: Added `check_health()`, `_get_newest_card_mtime()`, `_find_orphan_cards()`, `_find_orphan_categories()`, `_find_interest_category_gaps()`, `_check_cold_capacity()` — all passive observation, no intervention
- **`perfume.py`**: `level_save()` Step 5 now integrates health check + frequency filtering + `system_health` in `bi_notes.json`; added `_filter_by_reminder_tracking()` and `_update_reminder_tracking()`
- **`SKILL.md`**: Step 6 confirmation expanded with system health display format; Tier 0 loading now reads `system_health` for high-severity alerts; all suggestions use natural language (user says to Agent, not raw commands)

## [1.9.1] - 2026-06-02

### Fixed

- **Paper import truncation** (Bug 1): Replaced hardcoded `text[:2000]` with two-mode system (`--mode info` for LLM metadata + `--mode full` for complete text extraction). LLM now summarizes via templates (`templates/paper_summary.md`, `news_summary.md`, `other_summary.md`) with configurable character limits instead of blind truncation. See [SKILL.md import workflow](SKILL.md) for the three-step agent workflow.

- **Group discussion default rounds** (Bug 2): Changed default from 2 rounds to 1 round (Phase 1 only) to reduce verbosity. Override with explicit "继续讨论" or user request.

- **Cross-platform path detection** (Bug 3): Added `~/.alaya_path` file persistence. setup_wizard.py now saves the knowledge base root to `~/.alaya_path`, and SKILL.md first-launch detection reads this file before falling back to current directory. Enables consistent path resolution across CLI tools, IDE extensions, and subprocess scripts regardless of working directory.

- **Vague post-setup suggestions** (Bug 4): setup_wizard.py "Next steps" expanded from 3 generic lines to 4 categorized groups (📚 Build knowledge base, 👤 Create personas, 💬 Chat, 🔄 Maintenance) with ~3 concrete "try saying" examples each.

- **Session Boundary Protocol BI automation** (Bug 5): Added `--level save` mode to `perfume.py` that atomically executes Steps 3-5 of the Session Boundary Protocol (ambient.json semantic fields write, persona history write, BI Observer pass, protocol checklist) in a single script call. SKILL.md Save Protocol simplified: Steps 3-5 replaced with one `--level save` command taking `--ambient` and `--history` JSON arguments. Supports group discussion flows (run once per persona, omit `--ambient` on subsequent calls to preserve mechanical fields).

### Changed

- **`perfume.py`**: New `level_save()` function + `--level save` / `--ambient` / `--history` CLI options
- **`import_paper.py`**: Complete rewrite — `mode_info()` outputs JSON metadata for LLM decision; `mode_full()` extracts full text (no truncation); heuristic type detection (paper/news/other); backward-compatible help
- **`setup_wizard.py`: `~/.alaya_path` auto-save on setup; categorized actionable next-steps
- **`SKILL.md`**: Session Boundary Protocol streamlined (Steps 3-5 → single `--level save` command); paper import workflow section; group discussion default 1 round; cross-platform path detection logic; `~/.alaya_path` documented

### Added

- **Templates**: `templates/paper_summary.md`, `templates/news_summary.md`, `templates/other_summary.md` — structured summary templates with YAML frontmatter compatible with Obsidian knowledge graph and `build_index.py`
- **`scripts/perfume.py --level save`**: Atomic session-boundary save combining ambient semantic fields + persona history + BI observation + protocol checklist
- **`alaya/_protocol_checklist.json`**: Auto-generated protocol completion record tracking which steps were executed and when

## [1.9.0] - 2026-06-01

### Added
- **Session Boundary Protocol**: LLM detects conversation endpoints via weighted signals (explicit closing, persona switch, topic exhaustion) and prompts user to save memory
- **ambient.json semantic fields**: `mood_trajectory` (emotional arc, 3-entry cap), `recent_themes` (LLM-synthesized topic summary), `open_threads` (unresolved questions with lifecycle), `user_style_notes` (accumulated user preferences)
- **User-confirmed memory save**: both ambient.json (shared) and {persona}_history.json (isolated) are saved together at session boundary with explicit user confirmation
- **Rich ambient awareness**: Warm Recall Protocol now uses trajectory, themes, threads, and style notes for deeper persona awareness
- **Old-format ambient detection**: health_check and update_ambient auto-detect and initialize missing semantic fields
- **BI Observer (Rule G)**: passive pattern observer with three observation domains — affinity network dynamics (mutual growth, asymmetric, dense clusters), dormant persona detection (>14d inactive → gentle Tier 0 nudge), knowledge gap hints (interest area lacks wiki category or card count <5). No scoring, no ranking, no automatic intervention
- **bi_notes.json**: BI observation log (max 20 entries, append-only), stored in `alaya/memory/`, written by LLM at Session Boundary Save Protocol Step 5
- **bi_observer.py rewrite**: now reads all persona JSON + history files + ambient.json for real cross-persona pattern analysis (was: static persona config dump). Supports `--json` output for LLM consumption

### Changed
- **Level 1 xunxi batched**: no longer runs after every reply. All four operations (card boost, affinity, mood, attention) accumulate during session and execute ONCE at session boundary — zero fidelity loss, less overhead
- **update_ambient() refactored**: mechanical layer only (mood + trajectory + attention). Semantic fields preserved as-is — never overwritten by script
- **SKILL.md Rule C**: Level 1 retitled "At Session Boundary"; Agent no longer edits card files or runs scripts per-reply; tracks citations/tags/mood in memory for batched session-end execution
- **Save Protocol**: Level 1 script call integrated as Step 1 (mechanical), LLM semantic writes follow as Steps 2-4
- **SKILL.md Tier 0**: ambient loading now surfaces all 6 fields (mood, trajectory, themes, threads, style_notes, attention)
- **health_check.py [8]**: checks new ambient fields completeness; reports old-format ambient files
- **Level 2 triggers**: added session boundary detection as a trigger
- **Multi-persona / Group discussion**: card citations tracked for batch update at session boundary instead of immediate Level 1

### Design principle
- **Mechanical → script (auto)**: card strength, tag decay, affinity increment — no user involvement needed
- **Semantic → LLM (user-confirmed)**: themes, threads, style notes, persona history — user confirms at session boundary

## [1.8.0] - 2026-06-01

### Added
- **Emotional Memory System (方案C)**: per-persona interaction history with mood tracking + shared ambient state (recent_mood, recent_attention)
- **Warm Recall Protocol**: SKILL.md instructions for natural, character-voiced memory recall (structured data → warm output)
- **ambient.json**: shared cross-persona mood + attention state, stored in `alaya/memory/`
- **mood field**: interaction history entries now include user's emotional state (2-3 Chinese words)
- **attention weights**: tag frequency tracking with 0.7x decay + 0.3x boost, pruned below 0.1
- **Three-system architecture**: Knowledge / Memory / Persona subsystems with independent data directories and version numbers
- **config.json partitioning**: nested `knowledge`/`memory`/`persona` sections with per-system version fields
- **perfume_knowledge.py**: extracted knowledge operations (strength, decay, sleep, dirty tracking)
- **perfume_memory.py**: extracted memory operations (history hot/cold, ambient state, migration from manas/)
- **perfume_persona.py**: extracted persona operations (affinity increment and decay)
- **SKILL.md system markers**: `<!-- ALAYA:KNOWLEDGE -->`, `<!-- ALAYA:MEMORY -->`, `<!-- ALAYA:PERSONA -->` for section isolation
- **Auto-migration**: perfume.py auto-migrates flat config (v1.7) to nested structure (v1.8) and moves history files from manas/ to memory/
- **--mood parameter**: Level 1 xunxi accepts `--mood "开心"` for emotional state recording

### Changed
- **perfume.py**: rewritten as thin orchestrator (~100 lines), delegates to perfume_knowledge/memory/persona modules
- **Tier 0 loading**: now includes persona's hot zone history + ambient state (~200 tokens, always loaded)
- **SKILL.md**: added Three-System Architecture section, Warm Recall Protocol, updated all file paths (manas/ → memory/ for history)
- **Filesystem Convention**: new `alaya/memory/` directory for memory system data
- **config.json**: flat structure → nested `knowledge`/`memory`/`persona` sections

### Removed
- History files no longer stored in `manas/` (moved to `memory/`)

## [1.7.0] - 2026-06-01

### Added
- **Three-layer knowledge graph**: Layer 1 (wiki/index.md, concept network), Layer 2 (_category.md, card relations), Layer 3 (knowledge cards, leaf nodes)
- **Question-driven retrieval**: Tiers 1-2 are question-driven (not persona-driven); persona only intervenes at Tier 3 for card selection and interpretation
- **Category subfolders**: wiki/{category}/ structure replaces flat wiki/ for better organization
- **Cross-category links**: auto-generated from tag overlap (Concept Network in wiki/index.md)
- **Intra-category card relations**: auto-generated from tag overlap (Card Relations in _category.md)
- **Incremental index rebuild**: `--category` (single category) and `--incremental` (changed-only) modes
- **Dirty category tracking**: perfume.py marks categories dirty when strength crosses thresholds
- **AUTO/MANUAL section preservation**: build_index.py preserves user-edited content outside `<!-- AUTO -->` markers
- **format_converter.py**: zero-dependency format conversion (MD/TXT native, PDF via PyMuPDF optional)
- **batch_import.py**: batch import with checkpoint/resume, auto-scan + dedup, supports MD/TXT/PDF
- **Agent guidance template**: unsupported file formats trigger a template that guides the user's Agent to produce the right output
- **max_cards_per_persona**: configurable per-persona card selection limit (default 5)

### Changed
- **build_index.py**: complete rewrite — generates three-layer graph, injects missing metadata, supports incremental modes
- **SKILL.md Rule A**: retrieval reworked — question-driven Tiers 1-2, persona-driven Tier 3
- **import_paper.py**: supports `--category`, writes to wiki/{category}/, uses format_converter
- **health_check.py**: checks three-layer network integrity (broken links, orphans, bidirectionality, dirty categories)
- **perfume.py**: category-aware path resolution, skips _category.md, dirty category marking
- **fix_links.py**: category-aware card discovery, skips _category.md
- **setup_wizard.py**: version 1.7.0, max_cards_per_persona config step, updated post-setup instructions
- **docs/quick-start.md**: updated for three-layer graph, category subfolders, new commands
- **docs/role-guide.md**: added max_cards_per_persona documentation

### Removed
- **build_concepts.py**: cancelled — concept hub pages replaced by three-layer knowledge graph
- **scan_cards.py**: merged into build_index.py (metadata injection happens during index build)
- **seed_import.py**: replaced by batch_import.py
- **seeds/seed_index.json**: removed — card tracking now happens via _category.md files
- **alaya/seeds/ directory**: removed
- **alaya/index/ directory**: moved to wiki/ (index.md and _category.md)
- **wiki/concepts/ directory**: cancelled — three-layer graph replaces concept hub pages

## [1.6.0] - 2026-05-31

### Added
- **Persona profiles**: dual-file persona architecture (JSON config + Markdown profile.md) for richer character definition
- **8 persona profile.md files**: Feynman, Buddha, Zhuangzi, Socrates, Carl Jung, Galileo, Xiaozhao, Audrey Hepburn
- **Hot/Cold memory zones**: interaction history upgraded from flat FIFO to HOT (5 detailed) + COLD (45 compressed) with auto-rotation
- **Tags + Summary in history**: each interaction record now includes tags and one-line summary for better retrieval
- **Time-decay memory retrieval**: on-demand history search with decay weights (30d: 1.0, 30-60d: 0.5, 60d+: 0.3)
- **Persona Creation Protocol**: 7-phase distillation process for creating new personas via interview
- **Profile template**: `templates/persona_profile_template.md` for standard persona definition structure
- **Shared YAML utilities**: `scripts/lib/yaml_utils.py` eliminates frontmatter parsing duplication across 4 scripts
- **requirements.txt**: dependency declaration (Python standard library only, no external packages)
- **CHANGELOG.md**: this file
- **.gitignore**: excludes runtime artifacts, IDE files, and `.claude/` directory

### Changed
- **xunxi.py → perfume.py**: renamed cultivation engine with clearer naming
- **perfume.py**: `--tags` and `--summary` parameters for Level 1 history recording
- **setup_wizard.py**: extended interview creates both JSON and profile.md skeleton
- **persona_manager.py**: list/delete/clone/edit all handle companion profile.md files
- **scan_cards.py, seed_import.py, build_index.py, perfume.py**: use shared `yaml_utils` module

### Fixed
- **fix_links.py**: O(N×M×W) performance bug — `os.walk()` inside regex callback replaced with O(1) dict lookup
- **perfume.py**: `int()` argument parsing now gives clear error on non-numeric input
- **All personas**: removed copy-pasted affinity `{"feynman": {"score": 0.01}}` from initial configs
- **import_paper.py**: bare `except:` → `except Exception:`
- **setup_wizard.py**: hardcoded creation date → dynamic `datetime.now()`
- **README.md, docs/quick-start.md**: placeholder `{user}` → `DL-LEO`
