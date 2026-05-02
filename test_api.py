import os
from dotenv import load_dotenv
from anthropic import Anthropic

# .envファイル読み込み
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))
api_key = os.getenv('ANTHROPIC_API_KEY')

if not api_key:
    print('❌ APIキーが設定されていません')
    exit(1)

print('🔍 APIキーの形式チェック...')
print(f'長さ: {len(api_key)} 文字')
print(f'プレフィックス: {api_key[:15]}...')
print(f'有効な形式: {api_key.startswith("sk-ant-api03-")}')

print()
print('🔍 Anthropicクライアント初期化テスト...')
try:
    client = Anthropic(api_key=api_key)
    print('✅ クライアント初期化成功')

    # 最新の利用可能なモデルを確認
    print('🔍 最新の利用可能なモデル確認...')
    models_to_test = [
        'claude-3-5-sonnet-latest',
        'claude-3-5-haiku-latest',
        'claude-3-opus-latest',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307',
        'claude-3-opus-20240229',
        'claude-2.1',
        'claude-2.0'
    ]

    working_model = None
    for model in models_to_test:
        try:
            print(f'  テスト中: {model}...')
            response = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{'role': 'user', 'content': 'Hello'}]
            )
            print(f'  ✅ {model} は利用可能')
            working_model = model
            break
        except Exception as e:
            print(f'  ❌ {model} は利用不可: {str(e)[:50]}...')

    if working_model:
        print(f'\\n🎉 利用可能なモデル: {working_model}')
        print(f'\\n💡 app.py のモデル名を {working_model} に変更してください')
    else:
        print('\\n❌ 利用可能なモデルが見つかりません')

except Exception as e:
    print(f'❌ エラー: {e}')
    print(f'エラータイプ: {type(e).__name__}')