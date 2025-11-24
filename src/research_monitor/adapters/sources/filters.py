"""Shared filtering utilities for sources."""


def is_speech_related(title: str, content: str, keywords: list[str]) -> bool:
    """
    Check if content is related to speech/audio based on keywords.
    
    Args:
        title: Title of the item
        content: Content/abstract/description of the item
        keywords: List of keywords to check against
        
    Returns:
        True if any keyword is found in title or content (case-insensitive)
    """
    if not keywords:
        return True  # No filtering if no keywords provided
    
    text = f"{title} {content}".lower()
    return any(keyword.lower() in text for keyword in keywords)

