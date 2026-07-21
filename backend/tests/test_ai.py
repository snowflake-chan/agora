import asyncio
import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.ai import client as ai_client
from app.ai import classifier as political_classifier
from app.ai import service as ai_service
from app.ai import storage
from app.ai import routes as ai_routes
from app.ai.errors import AIServiceError
from app.ai.routes import (
    ai_eligible_user,
    published_poll_questions,
    router as ai_router,
)
from app.config import settings
from app.db import get_session


class FakeRedis:
    def __init__(self, *, count: int = 1, ttl: int = 60, reservations=None):
        self.count = count
        self.ttl = ttl
        self.reservations = list(reservations or [True])
        self.eval_calls = []
        self.set_calls = []
        self.get_calls = []
        self.cache = {}

    async def eval(self, *args):
        self.eval_calls.append(args)
        return [self.count, self.ttl]

    async def set(self, *args, **kwargs):
        self.set_calls.append((args, kwargs))
        if kwargs.get("nx"):
            return self.reservations.pop(0) if self.reservations else True
        self.cache[args[0]] = args[1]
        return True

    async def get(self, key):
        self.get_calls.append(key)
        return self.cache.get(key)


@pytest.fixture
def ai_app():
    app = FastAPI()
    app.include_router(ai_router, prefix="/api/v1/ai")

    async def authenticated_user():
        return SimpleNamespace(id=uuid.UUID(int=1))

    app.dependency_overrides[ai_eligible_user] = authenticated_user

    async def no_published_questions():
        return []

    app.dependency_overrides[published_poll_questions] = no_published_questions

    async def no_database_session():
        yield object()

    app.dependency_overrides[get_session] = no_database_session
    return app


@pytest.fixture(autouse=True)
def configured_ai(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "AI_FEATURES_ENABLED", True)
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "DEEPSEEK_MODEL", "deepseek-v4-flash")
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    monkeypatch.setattr(settings, "AI_BASE_URL", "")
    monkeypatch.setattr(settings, "AI_MODEL", "")
    monkeypatch.setattr(settings, "AI_HTTP_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(settings, "AI_TEMPERATURE", 0.0)
    monkeypatch.setattr(settings, "AI_RESPONSE_FORMAT_ENABLED", True)
    monkeypatch.setattr(settings, "AI_THINKING_MODE", "")
    monkeypatch.setattr(settings, "AI_POLITICAL_CLASSIFIER_URL", "")
    monkeypatch.setattr(settings, "AI_POLITICAL_CLASSIFIER_TIMEOUT_SECONDS", 3.0)
    monkeypatch.setattr(settings, "AI_MODERATION_PROVIDER_FALLBACK_ENABLED", True)
    monkeypatch.setattr(settings, "AI_MODERATION_POLICY_VERSION", "test-policy-v1")
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
    monkeypatch.setattr(settings, "AI_MODERATION_MAX_CONCURRENT_REQUESTS", 8)
    monkeypatch.setattr(settings, "AI_MAX_INPUT_CHARS", 12000)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_REQUESTS", 20)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_IP_REQUESTS", 60)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_GLOBAL_REQUESTS", 200)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_GLOBAL_QPS", 8)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_DAILY_GLOBAL_REQUESTS", 2000)
    monkeypatch.setattr(settings, "AI_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "AI_POLL_RESERVATION_TTL_SECONDS", 60)
    monkeypatch.setattr(settings, "AI_TRANSLATION_CACHE_TTL_SECONDS", 604800)
    monkeypatch.setattr(settings, "AI_MAX_CONCURRENT_REQUESTS", 8)

    async def allow_semantic_content(_texts, **_kwargs):
        return political_classifier.SemanticModerationDecision(
            status="non_political",
            provenance="provider",
        )

    # Most endpoint tests isolate task behavior. Classifier integration tests below
    # restore the real shared semantic gate explicitly.
    monkeypatch.setattr(
        ai_service,
        "require_semantic_classification",
        allow_semantic_content,
    )


async def post(app: FastAPI, path: str, payload: dict) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, json=payload)


async def get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def mock_redis(monkeypatch, fake: FakeRedis) -> FakeRedis:
    async def get_fake_redis():
        return fake

    monkeypatch.setattr(storage, "get_redis", get_fake_redis)
    return fake


