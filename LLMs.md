# Instructions for implementing LLM apis

The following is instructions for implementing with LLM APIs. The models that are currently targeted are the OpenAI GPT5+ models, the Anthropic Claude Sonnet/Opus 4+ models, and Google Gemini 3+ models.

**Important:** Always use the latest stable API versions and official SDKs. Avoid deprecated endpoints and legacy APIs.

## Current Implementation Status

**✅ Implemented:**
- OpenAI GPT-4/5 series (via Chat Completions API)
- Anthropic Claude Sonnet/Opus 4+ series (via Messages API)
- Google Gemini 2/3 series (via Gemini API)
- Multi-provider routing with model registry support

**Architecture:**
- Provider-agnostic `BaseLLMClient` abstraction
- Factory pattern for client instantiation (`create_llm_client`)
- Model registry-based routing (`get_llm_client_for_model`)
- Per-model timeout/retry configuration
- Thread-safe client caching
- Normalized error handling across providers

## OpenAI GPT5

When implementing OpenAI integration, the target API should be the **Chat Completions API** since it is the recommended most long term compatible option. The GPT 5 series models support the Chat Completions API and these are the models we want to use when implementing AI integration. Do not use the legacy Completions API as it is not recommended moving forward.

- Target model: `gpt-5.1`
- Use the official `openai` Python package or equivalent SDK for your language
- API endpoint: `/v1/chat/completions`

**Do NOT use:** Completions API (deprecated), legacy models like GPT-3.5 or older

### Current Implementation Details

The Software Planner uses the OpenAI Chat Completions API with the following characteristics:

**SDK**: `openai==2.14.0` (official Python SDK)

**API Endpoint**: Chat Completions (`/v1/chat/completions`)

**Request Format**:
```python
response = client.chat.completions.create(
    model="gpt-5.1",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_description}
    ],
    temperature=0.7,
    max_tokens=2000
)
```

**Retry Logic**:
- Max retries: 3 attempts
- Backoff: Exponential (1s → 2s → 4s → 8s, capped at 10s)
- Retryable errors: Timeouts, rate limits (429), connection errors, 5xx server errors
- Non-retryable errors: Authentication (401), bad request (400), not found (404)

**Timeout**: Configurable via `LLM_TIMEOUT` (default: 60 seconds per attempt)

## Anthropic Claude Sonnet/Opus 4

When implementing Anthropic integration, the target API should be the **Messages API** (API version `2023-06-01` or newer) since it is the most long term compatible option. The Claude Sonnet 4 and Opus 4 series models are supportive of the Messages API and these are the models we want to use when implementing AI integration.

- Target model: Sonnet 4.5
- Use the official `anthropic` Python package or `@anthropic-ai/sdk` for JS/TS

**Do NOT use:** Text Completions API (deprecated), Claude 2.x or older models

**Status**: ✅ Implemented in `app/services/llm_claude.py`

### Current Implementation Details

The Software Planner uses the Anthropic Messages API with the following characteristics:

**SDK**: `anthropic==0.75.0` (official Python SDK)

**API Endpoint**: Messages (`/v1/messages`)

**Request Format**:
```python
response = client.messages.create(
    model="claude-sonnet-4.5",
    max_tokens=2000,
    system=system_prompt,
    messages=[
        {"role": "user", "content": user_description}
    ],
    temperature=0.7
)
```

**Retry Logic**:
- Max retries: 3 attempts (configurable per model)
- Backoff: Exponential (1s → 2s → 4s, capped at 10s)
- Retryable errors: Timeouts, rate limits (429), connection errors, 5xx server errors
- Non-retryable errors: Authentication (401), permission (403), not found (404), bad request (400)

**Timeout**: Configurable per model in registry (default: 60 seconds per attempt)

## Google Gemini 3

When implementing Google integration, the target API should be the **Gemini API** since it is the most long term compatible option. The Gemini 3 series models are supportive of the Gemini API and these are the models we want to use when implementing AI integration.

