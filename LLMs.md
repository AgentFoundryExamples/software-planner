# Instructions for implementing LLM apis (Do NOT modify this file)

The following is instructions for implementing with LLM APIs. The models that are currently targeted are the OpenAI GPT5+ models, the Anthropic Claude Sonnet/Opus 4+ models, and Google Gemini 3+ models. Implement all LLM API calls according to the following guidance without modifying this file.

**Important:** Always use the latest stable API versions and official SDKs. Avoid deprecated endpoints and legacy APIs.

## OpenAI GPT5

When implementing OpenAI integration, the target API should be the **Responses API** since it is the recommended most long term compatible option. The GPT 5 series models are supportive of the responses API and these are the models we want to use when implementing AI integration. Do not use completions it is not recommended moving forward.

- Target model: `gpt-5.1`
- Use the official `openai` Python package or equivalent SDK for your language
- **API Endpoint:** Responses API (replaces Chat Completions for GPT-5+ models)
- **Required Environment Variables:**
  - `OPENAI_API_KEY` or `LLM_API_KEY` - API key from https://platform.openai.com/api-keys
  - Optional: `LLM_BASE_URL` - Custom base URL for Azure OpenAI or proxies
  - Optional: `LLM_TIMEOUT` - Request timeout in seconds (default: 60)
  - Optional: `LLM_MODEL` - Model identifier (default: gpt-4, recommended: gpt-5.1)

**Rate Limits and Troubleshooting:**
- OpenAI enforces rate limits based on your account tier (tokens per minute, requests per minute)
- **Common Rate Limit Errors (HTTP 429):**
  - Exceeded tokens per minute (TPM) quota
  - Exceeded requests per minute (RPM) quota
  - Exceeded daily token quota for free tier accounts
- **Solutions:**
  - Upgrade to a higher tier plan: https://platform.openai.com/account/billing/overview
  - Implement exponential backoff (already built into the planner service)
  - Reduce request frequency in client applications
  - Monitor usage in OpenAI dashboard: https://platform.openai.com/usage
- **Error Response Example:**
  ```json
  {
    "error": {
      "message": "Rate limit exceeded. Please try again in 20 seconds.",
      "type": "rate_limit_error",
      "code": "rate_limit_exceeded"
    }
  }
  ```
- **Auto-Retry Behavior:**
  - The planner service automatically retries rate limit errors (429) and transient server errors (5xx) with exponential backoff
  - Default: 3 retry attempts with 1s, 2s, 4s delays
  - If all retries exhausted, job is marked as FAILED with `LLMRequestError`

**Model Availability:**
- Verify your API key has access to GPT-5.1: Check model list at https://platform.openai.com/docs/models
- Some models require special access or are only available on certain account tiers
- If you get "model not found" (404), use a fallback model like `gpt-4` or `gpt-4-turbo`

**Do NOT use:** Completions API (deprecated), legacy models like GPT-3.5 or older

## Anthropic Claude Sonnet/Opus 4

When implementing Anthropic integration, the target API should be the **Messages API** (API version `2023-06-01` or newer) since it is the most long term compatible option. The Claude Sonnet 4 and Opus 4 series models are supportive of the Messages API and these are the models we want to use when implementing AI integration.

- Target model: Sonnet 4.5
- Use the official `anthropic` Python package or `@anthropic-ai/sdk` for JS/TS
- **API Endpoint:** Messages API (v2023-06-01 or newer)
- **Required Environment Variables:**
  - `ANTHROPIC_API_KEY` - API key from https://console.anthropic.com/settings/keys
  - Optional: Timeout, retry, and base URL configuration similar to OpenAI

**Rate Limits and Troubleshooting:**
- Anthropic enforces rate limits based on your account tier and organization settings
- **Common Rate Limit Errors (HTTP 429):**
  - Exceeded requests per minute for your tier
  - Exceeded tokens per minute for your tier
  - Concurrent request limits
- **Solutions:**
  - Contact Anthropic support to request higher limits
  - Implement request throttling and exponential backoff (built-in to planner)
  - Monitor usage in Anthropic console: https://console.anthropic.com/settings/usage
- **Auto-Retry Behavior:**
  - Same retry logic as OpenAI: 3 attempts with exponential backoff
  - Automatically handles transient 429 errors and 5xx server errors

**Do NOT use:** Text Completions API (deprecated), Claude 2.x or older models

## Google Gemini 3

When implementing Google integration, the target API should be the **Gemini API** since it is the most long term compatible option. The Gemini 3 series models are supportive of the Gemini API and these are the models we want to use when implementing AI integration.

- Target model: `gemini-3.0-pro`
- Use the official `google-genai` Python package or `@google/genai` for JS/TS
- Ex. `from google import genai`
- **API Endpoint:** Gemini API (https://generativelanguage.googleapis.com/v1)
- **Required Environment Variables:**
  - `GOOGLE_API_KEY` - API key from https://makersuite.google.com/app/apikey
  - Optional: `base_url` configuration for custom endpoints
  - Optional: Timeout and retry configuration similar to OpenAI

**Rate Limits and Troubleshooting:**
- Google enforces rate limits based on API key tier (free, paid, enterprise)
- **Common Rate Limit Errors (HTTP 429):**
  - Exceeded requests per minute (RPM)
  - Exceeded requests per day (free tier)
  - Concurrent request limits
- **Solutions:**
  - Upgrade to paid tier: https://ai.google.dev/pricing
  - Enable billing on your Google Cloud project
  - Implement request throttling (built-in to planner)
  - Monitor usage in Google Cloud Console
- **Auto-Retry Behavior:**
  - Same retry logic as OpenAI: 3 attempts with exponential backoff
  - Automatically handles transient 429 errors and 5xx server errors

**Do NOT use:** PaLM API (deprecated), Gemini 1.x models, or legacy Bard endpoints

## General Best Practices

- Always check official documentation for the latest API versions
- Use environment variables for API keys, never hardcode them
- Implement proper error handling and rate limiting
- Use streaming responses when available for better UX
- Keep SDKs updated to the latest stable versions