def mock_deepseek(monkeypatch, responses, *, finish_reason: str = "stop"):
    real_async_client = httpx.AsyncClient
    requests: list[httpx.Request] = []
    pending = list(responses)

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        content = pending.pop(0)
        if isinstance(content, dict):
            content = dict(content)
            if "political_status" in content:
                content.setdefault(
                    "output_political_status",
                    (
                        "non_political"
                        if content["political_status"] == "non_political"
                        else None
                    ),
                )
            content = json.dumps(content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": finish_reason, "message": {"content": content}}
                ]
            },
        )

    def build_client():
        return real_async_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(ai_client, "_build_http_client", build_client)
    return requests


def mock_local_classifier(monkeypatch, statuses, *, status_code: int = 200):
    real_async_client = httpx.AsyncClient
    requests: list[httpx.Request] = []
    batches = list(statuses) if statuses and isinstance(statuses[0], list) else [statuses]
    fallback = batches[-1]

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        batch = batches.pop(0) if batches else fallback
        return httpx.Response(status_code, json={"statuses": batch})

    def build_client():
        return real_async_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(political_classifier, "_build_http_client", build_client)
    return requests


@pytest.mark.asyncio
async def test_status_is_anonymous_and_does_not_probe_dependencies(ai_app, monkeypatch):
    async def unavailable_redis():
        raise AssertionError("status must not use Redis")

    monkeypatch.setattr(storage, "get_redis", unavailable_redis)
    monkeypatch.setattr(ai_client, "_build_http_client", lambda: (_ for _ in ()).throw(AssertionError()))

    enabled = await get(ai_app, "/api/v1/ai/status")
    assert enabled.status_code == 200
    assert enabled.json() == {"enabled": True}

    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "")
    disabled = await get(ai_app, "/api/v1/ai/status")
    assert disabled.status_code == 200
    assert disabled.json() == {"enabled": False}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("setting", "value"),
    [("AI_FEATURES_ENABLED", False), ("DEEPSEEK_API_KEY", "")],
)
async def test_ai_is_unavailable_when_disabled_or_unconfigured(
    ai_app,
    monkeypatch,
    setting,
    value,
):
    monkeypatch.setattr(settings, setting, value)

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "A short product update", "target_locale": "en"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI_FEATURE_UNAVAILABLE"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["political", "uncertain"])
async def test_political_or_uncertain_content_is_never_returned(
    ai_app,
    monkeypatch,
    status,
):
    mock_redis(monkeypatch, FakeRedis())
    requests = mock_deepseek(
        monkeypatch,
        [{"political_status": status}],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "Source content", "target_locale": "en"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "POLITICAL_CONTENT_UNAVAILABLE"}
    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    assert requests[0].url == "https://api.deepseek.com/chat/completions"
    assert payload["model"] == "deepseek-v4-flash"
    assert "thinking" not in payload
    assert payload["temperature"] == 0.0
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_semantic_source_guard_blocks_before_task_provider(
    ai_app,
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )

    async def reject_semantic_content(texts, **kwargs):
        calls.append((texts, kwargs))
        raise AIServiceError(
            422,
            "POLITICAL_CONTENT_UNAVAILABLE",
            source_moderation_reason=kwargs.get("source_moderation_reason"),
            source_moderation_provenance="provider",
        )

    mock_redis(monkeypatch, FakeRedis())
    monkeypatch.setattr(
        ai_service,
        "require_semantic_classification",
        reject_semantic_content,
    )
    monkeypatch.setattr(
        ai_client,
        "_build_http_client",
        lambda: (_ for _ in ()).throw(
            AssertionError("political text must not reach the provider")
        ),
    )

    response = await post(
        ai_app,
        "/api/v1/ai/translate",
        {
            "text": "A semantically political discussion",
            "target_locale": "en",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "POLITICAL_CONTENT_UNAVAILABLE"}
    assert calls[0][0] == ["A semantically political discussion"]


@pytest.mark.asyncio
async def test_semantic_guard_rechecks_mislabeled_provider_output(ai_app, monkeypatch):
    mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "output_political_status": "political",
                "summary": None,
            }
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "A short product update", "target_locale": "en"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "AI_OUTPUT_BLOCKED"}


