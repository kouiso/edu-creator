# 📚 edu-creator

> AI-powered educational material generator using CrewAI (GPT-5.2 + Gemini 2.0 Flash)

## 🎯 Overview

This tool automatically generates beginner-friendly programming tutorials from any repository.

### Architecture: PM + Scout + Scribe

```
┌─────────────────────────────────────────────────────────────┐
│  🎖️ Commander (GPT-5.2)                                     │
│  Role: PM / Director                                        │
│  Cost: PAID (minimal usage)                                 │
│  Tasks: Planning, Review, Quality Control                   │
└─────────────────────────────────────────────────────────────┘
                    ↓ Instructions    ↑ Reports
┌─────────────────────────────────────────────────────────────┐
│  🔍 Scout (Gemini 2.0 Flash)     ✍️ Scribe (Gemini 2.0 Flash)│
│  Role: Researcher                 Role: Writer              │
│  Cost: FREE                       Cost: FREE                │
│  Tasks: Code Search               Tasks: Tutorial Writing   │
└─────────────────────────────────────────────────────────────┘
```

### Safety Features

- ✅ Max iterations per task (prevents infinite loops)
- ✅ Rate limiting (prevents API abuse)
- ✅ Cost estimation before execution
- ✅ Configurable exclusion patterns

### Language Rules

- 🇬🇧 Inter-agent communication: **English only**
- 🇯🇵 Final output (tutorials): **Japanese (です・ます style)**

## 🚀 Quick Start

### 1. Install mise (Version Manager)

```bash
# macOS / Linux
curl https://mise.run | sh

# Windows (PowerShell)
winget install mise
# or
scoop install mise

# Add to shell (bash/zsh)
echo 'eval "$(mise activate bash)"' >> ~/.bashrc
# or for zsh
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc
```

### 2. Add as Submodule

```bash
cd your-project
git submodule add https://github.com/kouiso/edu-creator.git
cd edu-creator
```

### 3. Setup Environment (mise + uv)

```bash
# Install Python 3.11 + uv via mise
mise install

# Create virtual environment & install dependencies
uv venv
uv sync
```

### 4. Create Config

Create `edu-config.yaml` in your project root:

```yaml
# edu-config.yaml
paths:
  src_dir: "src"
  output_dir: "material/tutorials"

chapters:
  - id: "day01"
    title: "環境構築の第一歩"
    subtitle: "〜プログラミングの「キッチン」を準備しよう〜"
    topics: ["Node.js", "npm", "VS Code"]
    target_dirs: ["src/app/", "package.json"]

  - id: "day02"
    title: "TypeScriptの基礎"
    subtitle: "〜お弁当箱に名前をつけよう〜"
    topics: ["変数", "型", "const/let"]
    target_dirs: ["src/lib/", "src/types/"]
```

### 5. Set Environment Variables

```bash
# .env.example をコピーして .env を作成
cp .env.example .env

# .env を編集してAPIキーを設定
# OPENAI_API_KEY=sk-your-key-here
# GOOGLE_API_KEY=AIza-your-key-here

# (Optional) 環境選択（dev/prod）
# EDU_ENV=dev または EDU_ENV=prod
```

または直接環境変数を設定：

```bash
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."

# 環境選択（オプション）
export EDU_ENV=dev   # 開発環境（高速・低コスト）
export EDU_ENV=prod  # 本番環境（高品質・完全検証）
```

### 6. Run

#### 開発環境（高速・低コスト）

```bash
# Activate virtualenv
source .venv/bin/activate

# 開発環境で実行（安価なモデル、緩い品質チェック）
EDU_ENV=dev python main.py --config ../edu-config.yaml --chapters 1

# または環境変数を設定してから実行
export EDU_ENV=dev
python main.py --config ../edu-config.yaml --chapters 1
```

#### 本番環境（高品質・完全検証）

```bash
# 本番環境で実行（高機能モデル、厳格な品質チェック）
EDU_ENV=prod python main.py --config ../edu-config.yaml --chapters 1
```

#### その他の実行例

```bash
# Dry run (cost estimate only)
python main.py --config ../edu-config.yaml --dry-run

# Generate all chapters
python main.py --config ../edu-config.yaml --chapters 30

# With reference examples (for quality benchmarking)
python main.py --config ../edu-config.yaml --chapters 1 \
  --examples material/sample/example1.pdf material/sample/example2.pdf

# With custom logging directory
python main.py --config ../edu-config.yaml --chapters 1 \
  --log-dir logs
```

### 6.5 Environment Configuration

edu-creator supports environment-specific configurations for different use cases:

| Environment | Config File | Use Case | Models | Quality Check |
|-------------|-------------|----------|--------|---------------|
| **dev** | `config/dev-config.yaml` | Development, Testing, Prompt Experiments | Gemini Flash (all agents) | Relaxed (faster, cheaper) |
| **prod** | `config/prod-config.yaml` | Production, Final Materials | GPT-5.2 (PM layer) + Gemini Flash (workers) | Strict (full validation) |
| **(none)** | User config only | Custom | User-defined | User-defined |

**How to select environment:**

