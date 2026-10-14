"""
OpenAI Structured Outputを使用したLLM呼び出しユーティリティ

参考: 実務プロジェクトのLLMチャットフロー実装
"""
import os
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from typing import TypeVar, Type, Optional, Dict, Any
import json

# 環境変数からAPIキーを取得（遅延初期化）
_client: Optional[OpenAI] = None

def get_client() -> OpenAI:
    """OpenAIクライアントを取得（遅延初期化）"""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEYが設定されていません。\n"
                "以下のいずれかの方法で設定してください:\n"
                "1. export OPENAI_API_KEY='your-api-key'\n"
                "2. .envファイルにOPENAI_API_KEY=your-api-keyを追加"
            )
        _client = OpenAI(api_key=api_key)
    return _client

T = TypeVar('T', bound=BaseModel)


def call_structured_llm(
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    model: str = "gpt-4o-2024-08-06",
    temperature: float = 0.7,
) -> T:
    """
    OpenAI Structured Outputを使用してLLMを呼び出し、型安全な出力を取得
    
    Args:
        system_prompt: システムプロンプト
        user_prompt: ユーザープロンプト
        response_model: Pydanticモデルクラス（レスポンスの型）
        model: 使用するモデル（デフォルト: gpt-4o-2024-08-06）
        temperature: 温度パラメータ（0.0-2.0）
    
    Returns:
        response_modelで指定した型のインスタンス
    
    Raises:
        Vlient = get_client()
        calidationError: レスポンスが型に適合しない場合
        Exception: API呼び出しが失敗した場合
    
    Example:
        >>> from schemas.tutorial_output import ChapterOutline
        >>> outline = call_structured_llm(
        ...     system_prompt="あなたはチュートリアル作成の専門家です。",
        ...     user_prompt="Next.jsの環境構築について、章のアウトラインを作成してください。",
        ...     response_model=ChapterOutline
        ... )
        >>> print(outline.title)
        "環境構築"
    """
    try:
        # OpenAI Structured Output APIを呼び出し
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_model,
            temperature=temperature,
        )
        
        # パース済みのレスポンスを取得
        parsed_response = completion.choices[0].message.parsed
        
        if parsed_response is None:
            raise ValueError("LLMのレスポンスをパースできませんでした")
        
        return parsed_response
    
    except ValidationError as e:
        print(f"❌ バリデーションエラー: {e}")
        raise
    except Exception as e:
        print(f"❌ API呼び出しエラー: {e}")
        raise


def call_structured_llm_with_fallback(
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    model: str = "gpt-4o-2024-08-06",
    temperature: float = 0.7,
    max_retries: int = 3,
) -> Optional[T]:
    """
    リトライ機能付きのStructured LLM呼び出し
    
    Args:
        system_prompt: システムプロンプト
        user_prompt: ユーザープロンプト
        response_model: Pydanticモデルクラス
        model: 使用するモデル
        temperature: 温度パラメータ
        max_retries: 最大リトライ回数
    
    Returns:
        成功時: response_modelで指定した型のインスタンス
        失敗時: None
    """
    for attempt in range(max_retries):
        try:
            return call_structured_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
                model=model,
                temperature=temperature,
            )
        except Exception as e:
            print(f"⚠️ リトライ {attempt + 1}/{max_retries}: {e}")
            if attempt == max_retries - 1:
                print(f"❌ 最大リトライ回数に達しました")
                return None
    
    return None


def validate_and_parse_json(
    json_string: str,
    response_model: Type[T]
) -> T:
    """
    JSON文字列をPydanticモデルでバリデーション・パース
    
    Args:
        json_string: JSON文字列
        response_model: Pydanticモデルクラス
    
    Returns:
        response_modelで指定した型のインスタンス
    
    Raises:
        ValidationError: バリデーションエラー
        json.JSONDecodeError: JSON形式が不正
    """
    try:
        # JSON文字列をPythonオブジェクトに変換
        data = json.loads(json_string)
        
        # Pydanticモデルでバリデーション
        return response_model.model_validate(data)
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON形式エラー: {e}")
        raise
    except ValidationError as e:
        print(f"❌ バリデーションエラー: {e}")
        raise


# ===== 使用例 =====

if __name__ == "__main__":
    from schemas.tutorial_output import ChapterOutline, ReviewResult
    
    # Example 1: ChapterOutlineを取得
    print("=== Example 1: ChapterOutline ===")
    outline = call_structured_llm(
        system_prompt="あなたはチュートリアル作成の専門家です。",
        user_prompt="Next.jsの環境構築について、章のアウトラインを作成してください。",
        response_model=ChapterOutline,
    )
    print(f"タイトル: {outline.title}")
    print(f"学習目標: {outline.learning_objectives}")
    
    # Example 2: ReviewResultを取得
    print("\n=== Example 2: ReviewResult ===")
    review = call_structured_llm(
        system_prompt="あなたはコードレビューの専門家です。",
        user_prompt="""
        以下のコードをレビューしてください：
        
        ```typescript
        const getData = () => {
          fetch("https://api.example.com/data");
        }
        ```
        """,
        response_model=ReviewResult,
    )
    print(f"承認: {review.approval}")
    print(f"コメント: {review.review_comment}")
    print(f"指摘事項: {len(review.issues)}件")