@pytest.mark.asyncio
async def test_trusted_local_classifier_blocks_unmatched_political_language(
    ai_app,
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )
    monkeypatch.setattr(
        ai_service,
        "require_semantic_classification",
        political_classifier.require_semantic_classification,
    )
    mock_redis(monkeypatch, FakeRedis())
    requests = mock_local_classifier(monkeypatch, ["political"])
    monkeypatch.setattr(
        ai_client,
        "_build_http_client",
        lambda: (_ for _ in ()).throw(AssertionError("provider must not be called")),
    )

    response = await post(
        ai_app,
        "/api/v1/ai/translate",
        {
            "text": "Should a prominent figure continue after the next vote?",
            "target_locale": "en",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "POLITICAL_CONTENT_UNAVAILABLE"}
    assert len(requests) == 1
    assert "prominent figure" in json.loads(requests[0].content)["texts"][0]


@pytest.mark.asyncio
async def test_trusted_local_classifier_failure_is_fail_closed(ai_app, monkeypatch):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )
    monkeypatch.setattr(
        ai_service,
        "require_semantic_classification",
        political_classifier.require_semantic_classification,
    )
    mock_redis(monkeypatch, FakeRedis())
    mock_local_classifier(monkeypatch, [], status_code=503)
    monkeypatch.setattr(
        ai_client,
        "_build_http_client",
        lambda: (_ for _ in ()).throw(AssertionError("provider must not be called")),
    )

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "A short product update", "target_locale": "en"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI_POLITICAL_GUARD_UNAVAILABLE"}


@pytest.mark.asyncio
@pytest.mark.parametrize("output_status", ["political", "uncertain"])
async def test_trusted_local_classifier_rechecks_provider_output(
    ai_app,
    monkeypatch,
    output_status,
):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )
    monkeypatch.setattr(
        ai_service,
        "require_semantic_classification",
        political_classifier.require_semantic_classification,
    )
    mock_redis(monkeypatch, FakeRedis())
    requests = mock_local_classifier(
        monkeypatch,
        [["non_political"], [output_status]],
    )
    mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "summary": "A prominent figure should continue after the next vote.",
            }
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "A short product update", "target_locale": "en"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "AI_OUTPUT_BLOCKED"}
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_invalid_model_json_is_a_safe_error(ai_app, monkeypatch):
    mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(monkeypatch, ["not json"])

    response = await post(
        ai_app,
        "/api/v1/ai/translate",
        {"text": "Source content", "target_locale": "ja"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI_UPSTREAM_INVALID_RESPONSE"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("finish_reason", "expected_status", "expected_detail"),
    [
        ("length", 502, "AI_UPSTREAM_INVALID_RESPONSE"),
        ("content_filter", 422, "AI_PROVIDER_FILTERED"),
    ],
)
async def test_nonfinal_provider_responses_are_never_returned(
    ai_app,
    monkeypatch,
    finish_reason,
    expected_status,
    expected_detail,
):
    mock_redis(monkeypatch, FakeRedis())
    provider_content = None if finish_reason == "content_filter" else {
        "political_status": "non_political",
        "summary": "Partial output",
    }
    mock_deepseek(
        monkeypatch,
        [provider_content],
        finish_reason=finish_reason,
    )

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "A short product update", "target_locale": "en"},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


@pytest.mark.asyncio
async def test_provider_stop_with_null_content_is_a_safe_error(ai_app, monkeypatch):
    mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(monkeypatch, [None], finish_reason="stop")

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "A short product update", "target_locale": "en"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI_UPSTREAM_INVALID_RESPONSE"}


@pytest.mark.asyncio
async def test_provider_specific_thinking_is_only_sent_when_explicit(
    ai_app,
    monkeypatch,
):
    monkeypatch.setattr(settings, "AI_THINKING_MODE", "disabled")
    mock_redis(monkeypatch, FakeRedis())
    requests = mock_deepseek(
        monkeypatch,
        [{"political_status": "non_political", "summary": "Short summary"}],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "A short product update", "target_locale": "en"},
    )

    assert response.status_code == 200
    assert json.loads(requests[0].content)["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
async def test_generic_provider_omits_nonportable_request_fields(
    ai_app,
    monkeypatch,
):
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "https://provider.example/v1")
    monkeypatch.setattr(settings, "AI_THINKING_MODE", "enabled")
    monkeypatch.setattr(settings, "AI_RESPONSE_FORMAT_ENABLED", False)
    mock_redis(monkeypatch, FakeRedis())
    requests = mock_deepseek(
        monkeypatch,
        [{"political_status": "non_political", "summary": "Short summary"}],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "A short product update", "target_locale": "en"},
    )

    assert response.status_code == 200
    payload = json.loads(requests[0].content)
    assert "thinking" not in payload
    assert "response_format" not in payload
    assert payload["temperature"] == 0.0


