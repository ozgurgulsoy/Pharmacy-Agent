"""OpenAI client wrapper."""

import logging
from typing import Optional, Dict, Any
import json

from openai import OpenAI
from config.settings import OPENAI_API_KEY, LLM_MODEL, MAX_TOKENS, TEMPERATURE

logger = logging.getLogger(__name__)


class OpenAIClientWrapper:
    """OpenAI API istemcisini sarmalayan sınıf."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=60.0,  # Explicit timeout
            max_retries=2  # Reduce retries for faster failures
        )
        self.model = LLM_MODEL
        self.max_tokens = MAX_TOKENS
        self.temperature = TEMPERATURE
        self.logger = logging.getLogger(self.__class__.__name__)

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

            kwargs = {
                "model": self.model,
                "messages": messages,
            }

            # Handle model-specific parameters
            # gpt-5-* models: use max_completion_tokens, temperature must be 1 (default)
            # o1-* models: use max_completion_tokens, no temperature support
            # gpt-4-*, gpt-3.5-*: use max_tokens, support temperature
            
            if self.model.startswith("gpt-5"):
                kwargs["max_completion_tokens"] = self.max_tokens
                # gpt-5-nano only supports temperature=1 (default), so omit it
                # Temperature will use default value of 1
            elif self.model.startswith("o1"):
                kwargs["max_completion_tokens"] = self.max_tokens
                # o1 models don't support temperature parameter at all
            else:
                # Standard models (gpt-4, gpt-3.5, etc.)
                kwargs["max_tokens"] = self.max_tokens
                kwargs["temperature"] = self.temperature

            if response_format:
                kwargs["response_format"] = response_format

            # Calculate token estimate
            prompt_tokens = len(system_prompt + user_prompt) // 4  # rough estimate
            self.logger.info(f"🚀 Sending LLM request (model={self.model}, ~{prompt_tokens} prompt tokens)")
            
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
        user_prompt: str
    ) -> Dict[str, Any]:
        """
        JSON formatında yanıt döndürür.

        Args:
            system_prompt: System mesajı
            user_prompt: User mesajı

        Returns:
            Parse edilmiş JSON objesi
        """
        response_text = self.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format={"type": "json_object"}
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {e}")
            self.logger.debug(f"Response text: {response_text}")
            # Fallback: Metni JSON'a dönüştürmeye çalış
            return {"raw_response": response_text, "parse_error": str(e)}

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
