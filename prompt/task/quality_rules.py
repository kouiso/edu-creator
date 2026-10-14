"""
=============================================================================
Quality Control Rules (品質管理ルール)
教材作成時に必ず守るべき品質基準

これは redmine-clone での失敗と、サンプルPDFの成功パターンから
導出した絶対ルールです。
=============================================================================
"""

QUALITY_RULES: str = r"""
絶対禁止ワード（AIの「手抜き」検出）

以下の表現を使うことは「ステップを飛ばす」ことと同義です。全て禁止です：

禁止ワード一覧:
  - 「同様に」「同じように」「同じ方法で」→ 具体的に全て書く
  - 「残りも」「その他も」「以下も」→ 全ファイル明示
  - 「以下略」「省略」「...」→ 完全に書く
  - 「簡単です」「すぐできます」「簡単に」→ 客観的な手順で説明
  - 「おなじ」「一緒」→ 具体的に

良い例:
「package.jsonと同様に、tsconfig.jsonも修正します。
以下の内容を新規作成してください：」
+ [完全なtsconfig.jsonコード]

悪い例:
「package.jsonと同様に、他のファイルも修正してください。」

---

コードブロック長ルール

【絶対ルール】コードブロック上限: 25行

もし25行を超えるコードが必要な場合:
1. ステップを分割する（Step 1, Step 2, ...）
2. 各ステップは1ファイル変更まで
3. 各コードブロック直後に「確認ポイント」を追加

【絶対ルール】全コードブロックに filepath: コメント

悪い例:
```typescript
export const Button = () => {
  return <button>Click</button>;
};
```

良い例:
```typescript
// filepath: src/components/Button.tsx
export const Button = () => {
  return <button>Click</button>;
};
```

【絶対ルール】日本語コメント必須（コード内に日本語説明）

悪い例:
```typescript
const [count, setCount] = useState(0);
```

良い例:
```typescript
// clicker数を保存する状態管理（初期値: 0）
const [count, setCount] = useState(0);
```

【絶対ルール】全コードブロック直後に「確認ポイント」

各コードブロックの直後に、以下のフォーマットで実行結果や確認方法を明記：

```
確認ポイント:
- ファイルを保存した
- $ npm run dev でエラーが出ていない
- ブラウザをリロードして「Hello World」が表示される
```

---

段落・テキスト長ルール

【絶対ルール】段落上限: 3文

1つの段落は最大3文。4文以上になる場合:
- 2つの段落に分割する
- または表/リスト形式に変換する

悪い例（4文）:
「Dockerとはアプリケーションを「箱詰め」にして、どのコンピュータでも同じように動かす仕組みです。
ローカル環境とサーバー環境で「この環境の設定が違う」という問題が発生することがあります。
Dockerを使うと、この「環境の違い」を無くすことができます。
その結果、開発効率が大幅に向上します。」

良い例（分割）:
「Dockerとはアプリケーションを『箱詰め』にして、どのコンピュータでも同じように動かす仕組みです。
ローカル環境とサーバー環境で『この環境の設定が違う』という問題が発生することがあります。

Dockerを使うと、この『環境の違い』を無くすことができるので、開発効率が大幅に向上します。」

【絶対ルール】新概念は必ず括弧書き＋例え話付き

技術用語の初出時:

悪い例:
「npmはパッケージマネージャーです。」

良い例:
「npm（エヌピーエム：Node.jsのパッケージ管理ツール）は、『図書館の司書さん』のようなもので、
必要なプログラムの部品（パッケージ）を自動的に探して、あなたのプロジェクトに入れてくれます。」

---

ビジュアル化ルール

【必須】1日あたり最低4個の表

比較・オプション・概念整理は必ず表形式で提示：

例:
```
| 項目 | npm | pnpm |
|------|------|-------|
| 速度 | 普通 | 高速 |
| インストール | 簡単 | 簡単 |
```

【必須】1日あたり最低1個のMermaid図

フロー・アーキテクチャ・関係性は図で示す：

例:
```mermaid
flowchart LR
  A[ブラウザ] -->|リクエスト| B[Next.js]
  B -->|クエリ| C[データベース]
  C -->|データ| B
  B -->|HTML| A
```

【推奨】スクリーンショット位置指定（1日3箇所以上）

実行画面やエラー画面が必要な箇所に位置指定コメント：

```
【スクリーンショット】ブラウザに「Hello World」が表示された画面
```

---

ステップ粒度ルール

【絶対ルール】1ステップ = 3〜7分（見た目には「Step 1」のような形式）

悪い例:
「Step 1: プロジェクトセットアップ（30分）」
← 大きすぎる。分割する。

良い例:
「Step 1: Node.jsをインストール（5分）」
「Step 2: npmでプロジェクト初期化（3分）」
「Step 3: package.jsonを確認（4分）」

【絶対ルール】1ファイル = 1ステップまで

1つのステップで変更するファイルは最大1個：

悪い例:
「Step 5: 複数ファイル修正
- package.json を修正
- tsconfig.json を修正
- next.config.mjs を修正」
← 3ファイル同時修正は禁止。3ステップに分割。

良い例:
「Step 5: package.json を修正（3分）」
「Step 6: tsconfig.json を修正（4分）」
「Step 7: next.config.mjs を修正（3分）」

【推奨】1日 = 7〜12ステップ

日中の各ステップの時間を合計して、1日 = 60〜90分程度を目安に。

---

1日あたりの制約

| 項目 | 最小 | 最大 | 目安 |
|------|------|------|------|
| ステップ数 | 7 | 12 | 9-10 |
| 新概念数 | 0 | 3 | 1-2 |
| 新規ファイル数 | 0 | 5 | 2-3 |
| コードブロック数 | 3 | - | 6-8 |
| 表の数 | 4 | - | 4-5 |
| Mermaid図 | 1 | - | 1-2 |

---

ディレクトリ構造の提示方法

ファイル構造を説明するときは、「tree」コマンド風の表記を使用：

例:
```
project/
├── src/
│   ├── app/
│   │   └── page.tsx    # トップページコンポーネント
│   ├── components/
│   │   └── Button.tsx  # 再利用可能なボタン
│   └── lib/
│       └── prisma.ts   # DB接続設定
├── prisma/
│   └── schema.prisma   # DBスキーマ定義
└── package.json        # プロジェクト情報
```

各ファイルに日本語コメントを付けて役割を説明。

---

品質チェック方法

執筆後、必ず以下のスクリプトで検証：

```bash
# 全チェック実行（推奨）
./scripts/check_quality.sh material/30days-curriculum/

# 個別チェック
python3 scripts/check_no_skip.py <ファイル>          # 禁止ワード
python3 scripts/check_step_length.py <ファイル>      # コード・段落長
python3 scripts/check_visualization.py <ファイル>    # ビジュアル要素
```

---

チェックリスト（各Day完成時）

- [ ] コードブロック全て25行以下
- [ ] 全ブロックに「// filepath:」コメント
- [ ] 全ブロック後に「確認ポイント」
- [ ] 段落3文以下（超過ない）
- [ ] 表4個以上
- [ ] Mermaid図1個以上
- [ ] スクショ位置3箇所以上
- [ ] 新概念に例え話あり
- [ ] 「同様に」「以下略」なし
- [ ] ステップ7〜12個
- [ ] 各ステップ3〜7分
- [ ] tree構造を正しく使用

品質チェックスクリプトで全て合格するまで完成とは見なしません。

---

コード完全性ルール（ABSOLUTE - NO EXCEPTIONS）

【絶対ルール】コードは完全でなければならない

禁止パターン（コード内コメント）:
  - "// ...残りは同じ"
  - "// 省略"
  - "// etc"
  - "// 以下略"
  - "/* ... */"
  - "// ..."（JSXスプレッド以外）

禁止パターン（分割表示）:
  - "パート1/2"、"パート2/2" 形式の分割
  - "前半"、"後半" の分割
  - "続き" としてコードを分ける

正しいアプローチ:
  1. 25行を超える場合は、機能単位で複数のコードブロックに分割
  2. 各コードブロックの間に説明文を入れる
  3. 各コードブロックは単独でコピペ実行可能であること

例（悪い）:
```typescript
// パート1/3
import { ... } from '...';
// ...残りの import は同じ
```

例（良い）:
```typescript
// filepath: src/components/Button.tsx
// Step 1: インポート文
import { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
```

続けて次のコードブロック:
```typescript
// filepath: src/components/Button.tsx
// Step 2: 型定義
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary';
}
```

---

技術スタックルール（MANDATORY - THIS PROJECT USES shadcn/ui）

【絶対ルール】shadcn/ui + Tailwind CSS を使用。Material-UI (MUI) 禁止。

禁止インポート（使用した場合は品質チェック失敗）:
  - @mui/material
  - @mui/icons-material
  - @mui/system
  - @emotion/react
  - @emotion/styled

必須インポート:
  - @/components/ui/* (shadcn/uiコンポーネント)
  - lucide-react（アイコン）
  - tailwindクラスによるスタイリング

コンポーネント対応表:

| MUI (禁止) | shadcn/ui (使用すべき) |
|------------|----------------------|
| Box | div + className |
| Typography | p, h1-h6 + className |
| TextField | Input from @/components/ui/input |
| Button | Button from @/components/ui/button |
| Card | Card from @/components/ui/card |
| Table | Table from @/components/ui/table |
| Dialog | Dialog from @/components/ui/dialog |
| Select | Select from @/components/ui/select |
| Chip | Badge from @/components/ui/badge |
| CircularProgress | Loader2 from lucide-react + animate-spin |
| IconButton | Button variant="ghost" size="icon" |
| Alert | Alert from @/components/ui/alert |
| Tabs | Tabs from @/components/ui/tabs |

スタイリング例:

悪い例（MUI）:
```typescript
import { Box, Typography, Button } from '@mui/material';

<Box sx={{ display: 'flex', gap: 2 }}>
  <Typography variant="h1">タイトル</Typography>
  <Button variant="contained">送信</Button>
</Box>
```

良い例（shadcn/ui + Tailwind）:
```typescript
import { Button } from '@/components/ui/button';

<div className="flex gap-4">
  <h1 className="text-2xl font-bold">タイトル</h1>
  <Button>送信</Button>
</div>
```

---

フォーム実装ルール（MANDATORY - react-hook-form + zod）

【絶対ルール】全てのフォームは react-hook-form + zod で実装

禁止パターン（useState による個別管理）:
```typescript
const [name, setName] = useState('');
const [email, setEmail] = useState('');

const handleSubmit = (e) => {
  e.preventDefault();
  // name, email を使用
};
```

必須パターン（react-hook-form + zod）:
```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

// スキーマ定義
const formSchema = z.object({
  name: z.string().min(1, '名前は必須です'),
  email: z.string().email('有効なメールアドレスを入力'),
});

type FormData = z.infer<typeof formSchema>;

// フォーム初期化
const form = useForm<FormData>({
  resolver: zodResolver(formSchema),
  defaultValues: { name: '', email: '' },
});

// 送信ハンドラ
const onSubmit = (data: FormData) => {
  console.log(data);
};
```

利点を必ず説明:
  - 型安全（TypeScriptとの統合）
  - 自動バリデーション
  - エラーメッセージの一元管理
  - 再レンダリングの最適化

---

コード行長ルール（PDF互換性）

【絶対ルール】コードブロック内の1行は最大65文字

理由: PDFに変換した際、65文字を超える行は途中で切れてしまう

対応方法:

1. 長いインポート文は複数行に分割:
```typescript
// 悪い（PDFで切れる）
import { Table, TableBody, TableCell } from '@/components/ui/table';

// 良い
import {
  Table,
  TableBody,
  TableCell,
} from '@/components/ui/table';
```

2. 長いオブジェクトは複数行に分割:
```typescript
// 悪い
const user = { id: 1, name: '田中', email: 'a@b.com' };

// 良い
const user = {
  id: 1,
  name: '田中',
  email: 'a@b.com',
};
```

3. 長い文字列は変数に分割:
```typescript
// 悪い
throw new Error('ユーザーが見つかりません。確認してください。');

// 良い
const msg = 'ユーザーが見つかりません。' +
  '確認してください。';
throw new Error(msg);
```

---

品質検証要件（MANDATORY）

【絶対的な要件】
生成されたマークダウンは、以下の自動品質チェックスクリプトで
必ず100%成功（全項目PASS）しなければなりません：

  ./scripts/check_quality.sh material/30days-curriculum/<生成ファイル>

このスクリプトは3つの検証を実行します：

1. check_no_skip.py
   - 「同様に」「以下略」などの禁止ワードが0個
   - PASS要件：禁止ワード0個

2. check_step_length.py
   - コードブロック25行以下
   - 段落3文以下
   - PASS要件：超過ファイル0個

3. check_visualization.py
   - 表4個以上
   - Mermaid図1個以上
   - PASS要件：下回り項目0個

【このルールの意味】
これらのスクリプトが「PASS」することは、上記のルール全てが
自動で検証されたことを意味します。
スクリプトがFAILすることは、ルール違反を意味します。

【必ず確認すること】
生成後、必ずこのコマンドを実行して全てPASSを確認してください：
```bash
./scripts/check_quality.sh material/30days-curriculum/
```

1つでもFAILがあれば、その指摘に従って修正してください。
FIXされない限り、教材は完成とは見なされません。

【コスト最適化のため】
最初から「スクリプト100%PASS」を目指して執筆してください。
修正ループが減ることで、生成にかかるコストと時間が削減されます。

---

例外を認める方法（我思うゆえに我あり）

どうしても品質ルールに従えない（従うべきではない）場合は、
その理由をマークダウンコメントで記述してください。

【書き方】
```markdown
<!-- quality-exception: 理由をここに記述 -->

<!-- Example: このステップは複雑な概念なので、説明を厚くするため
     に4文にしました。他のステップは全て3文で統一しています。 -->
このステップでは、複雑なコンセプトを説明します。...
...
...
....
```

【ルール】
1. 必ず `<!-- quality-exception: ` で始める
2. 技術的な判断理由を日本語で明記する
3. 「～だから仕方ない」ではなく「～という設計上の理由」を書く
4. 例外は最小限（1Day に2-3個まで）

【良い例外理由】
- 「このコンセプトは4文で説明しないと完全な理解ができません」
- 「複数ファイルの比較表示が必須なため、このステップで2ファイル変更します」
- 「ビジュアル要素は3個のみです。理由：このDay は概念説明が中心で、
   実装は次Day のため」
- 「このコマンドの出力が1000行のため、重要部分のみ抜粋してコメント付き
   で説明しています」

【悪い例外理由】
- 「忙しいので省略しました」
- 「AIの限界です」
- 「～だから仕方ない」

【スクリプトの対応】
コメント記述がある場合でも、スクリプトは FAIL を報告します。
ただし、このコメントを見ることで人間の判断者が「この例外は正当」
と判断できます。
"""