- Target model: `gemini-3.0-pro`
- Use the official `google-genai` Python package or `@google/genai` for JS/TS
- Ex. `from google import genai`

**Do NOT use:** PaLM API (deprecated), Gemini 1.x models, or legacy Bard endpoints

**Status**: ✅ Implemented in `app/services/llm_gemini.py`

### Current Implementation Details

The Software Planner uses the Google GenAI API with the following characteristics:

**SDK**: `google-genai==1.56.0` (official Python SDK)

**API Endpoint**: Generate Content

**Request Format**:
```python
response = client.models.generate_content(
    model="gemini-3.0-pro",
    contents=full_prompt,  # System prompt + user description
    config=types.GenerateContentConfig(
        temperature=0.7,
        max_output_tokens=2000
    )
)
```

**Retry Logic**:
- Max retries: 3 attempts (configurable per model)
- Backoff: Exponential (1s → 2s → 4s, capped at 10s)
- Retryable errors: Timeouts, rate limits (429), quota errors, unavailable (503), 5xx server errors
- Non-retryable errors: Authentication (401), permission (403), not found (404), bad request (400)

**Timeout**: Configurable per model in registry (default: 60 seconds per attempt)

**Note**: The `base_url` parameter is not directly supported by Google's GenAI SDK and will be ignored with a warning.

## General Best Practices

- Always check official documentation for the latest API versions
- Use environment variables for API keys, never hardcode them
- Implement proper error handling and rate limiting
- Use streaming responses when available for better UX
- Keep SDKs updated to the latest stable versions

---

# Multi-Provider Architecture

## Overview

The Software Planner supports multiple LLM providers through a unified routing architecture. This allows you to:

- Use different providers for different models
- Configure timeout and retry policies per model
- Switch providers without code changes
- Cache client instances for efficiency
- Get normalized errors across providers

## Model Registry

The model registry is a configuration-based system for managing logical models and their provider mappings. Each model has:

- **Logical name**: User-friendly identifier (e.g., `my-gpt-model`, `my-claude-model`)
- **Provider**: Backend provider (`openai`, `anthropic`, `google`)
- **Model ID**: Provider-specific model identifier (e.g., `gpt-5.1`, `claude-sonnet-4.5`)
- **API key environment variable**: Name of env var containing the API key
- **Enabled flag**: Whether the model can be used
- **Timeout**: Request timeout in seconds
- **Max retries**: Maximum retry attempts for transient failures

### Configuration Example

Using environment variables (recommended for production):

```bash
# Legacy single-model configuration (still supported)
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4

# Or use model registry for multi-provider support
MODELS_REGISTRY='{"my-gpt-model": {"provider": "openai", "model_id": "gpt-5.1", "api_key_env": "OPENAI_API_KEY", "enabled": true, "timeout": 60, "max_retries": 3}}'
DEFAULT_MODEL=my-gpt-model
OPENAI_API_KEY=sk-...
```

Using Python configuration (for programmatic setup):

```python
from app.core.config import Settings, ModelConfig

settings = Settings(
    models_registry={
        'my-gpt-model': ModelConfig(
            provider='openai',
            model_id='gpt-5.1',
            api_key_env='OPENAI_API_KEY',
            enabled=True,
            timeout=60,
            max_retries=3
        ),
        'my-claude-model': ModelConfig(
            provider='anthropic',
            model_id='claude-sonnet-4.5',
            api_key_env='ANTHROPIC_API_KEY',
            enabled=True,
            timeout=90,
            max_retries=5
        ),
        'my-gemini-model': ModelConfig(
            provider='google',
            model_id='gemini-3.0-pro',
            api_key_env='GOOGLE_API_KEY',
            enabled=True,
            timeout=45,
            max_retries=3
        )
    },
    default_model='my-gpt-model'
)
```

## Client Factory and Router

### Creating Clients Directly

