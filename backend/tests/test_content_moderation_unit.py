import asyncio
import json

import pytest

from app import content_moderation
from app.ai import classifier, storage
from app.ai.runtime_config import environment_ai_config
from app.ai.errors import AIServiceError
from app.ai.schemas import ModerationAIResponse
from app.config import settings


class FakeRedis:
    def __init__(self):
        self.cache: dict[str, str] = {}
        self.eval_calls: list[tuple] = []
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[tuple, dict]] = []

    async def eval(self, *args):
        self.eval_calls.append(args)
        return [1, 60]

    async def get(self, key):
        self.get_calls.append(key)
        return self.cache.get(key)

    async def set(self, *args, **kwargs):
        self.set_calls.append((args, kwargs))
        self.cache[args[0]] = args[1]
        return True


@pytest.fixture
def semantic_provider(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "GITHUB_REPO", "")
    monkeypatch.setattr(settings, "DEPLOY_ENABLED", False)
    monkeypatch.setattr(settings, "AI_FEATURES_ENABLED", True)
    monkeypatch.setattr(settings, "AI_POLITICAL_CLASSIFIER_URL", "")
    monkeypatch.setattr(settings, "AI_MODERATION_PROVIDER_FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "AI_MODERATION_POLICY_VERSION", "test-semantic-v1")
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_VERSION",
        "test-classifier-v1",
    )
    monkeypatch.setattr(settings, "AI_MODERATION_CACHE_TTL_SECONDS", 604800)
    monkeypatch.setattr(settings, "AI_MODERATION_RATE_LIMIT_GLOBAL_QPS", 12)
    monkeypatch.setattr(
        settings,
        "AI_MODERATION_RATE_LIMIT_DAILY_GLOBAL_REQUESTS",
        10000,
    )
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "https://api.example")
    monkeypatch.setattr(settings, "DEEPSEEK_MODEL", "semantic-test-model")

    async def runtime_from_environment(*, force_refresh=False):
        return environment_ai_config()

    monkeypatch.setattr(classifier, "get_ai_runtime_config", runtime_from_environment)
    monkeypatch.setattr(
        content_moderation,
        "get_ai_runtime_config",
        runtime_from_environment,
    )

    fake = FakeRedis()

    async def get_fake_redis():
        return fake

    monkeypatch.setattr(storage, "get_redis", get_fake_redis)
    return fake


@pytest.mark.asyncio
async def test_provider_fallback_judges_whole_document_without_word_rules(
    monkeypatch,
    semantic_provider,
):
    calls = []

    async def classify(**kwargs):
        calls.append(kwargs)
        return ModerationAIResponse(political_status="non_political")

    monkeypatch.setattr(classifier, "request_structured_completion", classify)

    result = await content_moderation.assess_content_moderation(
        "Fast window",
        "Candidate product policy and community vote",
    )

    assert result.status == "published"
    assert len(calls) == 1
    assert calls[0]["max_tokens"] == 24
    assert len(calls[0]["system_prompt"]) < 1400
    assert json.loads(calls[0]["user_message"]) == {
        "content": "Fast window\n\nCandidate product policy and community vote"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["non_political", "political", "uncertain"])
async def test_semantic_verdict_cache_deduplicates_all_outcomes(
    monkeypatch,
    semantic_provider,
    status,
):
    calls = []

    async def classify(**kwargs):
        calls.append(kwargs)
        return ModerationAIResponse(political_status=status)

    monkeypatch.setattr(classifier, "request_structured_completion", classify)

    first = await classifier.classify_semantic_content(["Exact source text"])
    second = await classifier.classify_semantic_content(["Exact source text"])

    assert first.status == status
    assert first.cached is False
    assert second.status == status
    assert second.provenance == "provider"
    assert second.cached is True
    assert len(calls) == 1
    assert len(semantic_provider.eval_calls) == 3
    assert "ai:rate:global:qps" in str(semantic_provider.eval_calls[0])
    assert "ai:rate:global:day" in str(semantic_provider.eval_calls[1])
    assert "ai:moderation:global:day" in str(semantic_provider.eval_calls[2])
    assert all("ai:rate:user:" not in str(call) for call in semantic_provider.eval_calls)
    assert len(semantic_provider.set_calls) == 1
    cache_key = semantic_provider.set_calls[0][0][0]
    assert cache_key.startswith("ai:moderation:")
    assert "Exact source text" not in cache_key
    assert "Exact source text" not in semantic_provider.set_calls[0][0][1]


