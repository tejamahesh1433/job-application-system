import sys

sys.path.insert(0, "src")

from anthropic import Anthropic
from config import settings


client = Anthropic(api_key=settings.anthropic_api_key)
models = client.models.list(limit=20)

for model in models.data:
    print(model.id)
