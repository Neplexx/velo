"""validation du fichier yaml"""

from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_config_dir
from pydantic import ValidationError

from velo.models import AppConfig, VeloError


def config_path_de_base() -> Path:
    """Chemind de base du config.yaml"""
    return Path(user_config_dir("velo")) / "config.yaml"

def appliquer_options_cli(base: dict, options_cli : dict) -> dict:
    """CLI> yaml : Permet d'enregistrer la valeur entrée par l'utilisateur sans modifier le fichier yaml (juste pour une commande donc)"""
    for section, options in options_cli.items():
        cible = base.setdefault(section, {}) #prend section si existe sinon met un dico vide
        for cle, valeur in options.items():
            if valeur is not None:
                cible[cle] = valeur 
    return base

def load_option(config_path: Path | None = None, options_cli: dict[str, Any] | None = None) -> AppConfig:
    """Charge config.yaml et applique les options CLI au dessus"""
    if config_path:
        chemin = config_path
    else:
        chemin = config_path_de_base()
    if config_path is not None and not chemin.exists(): #si utilisateur a donné un fichier config pas valide
        raise VeloError(f"Fichier introuvable : {chemin}")
    
    data = {}
    if chemin.exists(): #existance de chemin
        try:
            contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
            if contenu is not None:
                data = contenu
            else: 
                data = {}
        except (OSError, yaml.YAMLError) as e:
            raise VeloError(f"Erreur de lecture : {e}") from e
        
    if not isinstance(data, dict): #vérifie que l'objet est bien un dico
        raise VeloError(f"Format invalide dans {chemin} (dictionnaire attendu).")
    
    if options_cli:
        data = appliquer_options_cli(data, options_cli)
    try:
        return AppConfig.model_validate(data)
    except ValidationError as e:
        raise VeloError(f"Configuration invalide : {e}") from e

def save_config(config: AppConfig, config_path: Path | None = None, force: bool = False) -> Path:
    """Stocke config.yaml sur le pc"""
    if config_path:
        chemin = config_path
    else:
        chemin = config_path_de_base()
    if chemin.exists() and not force: #si existe déjà et que force n'est pas activé
        raise VeloError(f"le fichier existe déjà : {chemin} (--force pour l'écraser)")
    
    chemin.parent.mkdir(parents=True, exist_ok=True)
    donnees = config.model_dump(mode="json")
    texte = yaml.safe_dump(donnees, sort_keys=False, allow_unicode=True)
    chemin.write_text(texte, encoding="utf-8")
    return  chemin