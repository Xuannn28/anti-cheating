# config.py

APP_CONFIG = {
    'detection': {
        'eyes': {
            'ear_threshold': 0.05,         # Eye Aspect Ratio threshold (below this = closed)
        },
        "audio": {
            "perplexity_threshold": 45.0,
            "min_word_count": 5
        }
    }
}