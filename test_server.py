#!/usr/bin/env python3
"""最小化检索测试服务器 - 支持对比和LLM生成"""
import sys
sys.path.insert(0, '.')

import asyncio
import os
import json
import uuid
import re
from datetime import datetime
from pipeline.retrieval import RetrievalPipeline
from core.llm_client import LLMClient
from core.prompt_builder import PromptBuilder, PromptConfig, ConsultationContext
from db.postgres_client import get_db_direct, init_db, DialogueSession, SessionSummary, Feedback, SafetyLog, Memory, UserProfile, User
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Retrieval Test")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

retrieval = RetrievalPipeline()
llm = LLMClient(provider="deepseek")
minimax_llm = LLMClient(provider="minimax")
prompt_builder = PromptBuilder()

# 初始化数据库
init_db()


class PersistentSessionStore:
    """本地 dict 缓存 + PostgreSQL 持久化"""

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def _load(self, session_id: str) -> dict | None:
        if session_id in self._cache:
            return self._cache[session_id]
        db = get_db_direct()
        row = db.query(DialogueSession).filter_by(session_id=session_id).first()
        db.close()
        if row:
            data = {"session_id": row.session_id, "turns": row.turns or [], "scenario": row.scenario}
            self._cache[session_id] = data
            return data
        return None

    def _save(self, session_id: str, data: dict):
        self._cache[session_id] = data
        db = get_db_direct()
        row = db.query(DialogueSession).filter_by(session_id=session_id).first()
        if row:
            row.turns = data.get("turns", [])
            row.scenario = data.get("scenario", "consultation")
            row.updated_at = datetime.utcnow()
        else:
            db.add(DialogueSession(session_id=session_id, turns=data.get("turns", []), scenario=data.get("scenario", "consultation")))
        db.commit()
        db.close()

    def __contains__(self, key: str) -> bool:
        return key in self._cache or self._load(key) is not None

    def __getitem__(self, key: str) -> dict:
        data = self._load(key)
        if data is None:
            raise KeyError(key)
        return data

    def __setitem__(self, key: str, value: dict):
        self._save(key, value)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def reset(self, session_id: str, scenario: str):
        data = {"session_id": session_id, "turns": [], "scenario": scenario}
        self._save(session_id, data)


sessions = PersistentSessionStore()


