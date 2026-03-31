#!/usr/bin/env python3
"""
Oscar Dialogue Manager 测试
验证：对话状态、技巧选择、阶段转换
"""
import sys
sys.path.insert(0, '.')

from core.dialogue_manager import (
    DialogueManager,
    DialogueTechnique,
    ConsultationPhase,
)


def test_dialogue_manager_init():
    """测试 DialogueManager 初始化"""
    print("=== test_dialogue_manager_init ===")
    dm = DialogueManager()
    assert dm is not None, "DialogueManager init failed"
    assert dm.persona is not None, "persona not loaded"
    print(f"  persona: {dm.persona.get('name', 'unknown')}")
    print("  ✓ PASS")


def test_start_session():
    """测试会话启动"""
    print("=== test_start_session ===")
    dm = DialogueManager()
    state = dm.start_session(user_id="test_user", initial_topic="哲学实践")
    assert state is not None, "start_session failed"
    assert state.phase == ConsultationPhase.GREETING, "wrong initial phase"
    assert state.user_id == "test_user", "wrong user_id"
    assert state.current_topic == "哲学实践", "topic not set"
    print(f"  session_id: {state.session_id}")
    print(f"  initial phase: {state.phase.value}")
    print("  ✓ PASS")


def test_process_message():
    """测试消息处理"""
    print("=== test_process_message ===")
    dm = DialogueManager()
    state = dm.start_session(user_id="test_user")

    response = dm.process_message(state, "我想谈谈工作和生活平衡的问题")

    assert response is not None, "process_message failed"
    assert response.message != "", "empty response"
    assert response.technique in DialogueTechnique, "invalid technique"
    print(f"  user: 我想谈谈工作和生活平衡的问题")
    print(f"  oscar: {response.message}")
    print(f"  technique: {response.technique.value}")
    print(f"  next_phase: {response.next_phase_suggestion.value}")
    print("  ✓ PASS")


def test_phase_transitions():
    """测试阶段转换 - 验证 next_phase_suggestion 随turns变化"""
    print("=== test_phase_transitions ===")
    dm = DialogueManager()
    state = dm.start_session(user_id="test_user")

    suggestions_seen = set()

    # 验证 next_phase_suggestion 随对话推进而变化
    for i, msg in enumerate([
        "我想谈谈工作的问题",
        "工作压力很大，经常加班到很晚",
        "是的，我觉得需要改变",
    ]):
        response = dm.process_message(state, msg)
        suggestions_seen.add(response.next_phase_suggestion.value)
        print(f"  turn {i+1}: next_phase={response.next_phase_suggestion.value}, technique={response.technique.value}")

    print(f"  phase suggestions seen: {suggestions_seen}")
    assert len(suggestions_seen) >= 2, "phase suggestion not changing"
    print("  ✓ PASS")


def test_technique_selection():
    """测试技巧选择"""
    print("=== test_technique_selection ===")
    dm = DialogueManager()
    state = dm.start_session(user_id="test_user")

    # 测试高焦虑情绪 → STOP_AND_BREATHE
    response1 = dm.process_message(state, "我非常焦虑，整夜睡不着")
    print(f"  焦虑输入: {response1.technique.value}")
    assert response1.technique == DialogueTechnique.STOP_AND_BREATHE, "wrong technique for anxiety"

    # 测试矛盾检测 (需要"I agree"后跟"no"或"but")
    dm.process_message(state, "Yes, I agree I should work less")
    response2 = dm.process_message(state, "But actually, no, I need the money")
    print(f"  矛盾输入: {response2.technique.value}")
    assert response2.technique == DialogueTechnique.LOGICAL_CHALLENGE, "wrong technique for contradiction"

    print("  ✓ PASS")


def test_session_history():
    """测试会话历史"""
    print("=== test_session_history ===")
    dm = DialogueManager()
    state = dm.start_session(user_id="test_user")

    dm.process_message(state, "第一个问题")
    dm.process_message(state, "第二个问题")

    history = dm.get_session_history(state.session_id)
    assert len(history) == 4, f"wrong history length: {len(history)}"  # 2 user + 2 oscar

    user_turns = [h for h in history if h["speaker"] == "user"]
    assert len(user_turns) == 2, "wrong user turn count"

    print(f"  total turns: {len(history)}")
    print(f"  user turns: {len(user_turns)}")
    print("  ✓ PASS")


def test_end_session():
    """测试会话结束"""
    print("=== test_end_session ===")
    dm = DialogueManager()
    state = dm.start_session(user_id="test_user")

    dm.process_message(state, "第一个问题")
    dm.process_message(state, "第二个问题")

    summary = dm.end_session(state.session_id)

    assert "session_id" in summary, "session_id missing"
    assert "questions_asked" in summary, "questions_asked missing"
    assert summary["questions_asked"] == 2, "wrong question count"
    print(f"  session_id: {summary['session_id']}")
    print(f"  questions_asked: {summary['questions_asked']}")
    print(f"  techniques_used: {summary['techniques_used']}")
    print("  ✓ PASS")


def run_all_tests():
    print("=" * 60)
    print("Oscar Dialogue Manager 测试")
    print("=" * 60)

    tests = [
        test_dialogue_manager_init,
        test_start_session,
        test_process_message,
        test_phase_transitions,
        test_technique_selection,
        test_session_history,
        test_end_session,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print("=" * 60)
    print(f"结果: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)