"""Tests for shared filtering utilities."""

import pytest

from research_monitor.adapters.sources.filters import is_speech_related


def test_is_speech_related_match():
    """Test keyword matching in title."""
    keywords = ["speech synthesis", "tts", "audio"]
    
    # "tts" keyword should match "TTS" in title (case-insensitive)
    assert is_speech_related(
        "Zero-Shot TTS System",
        "We present a novel approach",
        keywords
    )


def test_is_speech_related_match_in_content():
    """Test keyword matching in content."""
    keywords = ["speech synthesis", "tts", "audio"]
    
    assert is_speech_related(
        "Novel Approach",
        "This paper presents a speech synthesis model",
        keywords
    )


def test_is_speech_related_case_insensitive():
    """Test case-insensitive matching."""
    keywords = ["TTS", "Speech Synthesis"]
    
    # Uppercase keyword, lowercase text
    assert is_speech_related(
        "text-to-speech system",
        "a novel tts approach",
        keywords
    )
    
    # Lowercase keyword, uppercase text
    assert is_speech_related(
        "TEXT-TO-SPEECH SYSTEM",
        "A NOVEL TTS APPROACH",
        ["tts", "speech synthesis"]
    )


def test_is_speech_related_no_match():
    """Test when keywords don't match."""
    keywords = ["speech", "audio", "voice"]
    
    assert not is_speech_related(
        "Image Classification",
        "Computer vision with CNNs",
        keywords
    )


def test_is_speech_related_substring_match():
    """Test substring matching behavior."""
    keywords = ["speech synthesis"]
    
    # "speech synthesis" keyword will match text containing it
    assert is_speech_related(
        "Novel Speech Synthesis System",
        "We present emotional speech synthesis",
        keywords
    )
    
    # But won't match if only part of keyword is present
    assert not is_speech_related(
        "Speech Recognition System",
        "Automatic speech recognition",
        keywords
    )


def test_is_speech_related_empty_keywords():
    """Test with empty keywords list."""
    # Empty keywords should return True (no filtering)
    assert is_speech_related(
        "Any Title",
        "Any content",
        []
    )


def test_is_speech_related_empty_text():
    """Test with empty text."""
    keywords = ["speech", "audio"]
    
    # Empty text shouldn't match
    assert not is_speech_related("", "", keywords)


def test_is_speech_related_multiple_keywords():
    """Test matching with multiple keywords."""
    keywords = [
        "speech synthesis",
        "voice cloning",
        "emotional tts",
        "zero-shot",
    ]
    
    # Match first keyword
    assert is_speech_related(
        "Speech Synthesis Paper",
        "Novel approach",
        keywords
    )
    
    # Match last keyword
    assert is_speech_related(
        "Zero-Shot Learning",
        "Few-shot and zero-shot approaches",
        keywords
    )
    
    # Match middle keyword
    assert is_speech_related(
        "Novel Paper",
        "Voice cloning with minimal data",
        keywords
    )


def test_is_speech_related_special_characters():
    """Test with special characters in keywords."""
    keywords = ["speech-to-speech", "text-to-speech", "end-to-end"]
    
    assert is_speech_related(
        "Speech-to-Speech Translation",
        "Direct speech to speech model",
        keywords
    )
    
    assert is_speech_related(
        "End to End System",
        "An end-to-end approach",
        keywords
    )

