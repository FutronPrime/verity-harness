from verity.promptware import compile_promptware, render


def test_lean_promptware_is_bounded_and_model_agnostic():
    p = compile_promptware("repair the service", identity="orion", capabilities=["shell", "mcp:memory", "shell"])
    assert p.identity == "ORION"
    assert p.capabilities == ("shell", "mcp:memory")
    assert "DISCOVER -> PLAN -> EXECUTE -> VERIFY -> PERSIST -> SCHEDULE/FOLLOW-UP" in p.system_prompt
    assert "SELF-APPLICATION:" in p.system_prompt
    assert "quarantine and vet acquired code" in p.system_prompt
    assert "anthropic" not in p.system_prompt.lower()
    assert len(p.system_prompt) < 1800


def test_json_render_and_invalid_profile():
    import json
    p = compile_promptware("test", profile="standard")
    assert json.loads(render(p, "json"))["goal"] == "test"
    try:
        compile_promptware("test", profile="huge")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid profile must fail closed")
