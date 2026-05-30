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
        provider_keys: Optional[dict] = None,
    ):
        self.provider = (provider or "anthropic").lower()
        self.model = model
        self.custom_base_url = custom_base_url

        # Resolve API keys: per-provider dict > explicit list > env vars
        provider_specific = (provider_keys or {}).get(self.provider)
        if provider_specific:
            raw = provider_specific if isinstance(provider_specific, list) else [provider_specific]
            self.api_keys = [k.strip() for k in raw if str(k).strip()]
        elif api_keys:
            self.api_keys = [k.strip() for k in api_keys if k.strip()]
        else:
            self.api_keys = self._get_keys_from_env(self.provider)

        # Set default model if none specified
        if not self.model or self.model.strip() == "":
            self.model = self._get_default_model(self.provider)

        logger.info(
            f"Initialized LLMClient (provider: {self.provider}, model: {self.model}, "
            f"keys loaded: {len(self.api_keys)})"
        )

    def _get_keys_from_env(self, provider: str) -> List[str]:
        env_vars = {
            "anthropic": ["ANTHROPIC_API_KEY"],
            "openai": ["OPENAI_API_KEY"],
            "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
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
        if not self.api_keys:
            raise LLMException(
                f"No API keys configured for provider '{self.provider}'. "
                f"Please add a key in the settings panel or set it in backend/.env file."
            )

        # Try keys sequentially with rotation
        last_error = None
        for idx, api_key in enumerate(self.api_keys):
            try:
                return await self._call_provider_api(api_key, system_prompt, messages)
            except Exception as e:
                last_error = e
                status_code = getattr(e, "status_code", None)
                error_msg = str(e)
                
                logger.warning(
                    f"LLM API call failed with key {idx+1}/{len(self.api_keys)} "
                    f"for provider '{self.provider}': {error_msg} (status: {status_code})"
                )
                
                # If we encounter a Bad Request (400), don't rotate since it's a structural error
                if status_code == 400:
                    raise LLMException(f"Bad Request (400) from {self.provider}: {error_msg}", status_code=400)
                
                # Check if we have more keys to rotate to
                if idx < len(self.api_keys) - 1:
                    rotate_msg = (
                        f"[API Warning] Key #{idx+1} failed ({status_code or 'Error'}). "
                        f"Rotating to key #{idx+2} for provider '{self.provider}'..."
                    )
                    logger.info(rotate_msg)
                    if on_key_rotate:
                        try:
                            # Run callback if it is async or sync
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
            f"All configured API keys for provider '{self.provider}' failed. "
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