@app.post("/api/dialogue")
def dialogue(request: dict):
    """
    多轮对话接口：Oscar 主动发起，用户回复，持续多轮。
    第一轮：Oscar 先说开场白；后续轮次：带历史生成。
    """
    q = request.get("query", None)  # 第一轮为空
    scenario = request.get("scenario", "consultation")
    provider = request.get("provider", "minimax")
    session_id = request.get("session_id")
    is_first = request.get("is_first", False)  # 是否第一轮（Oscar开场）

    # 选 LLM
    llm_client = minimax_llm if provider == "minimax" else llm

    # 创建或获取会话
    if session_id and session_id in sessions:
        session = sessions[session_id]
        turns = session["turns"]
    else:
        session = None
        session_id = None
        turns = []

    # 安全检查（用户消息才检查）
    if q and not is_first:
        safety = _check_safety(q)
        if safety:
            risk_level, matched = safety
            _log_safety(session_id or "unknown", q, risk_level)
            safety_msg = _build_safety_response(risk_level)
            # 记录到 turns
            if session_id:
                sessions[session_id]["turns"].append({"speaker": "user", "message": q})
                sessions[session_id]["turns"].append({"speaker": "oscar", "message": safety_msg})
            return {
                "session_id": session_id,
                "scenario": scenario,
                "oscar": safety_msg,
                "turn_count": len(turns) // 2 + 1,
                "safety_alert": risk_level
            }

    # 构建对话上下文（带历史）
    dialogue_context = _build_dialogue_context(turns)

    # 检测用户语言：扫描历史中的用户消息 + 当前query，默认中文
    user_lang = _detect_user_language(turns, q)
    lang_config = "chinese" if user_lang == "chinese" else "english"

    # 6 轮后提示 Oscar 适时邀请评估（不做强制标记）
    user_turn_count = len([t for t in turns if t.get("speaker") == "user"])
    evaluation_invited = user_turn_count >= 6

    # 检索相关文档
    retrieved = []
    if q:
        try:
            raw_results = retrieval.retrieve(q, expand_context=True, context_window=2)
            retrieved = _format_results(raw_results)
        except Exception:
            retrieved = []

    # 检索用户记忆
    memories = []
    if q and session_id:
        memories = _retrieve_memories("anonymous", q, top_k=3)

    # 构建 prompt
    system_prompt, user_prompt = prompt_builder.build_consultation_prompt(
        query=q or "(开场)",
        context=ConsultationContext(
            user_id="user",
            session_id=session_id or "new",
            current_topic=None,
            consultation_phase=_infer_phase(turns),
            user_emotional_state=None,
            techniques_used=[],
            key_insights=[],
            previous_turns=turns,
            scenario=scenario,
            evaluation_invited=evaluation_invited
        ),
        retrieved_docs=retrieved,
        config=PromptConfig(
            persona_enabled=True,
            skills_enabled=True,
            fewshot_enabled=False,
            tone="direct",
            response_length="short",
            language=lang_config,
            scenario=scenario
        )
    )

    # 填充对话上下文到 user_prompt
    memory_section = ""
    if memories:
        mem_lines = [f"- {m['content']}" for m in memories]
        memory_section = f"\n## 相关记忆（来自历史对话）\n" + "\n".join(mem_lines) + "\n"

    if dialogue_context:
        # 把历史注入 user_prompt 前面
        user_prompt = f"## 对话历史\n{dialogue_context}{memory_section}\n\n## 当前输入\n{q or '(Oscar, please respond)'}"
    else:
        user_prompt = "Hi"

    try:
        oscar_response = asyncio.run(
            llm_client.generate(system_prompt=system_prompt, user_message=user_prompt)
        )
    except Exception as e:
        oscar_response = f"LLM Error: {str(e)}"

    # 生成 session_id
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())[:8]
        sessions[session_id] = {"turns": [], "scenario": scenario}

    # 记录
    if q:
        sessions[session_id]["turns"].append({"speaker": "user", "message": q})
    sessions[session_id]["turns"].append({"speaker": "oscar", "message": oscar_response})

    return {
        "session_id": session_id,
        "scenario": scenario,
        "oscar": oscar_response,
        "turn_count": len(sessions[session_id]["turns"]) // 2
    }


def _build_dialogue_context(turns: list) -> str:
    """构建对话历史字符串"""
    if not turns:
        return ""
    lines = []
    for t in turns:
        speaker = "Oscar" if t.get("speaker") == "oscar" else "Client"
        lines.append(f"**{speaker}**: {t.get('message', '')}")
    return "\n".join(lines)


def _infer_phase(turns: list) -> str:
    """根据对话轮次推断当前相位"""
    count = len([t for t in turns if t.get("speaker") == "user"])
    if count == 0:
        return "greeting"
    elif count < 3:
        return "problem_exploration"
    elif count < 6:
        return "focusing"
    elif count < 10:
        return "logical_exploration"
    else:
        return "closing"


def _detect_user_language(turns: list, current_query: str = None) -> str:
    """检测用户语言：扫描历史用户消息 + 当前query，中文多则中文，默认中文"""
    all_text = []
    for t in turns:
        if t.get("speaker") == "user":
            all_text.append(t.get("message", ""))
    if current_query:
        all_text.append(current_query)
    if not all_text:
        return "chinese"  # 默认中文
    combined = " ".join(all_text)
    chinese_chars = sum(1 for c in combined if '\u4e00' <= c <= '\u9fff')
    total = len(combined)
    return "chinese" if total > 0 and chinese_chars / total > 0.3 else "english"

class QueryRequest(BaseModel):
    query: str
    use_llm: bool = True
    scenario: str = "consultation"
    phase: str = "problem_exploration"
    provider: str = "deepseek"
    session_id: str = None


# ============ Session 管理 ============

@app.post("/api/session")
def create_session(request: dict):
    """创建新会话"""
    import uuid
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "turns": [],
        "phase_history": [],
        "scenario": request.get("scenario", "consultation")
    }
    return {"session_id": session_id}


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    """获取会话信息"""
    if session_id not in sessions:
        return {"error": "session not found"}
    return {
        "session_id": session_id,
        "turns": sessions[session_id]["turns"],
        "phase_history": sessions[session_id]["phase_history"]
    }


