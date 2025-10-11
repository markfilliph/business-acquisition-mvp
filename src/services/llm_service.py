"""
LLM Extraction Service with OpenAI integration and guardrails.
PRIORITY: P0 - Critical for revenue gate (staff signals).

Features:
- Structured extraction with Pydantic schemas
- Anti-hallucination prompts
- Token limits and cost tracking
- Null-rate monitoring
- Automatic retries with exponential backoff
"""

import asyncio
import json
import time
from typing import Optional, Dict
import structlog
from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from ..core.config import config
import os
from ..models.extraction_schemas import BusinessExtraction, ExtractionResult, WebsiteMetadata
from ..prompts.extraction_prompts import build_extraction_prompt
from ..utils.rate_limiter import get_limiter

logger = structlog.get_logger(__name__)


class LLMExtractionService:
    """
    Service for extracting business information from website content using LLMs.

    Implements strict guardrails to prevent hallucination and control costs.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",  # Fast, cheap, good for extraction
        max_tokens: int = 1000,
        temperature: float = 0.0,  # Deterministic for data extraction
        enable_validation: bool = True
    ):
        """
        Initialize LLM extraction service.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: OpenAI model to use (gpt-4o-mini recommended for cost)
            max_tokens: Maximum tokens for completion
            temperature: LLM temperature (0.0 = deterministic)
            enable_validation: Whether to double-check extractions
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.enable_validation = enable_validation

        if not self.api_key:
            logger.warning("openai_api_key_not_configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)

        # Metrics tracking
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self.null_extractions = 0
        self.successful_extractions = 0

        logger.info("llm_service_initialized", model=self.model, max_tokens=self.max_tokens)

    async def extract_from_website(
        self,
        url: str,
        company_name: str,
        content: str
    ) -> Optional[ExtractionResult]:
        """
        Extract business information from website content.

        Args:
            url: Website URL
            company_name: Business name
            content: Scraped website content (HTML or text)

        Returns:
            ExtractionResult if successful, None if failed
        """
        if not self.client:
            logger.error("llm_service_not_configured")
            return None

        start_time = time.time()

        try:
            # Build extraction prompt
            prompt = build_extraction_prompt(url, company_name, content)

            # Call OpenAI with structured output
            response = await self._call_openai(prompt['system'], prompt['user'])

            if not response:
                return None

            # Parse response into BusinessExtraction schema
            business_data = self._parse_extraction_response(response)

            if not business_data:
                self.null_extractions += 1
                return None

            # Track metrics
            tokens_used = response.get('usage', {}).get('total_tokens', 0)
            cost = self._calculate_cost(tokens_used)
            duration = time.time() - start_time

            self.total_requests += 1
            self.total_tokens += tokens_used
            self.total_cost_usd += cost
            self.successful_extractions += 1

            # Create metadata
            metadata = WebsiteMetadata(
                url=url,
                scrape_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                content_length=len(content),
                scrape_successful=True
            )

            # Build result
            result = ExtractionResult(
                business_data=business_data,
                metadata=metadata,
                tokens_used=tokens_used,
                cost_usd=cost,
                extraction_duration_sec=duration
            )

            logger.info(
                "extraction_successful",
                url=url,
                has_staff=result.has_staff_signal(),
                has_founding_year=result.has_founding_year(),
                quality_score=result.get_quality_score(),
                tokens=tokens_used,
                cost_usd=f"${cost:.4f}"
            )

            return result

        except Exception as e:
            logger.error("extraction_failed", url=url, error=str(e))
            self.null_extractions += 1
            return None

    async def _call_openai(self, system_prompt: str, user_prompt: str, retries: int = 3) -> Optional[Dict]:
        """
        Call OpenAI API with retries and error handling.

        Args:
            system_prompt: System message
            user_prompt: User message
            retries: Number of retries on failure

        Returns:
            Response dict or None
        """
        # Get rate limiter for OpenAI
        limiter = get_limiter("openai")

        for attempt in range(retries):
            try:
                # Wait for rate limit token
                await limiter.wait()

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}  # Force JSON output
                )

                # Convert to dict
                return {
                    'content': response.choices[0].message.content,
                    'usage': {
                        'total_tokens': response.usage.total_tokens,
                        'prompt_tokens': response.usage.prompt_tokens,
                        'completion_tokens': response.usage.completion_tokens
                    }
                }

            except OpenAIError as e:
                logger.warning("openai_api_error", attempt=attempt+1, error=str(e))
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error("openai_api_failed_all_retries", error=str(e))
                    return None

            except Exception as e:
                logger.error("unexpected_openai_error", error=str(e))
                return None

        return None

    def _parse_extraction_response(self, response: Dict) -> Optional[BusinessExtraction]:
        """
        Parse OpenAI response into BusinessExtraction schema.

        Args:
            response: OpenAI API response

        Returns:
            BusinessExtraction or None if parsing failed
        """
        try:
            content = response.get('content', '{}')

            # Parse JSON
            data = json.loads(content)

            # Validate with Pydantic
            business_data = BusinessExtraction(**data)

            return business_data

        except json.JSONDecodeError as e:
            logger.error("json_parse_failed", error=str(e), content=response.get('content', '')[:200])
            return None

        except ValidationError as e:
            logger.error("schema_validation_failed", error=str(e))
            return None

        except Exception as e:
            logger.error("unexpected_parse_error", error=str(e))
            return None

    def _calculate_cost(self, tokens: int) -> float:
        """
        Calculate API cost based on model and tokens.

        Args:
            tokens: Total tokens used

        Returns:
            Cost in USD
        """
        # Pricing as of 2024 (update as needed)
        pricing = {
            'gpt-4o-mini': {'input': 0.15 / 1_000_000, 'output': 0.60 / 1_000_000},  # $0.15/$0.60 per 1M tokens
            'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},  # More expensive
            'gpt-3.5-turbo': {'input': 0.50 / 1_000_000, 'output': 1.50 / 1_000_000}
        }

        model_pricing = pricing.get(self.model, pricing['gpt-4o-mini'])

        # Approximate: 75% prompt, 25% completion
        prompt_tokens = int(tokens * 0.75)
        completion_tokens = int(tokens * 0.25)

        cost = (prompt_tokens * model_pricing['input']) + (completion_tokens * model_pricing['output'])
        return cost

    def get_metrics(self) -> Dict:
        """
        Get service metrics.

        Returns:
            Dict with usage statistics
        """
        null_rate = (self.null_extractions / self.total_requests) if self.total_requests > 0 else 0.0

        return {
            'total_requests': self.total_requests,
            'successful_extractions': self.successful_extractions,
            'null_extractions': self.null_extractions,
            'null_rate': null_rate,
            'total_tokens': self.total_tokens,
            'total_cost_usd': self.total_cost_usd,
            'avg_cost_per_extraction': self.total_cost_usd / self.successful_extractions if self.successful_extractions > 0 else 0.0
        }

    def log_metrics(self):
        """Log current metrics to logger."""
        metrics = self.get_metrics()
        logger.info("llm_service_metrics", **metrics)


# Convenience function for single extraction
async def extract_business_info(url: str, company_name: str, content: str) -> Optional[ExtractionResult]:
    """
    Convenience function for single extraction.

    Args:
        url: Website URL
        company_name: Business name
        content: Website content

    Returns:
        ExtractionResult or None
    """
    service = LLMExtractionService()
    return await service.extract_from_website(url, company_name, content)
