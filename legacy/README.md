# legacy/

旧版（CrewAI）の部品の退避。`docs/legacy-audit.md` の方針で、生きている道からは読まれない物をここに移す。

| 移した物 | 元の場所 | 何をしていた物か |
|---|---|---|
| `skills/` | `skills/` | 旧版の skill 5 つ（`tutorial-writing` など）。`template_loader.load_skill` が読む対象だった |
| `templates/` | `templates/` | 旧版の Jinja2 のプロンプト 2 つ。`template_loader` が読む対象だった |
| `utils/template_loader.py` | `utils/template_loader.py` | 上の 2 つを読む道具。呼ぶ物が無くなっていた |
| `test_integration.py` | `test_integration.py` | 上の 3 つを試すだけのファイル。pytest の集める `tests/` の外にあって回っていなかった |

書き方の決まりの正本は `educreator/agent-skill/` の 1 か所（`docs/skill-integration.md`）。
旧版が使うプロンプトは `prompt/` に残る（`edu-creator-legacy` が import するため。A11 で旧版ごとここに移す予定）。