@app.post("/api/reset_session")
def reset_session(request: dict):
    """重置会话"""
    session_id = request.get("session_id")
    if session_id and session_id in sessions:
        sessions[session_id] = {
            "turns": [],
            "phase_history": [],
            "scenario": sessions[session_id].get("scenario", "consultation")
        }
    return {"ok": True}


@app.post("/api/session/summarize")
def summarize_session(request: dict):
    """
    生成对话摘要。
    分析对话历史，提取：主题、关键问题、洞察、矛盾、回避时刻等。
    """
    session_id = request.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    if session_id not in sessions:
        return {"error": "session not found"}

    session_data = sessions.get(session_id)
    if not session_data:
        return {"error": "session not found"}
    turns = session_data.get("turns", [])
    if not turns:
        return {"error": "no turns to summarize"}

    # 构建对话文本供 LLM 分析
    dialogue_text = _build_dialogue_context(turns)

    # 构造摘要 prompt
    summary_prompt = f"""请分析以下哲学咨询对话，生成结构化摘要。

## 对话内容
{dialogue_text}

## 输出格式（严格按 JSON 返回，不要有其他内容）
{{
    "main_topic": "本次对话的核心主题（一句话）",
    "key_questions": ["探索的关键问题1", "关键问题2", "关键问题3"],
    "user_insights": ["用户的洞察1", "用户的洞察2"],
    "contradictions_found": ["发现的逻辑矛盾1", "矛盾2"],
    "avoidance_moments": ["用户回避的时刻描述1", "回避2"],
    "unresolved_questions": ["未解决的悬而未决的问题"],
    "homework": ["建议的后续思考或行动1"],
    "next_session_focus": "下次来访的建议主题"
}}
"""

    # 调用 LLM 生成摘要
    try:
        summary_text = asyncio.run(
            minimax_llm.generate(
                system_prompt="You are a philosophical consultation analyst. Output only valid JSON.",
                user_message=summary_prompt
            )
        )
        # 提取 JSON
        summary_json = _extract_json(summary_text)
        summary_json["session_id"] = session_id
        summary_json["dialogue_history"] = turns

        # 存入数据库
        db = get_db_direct()
        existing = db.query(SessionSummary).filter_by(session_id=session_id).first()
        if existing:
            # 更新
            for k, v in summary_json.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
        else:
            # 新建
            import time
            summary_id = str(uuid.uuid4())[:8]
            s = SessionSummary(
                id=summary_id,
                session_id=session_id,
                user_id="anonymous",
                main_topic=summary_json.get("main_topic", ""),
                key_questions=summary_json.get("key_questions", []),
                user_insights=summary_json.get("user_insights", []),
                contradictions_found=summary_json.get("contradictions_found", []),
                avoidance_moments=summary_json.get("avoidance_moments", []),
                unresolved_questions=summary_json.get("unresolved_questions", []),
                homework=summary_json.get("homework", []),
                next_session_focus=summary_json.get("next_session_focus", ""),
                dialogue_history=turns,
                scenario=session_data.get("scenario", "consultation")
            )
            db.add(s)
        db.commit()
        db.close()

        # 存入 Memory
        _save_memories(session_id, "anonymous", summary_json)

        # 更新用户画像
        _update_user_profile("anonymous", summary_json, session_id)

        return {"session_id": session_id, "summary": summary_json}
    except Exception as e:
        return {"error": str(e), "session_id": session_id}


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON"""
    text = text.strip()
    # 尝试找 ```json ... ``` 块
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
    if m:
        text = m.group(1)
    else:
        # 尝试找第一个 { 到最后一个 }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            text = text[start:end+1]
    try:
        return json.loads(text)
    except:
        return {}


@app.post("/api/feedback")
def submit_feedback(request: dict):
    """
    提交评价。
    在 Oscar 邀请评估后，用户可以提交评分和反馈。
    """
    session_id = request.get("session_id")
    rating = request.get("rating", 0)  # 1-5
    helpful_aspects = request.get("helpful_aspects", [])  # list of strings
    improvement_suggestions = request.get("improvement_suggestions", "")

    if not session_id:
        return {"error": "session_id required"}
    if rating < 1 or rating > 5:
        return {"error": "rating must be between 1 and 5"}

    try:
        db = get_db_direct()
        feedback_id = str(uuid.uuid4())[:8]
        f = Feedback(
            id=feedback_id,
            session_id=session_id,
            user_id="anonymous",
            rating=rating,
            helpful_aspects=helpful_aspects,
            improvement_suggestions=improvement_suggestions
        )
        db.add(f)
        db.commit()
        db.close()
        return {"ok": True, "feedback_id": feedback_id, "session_id": session_id}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/profile/{user_id}")
def get_profile(user_id: str):
    """获取用户画像"""
    profile = _get_or_create_guest_profile(user_id)
    return {"user_id": user_id, "profile": profile}

@app.get("/")
def root():
    return {"message": "Retrieval Test Server", "endpoints": ["/api/query", "/api/compare"]}

@app.get("/scenario_tester.html")
def scenario_tester():
    path = os.path.join(os.path.dirname(__file__), "scenario_tester.html")
    return FileResponse(path, media_type="text/html")

@app.get("/retrieval_tester.html")
def retrieval_tester():
    path = os.path.join(os.path.dirname(__file__), "retrieval_tester.html")
    return FileResponse(path, media_type="text/html")

@app.post("/api/query")
def query(request: dict):
    """纯检索"""
    q = request.get("query", "")
    if not q:
        return {"error": "no query"}
    results = retrieval.retrieve(q, expand_context=False, context_window=0)
    return {
        "query": q,
        "results": _format_results(results)
    }

@app.post("/api/compare")
def compare(request: dict):
    """检索+对比重排前后+LLM生成（支持多轮会话）"""
    q = request.get("query", "")
    use_llm = request.get("use_llm", True)
    scenario = request.get("scenario", "consultation")
    phase = request.get("phase", "problem_exploration")
    provider = request.get("provider", "deepseek")
    session_id = request.get("session_id")

    if not q:
        return {"error": "no query"}

    # 1. 获取重排前后对比（不做合并）
    comparison = retrieval.retrieve_with_comparison(
        q,
        expand_context=False,
        context_window=0,
        before_rerank_limit=10,
        after_rerank_limit=5
    )

    # 2. 加载会话历史
    turns_history = []
    phase_history = []
    if session_id and session_id in sessions:
        turns_history = sessions[session_id]["turns"]
        phase_history = sessions[session_id]["phase_history"]

    # 3. LLM 生成（带会话历史）
    llm_response = None
    if use_llm:
        try:
            llm_response = asyncio.run(_generate_llm(
                q, comparison["after_rerank"], scenario, phase, provider, turns_history
            ))
        except Exception as e:
            llm_response = f"LLM Error: {str(e)}"

    # 4. 更新会话存储
    if session_id:
        if session_id not in sessions:
            sessions[session_id] = {"turns": [], "phase_history": [], "scenario": scenario}
        sessions[session_id]["turns"].append({"speaker": "user", "message": q})
        if llm_response:
            sessions[session_id]["turns"].append({"speaker": "oscar", "message": llm_response})
        sessions[session_id]["phase_history"].append({
            "phase": phase,
            "query": q[:50]
        })
    else:
        # 无 session_id 也记录到临时历史（供单次对比用）
        turns_history.append({"speaker": "user", "message": q})
        if llm_response:
            turns_history.append({"speaker": "oscar", "message": llm_response})

    return {
        "query": q,
        "scenario": scenario,
        "phase": phase,
        "provider": provider,
        "session_id": session_id,
        "before_rerank": _format_results(comparison["before_rerank"]),
        "after_rerank": _format_results(comparison["after_rerank"]),
        "llm_response": llm_response
    }

def _format_results(results):
    """格式化检索结果（fallback: zh为空时用en，en为空时用zh）"""
    formatted = []
    for r in results:
        text_zh = r.get("text_zh", "").strip()
        text_en = r.get("text_en", "").strip()

        # 显示用：各自独立，有啥显示啥
        formatted.append({
            "text_zh": text_zh,
            "text_en": text_en,
            "source": r.get("source", ""),
            "score": r.get("rerank_score", r.get("score", 0)),
            "dense_score": r.get("dense_score", 0),
            "sparse_score": r.get("sparse_score", 0)
        })

    return formatted

async def _generate_llm(query: str, results: list, scenario: str = "consultation", phase: str = "problem_exploration", provider: str = "deepseek", turns_history: list = None):
    """构建上下文并调用 LLM"""
    # 选择 LLM client
    llm_client = minimax_llm if provider == "minimax" else llm

    # 构建咨询上下文（带历史）
    context = ConsultationContext(
        user_id="anonymous",
        session_id="compare_query",
        current_topic=None,
        consultation_phase=phase,
        user_emotional_state=None,
        techniques_used=[],
        key_insights=[],
        previous_turns=turns_history or [],
        scenario=scenario,
        evaluation_invited=True  # compare 端不需要结束邀请
    )

    # 检测语言
    compare_lang = "chinese" if _detect_user_language(turns_history or [], query) == "chinese" else "english"

    # 使用 PromptBuilder 构建 prompts
    system_prompt, user_prompt = prompt_builder.build_consultation_prompt(
        query=query,
        context=context,
        retrieved_docs=results[:5],
        config=PromptConfig(
            persona_enabled=True,
            skills_enabled=True,
            fewshot_enabled=False,
            tone="direct",
            response_length="short",
            language=compare_lang,
            scenario=scenario
        )
    )

    response = await llm_client.generate(
        system_prompt=system_prompt,
        user_message=user_prompt
    )
    return response


# ============ Safety Check ============

# 危机信号关键词（中文为主）
CRISIS_KEYWORDS = [
    # 自杀相关
    (r"想死|不想活了|活着没意思|活着不如死了|想自杀|要死了|死掉算了", "HIGH"),
    (r"杀了自己|自己了断|自我了结", "CRISIS"),
    # 严重抑郁/绝望
    (r"绝望了|彻底完了|毫无希望|完全没有希望", "HIGH"),
    # 伤害意图
    (r"想伤害自己|要割腕|要跳楼|想自残", "CRISIS"),
    # 危机计划
    (r"我已经计划好了|已经准备好了", "CRISIS"),
    # 极端无助
    (r"没有人能帮我|没人能救我|谁也帮不了我", "MEDIUM"),
]


def _check_safety(text: str) -> tuple[str, str] | None:
    """
    检测用户输入中的危机信号。
    返回 (risk_level, matched_keyword) 或 None（无风险）
    """
    if not text:
        return None
    for pattern, level in CRISIS_KEYWORDS:
        if re.search(pattern, text):
            return level, pattern
    return None


def _log_safety(session_id: str, user_input: str, risk_level: str):
    """记录安全日志到数据库"""
    try:
        db = get_db_direct()
        log = SafetyLog(
            session_id=session_id,
            user_input=user_input[:500],
            risk_level=risk_level,
            message=f"Risk detected: {risk_level}"
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception:
        pass


def _build_safety_response(risk_level: str) -> str:
    """根据风险等级返回干预语"""
    if risk_level == "CRISIS":
        return "我注意到你表达了非常强烈的想法。如果你正在经历困难，我希望能确保你安全。建议你立即联系身边的人，或拨打心理援助热线。"
    elif risk_level == "HIGH":
        return "听起来你现在非常痛苦。如果你有伤害自己的想法，请告诉自己：这种痛苦是可以改变的。可以告诉我你现在的情况，或者联系身边信任的人。"
    else:
        return "听起来你现在很不容易。如果有什么困扰着你，说出来会有帮助的。"


# ============ Memory ============

def _save_memories(session_id: str, user_id: str, summary: dict):
    """从摘要提取洞察存入 Memory 表"""
    insights = summary.get("user_insights", [])
    contradictions = summary.get("contradictions_found", [])
    topic = summary.get("main_topic", "")
    key_qs = summary.get("key_questions", [])

    if not (insights or contradictions or topic):
        return

    try:
        db = get_db_direct()
        all_items = insights + contradictions + [topic] + key_qs
        for item in all_items[:10]:
            mem = Memory(
                id=str(uuid.uuid4())[:8],
                user_id=user_id,
                memory_type="session",
                session_id=session_id,
                content=item,
                tags=_extract_tags(item),
                importance=0.5
            )
            db.add(mem)
        db.commit()
        db.close()
    except Exception:
        pass


def _extract_tags(text: str) -> list:
    """从文本中提取简单标签"""
    keywords = ["工作", "压力", "失败", "迷茫", "价值", "关系", "家庭", "健康", "金钱", "成长", "意义", "自由", "责任", "选择"]
    return [k for k in keywords if k in text]


def _retrieve_memories(user_id: str, query: str, top_k: int = 3) -> list:
    """检索与当前 query 相关的记忆（基于关键词匹配）"""
    try:
        db = get_db_direct()
        # 简单关键词匹配
        tags = _extract_tags(query)
        query_lower = query.lower()

        rows = db.query(Memory).filter_by(user_id=user_id).all()
        db.close()

        if not rows:
            return []

        # 评分：标签匹配 + 内容包含
        scored = []
        for row in rows:
            score = 0
            content_lower = row.content.lower()
            for tag in tags:
                if tag in content_lower:
                    score += 1
            # 包含 query 关键词
            if any(w in content_lower for w in query_lower.split() if len(w) > 2):
                score += 2
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"content": r.content, "tags": r.tags, "importance": r.importance} for s, r in scored[:top_k]]
    except Exception:
        return []


# ============ UserProfile ============

def _get_or_create_guest_profile(user_id: str = "anonymous") -> dict:
    """获取或创建用户画像"""
    db = get_db_direct()
    profile = db.query(UserProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile_id = str(uuid.uuid4())[:8]
        profile = UserProfile(
            id=profile_id,
            user_id=user_id,
            thinking_patterns=[],
            blind_spots=[],
            avoidance_patterns=[],
            core_themes=[],
            strengths=[],
            growth_timeline=[],
            depth_trend=[],
            session_summaries=[]
        )
        db.add(profile)
        db.commit()
    data = {
        "id": profile.id,
        "user_id": profile.user_id,
        "thinking_patterns": profile.thinking_patterns or [],
        "blind_spots": profile.blind_spots or [],
        "avoidance_patterns": profile.avoidance_patterns or [],
        "core_themes": profile.core_themes or [],
        "strengths": profile.strengths or [],
        "growth_timeline": profile.growth_timeline or [],
        "depth_trend": profile.depth_trend or [],
        "session_summaries": profile.session_summaries or []
    }
    db.close()
    return data


def _update_user_profile(user_id: str, summary: dict, session_id: str):
    """根据 session summary 更新用户画像"""
    try:
        db = get_db_direct()
        profile = db.query(UserProfile).filter_by(user_id=user_id).first()

        if not profile:
            profile_id = str(uuid.uuid4())[:8]
            profile = UserProfile(
                id=profile_id,
                user_id=user_id,
                thinking_patterns=[],
                blind_spots=[],
                avoidance_patterns=[],
                core_themes=[],
                strengths=[],
                growth_timeline=[],
                depth_trend=[],
                session_summaries=[]
            )
            db.add(profile)

        # 从 summary 提取更新内容
        topic = summary.get("main_topic", "")
        contradictions = summary.get("contradictions_found", [])
        insights = summary.get("user_insights", [])
        avoidance = summary.get("avoidance_moments", [])

        # 更新核心主题
        if topic and topic not in (profile.core_themes or []):
            profile.core_themes = (profile.core_themes or []) + [topic]

        # 更新回避模式
        for a in avoidance[:2]:
            if a not in (profile.avoidance_patterns or []):
                profile.avoidance_patterns = (profile.avoidance_patterns or []) + [a]

        # 更新思维模式（从洞察和矛盾推断）
        for c in contradictions[:2]:
            if c not in (profile.thinking_patterns or []):
                profile.thinking_patterns = (profile.thinking_patterns or []) + [c]

        # 更新成长时间线
        from datetime import datetime
        timeline_entry = {
            "date": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "topic": topic,
            "insight": insights[0] if insights else ""
        }
        profile.growth_timeline = (profile.growth_timeline or []) + [timeline_entry]

        # 更新 session summaries 索引
        profile.session_summaries = (profile.session_summaries or []) + [{
            "session_id": session_id,
            "date": datetime.utcnow().isoformat(),
            "topic": topic
        }]

        db.commit()
        db.close()
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