@pytest.mark.asyncio
async def test_poll_retries_once_then_rejects_global_duplicate(ai_app, monkeypatch):
    redis = mock_redis(monkeypatch, FakeRedis(reservations=[False, False]))
    requests = mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "question": "Which workspace ritual helps you focus?",
                "options": ["Planning", "Music"],
            },
            {
                "political_status": "non_political",
                "question": "Which workspace ritual helps you focus most?",
                "options": ["Planning", "Music"],
            },
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/polls/generate",
        {"text": "Discussing work habits", "target_locale": "en"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "AI_POLL_DUPLICATE"}
    assert len(requests) == 2
    # The second near-duplicate is rejected before it can reserve another
    # global digest.
    assert len(redis.set_calls) == 1
    for args, kwargs in redis.set_calls:
        assert args[0].startswith("ai:poll:question:")
        assert "workspace ritual" not in args[0]
        assert args[1] == "1"
        assert kwargs == {"nx": True, "ex": 60}


@pytest.mark.asyncio
async def test_client_excluded_question_retries_once_then_rejects(ai_app, monkeypatch):
    redis = mock_redis(monkeypatch, FakeRedis())
    requests = mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "question": "Which workspace ritual helps you focus?",
                "options": ["Planning", "Music"],
            },
            {
                "political_status": "non_political",
                "question": "Which workspace ritual helps you focus?",
                "options": ["Planning", "Music"],
            },
        ],
    )

    question = "Which workspace ritual helps you focus?"
    response = await post(
        ai_app,
        "/api/v1/ai/polls/generate",
        {
            "text": "Discussing work habits",
            "target_locale": "en",
            "exclude_questions": [question],
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "AI_POLL_DUPLICATE"}
    assert len(requests) == 2
    assert redis.set_calls == []


@pytest.mark.asyncio
async def test_ai_rate_limit_fails_closed_before_upstream_request(ai_app, monkeypatch):
    mock_redis(monkeypatch, FakeRedis(count=21, ttl=42))
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )
    monkeypatch.setattr(
        ai_service,
        "require_semantic_classification",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("semantic moderation must run after user and IP admission")
        ),
    )
    monkeypatch.setattr(
        ai_client,
        "_build_http_client",
        lambda: (_ for _ in ()).throw(AssertionError("upstream must not be called")),
    )

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "Source content", "target_locale": "en"},
    )

    assert response.status_code == 429
    assert response.json() == {"detail": "AI_RATE_LIMITED"}
    assert response.headers["retry-after"] == "42"


@pytest.mark.asyncio
async def test_ai_redis_failure_fails_closed(ai_app, monkeypatch):
    async def unavailable_redis():
        raise RuntimeError("unavailable")

    monkeypatch.setattr(storage, "get_redis", unavailable_redis)

    response = await post(
        ai_app,
        "/api/v1/ai/summarize",
        {"text": "Source content", "target_locale": "en"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI_RATE_LIMIT_UNAVAILABLE"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload", "model_response", "expected"),
    [
        (
            "/api/v1/ai/summarize",
            {"text": "A release improves search speed.", "target_locale": "ja"},
            {"political_status": "non_political", "summary": "Search is faster."},
            {"summary": "Search is faster."},
        ),
        (
            "/api/v1/ai/translate",
            {"text": "A release improves search speed.", "target_locale": "zh-TW"},
            {"political_status": "non_political", "translation": "版本提升搜尋速度。"},
            {"translation": "版本提升搜尋速度。"},
        ),
        (
            "/api/v1/ai/polls/generate",
            {"text": "A release improves search speed.", "target_locale": "en"},
            {
                "political_status": "non_political",
                "question": "Which search improvement matters most?",
                "options": ["Speed", "Accuracy", "Filters"],
            },
            {
                "question": "Which search improvement matters most?",
                "options": ["Speed", "Accuracy", "Filters"],
            },
        ),
    ],
)
async def test_ai_endpoints_return_valid_non_political_results(
    ai_app,
    monkeypatch,
    path,
    payload,
    model_response,
    expected,
):
    redis = mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(monkeypatch, [model_response])

    response = await post(ai_app, path, payload)

    assert response.status_code == 200, response.text
    assert response.json() == expected
    assert len(redis.eval_calls) == 5
    if path.endswith("polls/generate"):
        assert len(redis.set_calls) == 1
    else:
        assert redis.set_calls == []


