import classGraphData
import sys
import pandas as pd
import importlib
import pickle
from mistralai import Mistral
import json 
from typing import List, Dict, Tuple
import os
from pathlib import Path
from tqdm import tqdm
import hashlib
from datetime import datetime
import re
import uuid
import time
from difflib import SequenceMatcher
sys.path.append('../../../../')
import src.pipeline as pipeline
import src.transform as transform
import src.study_text as study_text
# from src.columns_definition import ConcertOrganizerGraph
import src.columns_definition as columns_definition
# importlib.reload(columns_definition)
importlib.reload(study_text)
importlib.reload(pipeline)
importlib.reload(transform)
importlib.reload(columns_definition)
importlib.reload(classGraphData)

# Configuration pour le traitement batch avec GraphData
Prompt = classGraphData.Prompt
GraphData = classGraphData.GraphData

class ChunkedBatchGraphDataProcessor:
    """
    Processeur batch avec système de checkpoints pour reprendre après interruption
    """
    
    def __init__(self, api_key: str = "wm1af0pJ92Pj1tLbTSztHxeey62ru479", model: str = "mistral-large-latest"):
        self.api_key = api_key
        self.model = model
        self.client = Mistral(api_key=api_key)
        self.prompt = Prompt().prompt
        self.chunk_prompt = self._create_chunk_prompt()
        self.results = []
        self.failed_files = []
        
        # Configuration chunking
        self.max_chunk_size = 10**5  # 100k caractères
        self.chunk_overlap = 2000     # Overlap entre chunks pour contexte
        self.min_chunk_size = 5000    # Taille minimale d'un chunk
        
        # Configuration checkpoints
        self.checkpoint_file = "processing_checkpoint.json"
        self.backup_interval = 5  # Sauvegarde tous les N fichiers
        self.processed_files = set()  # Fichiers déjà traités
        self.current_file_index = 0
        
        # Charger l'état précédent si existant
        self._load_checkpoint()
        
    def _create_chunk_prompt(self) -> str:
        """Crée un prompt spécialisé pour le traitement par chunks"""
        return """Tu es un système d'extraction d'information qui transforme un FRAGMENT de texte en un graphe d'entités, de relations et d'événements.
                    
                    ⚠️ IMPORTANT: Ce texte est un FRAGMENT d'un document plus large.
                    
                    🚨 RÈGLES CRITIQUES - PRIORITÉS ABSOLUES 🚨
                    
                    1. **INTENTIONS - PRIORITÉ ABSOLUE** :
                       - Pour CHAQUE entité, tu DOIS identifier au minimum une intention/objectif
                       - Les intentions sont OBLIGATOIRES, jamais une liste vide []
                       - Analyse le contexte du fragment pour déduire les intentions
                       - Si non explicites, déduis-les du type d'activité
                       - Sois créatif et analytique pour identifier les motivations sous-jacentes
                    
                    2. **ÉVÉNEMENTS ET STYLES MUSICAUX - PRIORITÉ CRITIQUE** :
                       - Extrais TOUS les événements mentionnés dans ce fragment
                       - Pour CHAQUE concert/spectacle musical, le champ concert_style est OBLIGATOIRE
                       - Sois TRÈS précis sur les styles : Rock, Jazz, Électro, Hip-hop, Classique, Folk, Métal, Reggae, etc.
                       - Si le style n'est pas explicite, déduis-le du contexte disponible
                    
                    3. **TRAITEMENT PAR FRAGMENT** :
                       - NE traite QUE les informations présentes dans ce fragment
                       - Utilise des IDs uniques générés aléatoirement (UUID)
                       - Si tu vois une référence à une entité non définie dans ce fragment, ne crée pas de relation vers elle
                       - Concentre-toi sur les entités, événements et relations COMPLETS dans ce fragment
                    
                    4. **Autres règles importantes** :
                       - Tu dois extraire toutes les entités nommées pertinentes (associations, entreprises, institutions, personnes, autres).
                       - Chaque entité et événement doit avoir un identifiant unique généré aléatoirement (UUID).
                       - Si la date est mentionnée dans le texte, l'indiquer au format AAAA-MM-JJ. Sinon, laisse null.
                       - La sortie doit être uniquement un objet JSON valide, sans texte additionnel.
                       - IMPÉRATIF : Le JSON produit doit être parfaitement compatible avec json.loads() en Python."""
    
    def _load_checkpoint(self):
        """Charge l'état de traitement précédent depuis le checkpoint"""
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)
                
                self.processed_files = set(checkpoint_data.get('processed_files', []))
                self.current_file_index = checkpoint_data.get('current_file_index', 0)
                
                # Charger les résultats existants
                results_file = checkpoint_data.get('results_file', 'batch_graphdata_chunked_results.pkl')
                if os.path.exists(results_file):
                    with open(results_file, 'rb') as f:
                        self.results = pickle.load(f)
                
                # Charger les erreurs existantes
                errors_file = checkpoint_data.get('errors_file', 'batch_graphdata_chunked_results_errors.json')
                if os.path.exists(errors_file):
                    with open(errors_file, 'r', encoding='utf-8') as f:
                        self.failed_files = json.load(f)
                
                print(f"📁 Checkpoint chargé: {len(self.processed_files)} fichiers déjà traités")
                print(f"📄 {len(self.results)} résultats existants chargés")
                if self.failed_files:
                    print(f"❌ {len(self.failed_files)} erreurs précédentes chargées")
                    
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement du checkpoint: {e}")
            print("🔄 Démarrage d'un nouveau traitement...")
    
    def _save_checkpoint(self, all_files: List[Path], results_file: str = "batch_graphdata_chunked_results.pkl"):
        """Sauvegarde l'état actuel du traitement"""
        try:
            checkpoint_data = {
                'processed_files': list(self.processed_files),
                'current_file_index': self.current_file_index,
                'total_files': len(all_files),
                'results_file': results_file,
                'errors_file': results_file.replace('.pkl', '_errors.json'),
                'timestamp': datetime.now().isoformat(),
                'progress_percentage': (len(self.processed_files) / len(all_files)) * 100 if all_files else 0
            }
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            
            # Sauvegarder les résultats actuels
            self._save_intermediate_results(results_file)
            
        except Exception as e:
            print(f"⚠️ Erreur lors de la sauvegarde du checkpoint: {e}")
    
    def _save_intermediate_results(self, output_file: str = "batch_graphdata_chunked_results.pkl"):
        """Sauvegarde intermédiaire des résultats"""
        try:
            # Sauvegarder les résultats principaux
            with open(output_file, 'wb') as f:
                pickle.dump(self.results, f)
            
            # Sauvegarder les erreurs si il y en a
            if self.failed_files:
                error_file = output_file.replace('.pkl', '_errors.json')
                with open(error_file, 'w', encoding='utf-8') as f:
                    json.dump(self.failed_files, f, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            print(f"⚠️ Erreur lors de la sauvegarde intermédiaire: {e}")
    
    def _split_text_into_chunks(self, text: str, chunk_id_base: str) -> List[Tuple[str, str]]:
        """Découpe un texte en chunks intelligents avec overlap"""
        if len(text) <= self.max_chunk_size:
            return [(text, f"{chunk_id_base}_single")]
        
        chunks = []
        start = 0
        chunk_num = 1
        
        while start < len(text):
            # Calculer la fin du chunk
            end = min(start + self.max_chunk_size, len(text))
            
            # Si ce n'est pas le dernier chunk, essayer de couper à un endroit logique
            if end < len(text):
                # Chercher un point de coupure naturel (paragraphe, phrase, etc.)
                cut_points = [
                    text.rfind('\n\n', start, end),  # Fin de paragraphe
                    text.rfind('. ', start, end),    # Fin de phrase
                    text.rfind('\n', start, end),    # Fin de ligne
                    text.rfind(' ', start, end)      # Espace
                ]
                
                # Prendre le meilleur point de coupure
                for cut_point in cut_points:
                    if cut_point > start + self.min_chunk_size:
                        end = cut_point + 1
                        break
            
            # Extraire le chunk
            chunk_text = text[start:end]
            
            # Ajouter un peu de contexte du chunk précédent si possible
            if start > 0 and chunk_num > 1:
                context_start = max(0, start - self.chunk_overlap)
                context = text[context_start:start]
                chunk_text = f"[...CONTEXTE PRÉCÉDENT...]\n{context}\n[...SUITE DU DOCUMENT...]\n{chunk_text}"
            
            chunk_id = f"{chunk_id_base}_chunk{chunk_num}"
            chunks.append((chunk_text, chunk_id))
            
            # Passer au chunk suivant avec overlap
            start = end - self.chunk_overlap if end < len(text) else end
            chunk_num += 1
        
        return chunks
    
    def _process_single_chunk(self, chunk_text: str, chunk_id: str, file_name: str, chunk_checkpoint_file: str = None) -> Dict:
        """Traite un chunk unique avec checkpoint optionnel"""
        try:
            # Vérifier si ce chunk a déjà été traité (checkpoint de chunk)
            if chunk_checkpoint_file and os.path.exists(chunk_checkpoint_file):
                with open(chunk_checkpoint_file, 'r', encoding='utf-8') as f:
                    chunk_data = json.load(f)
                    if chunk_data.get('chunk_id') == chunk_id and chunk_data.get('status') == 'completed':
                        print(f"    ♻️  Chunk {chunk_id} déjà traité (checkpoint)")
                        return chunk_data.get('result')
            
            print(f"    📄 Processing chunk: {chunk_id} ({len(chunk_text)} chars)")
            
            # Appeler l'API Mistral
            chat_response = self.client.chat.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.chunk_prompt
                    },
                    { 
                        "role": "user",
                        "content": chunk_text 
                    }
                ],
                response_format=GraphData
            )
            
            # Parser le résultat JSON
            dic = json.loads(chat_response.choices[0].message.content)
            
            # Remapper les UUIDs générés par le LLM vers des UUIDs aléatoires
            dic = self._remap_llm_uuids_to_random(dic)
            
            # Ajouter les métadonnées du chunk
            dic['chunk_id'] = chunk_id
            dic['file_name'] = file_name
            dic['chunk_text_length'] = len(chunk_text)
            dic['processed_at'] = datetime.now().isoformat()
            
            # Sauvegarder le checkpoint du chunk si demandé
            if chunk_checkpoint_file:
                chunk_data = {
                    'chunk_id': chunk_id,
                    'status': 'completed',
                    'result': dic,
                    'processed_at': datetime.now().isoformat()
                }
                with open(chunk_checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump(chunk_data, f, indent=2, ensure_ascii=False)
            
            return dic
            
        except Exception as e:
            print(f"    ❌ Erreur chunk {chunk_id}: {str(e)}")
            
            # Sauvegarder l'erreur du chunk si demandé
            if chunk_checkpoint_file:
                chunk_data = {
                    'chunk_id': chunk_id,
                    'status': 'failed',
                    'error': str(e),
                    'processed_at': datetime.now().isoformat()
                }
                with open(chunk_checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump(chunk_data, f, indent=2, ensure_ascii=False)
            
            return None
    
    def _merge_graph_data_chunks(self, chunk_results: List[Dict], file_name: str, file_path: str, text_hash: str, total_length: int) -> Dict:
        """Fusionne les résultats de plusieurs chunks en un seul GraphData"""
        print(f"    🔄 Fusion de {len(chunk_results)} chunks...")
        
        merged = {
            'entities': [],
            'relations': [],
            'events': [],
            'file_name': file_name,
            'file_path': str(file_path),
            'hash': text_hash,
            'processed_at': datetime.now().isoformat(),
            'text_length': total_length,
            'chunks_processed': len(chunk_results),
            'processing_method': 'chunked'
        }
        
        # Dictionnaires pour déduplication intelligente
        entity_map = {}  # nom -> entité fusionnée
        event_map = {}   # nom -> événement fusionné
        seen_relations = set()
        
        # 1. Fusionner les entités
        for chunk_result in chunk_results:
            for entity in chunk_result.get('entities', []):
                entity_name = entity.get('name', '').strip().lower()
                entity_type = entity.get('type', 'autre')
                
                if entity_name and entity_name not in entity_map:
                    # Nouvelle entité - générer un UUID propre
                    clean_entity = entity.copy()
                    clean_entity['uuid'] = str(uuid.uuid4())
                    
                    entity_map[entity_name] = clean_entity
                    merged['entities'].append(clean_entity)
                else:
                    # Entité existante - fusionner les intentions
                    if entity_name in entity_map:
                        existing_intentions = set(entity_map[entity_name].get('intentions', []))
                        new_intentions = set(entity.get('intentions', []))
                        combined_intentions = list(existing_intentions.union(new_intentions))
                        entity_map[entity_name]['intentions'] = combined_intentions
                        
                        # Fusionner les descriptions si plus détaillée
                        if len(entity.get('description', '')) > len(entity_map[entity_name].get('description', '')):
                            entity_map[entity_name]['description'] = entity.get('description', '')
        
        # 2. Fusionner les événements
        for chunk_result in chunk_results:
            for event in chunk_result.get('events', []):
                event_name = event.get('name', '').strip().lower()
                event_date = event.get('date', '')
                
                # Clé unique basée sur nom + date
                event_key = f"{event_name}_{event_date}"
                
                if event_name and event_key not in event_map:
                    # Nouvel événement
                    clean_event = event.copy()
                    clean_event['uuid'] = str(uuid.uuid4())
                    
                    # Essayer de mapper l'organisateur
                    organizer_uuid = event.get('organizer_uuid', '')
                    if organizer_uuid:
                        # Chercher l'entité correspondante
                        for ent_name, ent_data in entity_map.items():
                            if ent_data['uuid'] == organizer_uuid or ent_name in organizer_uuid:
                                clean_event['organizer_uuid'] = ent_data['uuid']
                                break
                    
                    event_map[event_key] = clean_event
                    merged['events'].append(clean_event)
        
        # 3. Fusionner les relations en mappant les IDs
        for chunk_result in chunk_results:
            for relation in chunk_result.get('relations', []):
                source_uuid = relation.get('source_uuid', '')
                target_uuid = relation.get('target_uuid', '')
                relation_type = relation.get('relation_type', '')
                
                if source_uuid and target_uuid:
                    # Créer une clé unique pour éviter les doublons
                    relation_key = f"{source_uuid}_{target_uuid}_{relation_type}"
                    
                    if relation_key not in seen_relations:
                        clean_relation = relation.copy()
                        # Essayer de mapper les UUIDs vers les nouvelles entités
                        for ent_name, ent_data in entity_map.items():
                            if ent_data['uuid'] == source_uuid or ent_name in source_uuid:
                                clean_relation['source_uuid'] = ent_data['uuid']
                            if ent_data['uuid'] == target_uuid or ent_name in target_uuid:
                                clean_relation['target_uuid'] = ent_data['uuid']
                        
                        merged['relations'].append(clean_relation)
                        seen_relations.add(relation_key)
        
        print(f"    ✅ Fusion terminée: {len(merged['entities'])} entités, {len(merged['events'])} événements, {len(merged['relations'])} relations")
        
        return merged
    
    def process_single_file(self, file_path: str) -> Dict:
        """Traite un fichier unique, avec chunking si nécessaire et checkpoints"""
        try:
            file_path_str = str(file_path)
            
            # Vérifier si le fichier a déjà été traité
            if file_path_str in self.processed_files:
                print(f"♻️  Fichier déjà traité: {Path(file_path).name}")
                return None
            
            # Lire le fichier
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            
            file_name = Path(file_path).name
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            text_length = len(text)
            
            print(f"📄 Traitement: {file_name} ({text_length:,} caractères)")
            
            # Décider si chunking nécessaire
            if text_length <= self.max_chunk_size:
                print(f"    📝 Fichier petit, traitement direct")
                result = self._process_small_file(file_path, text, file_name, text_hash)
            else:
                print(f"    📚 Fichier volumineux, traitement par chunks")
                result = self._process_large_file(file_path, text, file_name, text_hash)
            
            if result:
                # Marquer le fichier comme traité
                self.processed_files.add(file_path_str)
                self.results.append(result)
                
            return result
                
        except Exception as e:
            error_info = {
                'file_name': Path(file_path).name,
                'file_path': str(file_path),
                'error': str(e),
                'processed_at': datetime.now().isoformat()
            }
            self.failed_files.append(error_info)
            print(f"  ❌ Erreur: {str(e)}")
            return None
    
    def _process_small_file(self, file_path: str, text: str, file_name: str, text_hash: str) -> Dict:
        """Traite un petit fichier normalement"""
        try:
            chat_response = self.client.chat.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt  # Utiliser le prompt normal
                    },
                    { 
                        "role": "user",
                        "content": text 
                    }
                ],
                response_format=GraphData
            )
            
            dic = json.loads(chat_response.choices[0].message.content)
            
            # Remapper les UUIDs générés par le LLM vers des UUIDs aléatoires
            dic = self._remap_llm_uuids_to_random(dic)
            
            # Ajouter les métadonnées
            dic['file_name'] = file_name
            dic['file_path'] = str(file_path)
            dic['hash'] = text_hash
            dic['processed_at'] = datetime.now().isoformat()
            dic['text_length'] = len(text)
            dic['processing_method'] = 'direct'
            
            entities_count = len(dic.get('entities', []))
            relations_count = len(dic.get('relations', []))
            events_count = len(dic.get('events', []))
            
            print(f"    ✅ Succès: {entities_count} entités, {relations_count} relations, {events_count} événements")
            
            return dic
            
        except Exception as e:
            print(f"    ❌ Erreur traitement direct: {str(e)}")
            return None
    
    def _process_large_file(self, file_path: str, text: str, file_name: str, text_hash: str) -> Dict:
        """Traite un gros fichier par chunks avec checkpoints de chunks"""
        try:
            # Découper en chunks
            chunks = self._split_text_into_chunks(text, file_name.replace('.', '_'))
            print(f"    📚 Divisé en {len(chunks)} chunks")
            
            # Créer un dossier pour les checkpoints de chunks
            chunks_dir = Path(f"chunks_checkpoints_{file_name.replace('.', '_')}")
            chunks_dir.mkdir(exist_ok=True)
            
            # Traiter chaque chunk avec checkpoint
            chunk_results = []
            for i, (chunk_text, chunk_id) in enumerate(chunks):
                chunk_checkpoint_file = chunks_dir / f"{chunk_id}.json"
                result = self._process_single_chunk(chunk_text, chunk_id, file_name, str(chunk_checkpoint_file))
                if result:
                    chunk_results.append(result)
                
                # Pause courte pour éviter la surcharge API
                time.sleep(0.5)
            
            if not chunk_results:
                print(f"    ❌ Aucun chunk traité avec succès")
                return None
            
            # Fusionner les résultats
            merged_result = self._merge_graph_data_chunks(
                chunk_results, file_name, file_path, text_hash, len(text)
            )
            
            entities_count = len(merged_result.get('entities', []))
            relations_count = len(merged_result.get('relations', []))
            events_count = len(merged_result.get('events', []))
            
            print(f"    ✅ Succès chunked: {entities_count} entités, {relations_count} relations, {events_count} événements")
            
            # Nettoyer les checkpoints de chunks après succès
            try:
                import shutil
                shutil.rmtree(chunks_dir)
            except:
                pass
            
            return merged_result
            
        except Exception as e:
            print(f"    ❌ Erreur traitement chunked: {str(e)}")
            return None
    
    def process_directory_resumable(self, directory_path: str, output_file: str = "batch_graphdata_chunked_results.pkl") -> List[Dict]:
        """Traite tous les fichiers d'un répertoire avec reprise automatique"""
        directory = Path(directory_path)
        
        if not directory.exists():
            raise FileNotFoundError(f"Le répertoire {directory_path} n'existe pas")
        
        # Lister tous les fichiers (pas les dossiers)
        all_files = [f for f in directory.iterdir() if f.is_file()]
        
        # Filtrer les fichiers non encore traités
        remaining_files = [f for f in all_files if str(f) not in self.processed_files]
        
        print(f"🚀 Traitement resumable de {len(all_files)} fichiers dans {directory_path}")
        print(f"✅ {len(self.processed_files)} fichiers déjà traités")
        print(f"🔄 {len(remaining_files)} fichiers restants à traiter")
        print(f"📏 Chunking automatique pour fichiers > {self.max_chunk_size:,} caractères")
        print("=" * 60)
        
        # Traiter chaque fichier restant avec barre de progression
        try:
            for i, file_path in enumerate(tqdm(remaining_files, desc="Traitement des fichiers")):
                self.current_file_index = len(self.processed_files) + i
                
                result = self.process_single_file(file_path)
                
                # Sauvegarder checkpoint tous les N fichiers
                if (i + 1) % self.backup_interval == 0:
                    print(f"\n💾 Sauvegarde checkpoint automatique ({i + 1}/{len(remaining_files)} fichiers)")
                    self._save_checkpoint(all_files, output_file)
                    print(f"📊 Progression: {((len(self.processed_files))/len(all_files)*100):.1f}%")
        
        except KeyboardInterrupt:
            print(f"\n⚠️ Interruption détectée (Ctrl+C)")
            print("💾 Sauvegarde du checkpoint d'urgence...")
            self._save_checkpoint(all_files, output_file)
            print("✅ Checkpoint sauvegardé. Vous pouvez reprendre avec la même commande.")
            raise
        
        except Exception as e:
            print(f"\n❌ Erreur inattendue: {e}")
            print("💾 Sauvegarde du checkpoint d'urgence...")
            self._save_checkpoint(all_files, output_file)
            raise
        
        # Sauvegarde finale
        self._save_checkpoint(all_files, output_file)
        
        print("=" * 60)
        print(f"✅ Traitement terminé:")
        print(f"   📊 {len(self.results)} fichiers traités avec succès")
        print(f"   ❌ {len(self.failed_files)} fichiers en erreur")
        
        # Statistiques sur le chunking
        chunked_files = [r for r in self.results if r.get('processing_method') == 'chunked']
        direct_files = [r for r in self.results if r.get('processing_method') == 'direct']
        
        print(f"   📚 {len(chunked_files)} fichiers traités par chunks")
        print(f"   📝 {len(direct_files)} fichiers traités directement")
        
        if chunked_files:
            total_chunks = sum(r.get('chunks_processed', 0) for r in chunked_files)
            print(f"   🔄 {total_chunks} chunks traités au total")
        
        # Nettoyer le checkpoint à la fin
        self._cleanup_checkpoint()
        
        return self.results
    
    def process_directory(self, directory_path: str) -> List[Dict]:
        """
        Méthode de compatibilité - redirige vers process_directory_resumable
        Maintient la compatibilité avec les scripts existants
        """
        return self.process_directory_resumable(directory_path)
    
    def _cleanup_checkpoint(self):
        """Nettoie les fichiers de checkpoint après completion"""
        try:
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
                print("🗑️ Checkpoint nettoyé après completion")
        except Exception as e:
            print(f"⚠️ Erreur lors du nettoyage du checkpoint: {e}")
    
    def _remap_llm_uuids_to_random(self, llm_output: Dict) -> Dict:
        """
        Remplace tous les UUIDs générés par le LLM par des UUIDs aléatoires
        tout en préservant les associations entre entités, événements et relations
        """
        # Dictionnaire de mapping: ancien_uuid_llm -> nouveau_uuid_aléatoire
        uuid_mapping = {}
        
        def get_new_random_uuid(old_uuid: str) -> str:
            """Génère ou récupère un nouveau UUID aléatoire pour un UUID LLM"""
            if not old_uuid or old_uuid.strip() == "":
                return ""
            
            if old_uuid not in uuid_mapping:
                uuid_mapping[old_uuid] = str(uuid.uuid4())
            
            return uuid_mapping[old_uuid]
        
        # Remapper les UUIDs des entités
        for entity in llm_output.get('entities', []):
            if 'uuid' in entity:
                old_uuid = entity['uuid']
                entity['uuid'] = get_new_random_uuid(old_uuid)
            # Compatibilité avec ancien format
            if 'id' in entity:
                old_id = entity['id']
                entity['id'] = get_new_random_uuid(old_id)
                if 'uuid' not in entity:
                    entity['uuid'] = entity['id']
        
        # Remapper les UUIDs des événements
        for event in llm_output.get('events', []):
            if 'uuid' in event:
                old_uuid = event['uuid']
                event['uuid'] = get_new_random_uuid(old_uuid)
            if 'id' in event:
                old_id = event['id']
                event['id'] = get_new_random_uuid(old_id)
                if 'uuid' not in event:
                    event['uuid'] = event['id']
            
            # Remapper organizer_uuid
            if 'organizer_uuid' in event and event['organizer_uuid']:
                event['organizer_uuid'] = get_new_random_uuid(event['organizer_uuid'])
            if 'organizer_id' in event and event['organizer_id']:
                event['organizer_id'] = get_new_random_uuid(event['organizer_id'])
                if 'organizer_uuid' not in event:
                    event['organizer_uuid'] = event['organizer_id']
        
        # Remapper les UUIDs des relations
        for relation in llm_output.get('relations', []):
            if 'source_uuid' in relation and relation['source_uuid']:
                relation['source_uuid'] = get_new_random_uuid(relation['source_uuid'])
            if 'source_id' in relation and relation['source_id']:
                relation['source_id'] = get_new_random_uuid(relation['source_id'])
                if 'source_uuid' not in relation:
                    relation['source_uuid'] = relation['source_id']
            
            if 'target_uuid' in relation and relation['target_uuid']:
                relation['target_uuid'] = get_new_random_uuid(relation['target_uuid'])
            if 'target_id' in relation and relation['target_id']:
                relation['target_id'] = get_new_random_uuid(relation['target_id'])
                if 'target_uuid' not in relation:
                    relation['target_uuid'] = relation['target_id']
            
            if 'event_uuid' in relation and relation['event_uuid']:
                relation['event_uuid'] = get_new_random_uuid(relation['event_uuid'])
            if 'event_id' in relation and relation['event_id']:
                relation['event_id'] = get_new_random_uuid(relation['event_id'])
                if 'event_uuid' not in relation:
                    relation['event_uuid'] = relation['event_id']
        
        return llm_output

    def _deduplicate_entities_by_name_similarity(self, results_data: List[Dict]) -> List[Dict]:
        """
        Détecte et fusionne les entités avec des noms identiques ou très similaires
        Regénère un UUID unique pour les entités fusionnées et met à jour toutes les références
        """
        print("🔍 Démarrage de la déduplication des entités par similarité de nom...")
        
        # Collecter toutes les entités avec leurs origines
        all_entities_with_context = []
        for result_idx, result in enumerate(results_data):
            for entity_idx, entity in enumerate(result.get('entities', [])):
                all_entities_with_context.append({
                    'entity': entity,
                    'result_idx': result_idx,
                    'entity_idx': entity_idx,
                    'original_uuid': entity.get('uuid', entity.get('id', ''))
                })
        
        print(f"  📊 Analyse de {len(all_entities_with_context)} entités...")
        
        # Fonction pour normaliser les noms
        def normalize_name(name):
            if not name:
                return ""
            # Supprimer les accents, espaces multiples, ponctuation excessive
            import unicodedata
            name = unicodedata.normalize('NFD', name.lower())
            name = ''.join(c for c in name if not unicodedata.combining(c))
            name = re.sub(r'[^\w\s-]', ' ', name)
            name = re.sub(r'\s+', ' ', name).strip()
            return name
        
        # Fonction pour calculer la similarité entre deux noms
        def calculate_similarity(name1, name2):
            if not name1 or not name2:
                return 0.0
            norm1 = normalize_name(name1)
            norm2 = normalize_name(name2)
            
            if norm1 == norm2:
                return 1.0
            
            # Utiliser SequenceMatcher pour calculer la similarité
            similarity = SequenceMatcher(None, norm1, norm2).ratio()
            
            # Bonus pour les mots clés communs
            words1 = set(norm1.split())
            words2 = set(norm2.split())
            if words1 and words2:
                word_overlap = len(words1.intersection(words2)) / len(words1.union(words2))
                similarity = max(similarity, word_overlap * 0.9)  # Bonus modéré pour les mots communs
            
            return similarity
        
        # Trouver les groupes d'entités similaires
        similarity_threshold = 0.85  # Seuil de similarité (ajustable)
        entity_groups = []
        processed_indices = set()
        
        for i, entity_ctx in enumerate(all_entities_with_context):
            if i in processed_indices:
                continue
                
            current_group = [entity_ctx]
            processed_indices.add(i)
            entity_name = entity_ctx['entity'].get('name', '')
            
            # Chercher les entités similaires
            for j, other_ctx in enumerate(all_entities_with_context[i+1:], i+1):
                if j in processed_indices:
                    continue
                    
                other_name = other_ctx['entity'].get('name', '')
                similarity = calculate_similarity(entity_name, other_name)
                
                if similarity >= similarity_threshold:
                    current_group.append(other_ctx)
                    processed_indices.add(j)
            
            entity_groups.append(current_group)
        
        # Statistiques de déduplication
        duplicates_found = sum(1 for group in entity_groups if len(group) > 1)
        total_duplicates = sum(len(group) - 1 for group in entity_groups if len(group) > 1)
        
        print(f"  🔍 Détection terminée:")
        print(f"    • Groupes de doublons trouvés: {duplicates_found}")
        print(f"    • Total entités dupliquées: {total_duplicates}")
        
        # Mapping des anciens UUIDs vers les nouveaux
        uuid_mapping = {}
        merged_entities_info = []
        
        # Traiter chaque groupe
        for group in entity_groups:
            if len(group) > 1:
                # Fusionner le groupe
                master_entity = group[0]['entity'].copy()  # Prendre la première entité comme master
                master_name = master_entity.get('name', 'unknown')
                
                # Générer un nouvel UUID unique pour le groupe fusionné
                new_uuid = str(uuid.uuid4())
                master_entity['uuid'] = new_uuid
                if 'id' in master_entity:
                    master_entity['id'] = new_uuid
                
                # Collecter les informations de toutes les entités du groupe
                all_descriptions = []
                all_intentions = set()
                source_files = set()
                old_uuids = []
                
                for entity_ctx in group:
                    entity = entity_ctx['entity']
                    old_uuid = entity_ctx['original_uuid']
                    old_uuids.append(old_uuid)
                    
                    # Mapper l'ancien UUID vers le nouveau
                    uuid_mapping[old_uuid] = new_uuid
                    
                    # Collecter les informations
                    if entity.get('description'):
                        all_descriptions.append(entity['description'])
                    if entity.get('intentions'):
                        all_intentions.update(entity['intentions'])
                    if entity.get('source_file'):
                        source_files.add(entity['source_file'])
                
                # Fusionner les informations dans l'entité master
                if all_descriptions:
                    # Prendre la description la plus longue
                    master_entity['description'] = max(all_descriptions, key=len)
                
                if all_intentions:
                    master_entity['intentions'] = list(all_intentions)
                
                # Ajouter info de fusion
                master_entity['merged_from'] = old_uuids
                master_entity['source_files_merged'] = list(source_files)
                
                # Mettre à jour l'entité dans le premier résultat du groupe
                first_ctx = group[0]
                results_data[first_ctx['result_idx']]['entities'][first_ctx['entity_idx']] = master_entity
                
                # Marquer les autres entités du groupe pour suppression
                entities_to_remove = []
                for entity_ctx in group[1:]:
                    entities_to_remove.append((entity_ctx['result_idx'], entity_ctx['entity_idx']))
                
                merged_entities_info.append({
                    'master_name': master_name,
                    'new_uuid': new_uuid,
                    'old_uuids': old_uuids,
                    'merged_count': len(group),
                    'entities_to_remove': entities_to_remove
                })
                
                print(f"    🔀 Fusionné: '{master_name}' ({len(group)} entités) -> UUID: {new_uuid[:8]}...")
        
        # Supprimer les entités dupliquées (en ordre inverse pour éviter les problèmes d'index)
        for merge_info in merged_entities_info:
            entities_to_remove = sorted(merge_info['entities_to_remove'], reverse=True)
            for result_idx, entity_idx in entities_to_remove:
                del results_data[result_idx]['entities'][entity_idx]
        
        print(f"  🗑️ Supprimé {total_duplicates} entités dupliquées")
        
        # Mettre à jour toutes les références aux anciens UUIDs dans les relations et événements
        if uuid_mapping:
            print("  🔄 Mise à jour des références UUID dans les relations et événements...")
            self._update_uuid_references_in_results(results_data, uuid_mapping)
        
        print(f"✅ Déduplication terminée: {duplicates_found} groupes fusionnés, {len(uuid_mapping)} UUIDs remappés")
        return results_data

    def _update_uuid_references_in_results(self, results_data: List[Dict], uuid_mapping: Dict[str, str]):
        """Met à jour toutes les références UUID dans les relations et événements"""
        updates_count = 0
        
        for result in results_data:
            # Mettre à jour les relations
            for relation in result.get('relations', []):
                if 'source_uuid' in relation and relation['source_uuid'] in uuid_mapping:
                    relation['source_uuid'] = uuid_mapping[relation['source_uuid']]
                    updates_count += 1
                if 'target_uuid' in relation and relation['target_uuid'] in uuid_mapping:
                    relation['target_uuid'] = uuid_mapping[relation['target_uuid']]
                    updates_count += 1
                if 'event_uuid' in relation and relation['event_uuid'] in uuid_mapping:
                    relation['event_uuid'] = uuid_mapping[relation['event_uuid']]
                    updates_count += 1
                
                # Compatibilité avec les anciens champs
                if 'source_id' in relation and relation['source_id'] in uuid_mapping:
                    relation['source_id'] = uuid_mapping[relation['source_id']]
                    updates_count += 1
                if 'target_id' in relation and relation['target_id'] in uuid_mapping:
                    relation['target_id'] = uuid_mapping[relation['target_id']]
                    updates_count += 1
                if 'event_id' in relation and relation['event_id'] in uuid_mapping:
                    relation['event_id'] = uuid_mapping[relation['event_id']]
                    updates_count += 1
            
            # Mettre à jour les événements (organizer_uuid)
            for event in result.get('events', []):
                if 'organizer_uuid' in event and event['organizer_uuid'] in uuid_mapping:
                    event['organizer_uuid'] = uuid_mapping[event['organizer_uuid']]
                    updates_count += 1
                if 'organizer_id' in event and event['organizer_id'] in uuid_mapping:
                    event['organizer_id'] = uuid_mapping[event['organizer_id']]
                    updates_count += 1
        
        print(f"    📝 {updates_count} références UUID mises à jour")

    def save_results(self, output_file: str = "batch_graphdata_chunked_results.pkl"):
        """Sauvegarde finale de tous les résultats"""
        # Sauvegarder les résultats principaux
        with open(output_file, 'wb') as f:
            pickle.dump(self.results, f)
        print(f"💾 Résultats finaux sauvegardés: {output_file}")
        
        # Sauvegarder aussi en JSON pour lisibilité
        json_output = output_file.replace('.pkl', '.json')
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"💾 Résultats JSON sauvegardés: {json_output}")
        
        # Sauvegarder les erreurs si il y en a
        if self.failed_files:
            error_file = output_file.replace('.pkl', '_errors.json')
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_files, f, indent=2, ensure_ascii=False)
            print(f"💾 Erreurs sauvegardées: {error_file}")
    
    def remap_all_uuids_consistently(self, results_data: List[Dict]) -> List[Dict]:
        """
        Remplace tous les UUIDs par des nouveaux UUIDs générés aléatoirement
        tout en préservant toutes les associations entre entités, événements et relations
        """
        print("🔄 Remapping de tous les UUIDs de façon cohérente...")
        
        # Dictionnaire de mapping: ancien_uuid -> nouveau_uuid
        uuid_mapping = {}
        
        def get_or_create_new_uuid(old_uuid: str) -> str:
            """Génère ou récupère le nouveau UUID pour un ancien UUID"""
            if not old_uuid or old_uuid.strip() == "":
                return ""
            
            if old_uuid not in uuid_mapping:
                uuid_mapping[old_uuid] = str(uuid.uuid4())
            
            return uuid_mapping[old_uuid]
        
        remapped_results = []
        
        for result in results_data:
            remapped_result = result.copy()
            
            # 1. Remapper les UUIDs des entités
            if 'entities' in remapped_result:
                for entity in remapped_result['entities']:
                    if 'uuid' in entity:
                        old_uuid = entity['uuid']
                        entity['uuid'] = get_or_create_new_uuid(old_uuid)
                    # Garder aussi la compatibilité avec 'id' si présent
                    if 'id' in entity:
                        old_id = entity['id']
                        entity['id'] = get_or_create_new_uuid(old_id)
                        # Si pas d'uuid mais id présent, créer l'uuid
                        if 'uuid' not in entity:
                            entity['uuid'] = entity['id']
            
            # 2. Remapper les UUIDs des événements et leurs références
            if 'events' in remapped_result:
                for event in remapped_result['events']:
                    # UUID de l'événement
                    if 'uuid' in event:
                        old_uuid = event['uuid']
                        event['uuid'] = get_or_create_new_uuid(old_uuid)
                    if 'id' in event:
                        old_id = event['id']
                        event['id'] = get_or_create_new_uuid(old_id)
                        if 'uuid' not in event:
                            event['uuid'] = event['id']
                    
                    # UUID de l'organisateur
                    if 'organizer_uuid' in event and event['organizer_uuid']:
                        event['organizer_uuid'] = get_or_create_new_uuid(event['organizer_uuid'])
                    if 'organizer_id' in event and event['organizer_id']:
                        event['organizer_id'] = get_or_create_new_uuid(event['organizer_id'])
                        if 'organizer_uuid' not in event:
                            event['organizer_uuid'] = event['organizer_id']
            
            # 3. Remapper les UUIDs des relations
            if 'relations' in remapped_result:
                for relation in remapped_result['relations']:
                    # UUID source
                    if 'source_uuid' in relation and relation['source_uuid']:
                        relation['source_uuid'] = get_or_create_new_uuid(relation['source_uuid'])
                    if 'source_id' in relation and relation['source_id']:
                        relation['source_id'] = get_or_create_new_uuid(relation['source_id'])
                        if 'source_uuid' not in relation:
                            relation['source_uuid'] = relation['source_id']
                    
                    # UUID target
                    if 'target_uuid' in relation and relation['target_uuid']:
                        relation['target_uuid'] = get_or_create_new_uuid(relation['target_uuid'])
                    if 'target_id' in relation and relation['target_id']:
                        relation['target_id'] = get_or_create_new_uuid(relation['target_id'])
                        if 'target_uuid' not in relation:
                            relation['target_uuid'] = relation['target_id']
                    
                    # UUID événement
                    if 'event_uuid' in relation and relation['event_uuid']:
                        relation['event_uuid'] = get_or_create_new_uuid(relation['event_uuid'])
                    if 'event_id' in relation and relation['event_id']:
                        relation['event_id'] = get_or_create_new_uuid(relation['event_id'])
                        if 'event_uuid' not in relation:
                            relation['event_uuid'] = relation['event_id']
            
            remapped_results.append(remapped_result)
        
        total_mappings = len(uuid_mapping)
        print(f"✅ Remapping terminé: {total_mappings} UUIDs remappés de façon cohérente")
        
        # Afficher quelques exemples de mapping pour vérification
        if total_mappings > 0:
            print("📋 Exemples de mappings (ancien -> nouveau):")
            sample_items = list(uuid_mapping.items())[:3]
            for old_uuid, new_uuid in sample_items:
                print(f"   {old_uuid[:8]}... -> {new_uuid[:8]}...")
        
        return remapped_results
    
    def save_results_with_uuid_remapping(self, output_file: str = "batch_graphdata_chunked_results.pkl"):
        """Sauvegarde les résultats avec déduplication automatique des entités par similarité"""
        print("💾 Sauvegarde des résultats avec UUIDs aléatoires et déduplication...")
        
        # Les UUIDs sont déjà aléatoires grâce au remapping dans _remap_llm_uuids_to_random()
        # Maintenant on applique la déduplication par similarité de noms
        
        print("🔄 Application de la déduplication par similarité des noms d'entités...")
        deduplicated_results = self._deduplicate_entities_by_name_similarity(self.results.copy())
        
        # Sauvegarder les résultats dédupliqués
        with open(output_file, 'wb') as f:
            pickle.dump(deduplicated_results, f)
        print(f"💾 Résultats dédupliqués sauvegardés: {output_file}")
        
        # Sauvegarder aussi en JSON pour lisibilité
        json_output = output_file.replace('.pkl', '.json')
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(deduplicated_results, f, indent=2, ensure_ascii=False)
        print(f"💾 Résultats JSON dédupliqués sauvegardés: {json_output}")
        
        # Sauvegarder les erreurs si il y en a
        if self.failed_files:
            error_file = output_file.replace('.pkl', '_errors.json')
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(self.failed_files, f, indent=2, ensure_ascii=False)
            print(f"💾 Erreurs sauvegardées: {error_file}")
        
        # Mettre à jour self.results avec la version dédupliquée
        self.results = deduplicated_results
        
        return self.results

    def get_summary_stats(self) -> Dict:
        """Génère des statistiques de résumé"""
        if not self.results:
            return {}
        
        stats = {
            'total_files_processed': len(self.results),
            'total_files_failed': len(self.failed_files),
            'total_entities': sum(len(r.get('entities', [])) for r in self.results),
            'total_relations': sum(len(r.get('relations', [])) for r in self.results),
            'total_events': sum(len(r.get('events', [])) for r in self.results),
            'chunked_files': len([r for r in self.results if r.get('processing_method') == 'chunked']),
            'direct_files': len([r for r in self.results if r.get('processing_method') == 'direct']),
            'total_chunks_processed': sum(r.get('chunks_processed', 0) for r in self.results)
        }
        
        # Statistiques par type d'entité
        entity_types = {}
        for result in self.results:
            for entity in result.get('entities', []):
                entity_type = entity.get('type', 'autre')
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        stats['entity_types'] = entity_types
        
        # Statistiques des styles musicaux
        music_styles = {}
        for result in self.results:
            for event in result.get('events', []):
                style = event.get('concert_style', '')
                if style:
                    music_styles[style] = music_styles.get(style, 0) + 1
        
        stats['music_styles'] = music_styles
        
        return stats
    
    def print_summary(self):
        """Affiche un résumé des résultats"""
        stats = self.get_summary_stats()
        
        print("\n" + "="*60)
        print("📊 RÉSUMÉ DU TRAITEMENT BATCH RESUMABLE")
        print("="*60)
        print(f"📄 Fichiers traités avec succès: {stats.get('total_files_processed', 0)}")
        print(f"❌ Fichiers en erreur: {stats.get('total_files_failed', 0)}")
        print(f"📚 Fichiers traités par chunks: {stats.get('chunked_files', 0)}")
        print(f"📝 Fichiers traités directement: {stats.get('direct_files', 0)}")
        print(f"🔄 Total chunks traités: {stats.get('total_chunks_processed', 0)}")
        print(f"🏢 Total entités extraites: {stats.get('total_entities', 0)}")
        print(f"🔗 Total relations extraites: {stats.get('total_relations', 0)}")
        print(f"🎪 Total événements extraits: {stats.get('total_events', 0)}")
        
        if stats.get('entity_types'):
            print(f"\n📋 Répartition des types d'entités:")
            for entity_type, count in sorted(stats['entity_types'].items(), key=lambda x: x[1], reverse=True):
                print(f"   • {entity_type.title()}: {count}")
        
        if stats.get('music_styles'):
            print(f"\n🎵 Top 10 des styles musicaux:")
            sorted_styles = sorted(stats['music_styles'].items(), key=lambda x: x[1], reverse=True)[:10]
            for style, count in sorted_styles:
                print(f"   • {style}: {count} événement(s)")
    
    def show_progress_info(self):
        """Affiche les informations de progression"""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            print("📊 INFORMATION DE PROGRESSION")
            print("=" * 40)
            print(f"📄 Fichiers traités: {len(self.processed_files)}")
            print(f"📂 Total fichiers: {checkpoint_data.get('total_files', '?')}")
            print(f"📈 Progression: {checkpoint_data.get('progress_percentage', 0):.1f}%")
            print(f"🕒 Dernière sauvegarde: {checkpoint_data.get('timestamp', 'Inconnue')}")
            print(f"💾 Fichier résultats: {checkpoint_data.get('results_file', 'N/A')}")

