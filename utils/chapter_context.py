"""
=============================================================================
Chapter Context (前章コンテキスト参照)
前章からの情報を抽出し、一貫性のある教材生成を支援

柱4: RAG（検索拡張生成）の簡易版
- ベクトルDBは不要
- 前章の「用語リスト」「メタファー」「構造」をJSON形式で渡す
- 用語の重複説明を防止
- メタファーの一貫性を保証
=============================================================================
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ChapterSummary:
    """章のサマリー情報"""

    chapter_id: str  # 例: "day01"
    title: str  # 例: "環境構築の第一歩"

    # 説明済み用語リスト
    terms_explained: list[str] = field(default_factory=list)

    # 使用メタファー
    metaphor_used: str = ""

    # 最終セクションの要約
    last_topic: str = ""

    # 紹介済みファイル
    code_files_introduced: list[str] = field(default_factory=list)

    # 紹介済みコマンド
    commands_introduced: list[str] = field(default_factory=list)

    # 章の概要（最初のセクションから抽出）
    overview: str = ""


@dataclass
class ChapterContext:
    """章の執筆に必要なコンテキスト"""

    # 前章のサマリーリスト
    previous_chapters: list[ChapterSummary] = field(default_factory=list)

    # 全章で説明済みの用語（重複防止用）
    already_explained_terms: list[str] = field(default_factory=list)

    # 一貫したメタファー（最新章から継承）
    consistent_metaphor: str = ""

    # 前章の最終トピック（接続用）
    last_topic: str = ""

    # 紹介済みの全ファイル
    all_introduced_files: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """プロンプトに挿入するコンテキスト文字列を生成"""
        parts = []

        # 説明済み用語
        if self.already_explained_terms:
            terms_str = ", ".join(self.already_explained_terms[:30])  # 最大30個
            parts.append(f"【既に説明済みの用語（再説明不要）】\n{terms_str}")

        # メタファー
        if self.consistent_metaphor:
            parts.append(f"【前章で使用したメタファー（一貫性を保つ）】\n{self.consistent_metaphor}")

        # 前章の最終トピック
        if self.last_topic:
            parts.append(f"【前章の最終トピック（接続を意識）】\n{self.last_topic}")

        # 紹介済みファイル
        if self.all_introduced_files:
            files_str = ", ".join(self.all_introduced_files[:20])  # 最大20個
            parts.append(f"【既に紹介済みのファイル】\n{files_str}")

        return "\n\n".join(parts)


def extract_explained_terms(content: str) -> list[str]:
    """説明済み用語を抽出

    形式: 用語（読み方：意味）または 用語（よみかた）

    Args:
        content: Markdownコンテンツ

    Returns:
        list[str]: 説明済み用語のリスト
    """
    terms = []

    # パターン1: 用語（読み方：意味）
    pattern1 = r"([A-Za-z][A-Za-z0-9\.\-]*|[ァ-ヶー]+|[一-龯]+)（[^）]+：[^）]+）"
    matches1 = re.findall(pattern1, content)
    terms.extend(matches1)

    # パターン2: 用語（よみかた）
    pattern2 = r"([A-Za-z][A-Za-z0-9\.\-]+)（[ぁ-んァ-ヶー]+）"
    matches2 = re.findall(pattern2, content)
    terms.extend(matches2)

    # パターン3: **用語** の形式で強調されているもの
    pattern3 = r"\*\*([A-Za-z][A-Za-z0-9\.\-]+)\*\*"
    matches3 = re.findall(pattern3, content)
    terms.extend(matches3)

    # 重複を除去して返す
    return list(dict.fromkeys(terms))


def extract_metaphor(content: str) -> str:
    """使用されているメタファーを抽出

    Args:
        content: Markdownコンテンツ

    Returns:
        str: メタファーの説明（見つからない場合は空文字）
    """
    # キッチンメタファーのパターン
    kitchen_patterns = [
        r"キッチン[^。]*メタファー",
        r"キッチン[^。]*例え",
        r"料理[^。]*例え",
        r"キッチン.*?のような",
    ]

    for pattern in kitchen_patterns:
        match = re.search(pattern, content)
        if match:
            return "キッチンメタファー"

    # その他のメタファーパターン
    metaphor_indicators = [
        r"「([^」]+)」のようなもの",
        r"「([^」]+)」に例える",
        r"([^。]+)に例えると",
    ]

    for pattern in metaphor_indicators:
        match = re.search(pattern, content)
        if match:
            return match.group(1) if match.groups() else match.group(0)

    return ""


def extract_last_section(content: str) -> str:
    """最終セクションの要約を抽出

    Args:
        content: Markdownコンテンツ

    Returns:
        str: 最終セクションの要約
    """
    # ## または ### の見出しを探す
    sections = re.split(r"\n#{2,3}\s+", content)

    if len(sections) >= 2:
        last_section = sections[-1]
        # 最初の段落を取得
        paragraphs = last_section.strip().split("\n\n")
        if paragraphs:
            # 最初の200文字を返す
            summary = paragraphs[0][:200]
            return summary.strip()

    return ""


def extract_files(content: str) -> list[str]:
    """紹介済みファイルを抽出

    Args:
        content: Markdownコンテンツ

    Returns:
        list[str]: ファイルパスのリスト
    """
    files = []

    # パターン1: // filepath: コメント
    pattern1 = r"//\s*filepath:\s*([^\n]+)"
    matches1 = re.findall(pattern1, content)
    files.extend([m.strip() for m in matches1])

    # パターン2: tree構造内のファイル
    pattern2 = r"[├└]──\s*([a-zA-Z0-9_\-\.]+\.[a-zA-Z]+)"
    matches2 = re.findall(pattern2, content)
    files.extend(matches2)

    # パターン3: バッククォート内のファイルパス
    pattern3 = r"`((?:src|app|components|lib|pages|prisma)/[a-zA-Z0-9_\-\./]+)`"
    matches3 = re.findall(pattern3, content)
    files.extend(matches3)

    # 重複を除去
    return list(dict.fromkeys(files))


def extract_commands(content: str) -> list[str]:
    """紹介済みコマンドを抽出

    Args:
        content: Markdownコンテンツ

    Returns:
        list[str]: コマンドのリスト
    """
    commands = []

    # パターン: $ で始まるコマンド
    pattern = r"\$\s+([a-zA-Z][a-zA-Z0-9\-_]*(?:\s+[a-zA-Z0-9\-_]+)?)"
    matches = re.findall(pattern, content)
    commands.extend(matches)

    # パターン: task コマンド
    task_pattern = r"task\s+([a-zA-Z][a-zA-Z0-9\-_]*)"
    task_matches = re.findall(task_pattern, content)
    commands.extend([f"task {m}" for m in task_matches])

    # 重複を除去
    return list(dict.fromkeys(commands))


def extract_title(content: str) -> str:
    """章のタイトルを抽出

    Args:
        content: Markdownコンテンツ

    Returns:
        str: タイトル
    """
    # # で始まる最初の見出しを探す
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    return ""


def extract_overview(content: str) -> str:
    """章の概要を抽出（最初のセクションから）

    Args:
        content: Markdownコンテンツ

    Returns:
        str: 概要
    """
    # 最初の ## セクションより前のテキストを取得
    parts = re.split(r"\n##\s+", content, maxsplit=1)
    if parts:
        # 最初の200文字を返す
        overview = parts[0].strip()
        # # タイトル行を除去
        overview = re.sub(r"^#\s+.+\n", "", overview)
        return overview[:200].strip()

    return ""


def extract_chapter_summary(chapter_path: Path) -> ChapterSummary:
    """章ファイルからサマリーを抽出

    Args:
        chapter_path: 章ファイルのパス

    Returns:
        ChapterSummary: 章のサマリー
    """
    content = chapter_path.read_text(encoding="utf-8")

    # chapter_idをファイル名から抽出（例: day01_環境構築.md → day01）
    chapter_id = chapter_path.stem.split("_")[0]

    return ChapterSummary(
        chapter_id=chapter_id,
        title=extract_title(content),
        terms_explained=extract_explained_terms(content),
        metaphor_used=extract_metaphor(content),
        last_topic=extract_last_section(content),
        code_files_introduced=extract_files(content),
        commands_introduced=extract_commands(content),
        overview=extract_overview(content),
    )


def build_context_for_chapter(chapter_num: int, output_dir: Path) -> ChapterContext:
    """指定章の執筆に必要なコンテキストを構築

    Args:
        chapter_num: 章番号（1から開始）
        output_dir: 出力ディレクトリ

    Returns:
        ChapterContext: 章のコンテキスト
    """
    if chapter_num <= 1:
        return ChapterContext()

    output_path = Path(output_dir)
    previous_summaries: list[ChapterSummary] = []

    # 前章までのファイルを検索
    for i in range(1, chapter_num):
        pattern = f"day{i:02d}_*.md"
        matches = list(output_path.glob(pattern))
        if matches:
            summary = extract_chapter_summary(matches[0])
            previous_summaries.append(summary)

    if not previous_summaries:
        return ChapterContext()

    # 全用語を収集
    all_terms: list[str] = []
    for summary in previous_summaries:
        all_terms.extend(summary.terms_explained)
    all_terms = list(dict.fromkeys(all_terms))  # 重複除去

    # 全ファイルを収集
    all_files: list[str] = []
    for summary in previous_summaries:
        all_files.extend(summary.code_files_introduced)
    all_files = list(dict.fromkeys(all_files))  # 重複除去

    # 最新章からメタファーと最終トピックを取得
    latest_summary = previous_summaries[-1]

    return ChapterContext(
        previous_chapters=previous_summaries,
        already_explained_terms=all_terms,
        consistent_metaphor=latest_summary.metaphor_used,
        last_topic=latest_summary.last_topic,
        all_introduced_files=all_files,
    )


def get_consistency_rules() -> str:
    """一貫性ルールのプロンプト文字列を取得

    Returns:
        str: 一貫性ルールの説明
    """
    return """
<consistency_rules>
以下のルールに従って、前章との一貫性を保ってください：

1. **用語の再説明禁止**: 「既に説明済みの用語」リストにある用語は、
   初出時の括弧書き説明（用語（読み方：意味））を省略してください。
   ただし、文脈上必要な場合は簡潔に言及しても構いません。

2. **メタファーの一貫性**: 前章で使用したメタファーを継続してください。
   例: キッチンメタファーを使っていた場合、同じメタファーを拡張して使用。

3. **接続の意識**: 「はじめに」セクションで前章との接続文を含めてください。
   例: 「前回は〇〇を学びました。今回は△△に進みます。」

4. **紹介済みファイルの参照**: 既に紹介したファイルを再度説明する場合は、
   「以前作成した〇〇ファイル」のように言及してください。
</consistency_rules>
"""


def format_context_for_prompt(context: ChapterContext) -> str:
    """プロンプト用にコンテキストをフォーマット

    Args:
        context: 章のコンテキスト

    Returns:
        str: フォーマットされたコンテキスト文字列
    """
    parts = ["<previous_context>"]
    parts.append(context.to_prompt_context())
    parts.append("</previous_context>")
    parts.append(get_consistency_rules())

    return "\n".join(parts)
