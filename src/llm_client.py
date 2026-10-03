"""
PostVisit AI - Milestone 2: Pluggable LLM Client
Responsible for communicating with LLM inference APIs (Gemini, OpenAI, Hugging Face, Groq).
Never hardcodes API keys or logs sensitive credentials.
Supports model switching via environment variables.
"""

import os
import re
import json
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Ensure environment variables are loaded from project root .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class LLMClient:
    """
    Provider-agnostic LLM interface for structured clinical information extraction.
    Configured via environment variables:
      LLM_PROVIDER: 'gemini', 'openai', 'huggingface', 'groq', 'custom'
      LLM_MODEL: model identifier (e.g., 'gemini-3.5-flash-lite', 'gpt-4o-mini', 'Qwen/Qwen2.5-7B-Instruct')
      LLM_API_KEY: secret API key
      LLM_BASE_URL: optional custom base URL
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        default_provider = "groq" if (os.getenv("GROQ_API_KEY") or os.getenv("LLM_PROVIDER") == "groq") else "gemini"
        self.provider = (provider or os.getenv("LLM_PROVIDER", default_provider)).lower()
        self.model = model or os.getenv("LLM_MODEL", "qwen/qwen3.8-27b" if self.provider == "groq" else "gemini-3.5-flash-lite")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "")

        # Fallback candidate models for high-traffic spikes
        self.fallback_models = [
            "gemma-4-26b-a4b-it",
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-flash-latest"
        ]

        if not self.api_key:
            raise ValueError(
                "LLM API Key is missing! Set LLM_API_KEY in .env file or environment variables. "
                "See .env.example for details."
            )

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_retries: int = 3,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Executes an inference request to the configured LLM provider and returns parsed JSON.
        Guarantees retry on transient network errors or rate spikes.
        """
        if self.provider == "gemini":
            return self._generate_gemini_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_retries=max_retries,
                timeout=timeout
            )
        elif self.provider in ["openai", "groq", "custom"]:
            return self._generate_openai_compatible_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_retries=max_retries,
                timeout=timeout
            )
        elif self.provider == "huggingface":
            return self._generate_huggingface_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_retries=max_retries,
                timeout=timeout
            )
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: '{self.provider}'. Supported: gemini, openai, groq, huggingface, custom.")

    def _generate_gemini_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_retries: int,
        timeout: float
    ) -> Dict[str, Any]:
        """
        Calls Google Gemini Generative Language API with native application/json enforcement.
        """
        models_to_try = [self.model]

        last_error = None
        for current_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={self.api_key}"
            
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": combined_prompt}]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": temperature
                }
            }

            for attempt in range(1, max_retries + 1):
                try:
                    with httpx.Client(timeout=timeout) as client:
                        response = client.post(url, json=payload)

                    if response.status_code == 200:
                        data = response.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return self._parse_json_text(raw_text)

                    # If model is unavailable (503) or rate-limited (429), retry with backoff
                    if response.status_code in [429, 503, 500]:
                        last_error = f"{current_model} returned HTTP {response.status_code}: {response.text[:150]}"
                        time.sleep(1.5 * attempt)
                        continue

                    # If model not found (404), switch to next model immediately
                    if response.status_code == 404:
                        last_error = f"{current_model} returned 404 Not Found"
                        break

                    # Other HTTP error
                    last_error = f"Gemini API Error ({current_model} HTTP {response.status_code}): {response.text[:200]}"
                    break

                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    last_error = f"Network exception on {current_model}: {str(e)}"
                    time.sleep(1.5 * attempt)
                    continue
                except Exception as e:
                    last_error = f"Unexpected error during generation on {current_model}: {str(e)}"
                    break

        raise RuntimeError(f"Failed to generate structured JSON from Gemini API: {last_error}")

    def _generate_openai_compatible_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_retries: int,
        timeout: float
    ) -> Dict[str, Any]:
        """
        Calls OpenAI-compatible endpoints (OpenAI, Groq, OpenRouter, Together AI).
        """
        base_url = self.base_url
        if not base_url:
            if self.provider == "groq":
                base_url = "https://api.groq.com/openai/v1/chat/completions"
            else:
                base_url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(base_url, headers=headers, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    raw_text = data["choices"][0]["message"]["content"]
                    return self._parse_json_text(raw_text)

                if response.status_code in [429, 503, 500]:
                    last_error = f"API Error (HTTP {response.status_code}): {response.text[:200]}"
                    sleep_duration = 1.0 * (2 ** (attempt - 1))
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            sleep_duration = min(float(retry_after), 10.0)
                        except (ValueError, TypeError):
                            pass
                    time.sleep(sleep_duration)
                    continue


                last_error = f"API Error (HTTP {response.status_code}): {response.text[:200]}"
                break

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = f"Network exception: {str(e)}"
                time.sleep(1.0 * attempt)
            except Exception as e:
                last_error = str(e)
                break

        raise RuntimeError(f"Failed to generate structured JSON from OpenAI-compatible API: {last_error}")

    def _generate_huggingface_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_retries: int,
        timeout: float
    ) -> Dict[str, Any]:
        """
        Calls Hugging Face Inference API / Serverless Endpoint using huggingface_hub.
        """
        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            raise ImportError("huggingface_hub is required for Hugging Face provider. Run: pip install huggingface-hub")

        client = InferenceClient(api_key=self.api_key)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
                raw_text = response.choices[0].message.content
                return self._parse_json_text(raw_text)
            except Exception as e:
                last_error = str(e)
                time.sleep(1.0 * attempt)

        raise RuntimeError(f"Failed to generate structured JSON from Hugging Face API: {last_error}")

    def _parse_json_text(self, text: str) -> Dict[str, Any]:
        """
        Safely parses JSON string, stripping markdown code blocks if present.
        """
        cleaned = text.strip()
        # Remove markdown code blocks if present (```json ... ``` or ``` ...)
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Fallback: find first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end+1])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"LLM returned malformed JSON: {e}\nRaw output:\n{text[:300]}")
