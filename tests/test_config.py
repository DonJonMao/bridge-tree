from bridgetree.config import load_config


def test_default_config_matches_datacenter_services():
    config = load_config("configs/default.yaml")
    assert config.models.embedding.model == "qwen3-embedding-8b"
    assert config.models.embedding.query_instruction.endswith("Query: ")
    assert config.models.reranker.endpoint.endswith(":8002/rerank")
    assert config.models.generator.model == "deepseek-v4-flash"
    assert config.models.generator.api_key == "Aa@11111"
