"""Multi-provider LLM service with fallback chain: DeepSeek → Qwen → Hunyuan."""
import json
import logging
from typing import Optional, List, Dict
import httpx
from config import settings

logger = logging.getLogger("llm_service")

# Provider definitions in fallback order
PROVIDERS = [
    {
        "name": "DeepSeek",
        "api_key": settings.DEEPSEEK_API_KEY,
        "base_url": settings.DEEPSEEK_BASE_URL.rstrip("/"),
        "model": "deepseek-chat",
        "fallback_key": settings.DEEPSEEK_ALT_API_KEY,
    },
    {
        "name": "Qwen",
        "api_key": settings.QWEN_API_KEY,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    {
        "name": "Hunyuan",
        "api_key": settings.HUNYUAN_API_KEY,
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-lite",
    },
]


async def _call_openai_compatible(
    provider: dict, system_prompt: str, user_prompt: str
) -> Optional[str]:
    """Call an OpenAI-compatible chat completion endpoint."""
    url = f"{provider['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 256,
        "temperature": 0.8,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)

    if resp.status_code == 200:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    else:
        logger.warning(f"[{provider['name']}] returned {resp.status_code}: {resp.text[:200]}")
        return None


async def generate_review(
    agent_name: str,
    personality: Dict[str, float],
    product_name: str,
    product_category: str,
    price_paid: float,
    rating_stars: int,
) -> str:
    """Generate an LLM review. Falls back through providers and finally to a template."""
    system_prompt = (
        "You are a consumer leaving a product review on an e-commerce platform. "
        "Write a short, authentic review (2-4 sentences) reflecting your personality. "
        "Respond ONLY with the review text, no quotes or prefixes."
    )

    # Build user prompt from persona
    trait_descriptions = []
    if personality.get("price_sensitivity", 0.5) > 0.7:
        trait_descriptions.append("very budget-conscious")
    elif personality.get("price_sensitivity", 0.5) < 0.3:
        trait_descriptions.append("unconcerned about price")

    if personality.get("impulsiveness", 0.5) > 0.7:
        trait_descriptions.append("impulsive buyer")
    if personality.get("risk_tolerance", 0.5) > 0.7:
        trait_descriptions.append("willing to try new things")
    if personality.get("brand_loyalty", 0.5) > 0.7:
        trait_descriptions.append("brand loyal")
    if personality.get("trend_alignment", 0.5) > 0.7:
        trait_descriptions.append("trend follower")

    trait_str = ", ".join(trait_descriptions) if trait_descriptions else "average consumer"

    rating_word = {1: "terrible", 2: "poor", 3: "average", 4: "good", 5: "excellent"}.get(
        rating_stars, "okay"
    )

    user_prompt = (
        f"You are {agent_name}, a {trait_str}. "
        f"You just bought {product_name} (category: {product_category}) for ${price_paid:.2f}. "
        f"You rate it {rating_stars}/5 stars ({rating_word}). "
        f"Write your review:"
    )

    # Try each provider in fallback order
    for provider in PROVIDERS:
        logger.info(f"Attempting review generation with {provider['name']}...")
        result = await _call_openai_compatible(provider, system_prompt, user_prompt)
        if result:
            return result

        # Try fallback key for DeepSeek
        if provider["name"] == "DeepSeek" and provider.get("fallback_key"):
            alt_provider = {**provider, "api_key": provider["fallback_key"]}
            result = await _call_openai_compatible(alt_provider, system_prompt, user_prompt)
            if result:
                return result

    # Final fallback: template-based review
    logger.warning("All providers failed, using template review.")
    return _template_review(agent_name, personality, product_name, rating_stars)


def _template_review(
    agent_name: str, personality: Dict[str, float], product_name: str, rating: int
) -> str:
    """Deterministic template reviews as ultimate fallback."""
    templates = {
        5: [
            f"Absolutely love {product_name}! Exceeded all expectations.",
            f"{product_name} is phenomenal. Best purchase I've made in a while.",
            f"Five stars all the way. {product_name} delivers on every front.",
        ],
        4: [
            f"Really solid product. {product_name} is well worth the price.",
            f"Happy with {product_name}. Minor room for improvement but overall great.",
            f"Good quality. I'd recommend {product_name} to friends.",
        ],
        3: [
            f"{product_name} is decent. Does the job but nothing special.",
            f"Average experience with {product_name}. It's okay for the price.",
            f"Not bad, not great. {product_name} meets basic expectations.",
        ],
        2: [
            f"Disappointed with {product_name}. Several issues out of the box.",
            f"Below average. {product_name} didn't meet my expectations.",
            f"Wouldn't buy {product_name} again. Has some flaws.",
        ],
        1: [
            f"Terrible experience with {product_name}. Complete waste of money.",
            f"{product_name} is awful. Do not recommend at all.",
            f"Worst purchase ever. {product_name} is simply broken.",
        ],
    }

    import random
    return random.choice(templates.get(rating, templates[3]))


async def test_providers() -> List[Dict]:
    """Quick connectivity test for all configured providers."""
    results = []
    test_prompt = "Reply with exactly 'OK' and nothing else."

    for provider in PROVIDERS:
        result = await _call_openai_compatible(
            provider, "You are a connectivity tester.", test_prompt
        )
        results.append({
            "provider": provider["name"],
            "status": "connected" if result else "failed",
        })

    return results