@pytest.mark.asyncio
async def test_structured_translation_preserves_fields_context_and_order(
    ai_app,
    monkeypatch,
):
    redis = mock_redis(monkeypatch, FakeRedis())
    requests = mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "translations": ["Release notes", "Search is faster."],
            }
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/translate/fields",
        {
            "fields": [
                {"key": "title", "text": "Release notes"},
                {"key": "body", "text": "Search is faster."},
            ],
            "target_locale": "ja",
            "context": "post",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "fields": [
            {"key": "title", "translation": "Release notes"},
            {"key": "body", "translation": "Search is faster."},
        ],
        "cached": False,
    }
    provider_payload = json.loads(requests[0].content)
    user_payload = json.loads(provider_payload["messages"][1]["content"])
    assert user_payload["task"] == "translate_fields"
    assert user_payload["content_context"] == "post"
    assert user_payload["source_items"] == [
        {"key": "title", "text": "Release notes"},
        {"key": "body", "text": "Search is faster."},
    ]
    assert len(redis.eval_calls) == 5
    assert len(redis.get_calls) == 2
    assert len(redis.set_calls) == 1
    assert "Release notes" not in redis.get_calls[0]


@pytest.mark.asyncio
async def test_release_candidate_translation_is_not_misclassified(
    ai_app,
    monkeypatch,
):
    mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "translations": ["快速視窗", "候選人"],
            }
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/translate/fields",
        {
            "fields": [
                {"key": "title", "text": "Fast window"},
                {"key": "body", "text": "Candidate"},
            ],
            "target_locale": "zh-TW",
            "context": "patch",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["fields"] == [
        {"key": "title", "translation": "快速視窗"},
        {"key": "body", "translation": "候選人"},
    ]


@pytest.mark.asyncio
async def test_related_fields_use_one_contextual_classifier_document(
    ai_app,
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )
    monkeypatch.setattr(
        ai_service,
        "require_semantic_classification",
        political_classifier.require_semantic_classification,
    )
    mock_redis(monkeypatch, FakeRedis())
    classifier_requests = mock_local_classifier(
        monkeypatch,
        [["non_political"], ["non_political"]],
    )
    mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "translations": ["Old merged work", "History"],
            }
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/translate/fields",
        {
            "fields": [
                {"key": "title", "text": "舊合併作品"},
                {"key": "body", "text": "歷史"},
            ],
            "target_locale": "en",
            "context": "post",
        },
    )

    assert response.status_code == 200, response.text
    source_batch = json.loads(classifier_requests[0].content)["texts"]
    assert source_batch == ["舊合併作品\n\n歷史"]
    assert len(classifier_requests) == 2


