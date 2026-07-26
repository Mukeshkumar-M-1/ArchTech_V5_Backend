from .engine import PromptEngine

# Singleton — loaded once, reused everywhere
prompts = PromptEngine()
