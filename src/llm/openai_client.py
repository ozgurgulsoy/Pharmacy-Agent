"""OpenAI client wrapper."""

import logging
from typing import Optional, Dict, Any
import json

from openai import OpenAI
from config.settings import OPENAI_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)


class OpenAIClientWrapper:
    """OpenAI API istemcisini sarmalayan sınıf."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key)
        self.model = LLM_MODEL
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

    def create_embedding(self, text: str, model: str = "gpt-5-nano") -> list:
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