@pytest.mark.asyncio
async def test_source_political_verdict_can_transition_canonical_content(
    ai_app,
    monkeypatch,
):
    content_id = uuid.uuid4()
    calls = []
    held = SimpleNamespace(
        id=content_id,
        revision_number=3,
        type="comment",
        parent_id=uuid.UUID(int=4),
        patch_id=None,
        guild_id=None,
    )

    async def hold(session, **kwargs):
        calls.append((session, kwargs))
        return held

    async def deliver(content):
        calls.append(("delivered", content))

    monkeypatch.setattr(ai_routes, "hold_translation_source_for_review", hold)
    monkeypatch.setattr(ai_routes, "_deliver_translation_moderation_hold", deliver)
    mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(
        monkeypatch,
        [{"political_status": "political", "translations": None}],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/translate/fields",
        {
            "fields": [{"key": "body", "text": "An indirect source"}],
            "target_locale": "en",
            "context": "comment",
            "source_content_id": str(content_id),
            "source_revision_number": 3,
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "POLITICAL_CONTENT_REVIEW_PENDING"}
    assert response.headers["x-agora-moderation-status"] == "pending_review"
    assert response.headers["x-agora-moderation-reason"] == "political_or_uncertain"
    assert response.headers["x-agora-content-id"] == str(content_id)
    assert response.headers["x-agora-revision-number"] == "3"
    assert response.headers["x-agora-target-href"] == f"/posts/{held.parent_id}#{content_id}"
    assert calls[0][1] == {
        "content_id": content_id,
        "revision_number": 3,
        "context": "comment",
        "fields": [("body", "An indirect source")],
        "reason": "political_or_uncertain",
        "verdict_provenance": "provider",
        "actor_id": uuid.UUID(int=1),
        "actor_is_staff": False,
    }
    assert calls[1] == ("delivered", held)


@pytest.mark.asyncio
async def test_output_only_verdict_never_transitions_source_content(
    ai_app,
    monkeypatch,
):
    content_id = uuid.uuid4()
    hold_calls = []

    async def hold(*args, **kwargs):
        hold_calls.append((args, kwargs))
        return None

    monkeypatch.setattr(ai_routes, "hold_translation_source_for_review", hold)
    mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "output_political_status": "political",
                "translations": None,
            }
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/translate/fields",
        {
            "fields": [{"key": "body", "text": "An ordinary source"}],
            "target_locale": "en",
            "context": "comment",
            "source_content_id": str(content_id),
            "source_revision_number": 2,
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "AI_OUTPUT_BLOCKED"}
    assert hold_calls == []


@pytest.mark.asyncio
async def test_ai_hold_uses_durable_delivery(monkeypatch):
    content = SimpleNamespace(
        id=uuid.uuid4(),
        revision_number=2,
        type="post",
        parent_id=None,
        patch_id=None,
    )
    delivered = []

    async def deliver(content_id):
        delivered.append(content_id)

    monkeypatch.setattr(ai_routes, "deliver_moderation_effects", deliver)

    await ai_routes._deliver_translation_moderation_hold(content)
    assert delivered == [content.id]


@pytest.mark.asyncio
async def test_structured_translation_cache_hit_skips_provider_but_charges_admission(
    ai_app,
    monkeypatch,
):
    redis = mock_redis(monkeypatch, FakeRedis())
    requests = mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "translations": ["A cached translation"],
            }
        ],
    )
    payload = {
        "fields": [{"key": "body", "text": "A source paragraph"}],
        "target_locale": "zh-TW",
        "context": "comment",
    }

    first = await post(ai_app, "/api/v1/ai/translate/fields", payload)
    second = await post(ai_app, "/api/v1/ai/translate/fields", payload)

    assert first.status_code == 200, first.text
    assert first.json()["cached"] is False
    assert second.status_code == 200, second.text
    assert second.json() == {
        "fields": [{"key": "body", "translation": "A cached translation"}],
        "cached": True,
    }
    assert len(requests) == 1
    assert len(redis.eval_calls) == 10
    assert len(redis.get_calls) == 3
    assert len(redis.set_calls) == 1


@pytest.mark.asyncio
async def test_concurrent_translation_cache_misses_use_one_provider_call(
    ai_app,
    monkeypatch,
):
    redis = mock_redis(monkeypatch, FakeRedis())
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def complete(**_kwargs):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return ai_service.TranslationBundleAIResponse(
            political_status="non_political",
            output_political_status="non_political",
            translations=["One translation"],
        )

    monkeypatch.setattr(ai_service, "_request_completion", complete)
    payload = {
        "fields": [{"key": "body", "text": "One source"}],
        "target_locale": "ja",
        "context": "comment",
    }
    first = asyncio.create_task(
        post(ai_app, "/api/v1/ai/translate/fields", payload)
    )
    await started.wait()
    second = asyncio.create_task(
        post(ai_app, "/api/v1/ai/translate/fields", payload)
    )
    await asyncio.sleep(0)
    release.set()

    responses = await asyncio.gather(first, second)

    assert calls == 1
    assert sorted(response.json()["cached"] for response in responses) == [False, True]
    assert len(redis.set_calls) == 1


