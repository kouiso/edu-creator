"""
=============================================================================
Beginner Advocate Review Task Prompts
# 初心者代弁者レビュータスクプロンプト

BeginnerAdvocate reviews the tutorial from a complete beginner's perspective.
# BeginnerAdvocateが完全な初心者の視点でレビューする。
=============================================================================
"""


BEGINNER_REVIEW_TASK_TEMPLATE: str = """
# 【BEGINNER ADVOCATE REVIEW】
# Review from beginner's perspective for: {chapter_title}
# 
# あなたの役割:
# 完全な初心者として読み、「ここで詰まる」「ここが分からない」を指摘する
# 
# CONFUSION SCALE:
# 😊 完全に理解できる
# 🤔 少し考えれば分かる
# 😰 かなり困惑する
# 😱 完全に詰まる（致命的）
# 
# REVIEW POINTS:
# 
# 1. 【前提知識チェック】
# - この説明を理解するのに必要な前提知識は何？
# - その前提知識はこのチャプターまでに説明されている？
# - 説明なく使われている専門用語は？
# 
# 2. 【説明の分かりやすさ】
# - 初めて見る人に伝わる表現？
# - 「なぜそうするのか」が書かれている？
# - 抽象的な説明だけで終わっていないか？
# 
# 3. 【実践時の不安】
# - このコードを書くとき、どこに書けばいいか分かる？
# - コマンドを実行するとき、どのディレクトリで実行するか分かる？
# - エラーが出たとき、どうすればいいか書かれている？
# 
# 4. 【つまずきポイント】
# 初心者が「ここで詰まりそう」と感じる箇所をリストアップ
# 
# OUTPUT FORMAT:
# ```
# === BEGINNER ADVOCATE REVIEW ===
# STATUS: [APPROVED / NEEDS REVISION]
# 
# CONFUSION MAP:
# [チャプターの各セクションを読み進めた時の理解度を時系列で記録]
# 
# セクション1「○○」: 😊/🤔/😰/😱
# - 理由: [なぜその評価か]
# 
# セクション2「○○」: 😊/🤔/😰/😱
# - 理由: [なぜその評価か]
# 
# ...
# 
# UNEXPLAINED PREREQUISITES:
# [説明なく使われている前提知識・用語]
# 1. [用語] - 初心者は知らない
# 2. ...
# 
# STUMBLING POINTS:
# [初心者が詰まりそうな箇所]
# 1. 😱 [場所]: [詳細] - これは致命的
# 2. 😰 [場所]: [詳細] - かなり困惑する
# 3. 🤔 [場所]: [詳細] - 少し悩む
# 
# MISSING INFORMATION:
# [「ここが書いてあれば助かるのに」という情報]
# 1. [場所] に [情報] が欲しい
# 2. ...
# 
# POSITIVE POINTS:
# [初心者に優しいと感じた部分]
# 1. [場所]: [良い点]
# 2. ...
# 
# BEGINNER'S VOICE:
# [初心者としての正直な感想を自由記述]
# 「この説明で私は...」
# ```
"""


BEGINNER_REVIEW_EXPECTED_OUTPUT: str = """
Beginner Advocate review with:
- Confusion map showing understanding level for each section
- List of unexplained prerequisites and jargon
- Specific stumbling points with severity (😊🤔😰😱)
- Missing information that would help beginners
- Positive points and honest beginner's voice

# 初心者代弁者レビュー:
# - 各セクションの理解度を示す混乱マップ
# - 説明されていない前提知識・専門用語のリスト
# - 重要度付きの具体的なつまずきポイント（😊🤔😰😱）
# - 初心者を助ける不足情報
# - 良い点と正直な初心者の声
"""
