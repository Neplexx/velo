"""Config du logging"""

import logging
from logging.handlers import RotatingFileHandler

from velo.models import AppConfig


def setup_logging(config: AppConfig) -> None:
    """Configure les logs dans la console et le fichier"""
    config.data.folder.mkdir(parents=True, exist_ok=True) #crée le dossier pour le fichier log
    log_path = config.data.folder / "velo.log"

    niveau = getattr(logging, config.logging.level, logging.INFO) #transforme le str en constant python

    root = logging.getLogger()
    root.setLevel(niveau) #pour définir le niveau minimum affiché
    root.handlers.clear() #supprime les anciens

    format_log = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s" #format du message
    )

    fichier_handler = RotatingFileHandler( #permet de faire une rotation tous les 1Mo (max 3 fichiers)
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    fichier_handler.setLevel(niveau)
    fichier_handler.setFormatter(format_log) #applique la config

    console_handler = logging.StreamHandler() #crée la sortie vers le terminal
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(format_log) #pareil applique la config

    root.addHandler(fichier_handler) #les connecte au niveau de la racine
    root.addHandler(console_handler)
