from wzkf.jobs.cost_ledger import OperationCache


def test_operation_cache_prevents_duplicate_expensive_calls():
    cache = OperationCache()
    key = cache.key_for(
        operation_name="transcribe",
        model_name="gpt-4o-transcribe",
        input_hash="sha256:input",
        prompt_hash="sha256:prompt",
        config_hash="sha256:config",
    )

    assert cache.has_succeeded(key) is False
    cache.mark_succeeded(key, result_hash="sha256:result")
    assert cache.has_succeeded(key) is True
    assert cache.result_hash_for(key) == "sha256:result"
