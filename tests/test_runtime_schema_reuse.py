from __future__ import annotations

from pathlib import Path

from vibecomfy.schema import RuntimeSchemaProvider, schema_registry_empty
from vibecomfy.schema.cache import runtime_fingerprint, write_object_info_cache


def test_runtime_schema_provider_validation_lookup_is_lazy(
    tmp_path: Path, monkeypatch
) -> None:
    provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)
    write_object_info_cache(
        provider.cache_path,
        {
            "NeededNode": {"input": {"required": {"value": ["STRING", {}]}}},
            **{
                f"UnusedNode{index}": {"input": {"required": {"value": ["STRING", {}]}}}
                for index in range(100)
            },
        },
        runtime_fingerprint=runtime_fingerprint("http://runtime.test"),
        server_url="http://runtime.test",
    )
    import vibecomfy.schema.provider as provider_module

    original = provider_module._schema_from_object_info
    parsed: list[str] = []

    def tracked(class_type, info):
        parsed.append(class_type)
        return original(class_type, info)

    monkeypatch.setattr(provider_module, "_schema_from_object_info", tracked)

    assert schema_registry_empty(provider) is False
    assert parsed == []
    assert provider.get_schema("NeededNode") is not None
    assert parsed == ["NeededNode"]
