import re
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class BrailleNotSupportedError(Exception):
    """
    Raised when Braille was requested for a language this service cannot
    honestly produce correct output for.

    WHY HINDI/KANNADA BRAILLE ISN'T IMPLEMENTED: the correct standard is
    Bharati Braille, India's unified Braille code for Indic scripts.
    Implementing it correctly needs a certified character-to-cell mapping
    table. No such library exists on PyPI (checked directly: no
    "bharati-braille", "indic-braille", or equivalent package). Hand-writing
    that table from general knowledge was deliberately rejected --
    Devanagari and Kannada each have 40+ consonants/vowels/matras with
    precise published assignments and virama/conjunct rules; getting even a
    few wrong would produce incorrect Braille that a blind reader has no way
    to independently detect as wrong, unlike a wrong caption a sighted user
    could compare against the video. So this raises a clear error instead of
    guessing -- see tests for the explicit assertions on this behavior.
    """


LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}

# Standard ASCII Braille to Unicode Braille pattern map
ASCII_TO_UNICODE_BRAILLE = {
    ' ': '⠀', '!': '⠮', '"': '⠐', '#': '⠼', '$': '⠫', '%': '⠩', '&': '⠯', "'": '⠄',
    '(': '⠷', ')': '⠾', '*': '⠡', '+': '⠬', ',': '⠂', '-': '⠤', '.': '⠨', '/': '⠌',
    '0': '⠼⠚', '1': '⠼⠁', '2': '⠼⠃', '3': '⠼⠉', '4': '⠼⠙', '5': '⠼⠑',
    '6': '⠼⠋', '7': '⠼⠛', '8': '⠼⠓', '9': '⠼⠊',
    ':': '⠒', ';': '⠆', '<': '⠪', '=': '⠿', '>': '⠻', '?': '⠹', '@': '⠈',
    'a': '⠁', 'b': '⠃', 'c': '⠉', 'd': '⠙', 'e': '⠑', 'f': '⠋', 'g': '⠛', 'h': '⠓',
    'i': '⠊', 'j': '⠚', 'k': '⠅', 'l': '⠇', 'm': '⠍', 'n': '⠝', 'o': '⠕', 'p': '⠏',
    'q': '⠟', 'r': '⠌', 's': '⠎', 't': '⠞', 'u': '⠥', 'v': '⠧', 'w': '⠺', 'x': '⠭',
    'y': '⠽', 'z': '⠵', '[': '⠹', '\\': '⠸', ']': '⠻', '^': '⠘', '_': '⠨'
}

# Grade 2 Common Contractions
GRADE_2_CONTRACTIONS = {
    r'\bthe\b': '!',
    r'\band\b': '&',
    r'\bfor\b': '=',
    r'\bof\b': '(',
    r'\bwith\b': ')',
    r'\bwill\b': 'w',
    r'\bthat\b': 't',
    r'\bthis\b': '?',
    r'\bhave\b': 'h',
    r'\bfrom\b': 'f',
    r'\bnot\b': 'n',
    r'\bbut\b': 'b',
    r'\bcan\b': 'c',
    r'\bknowledge\b': 'k',
    r'\bmore\b': 'm',
    r'\bpeople\b': 'p',
    r'\bquite\b': 'q',
    r'\brather\b': 'r',
    r'\bso\b': 's',
    r'\bvery\b': 'v',
    r'\bit\b': 'x',
    r'\byou\b': 'y',
    r'\bas\b': 'z'
}

class BrailleConverterService:
    """
    Converts English plain text into standard Grade 1 & Grade 2 Braille Ready Format (.BRF).
    Formatted specifically for 40-cell refreshable braille displays and embossers.
    """

    def text_to_brf(self, text: str, grade: int = 2, language: str = "en") -> Tuple[str, str]:
        """
        Converts text to (ASCII BRF format string, Unicode Braille visual string).
        Formats lines to a maximum of 40 characters per line.

        Raises BrailleNotSupportedError for languages without a verified
        Braille table -- see the class docstring above for why.
        """
        if language != "en":
            raise BrailleNotSupportedError(
                f"Braille conversion for {LANGUAGE_NAMES.get(language, language)} requires a certified "
                "Bharati Braille transliteration table, which is not available as a verified library in "
                "this environment. To avoid producing incorrect Braille output -- which a blind reader "
                "would have no way to independently detect as wrong -- this is intentionally not "
                "generated. English Braille remains fully supported. For certified Bharati Braille "
                "transcription, use dedicated assistive-technology tools such as those provided by "
                "India's National Institute for the Visually Handicapped."
            )

        if not text:
            text = "No content to convert."
            
        clean_text = self._sanitize_text(text)
        
        if grade == 2:
            ascii_braille = self._to_grade_2_ascii(clean_text)
        else:
            ascii_braille = self._to_grade_1_ascii(clean_text)
            
        # Format into 40-cell lines standard for .BRF files
        brf_formatted_lines = self._wrap_brf_lines(ascii_braille, cell_limit=40)
        brf_content = "\r\n".join(brf_formatted_lines)
        
        # Build visual Unicode braille display
        unicode_braille = self._ascii_to_unicode(brf_content)
        
        return brf_content, unicode_braille

    def _sanitize_text(self, text: str) -> str:
        text = text.replace("•", "- ").replace("“", '"').replace("”", '"').replace("’", "'")
        return re.sub(r'[^\x00-\x7F]+', ' ', text)

    def _to_grade_1_ascii(self, text: str) -> str:
        result = []
        in_number = False
        
        for char in text:
            if char.isupper():
                result.append(',')
                result.append(char.lower())
                in_number = False
            elif char.isdigit():
                if not in_number:
                    result.append('#')
                    in_number = True
                # Map digits to a-j in ASCII Braille
                num_map = {'0': 'j', '1': 'a', '2': 'b', '3': 'c', '4': 'd', '5': 'e', '6': 'f', '7': 'g', '8': 'h', '9': 'i'}
                result.append(num_map.get(char, char))
            else:
                if char.isspace() or char in ".,!?;:-()":
                    in_number = False
                result.append(char)
                
        return "".join(result)

    def _to_grade_2_ascii(self, text: str) -> str:
        # First convert case and digits using Grade 1 structure
        g1_text = self._to_grade_1_ascii(text)
        
        # Apply Grade 2 contractions
        for pattern, replacement in GRADE_2_CONTRACTIONS.items():
            g1_text = re.sub(pattern, replacement, g1_text, flags=re.IGNORECASE)
            
        return g1_text

    def _wrap_brf_lines(self, text: str, cell_limit: int = 40) -> list:
        lines = []
        for orig_line in text.splitlines():
            words = orig_line.split(" ")
            current_line = ""
            for word in words:
                if not word:
                    continue
                if len(current_line) + len(word) + (1 if current_line else 0) <= cell_limit:
                    current_line = f"{current_line} {word}" if current_line else word
                else:
                    lines.append(current_line)
                    current_line = word[:cell_limit]
            if current_line:
                lines.append(current_line)
            if not orig_line:
                lines.append("")
        return lines if lines else [""]

    def _ascii_to_unicode(self, ascii_text: str) -> str:
        unicode_chars = []
        for char in ascii_text:
            low_char = char.lower()
            if low_char in ASCII_TO_UNICODE_BRAILLE:
                unicode_chars.append(ASCII_TO_UNICODE_BRAILLE[low_char])
            elif char == '\r' or char == '\n':
                unicode_chars.append(char)
            else:
                unicode_chars.append('⠿')
        return "".join(unicode_chars)

braille_service = BrailleConverterService()
