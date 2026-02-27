"""
Claude Integration 五层集成测试

通过 mock LLM 调用测试所有 5 层，无需 API key 即可运行。

运行方式：
  cd mindlakevm/runtime
  python -m pytest tests/test_claude_integration.py -v
"""
from __future__ import annotations
import json
import os
import sys
import types
from unittest.mock import patch, MagicMock

import pytest

# 确保 runtime 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import (
    SemanticKernelIR, RCore, NCore, ECore, TCore,
    PathStep, DecisionPoint, ReferenceEntry,
    SkillPackage, RunRequest, EvidenceItem,
    TraceStep, Violation, TokenUsage, ValidationResult,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_ir() -> SemanticKernelIR:
    """创建一个用于测试的 SemanticKernelIR 实例。"""
    return SemanticKernelIR(
        kernel_id="ops-sev1-incident-response-v1",
        version="0.3",
        compiled_at="2025-01-01T00:00:00Z",
        source_doc="test-doc",
        compilation_strategy="default",
        r=RCore(
            domain="ops.incident",
            object_type="sop",
            semantic_space="Sev1 事故响应流程，面向 SRE 和 On-call 工程师",
        ),
        n=NCore(
            structure="step_by_step",
            constraints=["必须包含受影响用户数量", "必须包含恢复时间"],
            references=[
                ReferenceEntry(path="references/escalation-matrix.md", scope="升级策略", required=True),
                ReferenceEntry(path="references/runbook.md", scope="操作手册", required=False),
            ],
        ),
        e=ECore(
            format="markdown",
            target_entropy="消除 Sev1 事故处理中的决策不确定性",
            hard_constraints=["高峰期禁止扩缩容操作，除非 CTO 书面授权", "禁止在未通知客户的情况下回滚"],
            soft_constraints=["建议在 15 分钟内完成初步诊断"],
            meta_ignorance=["未覆盖多区域级联故障场景"],
        ),
        t=TCore(
            path=[
                PathStep(
                    id="detect",
                    name="故障检测",
                    description="确认告警并评估影响范围",
                    decision_points=[
                        DecisionPoint(condition="影响用户 > 1000", if_true="立即升级为 Sev1", if_false="按 Sev2 处理"),
                    ],
                    requires_evidence=True,
                ),
                PathStep(
                    id="triage",
                    name="分流与升级",
                    description="根据影响范围通知相关团队",
                    tool_required="pagerduty_alert",
                    requires_evidence=True,
                ),
                PathStep(
                    id="mitigate",
                    name="缓解措施",
                    description="执行缓解操作减少影响",
                ),
                PathStep(
                    id="resolve",
                    name="根因修复",
                    description="定位并修复根因",
                ),
            ],
            cot_steps=[
                "首先确认告警是否为真阳性",
                "评估影响范围（用户数、区域、服务）",
                "根据升级矩阵决定通知谁",
                "选择最小化影响的缓解方案",
            ],
        ),
    )


@pytest.fixture
def sample_package(sample_ir) -> SkillPackage:
    return SkillPackage(
        skill_id="ops-sev1-incident-response",
        skill_name="Sev1 事故响应流程",
        description="面向 SRE 和 On-call 工程师的 Sev1 事故处理流程",
        kernel_id=sample_ir.kernel_id,
        compiled_at=sample_ir.compiled_at,
    )


def _make_mock_response(content: str = "", tool_calls=None):
    """构造一个模拟的 OpenAI API response。"""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


def _make_mock_tool_call(call_id: str, name: str, arguments: dict):
    """构造一个模拟的 tool call 对象。"""
    tc = MagicMock()
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


# ══════════════════════════════════════════════════════════════════════════════
# Layer 1: LLM Adapter (llm.py)
# ══════════════════════════════════════════════════════════════════════════════

