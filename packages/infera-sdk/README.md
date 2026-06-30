# infera-sdk

A small Python SDK that wraps LLM calls and records what happened on every call —
latency, time-to-first-token, token usage, cost, and status — then ships those
records to an ingestion endpoint in the background. The logging path is fully
non-blocking, so it never slows down or breaks the chat itself.

```python
from infera import InferaClient
from infera.providers import FallbackProvider, OllamaProvider, OpenRouterProvider

client = InferaClient(
    provider=OllamaProvider(base_url="http://localhost:11434/v1"),
    ingestion_url="http://localhost:8001/v1/logs",
)

result = await client.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    model="qwen3:14b",
    session_id="sess_123",
)
print(result.text, result.latency_ms, result.usage.total_tokens)
```

OpenRouter can be used for hosted models:

```python
client = InferaClient(
    provider=OpenRouterProvider(api_key="sk-or-..."),
    ingestion_url="http://localhost:8001/v1/logs",
)
```

The providers can also be composed so a hosted provider falls back to local
Ollama before any streamed tokens are sent:

```python
provider = FallbackProvider(
    OpenRouterProvider(api_key="sk-or-..."),
    OllamaProvider(base_url="http://localhost:11434/v1"),
    fallback_model="qwen3:14b",
)
```
