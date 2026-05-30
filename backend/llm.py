import os
import httpx
import logging
import asyncio
from typing import List, Optional

logger = logging.getLogger(__name__)

class LLMException(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

class LLMClient:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        custom_base_url: Optional[str] = None,
        provider_keys: Optional[dict] = None
    ):
        self.provider = (provider or "anthropic").lower()
        self.model = model
        self.custom_base_url = custom_base_url
        self.provider_keys = provider_keys or {}
        
        # Resolve initial API keys for primary provider
        self.api_keys = self._get_keys_for_provider(self.provider)
        if api_keys and not self.api_keys:
            self.api_keys = [k.strip() for k in api_keys if k.strip()]

        # Set default model if none specified
        if not self.model or self.model.strip() == "":
            self.model = self._get_default_model(self.provider)

        logger.info(
            f"Initialized LLMClient (provider: {self.provider}, model: {self.model}, "
            f"keys loaded: {len(self.api_keys)})"
        )

    def _get_keys_for_provider(self, provider: str) -> List[str]:
        # 1. Check if keys were supplied dynamically from the UI keys map
        ui_keys = self.provider_keys.get(provider)
        if ui_keys:
            if isinstance(ui_keys, list):
                return [k.strip() for k in ui_keys if k.strip()]
            normalized = ui_keys.replace("\r\n", ",").replace("\n", ",")
            return [k.strip() for k in normalized.split(",") if k.strip()]
            
        # 2. Check env variables
        return self._get_keys_from_env(provider)

    def _get_keys_from_env(self, provider: str) -> List[str]:
        env_vars = {
            "anthropic": ["ANTHROPIC_API_KEY"],
            "openai": ["OPENAI_API_KEY"],
            "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
            "groq": ["GROQ_API_KEY"],
            "custom": ["CUSTOM_API_KEY"]
        }
        
        keys = []
        vars_to_check = env_vars.get(provider, [])
        for var in vars_to_check:
            val = os.getenv(var)
            if val:
                # Support comma-separated keys in .env
                keys.extend([k.strip() for k in val.split(",") if k.strip()])
        return keys

    def _get_default_model(self, provider: str) -> str:
        defaults = {
            "anthropic": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4o-mini",
            "gemini": "gemini-2.5-flash",
            "groq": "llama-3.3-70b-versatile",
            "custom": "custom-model"
        }
        return defaults.get(provider, "gpt-4o-mini")

    async def generate_response(
        self,
        system_prompt: str,
        messages: List[dict],
        on_key_rotate = None
    ) -> str:
        # Determine the order of providers to try
        # Primary provider first
        providers_to_try = [self.provider]
        
        # Add fallback candidates that have keys configured (either in provider_keys map or env)
        all_possible_providers = ["anthropic", "openai", "gemini", "groq"]
        for p in all_possible_providers:
            if p != self.provider:
                keys = self._get_keys_for_provider(p)
                if keys:
                    providers_to_try.append(p)

        last_error = None
        
        for current_provider in providers_to_try:
            # Resolve keys and model for this provider
            if current_provider == self.provider:
                current_keys = self.api_keys
                current_model = self.model
                current_base_url = self.custom_base_url
            else:
                current_keys = self._get_keys_for_provider(current_provider)
                current_model = self._get_default_model(current_provider)
                current_base_url = None
                
            if not current_keys:
                continue
                
            # If we had to fall back to a different provider, emit a warning/notification
            if current_provider != self.provider:
                fallback_msg = (
                    f"[API Fallback] selected provider '{self.provider}' failed. "
                    f"Switching to fallback provider '{current_provider}' ({current_model})..."
                )
                logger.info(fallback_msg)
                if on_key_rotate:
                    try:
                        if asyncio.iscoroutinefunction(on_key_rotate):
                            await on_key_rotate(fallback_msg)
                        else:
                            on_key_rotate(fallback_msg)
                    except Exception as cb_err:
                        logger.error(f"Callback error in on_key_rotate: {cb_err}")

            # Try the keys for the current provider
            for idx, api_key in enumerate(current_keys):
                try:
                    # Temporarily override self.provider/model/base_url for the API call
                    original_provider = self.provider
                    original_model = self.model
                    original_base_url = self.custom_base_url
                    
                    self.provider = current_provider
                    self.model = current_model
                    self.custom_base_url = current_base_url
                    
                    try:
                        return await self._call_provider_api(api_key, system_prompt, messages)
                    finally:
                        self.provider = original_provider
                        self.model = original_model
                        self.custom_base_url = original_base_url
                        
                except Exception as e:
                    last_error = e
                    status_code = getattr(e, "status_code", None)
                    error_msg = str(e)
                    
                    logger.warning(
                        f"LLM API call failed with key {idx+1}/{len(current_keys)} "
                        f"for provider '{current_provider}': {error_msg} (status: {status_code})"
                    )
                    
                    # If it's a Bad Request (400), it's probably structural so we stop rotating this pool
                    if status_code == 400:
                        break
                        
                    if idx < len(current_keys) - 1:
                        rotate_msg = (
                            f"[API Warning] Key #{idx+1} failed ({status_code or 'Error'}). "
                            f"Rotating to key #{idx+2} for provider '{current_provider}'..."
                        )
                        logger.info(rotate_msg)
                        if on_key_rotate:
                            try:
                                if asyncio.iscoroutinefunction(on_key_rotate):
                                    await on_key_rotate(rotate_msg)
                                else:
                                    on_key_rotate(rotate_msg)
                            except Exception as cb_err:
                                logger.error(f"Callback error in on_key_rotate: {cb_err}")
                        continue
                    else:
                        break
                        
        raise LLMException(
            f"All configured API keys and fallback providers failed. "
            f"Last error: {last_error}",
            status_code=getattr(last_error, "status_code", None)
        )

    async def _call_provider_api(self, api_key: str, system_prompt: str, messages: List[dict]) -> str:
        async with httpx.AsyncClient(timeout=90.0) as client:
            if self.provider == "anthropic":
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                
                # Anthropic doesn't allow 'system' inside messages array
                anthropic_messages = []
                for m in messages:
                    if m["role"] == "system":
                        continue
                    anthropic_messages.append({"role": m["role"], "content": m["content"]})
                
                payload = {
                    "model": self.model,
                    "max_tokens": 512,
                    "system": system_prompt,
                    "messages": anthropic_messages
                }
                
                response = await client.post(url, headers=headers, json=payload)
                self._handle_response_errors(response)
                return response.json()["content"][0]["text"].strip()
                
            elif self.provider == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json"
                }
                
                # Format system prompt standard way
                openai_messages = [{"role": "system", "content": system_prompt}] + messages
                payload = {
                    "model": self.model,
                    "max_tokens": 512,
                    "messages": openai_messages
                }
                
                response = await client.post(url, headers=headers, json=payload)
                self._handle_response_errors(response)
                return response.json()["choices"][0]["message"]["content"].strip()
                
            elif self.provider == "groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json"
                }
                
                groq_messages = [{"role": "system", "content": system_prompt}] + messages
                payload = {
                    "model": self.model,
                    "max_tokens": 512,
                    "messages": groq_messages
                }
                
                response = await client.post(url, headers=headers, json=payload)
                self._handle_response_errors(response)
                return response.json()["choices"][0]["message"]["content"].strip()
                
            elif self.provider == "gemini":
                # Google Gemini supports standard OpenAI compatibility over chat completions!
                url = "https://generativelanguage.googleapis.com/v1beta/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json"
                }
                
                gemini_messages = [{"role": "system", "content": system_prompt}] + messages
                payload = {
                    "model": self.model,
                    "max_tokens": 512,
                    "messages": gemini_messages
                }
                
                response = await client.post(url, headers=headers, json=payload)
                self._handle_response_errors(response)
                return response.json()["choices"][0]["message"]["content"].strip()
                
            elif self.provider == "custom":
                base_url = self.custom_base_url or "http://localhost:11434/v1"
                base_url = base_url.rstrip("/")
                if not base_url.endswith("/chat/completions"):
                    url = f"{base_url}/chat/completions"
                else:
                    url = base_url
                    
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json"
                }
                
                custom_messages = [{"role": "system", "content": system_prompt}] + messages
                payload = {
                    "model": self.model,
                    "max_tokens": 512,
                    "messages": custom_messages
                }
                
                response = await client.post(url, headers=headers, json=payload)
                self._handle_response_errors(response)
                return response.json()["choices"][0]["message"]["content"].strip()
            
            else:
                raise LLMException(f"Unsupported provider: {self.provider}")

    def _handle_response_errors(self, response: httpx.Response):
        if response.is_error:
            err_detail = ""
            try:
                err_json = response.json()
                if "error" in err_json:
                    err_detail = str(err_json["error"])
                elif "detail" in err_json:
                    err_detail = str(err_json["detail"])
                else:
                    err_detail = response.text
            except Exception:
                err_detail = response.text
                
            raise LLMException(
                f"HTTP Error {response.status_code}: {err_detail}",
                status_code=response.status_code
            )