@pytest.mark.asyncio
async def test_production_translation_cache_hit_rechecks_cached_output(
    ai_app,
    monkeypatch,
):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "AI_API_KEY", "production-key")
    monkeypatch.setattr(settings, "AI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setattr(settings, "AI_MODEL", "production-model")
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )
    moderation_calls = []

    async def approve(texts, **_kwargs):
        moderation_calls.append(texts)
        return political_classifier.SemanticModerationDecision(
            status="non_political",
            provenance="trusted_classifier",
        )

    monkeypatch.setattr(ai_service, "require_semantic_classification", approve)
    mock_redis(monkeypatch, FakeRedis())
    requests = mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "translations": ["Cached production output"],
            }
        ],
    )
    payload = {
        "fields": [{"key": "body", "text": "Production source"}],
        "target_locale": "en",
        "context": "comment",
    }

    first = await post(ai_app, "/api/v1/ai/translate/fields", payload)
    second = await post(ai_app, "/api/v1/ai/translate/fields", payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["cached"] is True
    assert len(requests) == 1
    assert moderation_calls[-1] == ["Cached production output"]


def test_translation_cache_key_tracks_provider_prompt_schema_and_sampling(
    monkeypatch,
):
    kwargs = {
        "fields": [("body", "Source")],
        "target_locale": "en",
        "context": "comment",
        "user_prompt": "prompt-v1",
    }
    first = storage.translation_cache_key(**kwargs)
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "https://next.example/v1")
    second = storage.translation_cache_key(**kwargs)
    monkeypatch.setattr(settings, "AI_TEMPERATURE", 0.4)
    third = storage.translation_cache_key(**kwargs)
    fourth = storage.translation_cache_key(**{**kwargs, "user_prompt": "prompt-v2"})

    class NextTranslationSchema:
        @staticmethod
        def model_json_schema():
            return {"type": "object", "required": ["next_translations"]}

    monkeypatch.setattr(storage, "TranslationBundleAIResponse", NextTranslationSchema)
    fifth = storage.translation_cache_key(**{**kwargs, "user_prompt": "prompt-v2"})
    monkeypatch.setattr(settings, "AI_POLITICAL_CLASSIFIER_VERSION", "classifier-v2")
    sixth = storage.translation_cache_key(**{**kwargs, "user_prompt": "prompt-v2"})

    assert len({first, second, third, fourth, fifth, sixth}) == 6


@pytest.mark.asyncio
async def test_provider_calls_share_one_client_semaphore(monkeypatch):
    active = 0
    max_active = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {"political_status": "non_political"}
                            )
                        },
                    }
                ]
            },
        )

    monkeypatch.setattr(ai_client, "_provider_semaphore", asyncio.Semaphore(1))
    monkeypatch.setattr(
        ai_client,
        "_build_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    await asyncio.gather(
        ai_client.request_structured_completion(
            user_message="{}",
            response_type=political_classifier.ModerationAIResponse,
            max_tokens=24,
        ),
        ai_client.request_structured_completion(
            user_message="{}",
            response_type=political_classifier.ModerationAIResponse,
            max_tokens=24,
        ),
    )

    assert max_active == 1


