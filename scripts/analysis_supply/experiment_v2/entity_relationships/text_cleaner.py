#!/usr/bin/env python3
"""
Script de nettoyage intelligent des fichiers textes
Nettoie et structure les fichiers avant traitement par le LLM
"""

import os
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Tuple
import logging
from datetime import datetime
import shutil
import json

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntelligentTextCleaner:
    """
    Nettoyeur intelligent pour les fichiers textes musicaux
    """
    
    def __init__(self):
        self.cleaning_stats = {
            'files_processed': 0,
            'files_failed': 0,
            'total_chars_removed': 0,
            'operations_performed': []
        }
        
        # Patterns de nettoyage spécifiques aux sites web musicaux
        self.web_patterns = {
            # Navigation et menus répétitifs
            'navigation_menu': r'A PROPOS FESTIVALS PRODUCTIONS CONTACT|FESTIVALS PRODUCTIONS CONTACT|CONTACT ART POINT M',
            'menu_separators': r'•/\\/*•|★|•',
            'email_footer': r'infos@[a-zA-Z0-9.-]+\.com|© \d{4} - [A-Za-z]+',
            'repeated_titles': r'Art Point M ★',
            'url_fragments': r'http[s]?://[^\s]+',
            
            # Structures HTML résiduelles
            'html_entities': r'&[a-zA-Z0-9#]+;',
            'html_tags': r'<[^>]+>',
            'css_classes': r'class="[^"]*"',
            
            # Éléments de navigation web
            'breadcrumb': r'Go to ->|<- on facebook',
            'social_media': r'Voir le profil de .+ sur Facebook',
            'generic_links': r'Plus d\'infos?|En savoir plus|Lire la suite',
        }
        
        # Patterns de structure à préserver mais nettoyer
        self.structure_patterns = {
            'dates': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}\b',
            'emails': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phones': r'\b\d{2}[-.\s]?\d{2}[-.\s]?\d{2}[-.\s]?\d{2}[-.\s]?\d{2}\b',
            'addresses': r'\b\d+\s+[A-Za-z\s]+\d{5}\s+[A-Za-z\s]+\b',
        }
        
    def analyze_file_content(self, file_path: str) -> Dict:
        """
        Analyse un fichier et identifie les problèmes de nettoyage
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            analysis = {
                'file_size': len(content),
                'line_count': len(content.split('\n')),
                'issues_detected': [],
                'suggested_operations': []
            }
            
            # Détecter les problèmes courants
            if '★' in content or '•/\\/•' in content:
                analysis['issues_detected'].append('web_navigation_elements')
                analysis['suggested_operations'].append('remove_web_navigation')
            
            if 'A PROPOS FESTIVALS PRODUCTIONS CONTACT' in content:
                analysis['issues_detected'].append('repeated_menu_structure')
                analysis['suggested_operations'].append('remove_repeated_menus')
            
            if len(re.findall(r'(.+?)\1{2,}', content)) > 0:
                analysis['issues_detected'].append('text_repetition')
                analysis['suggested_operations'].append('remove_repetitive_content')
            
            if re.search(r'\w{50,}', content):
                analysis['issues_detected'].append('concatenated_words')
                analysis['suggested_operations'].append('fix_word_segmentation')
            
            # Détecter l'encodage problématique
            try:
                content.encode('ascii')
            except UnicodeEncodeError:
                analysis['issues_detected'].append('special_characters')
                analysis['suggested_operations'].append('normalize_encoding')
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erreur analyse {file_path}: {str(e)}")
            return {'error': str(e)}
    
    def remove_web_navigation(self, text: str) -> Tuple[str, int]:
        """
        Supprime les éléments de navigation web répétitifs
        """
        original_length = len(text)
        
        # Supprimer les patterns de navigation
        for pattern_name, pattern in self.web_patterns.items():
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Nettoyer les espaces multiples résultants
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        chars_removed = original_length - len(text)
        return text.strip(), chars_removed
    
    def remove_repeated_content(self, text: str) -> Tuple[str, int]:
        """
        Supprime le contenu répétitif (blocs dupliqués) - VERSION AMÉLIORÉE
        """
        original_length = len(text)
        
        # 1. SUPPRESSION SPÉCIFIQUE DES LISTES RÉPÉTITIVES ART POINT M
        # Détecter et supprimer la liste répétitive de productions (pattern corrigé)
        production_pattern = r'/\\/\\ PRODUCTIONS Les Eurockéennes.*?(?=Art Point M|/\\/\\|$)'
        text = re.sub(production_pattern, '\n[LISTE ÉVÉNEMENTS SUPPRIMÉE]\n', text, flags=re.DOTALL)
        
        # Supprimer les longues listes d'événements répétées
        long_list_pattern = r'(Les Eurockéennes Juillet 2024 DRAGUE ME.*?Point M\s*){2,}'
        text = re.sub(long_list_pattern, r'\1', text, flags=re.DOTALL)
        
        # Supprimer les répétitions de "Art Point M" en début/fin de sections
        text = re.sub(r'(Art Point M\s*){2,}', 'Art Point M ', text)
        
        # Supprimer complètement les blocs répétitifs très longs
        repetitive_block = r'Les Eurockéennes Juillet 2024 DRAGUE ME Show Drag et Queer PARADE.*?SCÉNOGRAPHIE Point M'
        if text.count('Les Eurockéennes Juillet 2024 DRAGUE ME') > 5:  # Si répété plus de 5 fois
            # Garder seulement la première occurrence
            parts = re.split(repetitive_block, text)
            if len(parts) > 1:
                text = parts[0] + '\n[BLOC RÉPÉTITIF SUPPRIMÉ]\n' + parts[-1]
        
        # 2. NETTOYAGE STANDARD DES PARAGRAPHES DUPLIQUÉS
        # Diviser en paragraphes
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        # Supprimer les paragraphes dupliqués (seuil de similarité)
        cleaned_paragraphs = []
        seen_content = set()
        
        for paragraph in paragraphs:
            # Normaliser pour la comparaison
            normalized = re.sub(r'\s+', ' ', paragraph.lower().strip())
            
            # Si le paragraphe est très court, le garder
            if len(normalized) < 50:
                cleaned_paragraphs.append(paragraph)
                continue
            
            # NOUVEAUTÉ : Ignorer les listes répétitives d'événements
            if self._is_repetitive_event_list(normalized):
                if normalized not in seen_content:  # Garder seulement la première occurrence
                    cleaned_paragraphs.append(paragraph)
                    seen_content.add(normalized)
                continue
            
            # Vérifier la similarité avec les paragraphes déjà vus
            is_duplicate = False
            for seen in seen_content:
                if len(set(normalized.split()) & set(seen.split())) / len(set(normalized.split()) | set(seen.split())) > 0.8:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                cleaned_paragraphs.append(paragraph)
                seen_content.add(normalized)
        
        cleaned_text = '\n\n'.join(cleaned_paragraphs)
        chars_removed = original_length - len(cleaned_text)
        
        return cleaned_text, chars_removed
    
    def fix_word_segmentation(self, text: str) -> Tuple[str, int]:
        """
        Corrige la segmentation des mots collés
        """
        original_length = len(text)
        
        # Patterns courants de mots collés
        fixes = [
            # Correction des espaces manquants après la ponctuation
            (r'([.!?:;])([A-Z])', r'\1 \2'),
            
            # Séparer les mots collés avec des majuscules
            (r'([a-z])([A-Z][a-z])', r'\1 \2'),
            
            # Corriger les dates collées
            (r'(\d{4})([A-Za-z])', r'\1 \2'),
            
            # Corriger les emails collés
            (r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})([A-Z])', r'\1 \2'),
            
            # Espaces avant/après parenthèses
            (r'\s*\(\s*', ' ('),
            (r'\s*\)\s*', ') '),
            
            # Espaces multiples
            (r'\s{2,}', ' ')
        ]
        
        for pattern, replacement in fixes:
            text = re.sub(pattern, replacement, text)
        
        chars_removed = original_length - len(text)
        return text.strip(), chars_removed
    
    def normalize_encoding(self, text: str) -> Tuple[str, int]:
        """
        Normalise l'encodage et les caractères spéciaux
        """
        original_length = len(text)
        
        # Normalisation Unicode
        text = unicodedata.normalize('NFKC', text)
        
        # Corrections spécifiques courantes
        corrections = {
            'â€™': "'",  # Apostrophe mal encodée
            'â€œ': '"',  # Guillemets ouvrants
            'â€\x9d': '"',  # Guillemets fermants
            'Ã ': 'à',   # a accent grave
            'Ã©': 'é',   # e accent aigu
            'Ã¨': 'è',   # e accent grave
            'Ãª': 'ê',   # e circonflexe
            'Ã§': 'ç',   # c cedille
            'â€¦': '...',  # Points de suspension
            'â€"': '—',   # Tiret long
            '\xa0': ' ',  # Espace insécable
            '\u200b': '',  # Espace de largeur nulle
        }
        
        for bad_char, good_char in corrections.items():
            text = text.replace(bad_char, good_char)
        
        # Supprimer les caractères de contrôle problématiques
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', text)
        
        chars_removed = original_length - len(text)
        return text, chars_removed
    
    def structure_content(self, text: str) -> Tuple[str, int]:
        """
        Structure le contenu en sections logiques
        """
        original_length = len(text)
        
        # Identifier et marquer les sections importantes
        sections = []
        current_section = []
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Détecter les titres (lignes courtes en majuscules ou avec des patterns spéciaux)
            is_title = (
                len(line) < 100 and 
                (line.isupper() or 
                 re.match(r'^[A-Z][^.]*$', line) or
                 any(keyword in line.upper() for keyword in ['FESTIVAL', 'CONCERT', 'EVENT', 'ASSOCIATION', 'PRODUCTION']))
            )
            
            if is_title and current_section:
                # Finaliser la section précédente
                sections.append('\n'.join(current_section))
                current_section = [f"\n=== {line} ===\n"]
            else:
                current_section.append(line)
        
        # Ajouter la dernière section
        if current_section:
            sections.append('\n'.join(current_section))
        
        structured_text = '\n\n'.join(sections)
        chars_removed = original_length - len(structured_text)
        
        return structured_text, chars_removed
    
    def _is_repetitive_event_list(self, normalized_text: str) -> bool:
        """
        Détecte si un paragraphe est une liste répétitive d'événements
        """
        # Indicateurs de listes répétitives
        repetitive_indicators = [
            'les eurockéennes juillet 2024',
            'drague me show drag',
            'parade toutes et tous en fleurs',
            'art point m productions',
            '/\\/\\ productions'
        ]
        
        # Compter les occurrences d'événements typiques
        event_count = sum(1 for indicator in repetitive_indicators if indicator in normalized_text)
        
        # Si plus de 3 événements dans le même paragraphe, c'est probablement une liste
        return event_count >= 3
    
    def clean_single_file(self, input_path: str, output_path: str) -> Dict:
        """
        Nettoie un fichier unique
        """
        try:
            # Lire le fichier original
            with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
                original_content = f.read()
            
            logger.info(f"📄 Nettoyage: {Path(input_path).name} ({len(original_content):,} caractères)")
            
            # Analyser le fichier
            analysis = self.analyze_file_content(input_path)
            
            # Appliquer les nettoyages selon l'analyse
            content = original_content
            total_chars_removed = 0
            operations_log = []
            
            # 1. Supprimer la navigation web
            if 'remove_web_navigation' in analysis.get('suggested_operations', []):
                content, chars_removed = self.remove_web_navigation(content)
                total_chars_removed += chars_removed
                operations_log.append(f"Navigation web supprimée: -{chars_removed} chars")
            
            # 2. Supprimer le contenu répétitif
            if 'remove_repeated_menus' in analysis.get('suggested_operations', []):
                content, chars_removed = self.remove_repeated_content(content)
                total_chars_removed += chars_removed
                operations_log.append(f"Contenu répétitif supprimé: -{chars_removed} chars")
            
            # 3. Corriger la segmentation
            if 'fix_word_segmentation' in analysis.get('suggested_operations', []):
                content, chars_removed = self.fix_word_segmentation(content)
                total_chars_removed += chars_removed
                operations_log.append(f"Segmentation corrigée: -{chars_removed} chars")
            
            # 4. Normaliser l'encodage
            if 'normalize_encoding' in analysis.get('suggested_operations', []):
                content, chars_removed = self.normalize_encoding(content)
                total_chars_removed += chars_removed
                operations_log.append(f"Encodage normalisé: -{chars_removed} chars")
            
            # 5. Structurer le contenu
            content, chars_removed = self.structure_content(content)
            total_chars_removed += chars_removed
            operations_log.append(f"Contenu structuré: -{chars_removed} chars")
            
            # Nettoyage final
            content = content.strip()
            content = re.sub(r'\n{3,}', '\n\n', content)  # Max 2 retours à la ligne consécutifs
            
            # Créer le dossier de sortie si nécessaire
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Sauvegarder le fichier nettoyé
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Statistiques
            compression_ratio = (len(original_content) - len(content)) / len(original_content) * 100
            
            result = {
                'success': True,
                'input_file': input_path,
                'output_file': output_path,
                'original_size': len(original_content),
                'cleaned_size': len(content),
                'chars_removed': total_chars_removed,
                'compression_ratio': compression_ratio,
                'operations': operations_log,
                'issues_detected': analysis.get('issues_detected', [])
            }
            
            logger.info(f"  ✅ Nettoyé: {len(content):,} chars (-{compression_ratio:.1f}%)")
            
            self.cleaning_stats['files_processed'] += 1
            self.cleaning_stats['total_chars_removed'] += total_chars_removed
            self.cleaning_stats['operations_performed'].extend(operations_log)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage {input_path}: {str(e)}")
            self.cleaning_stats['files_failed'] += 1
            return {
                'success': False,
                'input_file': input_path,
                'error': str(e)
            }
    
    def clean_directory(self, input_dir: str, output_dir: str) -> List[Dict]:
        """
        Nettoie tous les fichiers d'un répertoire
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Répertoire source introuvable: {input_dir}")
        
        # Créer le répertoire de sortie
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Lister les fichiers à traiter
        files_to_process = [f for f in input_path.iterdir() if f.is_file()]
        
        logger.info(f"🧹 NETTOYAGE DE {len(files_to_process)} FICHIERS")
        logger.info(f"📁 Source: {input_path}")
        logger.info(f"📁 Destination: {output_path}")
        logger.info("="*60)
        
        results = []
        
        for file_path in files_to_process:
            output_file_path = output_path / file_path.name
            result = self.clean_single_file(str(file_path), str(output_file_path))
            results.append(result)
        
        # Sauvegarder le rapport de nettoyage
        self._save_cleaning_report(results, output_path)
        
        return results
    
    def _save_cleaning_report(self, results: List[Dict], output_dir: Path):
        """
        Sauvegarde un rapport détaillé du nettoyage
        """
        report = {
            'cleaning_timestamp': datetime.now().isoformat(),
            'summary': self.cleaning_stats,
            'file_results': results
        }
        
        report_path = output_dir / 'cleaning_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📋 Rapport sauvegardé: {report_path}")
    
    def print_cleaning_summary(self):
        """
        Affiche un résumé du nettoyage
        """
        stats = self.cleaning_stats
        
        print("\n" + "="*60)
        print("🧹 RÉSUMÉ DU NETTOYAGE")
        print("="*60)
        print(f"📄 Fichiers traités avec succès: {stats['files_processed']}")
        print(f"❌ Fichiers en erreur: {stats['files_failed']}")
        print(f"✂️ Total caractères supprimés: {stats['total_chars_removed']:,}")
        
        if stats['operations_performed']:
            print(f"\n🔧 Opérations les plus fréquentes:")
            operation_counts = {}
            for op in stats['operations_performed']:
                op_type = op.split(':')[0]
                operation_counts[op_type] = operation_counts.get(op_type, 0) + 1
            
            for op_type, count in sorted(operation_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   • {op_type}: {count} fois")

def main():
    """
    Fonction principale pour le nettoyage
    """
    print("🧹 NETTOYEUR INTELLIGENT DE FICHIERS TEXTES")
    print("="*60)
    
    # Configuration par défaut
    input_directory = "../../../../data/data_supply/textes"
    output_directory = "../../../../data/data_supply/textes_cleaned"
    
    # Permettre la personnalisation
    custom_input = input("Dossier source (défaut: data/data_supply/textes): ")
    if custom_input.strip():
        input_directory = custom_input.strip()
    
    custom_output = input("Dossier destination (défaut: data/data_supply/textes_cleaned): ")
    if custom_output.strip():
        output_directory = custom_output.strip()
    
    try:
        # Initialiser le nettoyeur
        cleaner = IntelligentTextCleaner()
        
        # Nettoyer tous les fichiers
        results = cleaner.clean_directory(input_directory, output_directory)
        
        # Afficher le résumé
        cleaner.print_cleaning_summary()
        
        print(f"\n✅ Nettoyage terminé!")
        print(f"📁 Fichiers nettoyés disponibles dans: {output_directory}")
        print(f"📋 Voir le rapport détaillé: {output_directory}/cleaning_report.json")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())