def test_moderation_cache_key_tracks_complete_classifier_contract(
    monkeypatch,
    semantic_provider,
):
    first = storage.moderation_cache_key(
        text="Exact source text",
        engine="provider:semantic-test-model",
    )
    monkeypatch.setattr(settings, "AI_MODERATION_POLICY_VERSION", "test-semantic-v2")
    second = storage.moderation_cache_key(
        text="Exact source text",
        engine="provider:semantic-test-model",
    )
    third = storage.moderation_cache_key(
        text="Exact source text",
        engine="provider:next-model",
    )
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "https://next.example/v1")
    fourth = storage.moderation_cache_key(
        text="Exact source text",
        engine="provider:next-model",
    )
    monkeypatch.setattr(settings, "AI_TEMPERATURE", 0.2)
    fifth = storage.moderation_cache_key(
        text="Exact source text",
        engine="provider:next-model",
    )
    monkeypatch.setattr(settings, "AI_POLITICAL_CLASSIFIER_VERSION", "classifier-v2")
    sixth = storage.moderation_cache_key(
        text="Exact source text",
        engine="provider:next-model",
    )
    monkeypatch.setattr(
        storage,
        "MODERATION_SYSTEM_PROMPT",
        storage.MODERATION_SYSTEM_PROMPT + " Contract v2.",
    )
    seventh = storage.moderation_cache_key(
        text="Exact source text",
        engine="provider:next-model",
    )

    class NextModerationSchema:
        @staticmethod
        def model_json_schema():
            return {"type": "object", "required": ["next_status"]}

    monkeypatch.setattr(storage, "ModerationAIResponse", NextModerationSchema)
    eighth = storage.moderation_cache_key(
        text="Exact source text",
        engine="provider:next-model",
    )

    keys = (first, second, third, fourth, fifth, sixth, seventh, eighth)
    assert len(set(keys)) == len(keys)
    assert all(key.startswith("ai:moderation:") for key in keys)
    assert all("Exact source text" not in key for key in keys)


@pytest.mark.asyncio
async def test_concurrent_moderation_cache_misses_use_one_provider_call(
    monkeypatch,
    semantic_provider,
):
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def classify(**_kwargs):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return ModerationAIResponse(political_status="non_political")

    monkeypatch.setattr(classifier, "request_structured_completion", classify)
    first = asyncio.create_task(
        classifier.classify_semantic_content(["Concurrent source text"])
    )
    await started.wait()
    second = asyncio.create_task(
        classifier.classify_semantic_content(["Concurrent source text"])
    )
    await asyncio.sleep(0)
    release.set()

    results = await asyncio.gather(first, second)

    assert calls == 1
    assert sorted(result.cached for result in results) == [False, True]
    assert len(semantic_provider.set_calls) == 1


@pytest.mark.asyncio
async def test_provider_fallback_failure_is_held_for_review(
    monkeypatch,
    semantic_provider,
):
    async def unavailable(**_kwargs):
        raise AIServiceError(502, "AI_UPSTREAM_UNAVAILABLE")

    monkeypatch.setattr(classifier, "request_structured_completion", unavailable)

    result = await content_moderation.assess_content_moderation(
        "An otherwise ordinary sentence."
    )

    assert result.status == "pending_review"
    assert result.reason == "classifier_unavailable"


@pytest.mark.asyncio
async def test_trusted_classifier_marks_semantic_political_content(
    monkeypatch,
    semantic_provider,
):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )

    async def classify(_texts):
        return ["political"]

    monkeypatch.setattr(
        classifier,
        "classify_with_trusted_local_service",
        classify,
    )
    result = await content_moderation.assess_content_moderation(
        "A semantically sensitive sentence without a magic keyword."
    )
    assert result.status == "pending_review"
    assert result.reason == "political_or_uncertain"
    assert len(semantic_provider.eval_calls) == 1
    assert "ai:moderation:local:qps" in str(semantic_provider.eval_calls[0])


def test_local_classifier_remains_preferred_over_provider_fallback(
    monkeypatch,
    semantic_provider,
):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )

    assert classifier._moderation_engine(environment_ai_config()) == (
        "trusted-local:http://politics-classifier:8080/classify",
        "trusted_classifier",
    )


@pytest.mark.asyncio
async def test_configured_classifier_failure_falls_back_to_provider(
    monkeypatch,
    semantic_provider,
):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )

    async def unavailable(_texts):
        raise AIServiceError(503, "AI_POLITICAL_GUARD_UNAVAILABLE")

    monkeypatch.setattr(
        classifier,
        "classify_with_trusted_local_service",
        unavailable,
    )
    result = await content_moderation.assess_content_moderation(
        "An otherwise ordinary sentence."
    )
    assert result.status == "pending_review"
    assert result.reason == "classifier_unavailable"


@pytest.mark.asyncio
async def test_enabled_moderation_without_a_semantic_engine_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "AI_FEATURES_ENABLED", True)
    monkeypatch.setattr(settings, "AI_POLITICAL_CLASSIFIER_URL", "")
    monkeypatch.setattr(settings, "AI_MODERATION_PROVIDER_FALLBACK_ENABLED", False)

    result = await content_moderation.assess_content_moderation("Ordinary content")

    assert result.status == "pending_review"
    assert result.reason == "classifier_unavailable"