@pytest.mark.asyncio
async def test_structured_translation_rejects_wrong_output_count(ai_app, monkeypatch):
    mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(
        monkeypatch,
        [{"political_status": "non_political", "translations": ["Only one"]}],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/translate/fields",
        {
            "fields": [
                {"key": "title", "text": "A title"},
                {"key": "body", "text": "A body"},
            ],
            "target_locale": "en",
            "context": "patch",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI_UPSTREAM_INVALID_RESPONSE"}


@pytest.mark.asyncio
async def test_writing_assist_preserves_field_order_and_declares_action(
    ai_app,
    monkeypatch,
):
    redis = mock_redis(monkeypatch, FakeRedis())
    requests = mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "rewrites": ["Clear release title", "A concise release description."],
            }
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/writing/assist",
        {
            "fields": [
                {"key": "title", "text": "Release title that is unclear"},
                {"key": "body", "text": "A release description with extra wording."},
            ],
            "target_locale": "en",
            "context": "composer",
            "action": "clarify",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "fields": [
            {"key": "title", "translation": "Clear release title"},
            {"key": "body", "translation": "A concise release description."},
        ]
    }
    provider_payload = json.loads(requests[0].content)
    user_payload = json.loads(provider_payload["messages"][1]["content"])
    assert user_payload["task"] == "write_assist"
    assert user_payload["writing_action"] == "clarify"
    assert user_payload["content_context"] == "composer"
    assert [item["key"] for item in user_payload["source_items"]] == ["title", "body"]
    assert len(redis.eval_calls) == 5


@pytest.mark.asyncio
async def test_writing_assist_rejects_wrong_output_count(ai_app, monkeypatch):
    mock_redis(monkeypatch, FakeRedis())
    mock_deepseek(
        monkeypatch,
        [{"political_status": "non_political", "rewrites": ["Only one rewrite"]}],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/writing/assist",
        {
            "fields": [
                {"key": "title", "text": "A title"},
                {"key": "body", "text": "A body"},
            ],
            "target_locale": "en",
            "context": "patch",
            "action": "polish",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI_UPSTREAM_INVALID_RESPONSE"}


@pytest.mark.asyncio
async def test_ai_honors_configurable_input_limit(ai_app, monkeypatch):
    monkeypatch.setattr(settings, "AI_MAX_INPUT_CHARS", 5)

    response = await post(
        ai_app,
        "/api/v1/ai/translate",
        {"text": "six chars", "target_locale": "en"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "AI_INPUT_TOO_LONG"}


@pytest.mark.asyncio
async def test_poll_exclusion_budget_is_bounded(ai_app):
    response = await post(
        ai_app,
        "/api/v1/ai/polls/generate",
        {
            "text": "A non-political product discussion",
            "target_locale": "en",
            "exclude_questions": [f"Question {index}" for index in range(13)],
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_excluded_questions_share_the_structured_semantic_verdict(
    ai_app,
    monkeypatch,
):
    requests = mock_deepseek(
        monkeypatch,
        [{"political_status": "political"}],
    )
    mock_redis(monkeypatch, FakeRedis())

    response = await post(
        ai_app,
        "/api/v1/ai/polls/generate",
        {
            "text": "A product design discussion",
            "target_locale": "en",
            "exclude_questions": ["政府选举"],
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "POLITICAL_CONTENT_UNAVAILABLE"}
    provider_payload = json.loads(requests[0].content)
    user_payload = json.loads(provider_payload["messages"][1]["content"])
    assert user_payload["excluded_questions"] == ["政府选举"]


@pytest.mark.asyncio
async def test_published_questions_block_exact_and_near_duplicate_generation(
    ai_app,
    monkeypatch,
):
    async def existing_questions():
        return ["Which workspace ritual helps you focus?"]

    ai_app.dependency_overrides[published_poll_questions] = existing_questions
    redis = mock_redis(monkeypatch, FakeRedis(reservations=[True]))
    requests = mock_deepseek(
        monkeypatch,
        [
            {
                "political_status": "non_political",
                "question": "Which workspace ritual helps you focus most?",
                "options": ["Planning", "Music"],
            },
            {
                "political_status": "non_political",
                "question": "Which break rhythm supports your day?",
                "options": ["Short walks", "Quiet time"],
            },
        ],
    )

    response = await post(
        ai_app,
        "/api/v1/ai/polls/generate",
        {"text": "Discussing work habits", "target_locale": "en"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["question"] == "Which break rhythm supports your day?"
    assert len(requests) == 2
    assert len(redis.set_calls) == 1


@pytest.mark.asyncio
async def test_ai_eligibility_checks_global_bans(monkeypatch):
    user = SimpleNamespace(id=uuid.UUID(int=2))
    session = SimpleNamespace()
    calls = []

    async def commit():
        calls.append("commit")

    session.commit = commit

    async def fake_check_not_banned(user_id, checked_session):
        calls.append((user_id, checked_session))

    monkeypatch.setattr(ai_routes, "check_not_banned", fake_check_not_banned)

    assert await ai_eligible_user(user, session) is user
    assert calls == [(user.id, session), "commit"]


@pytest.mark.asyncio
async def test_published_poll_questions_release_the_read_transaction():
    events = []

    class ScalarResult:
        def all(self):
            events.append("read")
            return ["First question", "Second question"]

    class Session:
        async def scalars(self, _statement):
            return ScalarResult()

        async def commit(self):
            events.append("commit")

    questions = await published_poll_questions(Session())

    assert questions == ["First question", "Second question"]
    assert events == ["read", "commit"]


def test_question_similarity_catches_reordered_high_overlap_phrasing():
    assert storage.questions_are_similar(
        "Which workspace rituals help you focus during a release?",
        "During a release, which workspace rituals help you focus?",
    )
