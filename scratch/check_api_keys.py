import sys

sys.path.insert(0, "src")

from config import settings


def preview(value, limit=180):
    return str(value).replace("\n", " ")[:limit]


def check_jsearch():
    import requests

    response = requests.get(
        "https://jsearch.p.rapidapi.com/search",
        params={"query": "devops engineer in United States", "num_pages": "1"},
        headers={
            "x-rapidapi-host": "jsearch.p.rapidapi.com",
            "x-rapidapi-key": settings.jsearch_api_key or "",
        },
        timeout=20,
    )
    if response.ok:
        data = response.json()
        return "OK", f"{len(data.get('data', []))} jobs returned"
    return f"HTTP {response.status_code}", preview(response.text)


def check_anthropic():
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    haiku = client.messages.create(
        model=settings.claude_haiku_model,
        max_tokens=5,
        messages=[{"role": "user", "content": "Reply OK"}],
    )
    sonnet = client.messages.create(
        model=settings.claude_sonnet_model,
        max_tokens=5,
        messages=[{"role": "user", "content": "Reply OK"}],
    )
    return (
        "OK",
        "Haiku "
        f"{haiku.content[0].text} ({haiku.usage.input_tokens}/{haiku.usage.output_tokens} tokens); "
        "Sonnet "
        f"{sonnet.content[0].text} ({sonnet.usage.input_tokens}/{sonnet.usage.output_tokens} tokens)",
    )


def check_openai():
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_fallback_model,
        max_tokens=5,
        messages=[{"role": "user", "content": "Reply OK"}],
    )
    return "OK", f"{response.choices[0].message.content} ({response.usage.prompt_tokens}/{response.usage.completion_tokens} tokens)"


checks = [
    ("JSearch", bool(settings.jsearch_api_key), check_jsearch),
    ("Anthropic Haiku", bool(settings.anthropic_api_key), check_anthropic),
    ("OpenAI", bool(settings.openai_api_key), check_openai),
]

for name, configured, check in checks:
    if not configured:
        print(f"{name}: MISSING")
        continue
    try:
        status, detail = check()
        print(f"{name}: {status} | {detail}")
    except Exception as exc:
        print(f"{name}: ERR | {preview(exc, 240)}")