```python
from app.services.llm_client import create_llm_client

# Create an OpenAI client
client = create_llm_client(
    provider='openai',
    model_id='gpt-5.1',
    api_key='sk-...',
    timeout=60,
    max_retries=3
)

# Create a Claude client
client = create_llm_client(
    provider='anthropic',
    model_id='claude-sonnet-4.5',
    api_key='sk-ant-...',
    timeout=90
)

# Create a Gemini client
client = create_llm_client(
    provider='google',
    model_id='gemini-3.0-pro',
    api_key='...',
    timeout=45
)
```

### Using the Router (Recommended)

```python
from app.services.llm_client import get_llm_client_for_model

# Get client for a logical model
client = get_llm_client_for_model('my-gpt-model')

# Use the client (provider-agnostic)
result = client.generate_specs("Build a REST API")
```

The router:
1. Fetches model config from the registry
2. Validates the model is enabled
3. Gets API key from the configured environment variable
4. Creates or returns a cached client instance
5. Enforces timeout and retry policies

### Client Caching

Clients are cached by logical model ID to avoid repeated SDK initialization. Caching is:

- **Thread-safe**: Uses locks to prevent race conditions
- **Per-model**: Each logical model gets its own cached client
- **Persistent**: Cached for the lifetime of the application
- **Optional**: Can be disabled by passing `cache_clients=False`

## Error Normalization

All providers raise consistent error types:

- `LLMConfigurationError`: Missing API key, invalid model, disabled model
- `LLMRequestError`: API request failures (timeout, rate limit, network error)
- `LLMResponseError`: Invalid or unparseable responses

This allows consistent error handling regardless of provider:

```python
from app.services.llm_client import (
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError
)

try:
    result = client.generate_specs(description)
except LLMConfigurationError as e:
    # Fix configuration (API key, model name, etc.)
    log_error("Configuration issue", error=e)
except LLMRequestError as e:
    # Retry or backoff (already retried internally)
    log_error("API request failed", error=e)
except LLMResponseError as e:
    # Invalid response format
    log_error("Response parsing failed", error=e)
```

## Telemetry and Logging

All clients emit structured logs with provider and model context:

```
INFO: Created LLM client for model 'my-claude-model'
  logical_model=my-claude-model
  provider=anthropic
  model_id=claude-sonnet-4.5
  timeout=90
  max_retries=5

INFO: Claude API call succeeded
  model=claude-sonnet-4.5
  retry_count=0
  latency_ms=3421
  input_tokens=50
  output_tokens=100
  stop_reason=end_turn
```

This allows:
- Tracking which provider/model was used for each request
- Monitoring latency per provider
- Tracking token usage per provider
- Debugging provider-specific issues

## Migration Guide

### From Legacy Single-Model to Registry

**Before** (legacy):
```bash
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4
```

**After** (registry):
```bash
MODELS_REGISTRY='{"my-model": {"provider": "openai", "model_id": "gpt-5.1", "api_key_env": "OPENAI_API_KEY", "enabled": true}}'
DEFAULT_MODEL=my-model
OPENAI_API_KEY=sk-...
```

The legacy configuration still works, but the registry provides more flexibility.

### Adding a New Provider

To add a new provider (e.g., `my-claude-model`):

1. Set up API key:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

2. Add model to registry:
   ```bash
   export MODELS_REGISTRY='{"my-claude-model": {"provider": "anthropic", "model_id": "claude-sonnet-4.5", "api_key_env": "ANTHROPIC_API_KEY", "enabled": true}}'
   ```

3. Optionally set as default:
   ```bash
   export DEFAULT_MODEL=my-claude-model
   ```

4. Restart the application

No code changes required!

---

# Model Discovery and Selection

This section explains how to discover available models and select them for planning requests.

## Discovery Endpoint

### GET /api/v1/models

The discovery endpoint lists all enabled models with their metadata, allowing clients to:
- Validate model availability before submitting jobs
- Understand model constraints (timeout limits, context windows)
- Select appropriate models based on requirements
- Monitor what models are currently available

**Example Request:**
```bash
curl http://localhost:8000/api/v1/models
```

