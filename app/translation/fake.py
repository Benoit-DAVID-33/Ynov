from app.translation.base import Translator, register_translator


class FakeTranslator(Translator):
    """Marks the text instead of translating it: for tests."""

    def translate(self, texts: list[str]) -> list[str]:
        return [f"[fr] {text}" for text in texts]


register_translator("fake-en-fr", FakeTranslator, source="en", target="fr")
