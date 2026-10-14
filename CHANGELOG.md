# Changelog

## [2.0.0] - 2026-01-24

### 🎯 Core Philosophy Change: From "Config-Driven" to "AI-Driven"

**Before**: Config file dictated everything (directories, metaphors, commands)
**After**: AI makes autonomous decisions based on context

### ✨ Added

#### 1. Playwright MCP Integration
- **Scout responsibility**: Automatically capture screenshots from official documentation
- **Auto-save location**: `material/screenshots/day{N}_{description}.png`
- **Use cases**:
  - Docker Desktop installation screen
  - VS Code interface
  - Node.js download page
  - Terminal success output

#### 2. Prerequisite Guidance & Install Paths
- **Scribe requirement**: If tools are missing (Node.js, npm, Docker, Taskfile, git, Prisma CLI), include official install steps + verification commands
- **Balanced setup**: Choose taskfile or raw npm/docker commands based on repository reality
- **Screenshots in tutorials**: Embed Scout-captured files via `../screenshots/*.png` (no base64)

```python
# Scout can now do this automatically:
mcp_playwright_browser_navigate(url="https://nodejs.org")
mcp_playwright_browser_screenshot(selector="body", path="material/screenshots/day01_nodejs_download.png")
```

#### 2. AI Autonomous Directory Exploration
- **Removed**: `chapters[].target_dirs` (manual directory specification)
- **AI decides**: Scout searches the entire codebase and finds relevant code autonomously
- **Benefit**: No more outdated `target_dirs` in config

#### 3. AI-Chosen Metaphors
- **Removed**: `teaching.metaphors` (fixed dictionary like "Variable = 名前のついたお弁当箱")
- **AI decides**: Chooses the best metaphor for each concept based on context
- **Benefit**: More natural, contextually appropriate explanations

#### 4. Taskfile Auto-Detection
- **Before**: Hardcoded `task init`, `task dev` commands
- **After**: AI checks if `taskfile.yaml` exists
  - **If exists**: Use `task` commands (explain WHY this simplifies multi-step commands)
  - **If not exists**: Use raw `npm`, `docker compose` commands
- **Benefit**: Works for ANY repository, not just those with Taskfile

### 🎨 Improved

#### 1. Font Rendering (Fixed "Chinese-looking" Font Issue)
**Before**:
```css
font-family: "Noto Sans CJK JP", "Hiragino Kaku Gothic ProN", ...
```

**After**:
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
  "Hiragino Sans", "Hiragino Kaku Gothic ProN",
  "Yu Gothic UI", "Meiryo UI", sans-serif;
```

**Benefit**: Uses system-native fonts for clean, native-looking Japanese text

#### 2. Simplified Config Structure
**Removed sections**:
- `paths.src_dir` → AI auto-detects
- `paths.output_dir` → Defaults to `material/30days-curriculum`
- `teaching.metaphors` → AI chooses freely

**New teaching section**:
```yaml
teaching:
  philosophy: |
    YOU decide the best metaphor for each concept.
    Guidelines are suggestions, not rules.
    Prioritize: clarity > consistency > guidelines

  guidelines:
    - "日常生活で誰でも知っているものに例える（料理、学校、ゲームなど）"
    - "1つの概念に1つの比喩（混ぜると混乱する）"
```

### 🗑️ Removed

- ❌ `edu-config-test.yaml` (duplicate config file)
- ❌ `chapters[].target_dirs` (all 30 days)
- ❌ `teaching.metaphors` (fixed metaphor dictionary)
- ❌ `paths.src_dir` (hardcoded to "src")
- ❌ Hardcoded taskfile assumption in prompts

### 🔧 Migration Guide

#### For Existing Projects

1. **Delete duplicate config**:
   ```bash
   rm edu-config-test.yaml
   ```

2. **Update edu-config.yaml**:
   ```bash
   # Remove all target_dirs lines
   sed -i '/target_dirs:/d' edu-config.yaml

   # Update LLM models
   sed -i 's/gpt-4.1/gpt-5.2/' edu-config.yaml
   sed -i 's/gemini-1.5-flash/gemini-2.0-flash/' edu-config.yaml
   ```

3. **Create screenshots directory**:
   ```bash
   mkdir -p material/screenshots
   ```

4. **Run with new config**:
   ```bash
   python edu-creator/main.py --config edu-config.yaml --chapters 1
   ```

### 📚 Updated Prompts

#### Scout (`edu-creator/prompt/agent/scout.py`)
- ➕ Added Playwright MCP screenshot instructions
- ➕ Added screenshot reporting format

#### Scribe (`edu-creator/prompt/task/write.py`)
- 🔄 Changed from "BASE ALL SETUP ON TASKFILE" to "CHOOSE SETUP COMMANDS WISELY"
- ➕ Added taskfile auto-detection logic

### 🐛 Bug Fixes

- Fixed Chinese-looking font rendering in PDF output
- Fixed hardcoded taskfile assumption (now works for repos without Taskfile)
- Removed config duplication (edu-config.yaml vs edu-config-test.yaml)

### 💡 Philosophy

**Old approach**: "Tell AI exactly what to do via config"
**New approach**: "Give AI guidelines and let it think"

This change makes edu-creator:
- ✅ More flexible (works with any repo structure)
- ✅ More maintainable (less config to update)
- ✅ More intelligent (AI makes context-aware decisions)
- ✅ More accurate (no outdated config entries)

---

## [1.0.0] - 2026-01-20

- Initial release with Commander + Scout + Scribe architecture
- Support for 30-day curriculum generation
- Japanese tutorial output with metaphor-based teaching
