import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logger():
    logger = logging.getLogger('food-api')
    logger.setLevel(logging.INFO)

    # Format du log
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Handler pour la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler pour le fichier (avec rotation)
    try:
        file_handler = RotatingFileHandler(
            'logs/food-api.log',
            maxBytes=1024 * 1024,  # 1MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        # En cas d'erreur (ex: sur Render où l'écriture peut être limitée)
        pass

    return logger

logger = setup_logger() 