class TestLayer1LLMAdapter:
    """测试 llm.py 的 tools 参数支持。"""

    def test_llm_json_without_tools(self):
        """无 tools 时，行为不变：从 content 解析 JSON。"""
        from compiler.llm import llm_json
        mock_resp = _make_mock_response(content='{"violations": []}')
        with patch("compiler.llm._get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            result = llm_json("system", "user")
        assert result == {"violations": []}

    def test_llm_json_with_tools_extracts_from_tool_calls(self):
        """有 tools 时，优先从 tool_calls 提取数据。"""
        from compiler.llm import llm_json
        tc = _make_mock_tool_call("tc1", "report_violations", {"violations": [{"constraint_index": 0, "reason": "test"}]})
        mock_resp = _make_mock_response(content="ignored text", tool_calls=[tc])
        with patch("compiler.llm._get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            result = llm_json("system", "user", tools=[{"type": "function", "function": {"name": "test"}}])
        assert result["violations"][0]["reason"] == "test"

    def test_llm_json_tool_calls_fallback_to_content(self):
        """tool_calls 解析失败时，回退到 content 解析。"""
        from compiler.llm import llm_json
        mock_resp = _make_mock_response(content='{"fallback": true}', tool_calls=None)
        with patch("compiler.llm._get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            result = llm_json("system", "user", tools=[{"type": "function", "function": {"name": "test"}}])
        assert result == {"fallback": True}

    def test_llm_text_with_tools(self):
        """llm_text 透传 tools 参数。"""
        from compiler.llm import llm_text
        mock_resp = _make_mock_response(content="output text")
        with patch("compiler.llm._get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            text, in_tok, out_tok = llm_text("system", "user", tools=[{"type": "function", "function": {"name": "test"}}])
        assert text == "output text"
        assert in_tok == 100
        assert out_tok == 50

    def test_llm_chat_returns_raw_response(self):
        """llm_chat 返回原始 response 对象。"""
        from compiler.llm import llm_chat
        mock_resp = _make_mock_response(content="hello")
        with patch("compiler.llm._get_client") as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            resp = llm_chat("system", [{"role": "user", "content": "hi"}])
        assert resp.choices[0].message.content == "hello"


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2: Guardrail + Compiler tool_use
# ══════════════════════════════════════════════════════════════════════════════

class TestLayer2Guardrail:
    """测试 guardrail 的 tool_use 模式。"""

    def test_guardrail_no_constraints_returns_empty(self, sample_ir):
        """无硬约束时，直接返回空。"""
        from executor.guardrail import check_guardrails
        e_no_constraints = ECore(format="markdown", target_entropy="test")
        assert check_guardrails(e_no_constraints, "any input") == []

    def test_guardrail_tool_mode_extracts_violations(self, sample_ir):
        """tool_use 模式：从 tool_calls 中提取 violations。"""
        from executor.guardrail import check_guardrails, GUARDRAIL_TOOL
        violations_data = {"violations": [{"constraint_index": 0, "reason": "用户要求高峰期扩缩容"}]}
        tc = _make_mock_tool_call("tc1", "report_violations", violations_data)
        mock_resp = _make_mock_response(tool_calls=[tc])

        with patch("compiler.llm._get_client") as mock_client, \
             patch.dict(os.environ, {"OPENAI_BASE_URL": "https://openrouter.ai/api/v1"}):
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            violations = check_guardrails(sample_ir.e, "高峰期帮我扩容")

        assert len(violations) == 1
        assert "高峰期" in violations[0].constraint
        assert violations[0].severity == "hard"

    def test_guardrail_fallback_json_mode(self, sample_ir):
        """非 OpenRouter 时，走 JSON prompt 模式。"""
        from executor.guardrail import check_guardrails
        mock_resp = _make_mock_response(content='{"violations": []}')

        with patch("compiler.llm._get_client") as mock_client, \
             patch.dict(os.environ, {"OPENAI_BASE_URL": "https://api.openai.com/v1"}, clear=False):
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            violations = check_guardrails(sample_ir.e, "正常查询")

        assert violations == []

    def test_guardrail_tool_definition_schema(self):
        """验证 GUARDRAIL_TOOL 的 schema 结构正确。"""
        from executor.guardrail import GUARDRAIL_TOOL
        assert GUARDRAIL_TOOL["type"] == "function"
        func = GUARDRAIL_TOOL["function"]
        assert func["name"] == "report_violations"
        props = func["parameters"]["properties"]
        assert "violations" in props
        assert props["violations"]["type"] == "array"


class TestLayer2Compiler:
    """测试 compiler pipeline 的 tool_use 模式。"""

    def test_compile_ir_tool_schema(self):
        """验证 COMPILE_IR_TOOL 的 schema 包含 RNET 四核。"""
        from compiler.pipeline import COMPILE_IR_TOOL
        func = COMPILE_IR_TOOL["function"]
        assert func["name"] == "generate_semantic_kernel_ir"
        props = func["parameters"]["properties"]
        assert "r" in props
        assert "n" in props
        assert "e" in props
        assert "t" in props
        # T 核 path 应包含 tool_required
        path_item_props = props["t"]["properties"]["path"]["items"]["properties"]
        assert "tool_required" in path_item_props

    def test_use_tool_mode_detection(self):
        """_use_tool_mode 正确检测 OpenRouter。"""
        from compiler.pipeline import _use_tool_mode
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://openrouter.ai/api/v1"}):
            assert _use_tool_mode() is True
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://api.openai.com/v1"}):
            assert _use_tool_mode() is False
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "", "ENABLE_TOOL_USE": "1"}):
            assert _use_tool_mode() is True


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3: Agent Runner
# ══════════════════════════════════════════════════════════════════════════════

class TestLayer3AgentRunner:
    """测试 agent_runner.py 的 Agent 循环执行。"""

    def test_compile_ir_to_tools(self, sample_ir):
        """IR 正确编译为 tool 列表。"""
        from executor.agent_runner import compile_ir_to_tools
        tools = compile_ir_to_tools(sample_ir)
        names = [t["function"]["name"] for t in tools]
        assert "cite_reference" in names
        assert "report_decision" in names
        assert "step_complete" in names
        assert "pagerduty_alert" in names  # 从 tool_required 来的

    def test_compile_ir_to_tools_no_refs(self):
        """无 references 时不生成 cite_reference。"""
        from executor.agent_runner import compile_ir_to_tools
        ir = SemanticKernelIR(
            kernel_id="test", r=RCore(domain="test", object_type="sop", semantic_space="test"),
            n=NCore(structure="step_by_step"),
            e=ECore(format="markdown", target_entropy="test"),
            t=TCore(path=[PathStep(id="s1", name="step1", description="desc")]),
        )
        tools = compile_ir_to_tools(ir)
        names = [t["function"]["name"] for t in tools]
        assert "cite_reference" not in names
        assert "report_decision" not in names
        assert "step_complete" in names

    def test_build_agent_system_prompt(self, sample_ir):
        """system prompt 包含关键信息。"""
        from executor.agent_runner import build_agent_system_prompt
        prompt = build_agent_system_prompt(sample_ir)
        assert "ops.incident" in prompt
        assert "故障检测" in prompt
        assert "pagerduty_alert" in prompt
        assert "step_complete" in prompt
        assert "cite_reference" in prompt

    def test_handle_cite_reference(self, sample_ir):
        """cite_reference 工具正确收集 evidence。"""
        from executor.agent_runner import _handle_tool_call
        trace, evidence = [], []
        result = _handle_tool_call(
            "cite_reference",
            {"reference_path": "references/escalation-matrix.md", "relevant_excerpt": "P1 升级到 VP", "relevance": "升级策略"},
            sample_ir, trace, evidence,
        )
        assert len(evidence) == 1
        assert evidence[0].source_path == "references/escalation-matrix.md"
        assert "P1" in evidence[0].excerpt

    def test_handle_report_decision(self, sample_ir):
        """report_decision 工具正确更新 trace。"""
        from executor.agent_runner import _handle_tool_call
        trace = [TraceStep(step_id="detect", status="pending")]
        evidence = []
        _handle_tool_call(
            "report_decision",
            {"step_id": "detect", "condition": "影响用户 > 1000", "result": True, "reasoning": "监控显示 5000 用户受影响"},
            sample_ir, trace, evidence,
        )
        assert "✓" in trace[0].decision_taken
        assert "5000" in trace[0].decision_taken

    def test_handle_step_complete(self, sample_ir):
        """step_complete 工具正确标记步骤完成。"""
        from executor.agent_runner import _handle_tool_call
        trace = [TraceStep(step_id="detect", status="pending")]
        evidence = []
        _handle_tool_call(
            "step_complete",
            {"step_id": "detect", "summary": "确认为真阳性告警"},
            sample_ir, trace, evidence,
        )
        assert trace[0].status == "completed"
        assert trace[0].notes == "确认为真阳性告警"

    def test_handle_unregistered_external_tool(self, sample_ir):
        """未注册的外部工具返回模拟结果。"""
        from executor.agent_runner import _handle_tool_call
        result = _handle_tool_call(
            "pagerduty_alert", {"query": "notify sre team"}, sample_ir, [], [],
        )
        assert "[模拟]" in result
        assert "pagerduty_alert" in result

    def test_run_skill_agent_guardrail_block(self, sample_ir):
        """guardrail 拦截时直接返回 blocked。"""
        from executor.agent_runner import run_skill_agent
        violations_data = {"violations": [{"constraint_index": 0, "reason": "高峰期扩缩容"}]}
        tc = _make_mock_tool_call("tc1", "report_violations", violations_data)
        mock_resp = _make_mock_response(tool_calls=[tc])

        with patch("compiler.llm._get_client") as mock_client, \
             patch.dict(os.environ, {"OPENAI_BASE_URL": "https://openrouter.ai/api/v1"}):
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            req = RunRequest(skill_id="test", user_input="高峰期帮我扩容 100 台机器")
            resp = run_skill_agent(sample_ir, req)

        assert resp.blocked is True
        assert len(resp.violations) == 1
        assert "⛔" in resp.output_text

    def test_run_skill_agent_normal_execution(self, sample_ir):
        """正常执行：guardrail 通过 → Agent 循环。"""
        from executor.agent_runner import run_skill_agent

        # Mock 1: guardrail 通过（无 violations）
        guardrail_resp = _make_mock_response(content='{"violations": []}')
        # Mock 2: Agent 第一轮 — 调用 step_complete
        tc_step = _make_mock_tool_call("tc2", "step_complete", {"step_id": "detect", "summary": "告警确认"})
        agent_turn1 = _make_mock_response(content="正在处理...", tool_calls=[tc_step])
        # Mock 3: Agent 第二轮 — 最终回答
        agent_turn2 = _make_mock_response(content="事故处理完成，根因已修复。")

        call_count = {"n": 0}
        def mock_create(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return guardrail_resp
            elif call_count["n"] == 2:
                return agent_turn1
            else:
                return agent_turn2

        with patch("compiler.llm._get_client") as mock_client, \
             patch.dict(os.environ, {"OPENAI_BASE_URL": "https://openrouter.ai/api/v1"}):
            mock_client.return_value.chat.completions.create.side_effect = mock_create
            req = RunRequest(skill_id="test", user_input="线上告警 API 延迟飙升")
            resp = run_skill_agent(sample_ir, req)

        assert resp.blocked is False
        assert "事故处理完成" in resp.output_text
        # 应有 detect 步骤被标记为 completed
        detect_trace = [t for t in resp.trace if t.step_id == "detect"]
        assert detect_trace[0].status == "completed"
        # 未执行的步骤应为 skipped
        skipped = [t for t in resp.trace if t.status == "skipped"]
        assert len(skipped) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Layer 4: Tool Export
# ══════════════════════════════════════════════════════════════════════════════

class TestLayer4ToolExport:
    """测试 IR → Claude Tool Definition 导出。"""

    def test_ir_to_claude_tool(self, sample_ir):
        """基本 Claude Tool Definition 导出。"""
        from compiler.tool_export import ir_to_claude_tool
        tool = ir_to_claude_tool(sample_ir)
        assert tool["type"] == "function"
        func = tool["function"]
        assert func["name"] == "mindlake_skill_ops_sev1_incident_response_v1"
        assert "Sev1" in func["description"]
        assert "ops.incident" in func["description"]
        assert func["parameters"]["required"] == ["user_input"]

    def test_ir_to_claude_tool_with_examples(self, sample_ir):
        """导出包含 Tool Use Examples。"""
        from compiler.tool_export import ir_to_claude_tool
        tool = ir_to_claude_tool(sample_ir, include_examples=True)
        examples = tool["function"].get("examples", [])
        assert len(examples) > 0
        # 应包含 guardrail 场景
        tags_all = [tag for e in examples for tag in e.get("tags", [])]
        assert "guardrail" in tags_all
        # 应包含 decision_point 场景
        assert "decision_point" in tags_all
        # 应包含 normal_execution
        assert "normal_execution" in tags_all

    def test_ir_to_claude_tool_without_examples(self, sample_ir):
        """可以关闭 examples。"""
        from compiler.tool_export import ir_to_claude_tool
        tool = ir_to_claude_tool(sample_ir, include_examples=False)
        assert "examples" not in tool["function"]

    def test_generate_tool_examples(self, sample_ir):
        """Tool Use Examples 生成覆盖所有策略。"""
        from compiler.tool_export import generate_tool_examples
        examples = generate_tool_examples(sample_ir)
        assert len(examples) >= 4  # 2 constraints + 1 decision + 1 path + 1 generic
        # 最后一个应为 generic
        assert "generic" in examples[-1]["tags"]

    def test_ir_to_tool_search_metadata(self, sample_ir):
        """Tool Search Metadata 格式正确。"""
        from compiler.tool_export import ir_to_tool_search_metadata
        meta = ir_to_tool_search_metadata(sample_ir)
        assert meta["domain"] == "ops.incident"
        assert meta["has_guardrail"] is True
        assert meta["step_count"] == 4
        assert meta["defer_loading"] is True
        assert len(meta["keywords"]) > 0

    def test_ir_to_mcp_tool(self, sample_ir):
        """MCP Tool 格式正确。"""
        from compiler.tool_export import ir_to_mcp_tool
        tool = ir_to_mcp_tool(sample_ir)
        assert tool["name"] == "mindlake/ops-sev1-incident-response-v1"
        assert "inputSchema" in tool
        assert tool["annotations"]["has_guardrail"] is True
        assert "detect" in tool["annotations"]["execution_path"]

    def test_export_skill_bundle(self, sample_ir):
        """完整导出包包含所有格式。"""
        from compiler.tool_export import export_skill_bundle
        bundle = export_skill_bundle(sample_ir)
        assert "claude_tool" in bundle
        assert "mcp_tool" in bundle
        assert "search_metadata" in bundle
        assert "examples" in bundle
        assert bundle["skill_id"] == sample_ir.kernel_id

    def test_export_all_tools(self, sample_ir):
        """批量导出。"""
        from compiler.tool_export import export_all_tools
        tools = export_all_tools([sample_ir, sample_ir], format="claude")
        assert len(tools) == 2
        tools_mcp = export_all_tools([sample_ir], format="mcp")
        assert tools_mcp[0]["name"].startswith("mindlake/")


# ══════════════════════════════════════════════════════════════════════════════
# Layer 5: MCP Server
# ══════════════════════════════════════════════════════════════════════════════

class TestLayer5MCPServer:
    """测试 MCP Server 的 tool/resource/prompt 注册。"""

    def test_mcp_server_instance(self):
        """MCP Server 实例正确创建。"""
        try:
            from mcp_server import mcp
            assert mcp.name == "MindLakeVM"
        except ImportError:
            pytest.skip("mcp package not installed")

    def test_mcp_compile_tool(self, sample_ir, sample_package, tmp_path):
        """mindlake_compile tool 编译并保存 Skill。"""
        try:
            from mcp_server import mindlake_compile
        except ImportError:
            pytest.skip("mcp package not installed")

        ir_data = {
            "kernel_id": "test-skill-v1",
            "version": "0.3",
            "compiled_at": "2025-01-01T00:00:00Z",
            "source_doc": "test",
            "compilation_strategy": "default",
            "r": {"domain": "test", "object_type": "sop", "semantic_space": "test skill"},
            "n": {"structure": "step_by_step"},
            "e": {"format": "markdown", "target_entropy": "test"},
            "t": {"path": [{"id": "s1", "name": "step1", "description": "desc"}]},
        }
        tc = _make_mock_tool_call("tc1", "generate_semantic_kernel_ir", ir_data)
        mock_resp = _make_mock_response(tool_calls=[tc])

        with patch("compiler.llm._get_client") as mock_client, \
             patch.dict(os.environ, {
                 "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
                 "SKILLS_DIR": str(tmp_path),
             }):
            mock_client.return_value.chat.completions.create.return_value = mock_resp
            result_json = mindlake_compile(
                task_description="测试编译",
                document_content="测试文档内容",
                strategy="default",
            )

        result = json.loads(result_json)
        assert result["status"] == "compiled"
        assert "skill_id" in result

    def test_mcp_list_skills(self, sample_ir, sample_package, tmp_path):
        """mindlake_list_skills tool 列出已编译 Skills。"""
        try:
            from mcp_server import mindlake_list_skills
        except ImportError:
            pytest.skip("mcp package not installed")

        # 先保存一个 skill
        with patch.dict(os.environ, {"SKILLS_DIR": str(tmp_path)}):
            import store
            store.save("test-skill", sample_ir, sample_package)
            result_json = mindlake_list_skills()

        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["skill_id"] == "test-skill"

    def test_mcp_run_skill(self, sample_ir, sample_package, tmp_path):
        """mindlake_run tool 执行 Skill。"""
        try:
            from mcp_server import mindlake_run
        except ImportError:
            pytest.skip("mcp package not installed")

        # 保存 skill + mock LLM
        guardrail_resp = _make_mock_response(content='{"violations": []}')
        agent_resp = _make_mock_response(content="处理完成")

        call_count = {"n": 0}
        def mock_create(**kwargs):
            call_count["n"] += 1
            return guardrail_resp if call_count["n"] == 1 else agent_resp

        with patch("compiler.llm._get_client") as mock_client, \
             patch.dict(os.environ, {
                 "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
                 "SKILLS_DIR": str(tmp_path),
             }):
            import store
            store.save("test-skill", sample_ir, sample_package)
            mock_client.return_value.chat.completions.create.side_effect = mock_create
            result_json = mindlake_run(skill_id="test-skill", user_input="告警处理")

        result = json.loads(result_json)
        assert result["blocked"] is False
        assert "处理完成" in result["output_text"]

    def test_mcp_skill_not_found(self, tmp_path):
        """不存在的 Skill 返回错误。"""
        try:
            from mcp_server import mindlake_run
        except ImportError:
            pytest.skip("mcp package not installed")

        with patch.dict(os.environ, {"SKILLS_DIR": str(tmp_path)}):
            result_json = mindlake_run(skill_id="nonexistent", user_input="test")

        result = json.loads(result_json)
        assert "error" in result


# ══════════════════════════════════════════════════════════════════════════════
# API 端点集成测试（通过 FastAPI TestClient）
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIEndpoints:
    """测试 REST API 端点。"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_skills_list_empty(self, client, tmp_path):
        with patch.dict(os.environ, {"SKILLS_DIR": str(tmp_path)}):
            resp = client.get("/skills")
        assert resp.status_code == 200

    def test_skill_tool_definition_404(self, client, tmp_path):
        with patch.dict(os.environ, {"SKILLS_DIR": str(tmp_path)}):
            resp = client.get("/skills/nonexistent/tool")
        assert resp.status_code == 404

    def test_skill_tool_definition(self, client, sample_ir, sample_package, tmp_path):
        with patch.dict(os.environ, {"SKILLS_DIR": str(tmp_path)}):
            import store
            store.save("test-skill", sample_ir, sample_package)
            resp = client.get("/skills/test-skill/tool?format=claude")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "function"

    def test_skill_tool_bundle(self, client, sample_ir, sample_package, tmp_path):
        with patch.dict(os.environ, {"SKILLS_DIR": str(tmp_path)}):
            import store
            store.save("test-skill", sample_ir, sample_package)
            resp = client.get("/skills/test-skill/tool?format=bundle")
        assert resp.status_code == 200
        data = resp.json()
        assert "claude_tool" in data
        assert "mcp_tool" in data

    def test_skill_examples(self, client, sample_ir, sample_package, tmp_path):
        with patch.dict(os.environ, {"SKILLS_DIR": str(tmp_path)}):
            import store
            store.save("test-skill", sample_ir, sample_package)
            resp = client.get("/skills/test-skill/examples")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["examples"]) > 0

    def test_tools_list(self, client, sample_ir, sample_package, tmp_path):
        with patch.dict(os.environ, {"SKILLS_DIR": str(tmp_path)}):
            import store
            store.save("test-skill", sample_ir, sample_package)
            resp = client.get("/tools?format=claude")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1

    def test_run_agent_mode(self, client, sample_ir, sample_package, tmp_path):
        """通过 API 端点测试 Agent 模式执行。"""
        guardrail_resp = _make_mock_response(content='{"violations": []}')
        agent_resp = _make_mock_response(content="处理完成")

        call_count = {"n": 0}
        def mock_create(**kwargs):
            call_count["n"] += 1
            return guardrail_resp if call_count["n"] == 1 else agent_resp

        with patch("compiler.llm._get_client") as mock_client, \
             patch.dict(os.environ, {
                 "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
                 "SKILLS_DIR": str(tmp_path),
             }):
            import store
            store.save("test-skill", sample_ir, sample_package)
            mock_client.return_value.chat.completions.create.side_effect = mock_create
            resp = client.post("/run", json={"skill_id": "test-skill", "user_input": "告警"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["blocked"] is False
