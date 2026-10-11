"""Capabilities of the pinned Chatterbox integration, without imaginary controls."""

def capabilities(engine):
    original = engine == 'chatterbox'
    return {
        'engine': engine,
        'expression': {'available': original, 'method': 'Original exaggeration and CFG' if original else 'Turbo ignores exaggeration and CFG'},
        'delivery_styles': {'available': True, 'method': 'Saved pitch, pace, gain and pauses; Original also uses exaggeration', 'limitation': 'Approximations; no categorical emotion guarantee'},
        'accent': {'available': False, 'method': 'Choose a reference recording with the desired natural accent', 'limitation': 'No accent-transfer parameter'},
        'similarity_control': {'available': False, 'limitation': 'No dedicated similarity parameter; CFG is not a similarity percentage'},
        'similarity_measurement': {'available': True, 'method': 'Local Chatterbox speaker-encoder cosine comparison', 'limitation': 'Uncalibrated acoustic metric, not identity verification or a percentage; listen to both clips'},
        'laughter': {'available': not original, 'method': 'Turbo upstream [laugh] text tag', 'limitation': 'Acoustic result varies; Original tag support is unavailable'},
        'whisper': {'available': False, 'limitation': 'No validated whisper control in this integration'},
        'generation_modes': {'available': True, 'method': 'Fast uses Turbo; Final uses Original', 'limitation': 'Both models must be downloaded; Original is not guaranteed to sound better'},
        'preview': {'available': True, 'method': 'Real synthesis of the first sentence, at most 240 characters'},
        'language': {'available': ['en'], 'limitation': 'Integrated models are English only'},
    }