**Example Response:**
```json
{
  "models": [
    {
      "logical_name": "my-gpt-model",
      "provider": "openai",
      "model_id": "gpt-5.1",
      "enabled": true,
      "timeout": 60,
      "max_retries": 3,
      "description": "OpenAI gpt-5.1 - Latest generation model with improved reasoning and performance",
      "metadata": {
        "approximate_max_context": 128000,
        "supports_streaming": false,
        "has_custom_base_url": false
      }
    },
    {
      "logical_name": "my-claude-model",
      "provider": "anthropic",
      "model_id": "claude-sonnet-4.5",
      "enabled": true,
      "timeout": 90,
      "max_retries": 5,
      "description": "Anthropic claude-sonnet-4.5 - Balanced performance and speed for most tasks",
      "metadata": {
        "approximate_max_context": 200000,
        "supports_streaming": false
      }
    }
  ]
}
```

### Response Field Reference

**Top-Level Fields:**
- `logical_name` (string): User-friendly identifier to use in planning requests
- `provider` (string): Backend provider (`openai`, `anthropic`, `google`)
- `model_id` (string): Provider-specific model identifier (e.g., `gpt-5.1`, `claude-sonnet-4.5`)
- `enabled` (boolean): Whether the model is available (always `true` in responses, disabled models are filtered out)
- `timeout` (integer): Request timeout in seconds - planning requests will time out after this duration
- `max_retries` (integer): Maximum automatic retry attempts for transient failures (rate limits, timeouts, 5xx errors)
- `description` (string): Human-readable description of the model's capabilities

**Metadata Fields:**
- `approximate_max_context` (integer): Approximate token limit for the model's context window
  - OpenAI GPT-5: 128,000 tokens
  - OpenAI GPT-4 Turbo: 128,000 tokens
  - OpenAI GPT-4: 8,192 tokens
  - Anthropic Claude 4/Sonnet/Opus: 200,000 tokens
  - Google Gemini 1.5+/2.0/3.0: 1,000,000 tokens
- `supports_streaming` (boolean): Whether streaming responses are supported (currently always `false`)
- `has_custom_base_url` (boolean, optional): Indicates a custom base URL is configured (actual URL not exposed for security)

### Empty Response Behavior

When no models are enabled or the registry is empty:
```json
{
  "models": []
}
```

This is still a successful response (HTTP 200 OK). Clients should handle this gracefully and inform users that no models are currently available.

### Security Considerations

The `/models` endpoint **does not expose**:
- API keys or credentials
- Full base URLs (only presence indicator)
- Internal environment variable names
- Any sensitive configuration beyond what's necessary for model selection

## Selecting Models in Planning Requests

### Default Model Behavior

If you don't specify a model in your planning request, the system uses the configured default model:
- For model registry configuration: The model specified by `DEFAULT_MODEL` environment variable
- For legacy configuration: The model specified by `LLM_MODEL` (defaults to `gpt-4`)

### Specifying a Model

Include the `model` field in your planning request body:

**Synchronous Planning:**
```bash
curl -X POST http://localhost:8000/api/v1/plan \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a REST API for managing tasks",
    "model": "my-claude-model"
  }'
```

**Asynchronous Planning:**
```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a REST API for managing tasks",
    "model": "my-gpt-model"
  }'
```

### Custom System Prompts

You can override the default system prompt (advanced users only):

```bash
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Build a REST API for managing tasks",
    "model": "my-gpt-model",
    "system_prompt": "You are an expert software architect specializing in microservices..."
  }'
```

**Constraints:**
- System prompts must not exceed 32,768 bytes (UTF-8 encoded)
- Custom prompts should enforce JSON-only output matching the expected schema
- Improper prompts may break response parsing - use with caution

### Model Validation

The API validates model names at request time:

**Unknown Model:**
```bash
# Request with invalid model
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{"description": "Build an API", "model": "nonexistent-model"}'

# Response: 400 Bad Request
{
  "error": "Unknown model 'nonexistent-model'. Available models: my-gpt-model, my-claude-model",
  "status_code": 400
}
```

