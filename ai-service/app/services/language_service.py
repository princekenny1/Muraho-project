"""
Language Service — Detection and translation for multilingual support.

Supports: English (en), French (fr), Kinyarwanda (rw)

Strategy for Kinyarwanda:
  - Detect language using fasttext-langdetect
  - Translate RW queries → EN for embedding search (better retrieval)
  - Generate response in user's language via LLM instruction
  - Optional: back-translate for verification
"""

import logging

logger = logging.getLogger(__name__)

# Lazy-loaded to avoid import time penalties
_detector = None
_translator = None


def _get_detector():
    """Lazy-load the language detector."""
    global _detector
    if _detector is None:
        try:
            from langdetect import detect as langdetect_detect
            _detector = langdetect_detect
            logger.info("Language detector loaded (langdetect)")
        except ImportError:
            logger.warning("langdetect not installed. Falling back to simple detection.")
            _detector = _simple_detect
    return _detector


def _simple_detect(text: str) -> str:
    """
    Simple fallback language detection based on character patterns.
    Not accurate but works as a fallback.
    """
    text_lower = text.lower()

    # Kinyarwanda common words and patterns
    rw_signals = [
        "muraho", "amakuru", "murakoze", "neza", "cyane",
        "umwami", "igihugu", "ubwoko", "umuntu", "abantu",
        "iki", "ibi", "umu", "aba", "imi", "ndi", "turi",
    ]
    rw_count = sum(1 for s in rw_signals if s in text_lower)
    if rw_count >= 2:
        return "rw"

    # French common patterns
    fr_signals = [
        " le ", " la ", " les ", " des ", " du ", " un ", " une ",
        " est ", " sont ", " dans ", " pour ", " avec ", " sur ",
        "qu'est", "c'est", "n'est", "j'ai", "l'histoire",
    ]
    fr_count = sum(1 for s in fr_signals if s in text_lower)
    if fr_count >= 2:
        return "fr"

    # Default to English
    return "en"


class LanguageService:
    """
    Multilingual support for Muraho Rwanda.
    Handles detection and translation for EN/FR/RW.
    """

    def __init__(self):
        self._translator_model = None
        self._translator_tokenizer = None

    def detect(self, text: str) -> str:
        """
        Detect the language of input text.

        Returns: 'en', 'fr', or 'rw'
        """
        if not text or len(text.strip()) < 3:
            return "en"

        try:
            detector = _get_detector()
            detected = detector(text)

            # Map langdetect codes to our supported languages
            lang_map = {
                "en": "en",
                "fr": "fr",
                "rw": "rw",
                "sw": "rw",  # Swahili sometimes confused with Kinyarwanda
            }
            result = lang_map.get(detected, "en")
            logger.debug(f"Language detected: '{text[:50]}...' → {result} (raw: {detected})")
            return result

        except Exception as e:
            logger.warning(f"Language detection failed: {e}. Defaulting to 'en'.")
            return "en"

    def translate_to_english(self, text: str) -> str:
        """
        Translate Kinyarwanda or French text to English for embedding search.
        Uses NLLB-200 (Meta's translation model) running locally.

        Falls back to returning original text if translation fails.
        """
        try:
            model, tokenizer = self._load_translator()

            # NLLB-200 language codes
            src_lang = "kin_Latn"  # Kinyarwanda
            tgt_lang = "eng_Latn"  # English

            tokenizer.src_lang = src_lang
            inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)

            translated = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_lang),
                max_length=512,
            )

            result = tokenizer.batch_decode(translated, skip_special_tokens=True)[0]
            logger.info(f"Translation RW→EN: '{text[:50]}' → '{result[:50]}'")
            return result

        except Exception as e:
            logger.warning(f"Translation failed: {e}. Using original text for search.")
            return text

    def _load_translator(self):
        """Lazy-load the NLLB-200 translation model."""
        if self._translator_model is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            from app.core.config import settings

            logger.info(f"Loading translation model: {settings.TRANSLATION_MODEL}")
            self._translator_tokenizer = AutoTokenizer.from_pretrained(
                settings.TRANSLATION_MODEL
            )
            self._translator_model = AutoModelForSeq2SeqLM.from_pretrained(
                settings.TRANSLATION_MODEL
            )
            logger.info("Translation model loaded")

        return self._translator_model, self._translator_tokenizer

    def get_response_language_instruction(self, detected_lang: str) -> str:
        """
        Returns an instruction for the LLM to respond in the user's language.
        """
        instructions = {
            "en": "Respond in English.",
            "fr": "Répondez en français. (Respond in French.)",
            "rw": "Respond in English but include key Kinyarwanda terms where culturally appropriate.",
        }
        return instructions.get(detected_lang, "Respond in English.")