```bash
# Set EDU_ENV environment variable
export EDU_ENV=dev   # or prod

# Or inline with command
EDU_ENV=dev python main.py --config ../edu-config.yaml --chapters 1
```

**Priority (later overrides earlier):**
1. `config/defaults.py` (Built-in defaults)
2. `config/{dev|prod}-config.yaml` (Environment config)
3. `edu-config.yaml` (User config - highest priority)

### 6.6 CLI Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--config, -c` | str | `edu-config.yaml` | Path to config file |
| `--chapters, -n` | int | `1` | Number of chapters to generate |
| `--dry-run` | flag | - | Show cost estimate without executing |
| `--examples` | list | - | Reference example files (e.g., `file1.pdf file2.pdf`) |
| `--log-dir` | str | `logs` | Directory to save verbose logs and task outputs |
| `--log-level` | str | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

**Examples:**
```bash
# Cost estimate only
python main.py --config edu-config.yaml --dry-run

# Generate with reference examples for quality
python main.py --config edu-config.yaml --chapters 1 \
  --examples material/sample/tkinter基礎知識ガイド.pdf material/sample/Python基礎知識ガイド.pdf

# Custom log directory with DEBUG logging
python main.py --config edu-config.yaml --chapters 5 --log-dir my-logs --log-level DEBUG
```

## 📝 Logging & Verbose Output

All generated chapters automatically save detailed logs to the `--log-dir` directory.

### Log Directory Structure

```
logs/
└── day01/
  ├── crew_output.log       # Full CrewAI verbose output (stdout + stderr)
  ├── task_research.md      # Scout's research findings
  ├── task_outline.md       # Commander's outline
  ├── task_write.md         # Scribe's tutorial draft
  ├── task_review.md        # Commander's quality review
  └── metadata.json         # Execution metadata
```

### Viewing Logs

```bash
tail -100 logs/day01/crew_output.log
cat logs/day01/task_research.md
cat logs/day01/metadata.json | jq .
```

## 🧠 Thinking Process Transparency

The verbose logging feature captures the complete thinking process of all agents during generation.

## 🛠️ Development

### Lint & Format (Ruff)

```bash
# Check linting
uv run ruff check .

# Auto-fix
uv run ruff check --fix .

# Format
uv run ruff format .
```

### Type Check (MyPy)

```bash
uv run mypy main.py
```

### Test

```bash
uv run pytest
```

## 📝 Configuration

### Full Config Example

```yaml
# Safety settings
safety:
  max_iterations: 3
  max_retries: 3
  max_rpm: 10
  timeout_seconds: 1800
  cost_confirmation_threshold_usd: 1.0

# Directory exclusions
exclusions:
  directories:
    - node_modules
    - .next
    - dist
    - coverage
    - edu-creator
  patterns:
    - "*.log"
    - "*.env*"
    - "*.py"

# LLM settings (モデルは.envで設定可能)
llm:
  commander_model: "gpt-5.2"         # OPENAI_MODEL環境変数で上書き可
  worker_model: "gemini-2.0-flash"   # GOOGLE_MODEL環境変数で上書き可
  commander_temperature: 0.2
  worker_temperature: 0.4

# Paths
paths:
  src_dir: "src"
  output_dir: "material/30days-curriculum"

# Custom metaphors (optional)
teaching:
  metaphors:
    Variable: "名前のついたお弁当箱"
    Function: "魔法のレンジ"
    Array: "学校のロッカー"

# Chapters
chapters:
  - id: "day01"
    title: "環境構築の第一歩"
    subtitle: "〜プログラミングの「キッチン」を準備しよう〜"
    topics: ["Node.js", "npm", "VS Code", "ターミナル基礎"]
    target_dirs: ["src/app/", "package.json", "tsconfig.json"]
```

## 💰 Cost Estimate

| Component | Model | Cost per Chapter |
|-----------|-------|------------------|
| Commander | GPT-5.2 | ~$0.15 |
| Scout | Gemini 2.0 Flash | FREE |
| Scribe | Gemini 2.0 Flash | FREE |
| **Total** | | **~$0.15/chapter** |

30 chapters ≈ $4.50 (mostly GPT-5.2 review costs)

## 📁 Project Structure

```
your-project/
├── edu-creator/            # This repo (submodule)
│   ├── .mise.toml          # Python version (mise)
│   ├── pyproject.toml      # Dependencies (uv) + Lint (ruff)
│   ├── main.py
│   └── README.md
├── edu-config.yaml         # Your config
├── src/                    # Your source code
└── material/               # Generated tutorials
    └── 30days-curriculum/
        ├── day01_環境構築の第一歩.md
        ├── day02_TypeScriptの基礎.md
        └── ...
```

## 🔧 Troubleshooting

### "No chapters defined in config!"

Make sure your `edu-config.yaml` has a `chapters` section.

### Rate limit errors

Reduce `max_rpm` in config or wait for the rate limit to reset.

### Infinite loop

The system has built-in `max_iterations` limit. If it seems stuck, check the verbose output.

### mise not found

Make sure you've added mise activation to your shell rc file:
```bash
echo 'eval "$(mise activate bash)"' >> ~/.bashrc
source ~/.bashrc
```

### uv command not found

Run `mise install` to install uv via mise, or install manually:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 📄 License

MIT
