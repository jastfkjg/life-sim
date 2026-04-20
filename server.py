"""
Life Sim - Flask后端
调用LLM生成人生事件和选择
"""

import os
import json
import re
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# 支持的Provider
PROVIDERS = {
    "openai": {"env": "OPENAI_API_KEY", "base_url": None, "model_env": "OPENAI_MODEL", "default_model": "gpt-4o"},
    "minimax": {"env": "MINIMAX_API_KEY", "base_url": "https://api.minimax.chat/v1", "model_env": "MINIMAX_MODEL", "default_model": "MiniMax-M2.7"},
    "deepseek": {"env": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1", "model_env": "DEEPSEEK_MODEL", "default_model": "deepseek-chat"},
    "qwen": {"env": "DASHSCOPE_API_KEY", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model_env": "DASHSCOPE_MODEL", "default_model": "qwen-max"},
    "kimi": {"env": "KIMI_API_KEY", "base_url": "https://api.moonshot.cn/v1", "model_env": "KIMI_MODEL", "default_model": "kimi-k2.5"},
    "glm": {"env": "ZHIPU_API_KEY", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model_env": "ZHIPU_MODEL", "default_model": "glm-5"},
}


def get_llm_client():
    provider_name = os.getenv("PROVIDER", "openai").lower()
    
    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    config = PROVIDERS[provider_name]
    api_key = os.getenv(config["env"])
    
    if not api_key:
        raise ValueError(f"Missing API key for {provider_name}: {config['env']}")
    
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key)
    if config["base_url"]:
        client.base_url = config["base_url"]
    
    model = os.getenv(config["model_env"], config["default_model"])
    
    return client, model, provider_name


def call_llm(messages, temperature=0.9, max_tokens=1000):
    client, model, _ = get_llm_client()
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    return response.choices[0].message.content


def build_event_prompt(age, stats, history):
    labels = {
        "hp": "健康", "money": "金钱", "happiness": "快乐", "career": "事业",
        "social": "社交", "family": "家庭", "friends": "朋友", "love": "爱情",
        "loneliness": "孤独", "freedom": "自由", "sanity": "精神"
    }

    stats_text = " ".join([f"{labels[k]}:{v}" for k, v in stats.items()])
    
    # 近期历史（最近5条）
    recent = history[-5:] if history else ["刚成年"]
    history_text = "\n".join([f"- {h}" for h in recent])

    prompt = f"""你是一个人生模拟游戏的事件生成器。

当前角色状态：
- 年龄：{age}岁
- 属性：{stats_text}

最近经历：
{history_text}

请生成一个人生事件，要求：
1. 事件类型要多样（机会/挑战/意外/人际/选择等）
2. 要和当前状态有关（某属性过低时生成相关事件）
3. 考虑属性间的关联（如金钱低→健康差，孤独高→快乐低）
4. 每个选择要有权衡，没有绝对正确答案

输出严格的JSON格式：
{{
  "event": "事件描述，40-60字，要生动具体，有画面感",
  "choices": [
    {{"text": "选择1描述", "effects": {{"hp": 0, "money": 0, "happiness": 0, "career": 0, "social": 0, "family": 0, "friends": 0, "love": 0, "loneliness": 0, "freedom": 0, "sanity": 0}}}},
    {{"text": "选择2描述", "effects": {{"hp": 0, "money": 0, "happiness": 0, "career": 0, "social": 0, "family": 0, "friends": 0, "love": 0, "loneliness": 0, "freedom": 0, "sanity": 0}}}},
    {{"text": "选择3描述", "effects": {{"hp": 0, "money": 0, "happiness": 0, "career": 0, "social": 0, "family": 0, "friends": 0, "love": 0, "loneliness": 0, "freedom": 0, "sanity": 0}}}}
  ]
}}

注意：effects中0表示无变化，正数增加，负数减少。每个选择的effects总和应接近0（资源守恒）。
直接输出JSON，不要有任何前缀。"""

    return prompt


def build_history_prompt(age, gender, stats):
    gender_text = "男性" if gender == "male" else ("女性" if gender == "female" else "中性")

    prompt = f"""为一个{gender_text}角色生成一段初始背景故事，25-40字，要有特点。

当前状态：
- 年龄：{age}岁
- 健康: {stats.get('hp', 50)} 金钱: {stats.get('money', 50)} 快乐: {stats.get('happiness', 50)}
- 事业: {stats.get('career', 30)} 社交: {stats.get('social', 30)} 家庭: {stats.get('family', 20)}
- 朋友: {stats.get('friends', 30)} 爱情: {stats.get('love', 0)} 孤独: {stats.get('loneliness', 20)} 自由: {stats.get('freedom', 60)} 精神: {stats.get('sanity', 70)}

直接输出一段话作为背景介绍，不要JSON，不要前缀。"""

    return prompt


def parse_json_response(text):
    """从LLM输出中提取JSON"""
    # 尝试找 ```json ... ``` 或 ``` ... ```
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass
    
    # 尝试找 { ... }
    brace_match = re.search(r'\{[\s\S]*\}', text)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except:
            pass
    
    # 尝试直接解析
    try:
        return json.loads(text.strip())
    except:
        return None


@app.route("/")
def index():
    return send_file("index.html")

@app.route("/api/event", methods=["POST"])
def generate_event():
    data = request.json
    
    age = data.get("age", 18)
    stats = data.get("stats", {})
    history = data.get("history", [])

    prompt = build_event_prompt(age, stats, history)

    try:
        raw = call_llm([
            {"role": "system", "content": "你是一个游戏事件生成器，擅长创造有趣的人生选择场景。"},
            {"role": "user", "content": prompt}
        ], temperature=0.9, max_tokens=1000)

        result = parse_json_response(raw)

        if not result or "event" not in result or "choices" not in result:
            # Fallback
            result = {
                "event": "你面临一个人生的重要抉择...",
                "choices": [
                    {"text": "稳妥保守", "effects": {"hp": 0, "money": -5, "happiness": 5, "career": -5, "social": 0, "family": 0, "friends": 0, "love": 0, "loneliness": 0, "freedom": -10, "sanity": 0}},
                    {"text": "冒险一搏", "effects": {"hp": -5, "money": 15, "happiness": 0, "career": 10, "social": -5, "family": 0, "friends": 0, "love": 0, "loneliness": 5, "freedom": 10, "sanity": 0}},
                    {"text": "社交拓展", "effects": {"hp": 0, "money": -10, "happiness": 10, "career": 0, "social": 15, "family": 0, "friends": 10, "love": 0, "loneliness": -10, "freedom": 0, "sanity": 0}}
                ]
            }

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history", methods=["POST"])
def generate_history():
    data = request.json
    age = data.get("age", 18)
    gender = data.get("gender", "male")
    stats = data.get("stats", {})

    prompt = build_history_prompt(age, gender, stats)

    try:
        result = call_llm([
            {"role": "system", "content": "你是一个人生背景故事作家，擅长创作有深度的角色背景。"},
            {"role": "user", "content": prompt}
        ], temperature=0.9, max_tokens=200)

        return jsonify({"history": result.strip()})

    except Exception as e:
        return jsonify({"history": f"出生于普通家庭，从小镇来到大城市闯荡"})


if __name__ == "__main__":
    print("=" * 50)
    print("🎲 人生模拟器 - Life Sim Server")
    print("=" * 50)
    
    try:
        provider = os.getenv("PROVIDER", "openai")
        _, model, _ = get_llm_client()
        print(f"✅ LLM Provider: {provider} ({model})")
    except Exception as e:
        print(f"⚠️  Warning: {e}")
        print("   请检查 .env 文件中的 API key 配置")
    
    print("\n🌐 启动服务器: http://localhost:5000")
    print("   或者直接打开 index.html（需先启动 server.py）")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=5000, debug=True)