**Disabled Model:**
```bash
# Response: 400 Bad Request
{
  "error": "Model 'disabled-model' is disabled",
  "status_code": 400
}
```

### Tracking Model Usage in Results

When you retrieve job status, the response includes which model was used:

```bash
curl http://localhost:8000/api/v1/plans/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "succeeded",
  "model": "my-claude-model",
  "system_prompt_hash": "a7b3c2d1e5f6...",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:05Z",
  "result": {
    "specs": [...]
  }
}
```

**Fields:**
- `model` (string, optional): Logical model name that was used (null if legacy config or default was used without registry)
- `system_prompt_hash` (string, optional): SHA-256 hash of the system prompt (only present if custom prompt was provided)

**Uses for Metadata:**
- **Debugging**: Identify which model generated a specific result
- **Performance Analysis**: Compare results across different models
- **Cost Tracking**: Monitor which models are being used most frequently
- **Audit Trail**: Track custom prompts via hash (actual prompt not stored for security)

## Telemetry and Monitoring

### Model Usage Logging

All model usage is logged with structured metadata:

```
INFO: Created LLM client for model 'my-claude-model'
  logical_model=my-claude-model
  provider=anthropic
  model_id=claude-sonnet-4.5
  timeout=90
  max_retries=5

INFO: Starting plan generation
  job_id=550e8400-...
  model=my-claude-model
  description_length=245
  using_custom_prompt=false

INFO: Claude API call succeeded
  model=claude-sonnet-4.5
  retry_count=0
  latency_ms=3421
  input_tokens=50
  output_tokens=100
  stop_reason=end_turn
```

### Monitoring Model Availability

Use the `/models` endpoint for health checks:

```bash
# Check model availability periodically
curl -s http://localhost:8000/api/v1/models | jq '.models | length'

# Expected: Number of enabled models (e.g., 2)
# If 0: All models are disabled or misconfigured
```

### Latency Expectations by Model

Based on typical usage patterns:

| Model | Typical Latency | Timeout Setting | Notes |
|-------|----------------|-----------------|-------|
| GPT-5.1 | 2-6 seconds | 60 seconds | Fastest for most tasks |
| GPT-4 Turbo | 3-8 seconds | 60 seconds | Good balance |
| GPT-4 | 4-10 seconds | 60 seconds | Slower but reliable |
| Claude Sonnet 4.5 | 3-7 seconds | 90 seconds | Balanced performance |
| Claude Opus 4 | 5-12 seconds | 120 seconds | Best quality, slowest |
| Gemini 3.0 Pro | 2-5 seconds | 60 seconds | Very fast |

**Factors Affecting Latency:**
- Description length and complexity
- Model generation speed
- Provider API load
- Network conditions
- Retry attempts

---

# Operational Guide

This section describes how the LLM integration operates at runtime, including logging, monitoring, error handling, and troubleshooting.

## Runtime Behavior

### Planning Flow

When a planning job is submitted, the system follows this flow:

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant JobStore
    participant Planner
    participant LLM as LLM Client
    participant OpenAI as OpenAI API

    Client->>API: POST /api/v1/plans
    API->>JobStore: Create job (pending)
    API->>Client: 202 Accepted (job_id)
    
    API->>Planner: Run in background
    Planner->>JobStore: Update status (running)
    
    Planner->>LLM: generate_specs(description)
    LLM->>OpenAI: API request (with system prompt)
    
    alt Success
        OpenAI->>LLM: JSON response
        LLM->>LLM: Parse & validate
        LLM->>Planner: Specs dict
        Planner->>JobStore: Update (succeeded, result)
    else Retryable Error
        OpenAI->>LLM: Timeout/429/5xx
        LLM->>LLM: Wait (backoff)
        LLM->>OpenAI: Retry request
    else Non-Retryable Error
        OpenAI->>LLM: 401/400/404
        LLM->>Planner: Raise exception
        Planner->>JobStore: Update (failed, error)
    end
    
    Client->>API: GET /api/v1/plans/{job_id}
    JobStore->>API: Job status & result
    API->>Client: Job details