def remap_existing_results_file(input_file: str, output_file: str = None):
    """
    Fonction utilitaire pour remapper les UUIDs d'un fichier de résultats existant
    (utilise la fonction complète de remapping pour les anciens fichiers)
    """
    if output_file is None:
        output_file = input_file.replace('.pkl', '_remapped.pkl').replace('.json', '_remapped.json')
    
    print(f"🔄 Remapping des UUIDs du fichier existant: {input_file}")
    
    # Charger les données existantes
    if input_file.endswith('.pkl'):
        with open(input_file, 'rb') as f:
            existing_results = pickle.load(f)
    elif input_file.endswith('.json'):
        with open(input_file, 'r', encoding='utf-8') as f:
            existing_results = json.load(f)
    else:
        raise ValueError("Le fichier doit être un .pkl ou .json")
    
    # Créer un processeur temporaire pour utiliser la fonction de remapping complète
    processor = ChunkedBatchGraphDataProcessor()
    processor.results = existing_results
    
    # Utiliser la fonction complète de remapping pour les anciens fichiers
    remapped_results = processor.remap_all_uuids_consistently(existing_results)
    
    # Sauvegarder
    with open(output_file, 'wb' if output_file.endswith('.pkl') else 'w', encoding='utf-8' if output_file.endswith('.json') else None) as f:
        if output_file.endswith('.pkl'):
            pickle.dump(remapped_results, f)
        else:
            json.dump(remapped_results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Remapping terminé. Nouveau fichier: {output_file}")
    return remapped_results

def deduplicate_entities_in_existing_file(input_file: str, output_file: str = None, similarity_threshold: float = 0.85):
    """
    Fonction utilitaire pour dédupler les entités d'un fichier existant par similarité de noms
    """
    if output_file is None:
        output_file = input_file.replace('.pkl', '_deduplicated.pkl').replace('.json', '_deduplicated.json')
    
    print(f"🔍 Déduplication des entités du fichier: {input_file}")
    print(f"📊 Seuil de similarité: {similarity_threshold}")
    
    # Charger les données existantes
    if input_file.endswith('.pkl'):
        with open(input_file, 'rb') as f:
            existing_results = pickle.load(f)
    elif input_file.endswith('.json'):
        with open(input_file, 'r', encoding='utf-8') as f:
            existing_results = json.load(f)
    else:
        raise ValueError("Le fichier doit être un .pkl ou .json")
    
    # Créer un processeur temporaire pour utiliser la fonction de déduplication
    processor = ChunkedBatchGraphDataProcessor()
    processor.results = existing_results
    
    # Modifier temporairement le seuil si nécessaire
    original_threshold = None
    if hasattr(processor, '_deduplicate_entities_by_name_similarity'):
        # On va passer le seuil via une modification temporaire de la fonction
        pass
    
    # Appliquer la déduplication
    deduplicated_results = processor._deduplicate_entities_by_name_similarity(existing_results.copy())
    
    # Sauvegarder
    with open(output_file, 'wb' if output_file.endswith('.pkl') else 'w', encoding='utf-8' if output_file.endswith('.json') else None) as f:
        if output_file.endswith('.pkl'):
            pickle.dump(deduplicated_results, f)
        else:
            json.dump(deduplicated_results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Déduplication terminée. Fichier sauvegardé: {output_file}")
    
    # Statistiques finales
    original_entities = sum(len(result.get('entities', [])) for result in existing_results)
    final_entities = sum(len(result.get('entities', [])) for result in deduplicated_results)
    entities_removed = original_entities - final_entities
    
    print(f"📈 Résultat: {original_entities} → {final_entities} entités ({entities_removed} supprimées)")
    
    return deduplicated_results

def run_chunked_batch_processing():
    """Fonction principale pour lancer le traitement batch avec reprise automatique"""
    print("🎵 TRAITEMENT BATCH CHUNKED RESUMABLE - EXTRACTION GRAPHDATA")
    print("="*60)
    print("🔄 Ce processus peut être interrompu (Ctrl+C) et repris automatiquement")
    print("💾 Les progrès sont sauvegardés régulièrement")
    print("=" * 60)
    
    # Initialiser le processeur
    processor = ChunkedBatchGraphDataProcessor()
    
    # Afficher les informations de progression si existantes
    processor.show_progress_info()
    
    # Traiter tous les fichiers du répertoire textes  
    directory_path = "../../../../data/data_supply/textes"
    results = processor.process_directory_resumable(directory_path)
    
    # Sauvegarder les résultats finaux avec remapping des UUIDs
    processor.save_results_with_uuid_remapping("batch_graphdata_chunked_results.pkl")
    
    # Afficher le résumé
    processor.print_summary()
    
    return processor

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "remap":
            # Mode remapping d'un fichier existant
            if len(sys.argv) < 3:
                print("❌ Usage pour remapping: python run_batch_processor_chunked.py remap <fichier_input> [fichier_output]")
                print("📝 Exemple: python run_batch_processor_chunked.py remap batch_graphdata_chunked_results.pkl")
                sys.exit(1)
            
            input_file = sys.argv[2]
            output_file = sys.argv[3] if len(sys.argv) > 3 else None
            
            print("🔄 MODE REMAPPING UUID")
            print("="*50)
            remap_existing_results_file(input_file, output_file)
            
        elif command == "deduplicate":
            # Mode déduplication d'un fichier existant
            if len(sys.argv) < 3:
                print("❌ Usage pour déduplication: python run_batch_processor_chunked.py deduplicate <fichier_input> [fichier_output] [seuil]")
                print("📝 Exemple: python run_batch_processor_chunked.py deduplicate batch_graphdata_chunked_results.pkl")
                print("📝 Avec seuil: python run_batch_processor_chunked.py deduplicate batch_graphdata_chunked_results.pkl results_clean.pkl 0.9")
                sys.exit(1)
            
            input_file = sys.argv[2]
            output_file = sys.argv[3] if len(sys.argv) > 3 else None
            similarity_threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.85
            
            print("🔍 MODE DÉDUPLICATION DES ENTITÉS")
            print("="*50)
            deduplicate_entities_in_existing_file(input_file, output_file, similarity_threshold)
            
        else:
            print(f"❌ Commande inconnue: {command}")
            print("📝 Commandes disponibles:")
            print("   python run_batch_processor_chunked.py                    # Traitement normal")
            print("   python run_batch_processor_chunked.py remap <fichier>    # Remapping UUID")
            print("   python run_batch_processor_chunked.py deduplicate <fichier> # Déduplication entités")
            sys.exit(1)
        
    else:
        # Mode traitement normal
        processor = run_chunked_batch_processing()
        
        print("\n🎯 Traitement resumable terminé!")
        print("📂 Prochaine étape: Utiliser neo4j_inserter.py pour insérer les données dans Neo4j")
        print("\n💡 Pour reprendre un traitement interrompu, relancez simplement ce script.")
        print("🔧 Outils disponibles:")
        print("   python run_batch_processor_chunked.py remap <fichier.pkl>")
        print("   python run_batch_processor_chunked.py deduplicate <fichier.pkl> [seuil_0.85]")