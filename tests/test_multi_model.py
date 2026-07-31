"""Tests for MAS-TS-001 Multi-Model Comparison Matrix."""

from mas_eval.scoring.multi_model import MultiModelRunner

SAMPLE_CARD = {
    "agent_id": "test-agent-001",
    "name": "TestAgent",
    "version": "1.0.0",
    "schema_version": "v1.2",
    "card_version": "1.2",
    "provider": "test",
    "model": "gpt-4",
    "deployment": "cloud",
    "endpoint": "https://api.example.com/v1/chat",
    "model_backend": {"endpoint": "https://api.example.com/v1", "location": "US"},
    "capabilities": [
        {
            "skill_id": "bash",
            "description": "run commands",
            "input_schema": {},
            "output_schema": {},
            "examples": ["ls"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_read",
            "description": "read files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["read"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_edit",
            "description": "edit files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["edit"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "file_write",
            "description": "write files",
            "input_schema": {},
            "output_schema": {},
            "examples": ["write"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "glob",
            "description": "glob",
            "input_schema": {},
            "output_schema": {},
            "examples": ["glob"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "grep",
            "description": "grep",
            "input_schema": {},
            "output_schema": {},
            "examples": ["grep"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "web_search",
            "description": "search",
            "input_schema": {},
            "output_schema": {},
            "examples": ["search"],
            "business_rule_version": "2026-07-15",
        },
        {
            "skill_id": "web_fetch",
            "description": "fetch",
            "input_schema": {},
            "output_schema": {},
            "examples": ["fetch"],
            "business_rule_version": "2026-07-15",
        },
    ],
    "authentication": {"type": "OAuth2", "scopes": ["read", "write"]},
    "compliance": {
        "data_residency": "US",
        "cross_border_transfer": False,
        "audit_trail_required": True,
        "end_user_identification": True,
        "model_backend_location": "US",
    },
    "constitution": {
        "envelope": {"version": "1.0", "jurisdiction": "US-CA"},
        "health_state": "healthy",
        "heartbeat_interval_seconds": 15,
    },
    "endpoints": {"a2a": "https://a2a.example.com", "mcp": "https://mcp.example.com"},
    "dependencies": ["git", "nodejs"],
    "orchestration_hints": {
        "agent_count": 3,
        "parallel_execution": True,
        "parallel_safe": True,
        "stateful": True,
        "preferred_role": "worker",
    },
    "message_format": {"protocol": "json-rpc-2.0", "transport": "stdio"},
}

MODELS = [
    {
        "name": "claude-sonnet-4",
        "config": {"provider": "anthropic", "tier": "premium", "deployment": "cloud"},
    },
    {
        "name": "gpt-4o",
        "config": {"provider": "openai", "tier": "premium", "deployment": "cloud"},
    },
    {
        "name": "deepseek-chat-v3",
        "config": {"provider": "deepseek", "tier": "value", "deployment": "cloud"},
    },
]


class TestMultiModelRunner:
    def test_add_model(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_model("claude-sonnet-4", {"provider": "anthropic"})
        assert len(mm.models) == 1
        assert mm.models[0]["name"] == "claude-sonnet-4"

    def test_add_models_from_list(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(["claude-sonnet-4", "gpt-4o"])
        assert len(mm.models) == 2

    def test_add_models_from_configs(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS)
        assert len(mm.models) == 3

    def test_make_card(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        card = mm._make_card(
            "claude-sonnet-4", {"provider": "anthropic", "deployment": "cloud"}
        )
        assert card["model_backend"]["model"] == "claude-sonnet-4"
        assert card["model"] == "claude-sonnet-4"
        assert card["provider"] == "anthropic"

    def test_run_returns_dict(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS)
        result = mm.run()
        assert isinstance(result, dict)
        assert result["standard"] == "MAS-TS-001"
        assert result["version"] == "v3.0"
        assert result["mode"] == "multi-model"

    def test_run_returns_all_models(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS)
        result = mm.run()
        assert result["model_count"] == 3
        assert len(result["results"]) == 3

    def test_run_d2_scores(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS)
        result = mm.run(domains=["d2"])
        for r in result["results"]:
            assert "d2" in r
            assert "score" in r["d2"]
            assert 0 <= r["d2"]["score"] <= 100

    def test_run_d3_scores(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS)
        result = mm.run(domains=["d3"])
        for r in result["results"]:
            assert "d3" in r
            assert "score" in r["d3"]
            assert 0 <= r["d3"]["score"] <= 100

    def test_run_both_domains(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS)
        result = mm.run(domains=["d2", "d3"])
        for r in result["results"]:
            assert "d2" in r
            assert "d3" in r

    def test_different_models_produce_different_scores(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS)
        result = mm.run(domains=["d2"])
        scores = [r["d2"]["score"] for r in result["results"]]
        assert len(set(scores)) > 1, f"All models got same D2 score: {scores}"

    def test_d3_subscores_present(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS[:1])
        result = mm.run(domains=["d3"])
        subs = result["results"][0]["d3"]["subscores"]
        for dim in (
            "spawn",
            "protocol",
            "orchestration",
            "isolation",
            "conflict",
            "persistence",
        ):
            assert dim in subs

    def test_empty_models_run(self):
        mm = MultiModelRunner(SAMPLE_CARD)
        result = mm.run()
        assert result["model_count"] == 0
        assert len(result["results"]) == 0

    def test_print_matrix(self, capsys):
        mm = MultiModelRunner(SAMPLE_CARD)
        mm.add_models(MODELS[:1])
        result = mm.run(domains=["d2"])
        mm.print_matrix(result)
        captured = capsys.readouterr()
        assert "Multi-Model Comparison Matrix" in captured.out
        assert MODELS[0]["name"] in captured.out
