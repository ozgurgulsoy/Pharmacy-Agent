"""OpenAI client wrapper."""

import logging
from typing import Optional, Dict, Any
import json

from openai import OpenAI
from app.config.settings import (
    OPENAI_API_KEY, 
    OPENROUTER_API_KEY,
    LLM_MODEL, 
    LLM_PROVIDER,
    OPENROUTER_BASE_URL
)

logger = logging.getLogger(__name__)


class OpenAIClientWrapper:
    """OpenAI/OpenRouter API client wrapper."""

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None):
        self.provider = provider or LLM_PROVIDER
        self.model = LLM_MODEL
        self.logger = logging.getLogger(self.__class__.__name__)
        
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
                        # Try to extract JSON from markdown code blocks
                        import re
                        json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response_text, re.DOTALL)
                        if json_match:
                            try:
                                return json.loads(json_match.group(1))
                            except:
                                pass
                        
                        # Try to find first { and last } to extract JSON
                        first_brace = response_text.find('{')
                        last_brace = response_text.rfind('}')
                        if first_brace >= 0 and last_brace > first_brace:
                            try:
                                extracted = response_text[first_brace:last_brace + 1]
                                return json.loads(extracted)
                            except:
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
