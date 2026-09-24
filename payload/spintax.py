import random
import re
from typing import Optional

class SpintaxParser:
    """
    Parser for recursive nested spintax.
    Example: "{Fast|Quick} {delivery|shipping {worldwide|locally}}"
    """
    SPINTAX_PATTERN = re.compile(r"\{([^{}]+)\}")

    @classmethod
    def spin(cls, text: str, seed: Optional[int] = None) -> str:
        """
        Recursively spins spintax string until no nested brackets remain.
        """
        if not text:
            return ""

        rng = random.Random(seed) if seed is not None else random

        while True:
            match = cls.SPINTAX_PATTERN.search(text)
            if not match:
                break
            
            raw_options = match.group(1)
            # Split by pipe
            options = raw_options.split("|")
            chosen = rng.choice(options)
            
            # Replace the outermost match instance
            text = text[:match.start()] + chosen + text[match.end():]

        return text

    @classmethod
    def generate_variations(cls, text: str, count: int = 5) -> list[str]:
        """Generate multiple distinct spun variations for previewing."""
        results = set()
        attempts = 0
        max_attempts = count * 10
        
        while len(results) < count and attempts < max_attempts:
            results.add(cls.spin(text))
            attempts += 1
            
        return list(results)
