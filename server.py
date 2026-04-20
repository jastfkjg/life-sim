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

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

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

    prompt = (
        f"你是一个人生模拟游戏的事件生成器。\n\n"
        f"当前角色状态：\n"
        f"- 年龄：{age}岁\n"
        f"- 属性：{stats_text}\n\n"
        f"最近经历：\n{history_text}\n\n"
        "你必须生成一个多样化的人生事件。事件类型包括：\n"
        "- 学业/教育：高考、考研、出国、留学、专业选择\n"
        "- 事业/工作：求职、升职、加薪、跳槽、创业、失业\n"
        "- 爱情/婚姻：邂逅、恋爱、表白、结婚、分手、离婚\n"
        "- 友情/社交：结交朋友、友情破裂、人际纠纷、社交活动\n"
        "- 家庭/亲情：与父母关系、生病照顾、家庭矛盾、亲子教育\n"
        "- 意外/突发：车祸、疾病、自然灾害、飞来横祸\n"
        "- 爱好/娱乐：培养兴趣、旅行、游戏、运动、追星\n"
        "- 人生抉择：重大决定、理想与现实、道德困境\n"
        "- 财务/投资：彩票中奖、投资亏损、意外收入、财务危机\n"
        "- 健康/生活：作息紊乱、身体报警、养成习惯、戒除恶习\n\n"
        "要求：\n"
        "1. 不要连续生成同一类型事件（查看最近经历避免重复）\n"
        "2. 选项数量由你决定（1-5个），根据事件复杂度灵活设置\n"
        "3. 每个选项描述要具体真实，不要泛泛而谈\n"
        "4. 选项可以只影响后续剧情，不一定有属性变化\n"
        "5. 选项可以有无关属性的（如只是休闲选择）\n"
        "6. 事件描述要50-80字，有画面感\n\n"
        "输出严格的JSON格式，不要有任何前缀或解释：\n"
        "{\"event\": \"事件描述...\",\n"
        " \"choices\": [\n"
        "   {\"text\": \"选项1具体描述\", \"effects\": {}},\n"
        "   {\"text\": \"选项2具体描述\", \"effects\": {}},\n"
        "   {\"text\": \"选项3具体描述\", \"effects\": {}}\n"
        " ]\n"
        "}"
    )

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
                "event": "大学毕业季，你收到了几家公司的offer，面临选择...",
                "choices": [
                    {"text": "接受北京某互联网公司offer，薪资高但加班多", "effects": {"money": 20, "happiness": -5, "loneliness": 10}},
                    {"text": "留在家乡小城，接受稳定的国企工作", "effects": {"family": 15, "money": 5, "career": -10}},
                    {"text": "去上海闯荡，追求更大发展机会", "effects": {"career": 15, "money": 10, "loneliness": 15}}
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