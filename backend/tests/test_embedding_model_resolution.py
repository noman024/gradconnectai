from app.services.portfolio.embedding import _resolve_st_model_name


def test_resolve_alias_for_nomic_embed_text():
    resolved, changed = _resolve_st_model_name("nomic-embed-text")
    assert resolved == "nomic-ai/nomic-embed-text-v1.5"
    assert changed is True


def test_resolve_ollama_style_tag_to_default():
    resolved, changed = _resolve_st_model_name("frob/qwen3.5-instruct:9b")
    assert resolved == "all-MiniLM-L6-v2"
    assert changed is True


def test_keep_sentence_transformer_name():
    resolved, changed = _resolve_st_model_name("all-MiniLM-L6-v2")
    assert resolved == "all-MiniLM-L6-v2"
    assert changed is False