```

### System Prompt and Response Structure

The LLM is instructed via a system prompt to generate specs in a specific JSON format:

**Default System Prompt** (simplified):
> You are a software planning assistant. Generate a structured software plan.
> 
> Your response MUST be valid JSON only:
> ```json
> {
>   "specs": [
>     {
>       "purpose": "string",
>       "vision": "string",
>       "must": ["array of strings"],
>       "dont": ["array of strings"],
>       "nice": ["array of strings"]
>     }
>   ]
> }
> ```

The planner then:
1. Extracts JSON from the response (handles markdown code blocks)
2. Validates the structure matches the schema
3. Normalizes edge cases (single spec → list, whitespace, oversized fields)
4. Validates against `PlanResponse` Pydantic model

## Logging and Monitoring

### Log Levels and Content

**INFO Level**:
- LLM client initialization (model, timeout, base URL presence)
- Request metadata (description length, using default/custom prompt)
- Retry attempts (retry count, backoff duration)
- Success metrics (latency, token count, spec count)

**WARNING Level**:
- Empty system prompt override (falls back to default)
- Empty `must` fields in specs after normalization
- Oversized fields being truncated

**ERROR Level**:
- Authentication failures (without exposing API key)
- API request failures (timeout, rate limit, network error)
- Response parsing failures (JSON errors, schema violations)
- Job update failures

**DEBUG Level** (if enabled):
- Response metadata (token counts, finish reason)

### Example Log Output

**Successful Planning**:
```
INFO: Initialized LLM client - model=gpt-5.1, base_url=default, timeout=60, has_api_key=True
INFO: Starting plan generation - job_id=550e8400-..., description_length=245
INFO: Generating specs via LLM - model=gpt-5.1, description_length=245, using_default_prompt=True
INFO: OpenAI API call succeeded - retry_count=0, latency_ms=3421, total_tokens=456, finish_reason=stop
INFO: Successfully generated specs - spec_count=2
INFO: Plan generation succeeded - job_id=550e8400-..., specs_count=2
```

**Failed Planning (Rate Limit)**:
```
INFO: Starting plan generation - job_id=550e8400-..., description_length=245
WARNING: OpenAI API call failed, will retry - error=Rate limit exceeded, retry_count=0, backoff=1.0
INFO: Retrying OpenAI API call - retry_count=1, max_retries=3, backoff=1.0
WARNING: OpenAI API call failed, will retry - error=Rate limit exceeded, retry_count=1, backoff=2.0
INFO: Retrying OpenAI API call - retry_count=2, max_retries=3, backoff=2.0
INFO: OpenAI API call succeeded - retry_count=2, latency_ms=5234, total_tokens=456
```

**Failed Planning (Authentication)**:
```
ERROR: OpenAI authentication failed - error=Invalid API key, retry_count=0
ERROR: Plan generation failed due to configuration error - job_id=550e8400-..., error=OpenAI authentication failed: Invalid API key. Please check your API key., error_type=LLMConfigurationError
```

### Security in Logging

The logging implementation follows these security principles:

✅ **Safe to Log**:
- Model name
- Request/response metadata (length, token count, latency)
- Error types and categories
- Retry counts and backoff durations
- Job IDs and timestamps

❌ **Never Logged**:
- API keys or credentials
- Full request descriptions (may contain sensitive project details)
- Full response content (may contain sensitive generated content)
- User-specific identifiers beyond job IDs

## Failure Modes and Troubleshooting

### 1. Configuration Errors (`LLMConfigurationError`)

**Symptoms**:
- Job fails immediately (usually within seconds)
- Error type: `LLMConfigurationError`
- Status: `failed`

**Common Causes**:

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "LLM API key is required" | `LLM_API_KEY` not set or empty | Set `LLM_API_KEY` in `.env` file |
| "OpenAI authentication failed: Invalid API key" | Invalid or revoked API key | Verify key in OpenAI dashboard, get new key |
| "OpenAI resource not found" | Invalid model name | Check `LLM_MODEL` spelling (e.g., "gpt-5.1") |
| "Failed to initialize OpenAI client" | SDK initialization error | Check OpenAI SDK is installed, verify Python version |

**How to Diagnose**:
1. Check job error via `GET /api/v1/plans/{job_id}`
2. Look for `LLMConfigurationError` in error type
3. Check application logs for detailed error message
4. Verify environment variables in `.env` file

**Resolution**:
- Most configuration errors require fixing `.env` and restarting the server
- No retry logic applies (non-retryable by design)

### 2. Request Errors (`LLMRequestError`)

**Symptoms**:
- Job fails after some delay (after retries exhausted)
- Error type: `LLMRequestError`
- Status: `failed`

**Common Causes**:

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "OpenAI API request failed after 3 retries: Timeout" | Network slow, model overloaded | Increase `LLM_TIMEOUT`, retry later |
| "OpenAI API request failed after 3 retries: Rate limit exceeded" | Too many requests to OpenAI | Wait, check account limits, upgrade plan |
| "OpenAI API request failed after 3 retries: 500 Internal Server Error" | OpenAI server issue | Wait, retry later, check OpenAI status |
| "OpenAI invalid request" | Bad request parameters | Check logs for details, file bug report |

**How to Diagnose**:
1. Check job error via `GET /api/v1/plans/{job_id}`
2. Look for `LLMRequestError` in error type
3. Check application logs for retry attempts and final error
4. Look for retry count in logs (if > 0, it retried)

**Resolution**:
- **Timeout**: Increase `LLM_TIMEOUT`, simplify description, retry
- **Rate limit**: Wait 1-5 minutes, check OpenAI account quota
- **5xx errors**: Wait and retry (usually transient OpenAI issues)
- **Network errors**: Check internet connection, firewall settings

### 3. Response Errors (`LLMResponseError`)

**Symptoms**:
- Job fails after LLM responds (parsing stage)
- Error type: `LLMResponseError`
- Status: `failed`

**Common Causes**:

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "Invalid JSON response from LLM" | LLM returned non-JSON text | Remove custom `LLM_SYSTEM_PROMPT`, retry |
| "LLM response missing required 'specs' field" | Schema violation | Check custom prompt, use default prompt |
| "Spec at index 0 missing required field 'purpose'" | Incomplete spec object | Remove custom prompt, file bug if using default |
| "Response validation failed" | Pydantic validation error | Check logs for field details, verify prompt |

**How to Diagnose**:
1. Check job error via `GET /api/v1/plans/{job_id}`
2. Look for `LLMResponseError` in error type
3. Check application logs for JSON parsing errors
4. If using custom `LLM_SYSTEM_PROMPT`, that's likely the cause

**Resolution**:
- Remove custom `LLM_SYSTEM_PROMPT` from `.env` (use default)
- Restart server and retry the planning request
- If error persists with default prompt, file a bug report (LLM regression)

### 4. Timeout vs Rate Limit Confusion

**Problem**: Users often confuse timeouts with rate limits.

**Timeout Error**:
- Happens after `LLM_TIMEOUT` seconds
- Message contains "timeout" or "timed out"
- Solution: Increase `LLM_TIMEOUT` or simplify description

**Rate Limit Error**:
- Happens before timeout (usually immediate)
- HTTP status 429
- Message contains "rate limit" or "too many requests"
- Solution: Wait, check OpenAI quota, upgrade plan

### 5. Malformed JSON Responses

**Problem**: LLM occasionally returns malformed JSON (rare with default prompt).

**Symptoms**:
- `LLMResponseError` with "Invalid JSON" message
- Logs show JSON parsing failure

**Root Causes**:
- Custom system prompt that doesn't enforce JSON-only output
- LLM model regression (very rare)
- Prompt injection in user description (if description isn't sanitized)

**Solutions**:
1. Remove custom `LLM_SYSTEM_PROMPT` to use default
2. Retry the request (may be transient)
3. If persistent, file a bug report with job ID

### 6. Empty or Minimal Specs

**Problem**: LLM returns valid JSON but with empty or low-quality specs.

**Symptoms**:
- Job succeeds but `specs[0].must` is empty or minimal
- Specs don't match project description

**Root Causes**:
- Vague or minimal project description
- Model quality issue (rare with gpt-5.1)
- Custom system prompt that doesn't guide well

**Solutions**:
1. Provide more detailed project descriptions
2. Use `LLM_MODEL=gpt-5.1` for better results
3. Review and improve custom system prompt if using one

## Performance Considerations

### Typical Latencies

Based on production usage with `gpt-5.1`:

| Scenario | Latency | Notes |
|----------|---------|-------|
| Simple description (< 100 chars) | 2-4 seconds | Fast generation |
| Medium description (100-500 chars) | 3-6 seconds | Typical case |
| Long description (500-2000 chars) | 5-10 seconds | More complex |
| With 1 retry (rate limit) | +1-2 seconds | Backoff delay |
| With 2 retries | +3-4 seconds | Exponential backoff |

**Factors Affecting Latency**:
- Description length and complexity
- Model choice (gpt-5.1 vs gpt-4)
- OpenAI API load
- Network latency
- Retry attempts

### Token Usage

Approximate token consumption per request:

- **System prompt**: ~150 tokens (default prompt)
- **User description**: ~1 token per 4 characters
- **Response**: ~200-800 tokens (depends on complexity)

**Example**:
- Description: 400 characters → ~100 tokens
- Total input: 250 tokens
- Response: 500 tokens
- **Total**: 750 tokens (~$0.02 at GPT-5.1 pricing)

### Cost Optimization Tips

1. **Use shorter descriptions**: More concise descriptions reduce token usage
2. **Cache results**: Store successful plans to avoid redundant API calls (future feature)
3. **Monitor usage**: Check OpenAI dashboard regularly
4. **Set budget alerts**: Configure alerts in OpenAI account settings
5. **Use appropriate model**: `gpt-4` is cheaper but less capable than `gpt-5.1`

## Best Practices

### For Operators

1. **Set Conservative Timeouts**: Start with `LLM_TIMEOUT=90` to avoid premature timeouts
2. **Monitor Logs**: Watch for patterns in retry rates and error types
3. **Set OpenAI Budget Alerts**: Prevent unexpected charges
4. **Test Configuration**: Verify API key and model before deploying
5. **Use Default Prompt**: Only customize system prompt if absolutely necessary

### For Developers

1. **Handle All Error Types**: Catch `LLMConfigurationError`, `LLMRequestError`, `LLMResponseError`
2. **Don't Retry Non-Retryable Errors**: Check error type before implementing retry logic
3. **Log Without Secrets**: Never log API keys or sensitive response content
4. **Validate Environment**: Check `LLM_API_KEY` presence at startup
5. **Test Failure Modes**: Write tests for timeout, rate limit, auth failure scenarios

### For Users

1. **Provide Clear Descriptions**: Better input → better output
2. **Use Asynchronous API**: Don't block on synchronous endpoint for production
3. **Poll Intelligently**: Use exponential backoff when checking job status
4. **Handle Failed Jobs**: Check `error` field when `status` is `failed`
5. **Don't Commit Secrets**: Never commit `.env` with real API keys

## Future Enhancements

Planned improvements to the LLM integration:

1. **Multi-Provider Support**: Anthropic Claude, Google Gemini implementations
2. **Streaming Responses**: Real-time spec generation (for synchronous endpoint)
3. **Response Caching**: Avoid redundant API calls for similar descriptions
4. **Token Usage Tracking**: Track and report token consumption per job
5. **Custom Retry Config**: Expose retry settings via environment variables
6. **Prompt Templates**: Library of pre-built system prompts for different use cases