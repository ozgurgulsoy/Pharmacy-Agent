"""OpenAI client wrapper."""

import logging
from typing import Optional, Dict, Any, List
import json

from openai import OpenAI
from app.config.settings import (
    OPENAI_API_KEY, 
    OPENROUTER_API_KEY,
    LLM_MODEL, 
    LLM_PROVIDER,
    OPENROUTER_BASE_URL,
    OPENROUTER_PROVIDER,
)

logger = logging.getLogger(__name__)


class OpenAIClientWrapper:
    """OpenAI/OpenRouter API client wrapper."""

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None):
        self.provider = provider or LLM_PROVIDER
        self.model = LLM_MODEL
        self.logger = logging.getLogger(self.__class__.__name__)
        self.provider_preferences: List[str] = []
        
        # Configure client based on provider
        if self.provider == "openrouter":
            self.api_key = api_key or OPENROUTER_API_KEY
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=OPENROUTER_BASE_URL,
                timeout=120.0,  # OpenRouter may need more time for some models
                max_retries=2
            )
            # Store headers for use in requests
            self.extra_headers = {
                "HTTP-Referer": "https://pharmacy-agent.local",
                "X-Title": "Pharmacy Agent"
            }
            self.provider_preferences = self._parse_provider_override(OPENROUTER_PROVIDER)
            if self.provider_preferences:
                self.logger.info(f"OpenRouter provider preference order: {self.provider_preferences}")
            self.logger.info(f"Initialized OpenRouter client with model: {self.model}")
        else:
            # Default to OpenAI
            self.api_key = api_key or OPENAI_API_KEY
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=90.0,
                max_retries=1
            )
            self.extra_headers = {}
            self.logger.info(f"Initialized OpenAI client with model: {self.model}")

    @staticmethod
    def _parse_provider_override(raw_value: Optional[str]) -> List[str]:
        """Return a provider preference list from a comma-delimited string."""
        if not raw_value:
            return []
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    def _inject_provider_preferences(self, kwargs: Dict[str, Any]) -> None:
        """Augment request kwargs with provider preferences."""
        if not self.provider_preferences:
            return

        provider_body = {
            "order": self.provider_preferences,
            "allow_fallbacks": len(self.provider_preferences) > 1
        }

        extra_body = kwargs.setdefault("extra_body", {})
        extra_body["provider"] = provider_body

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Chat completion isteği gönderir.

        Args:
            system_prompt: System mesajı
            user_prompt: User mesajı
            response_format: Yanıt formatı (örn: {"type": "json_object"})

        Returns:
            Model yanıtı
        """
        try:
            import time
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }

            # Handle different model families
            if self.model.startswith("o1"):
                # o1 models use max_completion_tokens, no temperature support
                kwargs["max_completion_tokens"] = 8192
            elif self.model.startswith("gpt-4"):
                # gpt-4 models support standard parameters
                kwargs["max_tokens"] = 4096
                kwargs["temperature"] = 0.7

            if response_format:
                kwargs["response_format"] = response_format

            # Calculate token estimate
            prompt_tokens = len(system_prompt + user_prompt) // 4  # rough estimate
            self.logger.info(f"🚀 Sending LLM request (model={self.model}, ~{prompt_tokens} prompt tokens)")
            
            # Add extra headers for OpenRouter
            if hasattr(self, 'extra_headers') and self.extra_headers:
                kwargs['extra_headers'] = self.extra_headers

            # Force a specific OpenRouter provider when configured
            self._inject_provider_preferences(kwargs)
            
            api_start = time.time()
            response = self.client.chat.completions.create(**kwargs)
            api_elapsed = time.time() - api_start
            
            content = response.choices[0].message.content
            
            # Log actual token usage if available
            usage = getattr(response, 'usage', None)
            if usage:
                self.logger.info(f"✅ LLM response: {api_elapsed:.2f}s, {usage.prompt_tokens} prompt + {usage.completion_tokens} completion = {usage.total_tokens} total tokens")
            else:
                self.logger.info(f"✅ LLM response: {api_elapsed:.2f}s, {len(content)} chars")
            
            return content

        except Exception as e:
            self.logger.error(f"Chat completion error: {e}")
            raise

    def chat_completion_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        JSON formatında yanıt döndürür.

        Args:
            system_prompt: System mesajı
            user_prompt: User mesajı
            max_retries: JSON parse hatası durumunda retry sayısı

        Returns:
            Parse edilmiş JSON objesi
        """
        last_error = None
        response_text = None
        
        for attempt in range(max_retries + 1):
            try:
                response_text = self.chat_completion(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_format={"type": "json_object"}
                )

                # Try to parse JSON
                return json.loads(response_text)
                
            except json.JSONDecodeError as e:
                last_error = e
                self.logger.warning(f"JSON parse attempt {attempt + 1}/{max_retries + 1} failed: {e}")
                
                if attempt < max_retries:
                    # Try to fix common JSON issues
                    if response_text:
                        candidate = self._extract_json_snippet(response_text)
                        if candidate:
                            try:
                                return json.loads(candidate)
                            except Exception:
                                pass

                    self.logger.info(f"Retrying request (attempt {attempt + 2}/{max_retries + 1})...")
                    continue
                else:
                    # Final attempt failed
                    self.logger.error(f"Failed to parse JSON after {max_retries + 1} attempts")
                    if response_text:
                        self.logger.debug(f"Response text (first 500 chars): {response_text[:500]}")
                    # Fallback: Return raw response
                    return {"raw_response": response_text or "", "parse_error": str(last_error)}

    def create_embedding(self, text: str, model: str = "gpt-5-mini") -> list:
        """
        Metin için embedding oluşturur.

        Args:
            text: Metin
            model: Embedding model

        Returns:
            Embedding vektörü
        """
        try:
            response = self.client.embeddings.create(
                model=model,
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding

        except Exception as e:
            self.logger.error(f"Embedding creation error: {e}")
            raise

    def _extract_json_snippet(self, text: str) -> Optional[str]:
        """Attempt to recover a JSON object from a free-form response."""
        if not text:
            return None

        fence = "```"
        if fence in text:
            first = text.find(fence)
            second = text.find(fence, first + len(fence))
            if second != -1:
                snippet = text[first + len(fence):second].strip()
                if snippet.lower().startswith("json"):
                    snippet = snippet[4:].lstrip()
                if snippet:
                    return snippet

        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            return text[first_brace:last_brace + 1].strip()

        return None
