from typing import List, Optional, Literal, Dict, Tuple, Set
from pydantic import BaseModel, Field, validator
from datetime import date, datetime
import numpy as np
import uuid
import logging
from collections import defaultdict
import json

def generate_uuid() -> str:
    """Génère un UUID aléatoire sous forme de string"""
    return str(uuid.uuid4())

class Entity(BaseModel):
    uuid: str = Field(default="")  # L'UUID sera assigné par le déduplicateur
    type: Literal["association", "entreprise", "institution", "personne", "autre"]
    name: str
    description: Optional[str] = ""
    intentions: List[str]                 # OBLIGATOIRE: objectifs/intentions de l'entité
    
    @validator('name')
    def validate_name(cls, v):
        """Valide que le nom n'est pas 'Unknown' ou vide"""
        if not v or v.strip().lower() == 'unknown':
            raise ValueError("Entity name cannot be 'Unknown' or empty")
        return v.strip()
    
    @validator('intentions')
    def validate_intentions(cls, v):
        """Valide que les intentions ne sont pas vides"""
        if not v or len(v) == 0:
            raise ValueError("Entity must have at least one intention")
        return [intention.strip() for intention in v if intention.strip()]
    
    def assign_unique_uuid(self, deduplicator=None):
        """Assigne un UUID unique via le système de déduplication"""
        if deduplicator:
            self.uuid = deduplicator.get_or_create_entity_uuid(self.dict())
        else:
            self.uuid = str(uuid.uuid4())
    
    def get_normalized_name(self) -> str:
        """Retourne le nom normalisé pour la déduplication"""
        return self.name.lower().strip()


class Event(BaseModel):
    uuid: str = Field(default="")  # L'UUID sera assigné par le déduplicateur
    name: str                    # nom de l'événement
    date: Optional[str] = ""     # date au format AAAA-MM-JJ
    location: Optional[str] = "" # lieu de l'événement
    description: Optional[str] = ""
    concert_style: Optional[str] = "" # style musical si c'est un concert
    organizer_uuid: Optional[str] = ""  # uuid de l'entité organisatrice
    
    def assign_unique_uuid(self, deduplicator=None):
        """Assigne un UUID unique via le système de déduplication"""
        if deduplicator:
            # Pour les événements, on peut aussi implémenter une déduplication
            # Pour l'instant, on génère toujours un nouvel UUID
            self.uuid = str(uuid.uuid4())
        else:
            self.uuid = str(uuid.uuid4())


class Relation(BaseModel):
    source_uuid: str               # uuid de l'entité source
    target_uuid: str               # uuid de l'entité cible
    relation_type: Literal[
        "collaboration",
        "intention",
        "événement",
        "appartenance",
        "autre"
    ]
    description: Optional[str] = ""
    date: Optional[str] = ""
    event_uuid: Optional[str] = "" # référence vers un événement si applicable
    
    @validator('source_uuid', 'target_uuid')
    def validate_uuids(cls, v):
        """Valide que les UUIDs ne sont pas vides"""
        if not v or v.strip() == "":
            raise ValueError("Relation UUIDs cannot be empty")
        return v.strip()
    
    def is_valid_uuid_format(self, uuid_string: str) -> bool:
        """Vérifie si une chaîne est un UUID valide"""
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False


class GraphData(BaseModel):
    entities: List[Entity]
    relations: List[Relation]
    events: List[Event] = []     # liste des événements identifiés
    
    def validate_and_fix_data(self) -> 'GraphData':
        """Valide et corrige les données pour assurer la cohérence Neo4j ↔ Dashboard"""
        logging.info("🔧 Démarrage de la validation et correction des données")
        
        # 1. Valider et corriger les UUIDs d'entités
        self._fix_entity_uuids()
        
        # 2. Déduplication des entités par nom
        self._deduplicate_entities()
        
        # 3. Valider et corriger les UUIDs d'événements
        self._fix_event_uuids()
        
        # 4. Nettoyer les relations orphelines
        self._clean_orphaned_relations()
        
        # 5. Validation finale
        self._final_validation()
        
        logging.info("✅ Validation et correction terminées")
        return self
    
    def _fix_entity_uuids(self):
        """Corrige les UUIDs d'entités invalides"""
        for entity in self.entities:
            if not entity.uuid or not self._is_valid_uuid(entity.uuid):
                entity.uuid = str(uuid.uuid4())
                logging.debug(f"🆔 UUID corrigé pour entité: {entity.name}")
    
    def _fix_event_uuids(self):
        """Corrige les UUIDs d'événements invalides"""
        for event in self.events:
            if not event.uuid or not self._is_valid_uuid(event.uuid):
                event.uuid = str(uuid.uuid4())
                logging.debug(f"🆔 UUID corrigé pour événement: {event.name}")
    
    def _deduplicate_entities(self):
        """Déduplique les entités par nom normalisé"""
        entity_name_to_id = {}
        entities_to_merge = defaultdict(list)
        
        # Identifier les doublons
        for entity in self.entities:
            normalized_name = entity.get_normalized_name()
            if normalized_name in entity_name_to_id:
                entities_to_merge[normalized_name].append(entity)
            else:
                entity_name_to_id[normalized_name] = entity.uuid
                entities_to_merge[normalized_name] = [entity]
        
        # Fusionner les entités dupliquées
        merged_entities = []
        uuid_mapping = {}
        
        for normalized_name, entity_group in entities_to_merge.items():
            if len(entity_group) > 1:
                # Fusionner les entités
                master_entity = entity_group[0]  # Garder la première
                
                # Fusionner les intentions
                all_intentions = set(master_entity.intentions)
                for entity in entity_group[1:]:
                    all_intentions.update(entity.intentions)
                    uuid_mapping[entity.uuid] = master_entity.uuid
                
                master_entity.intentions = list(all_intentions)
                merged_entities.append(master_entity)
                
                logging.info(f"🔀 Fusion de {len(entity_group)} entités: {master_entity.name}")
            else:
                merged_entities.append(entity_group[0])
        
        self.entities = merged_entities
        
        # Mettre à jour les références dans les relations et événements
        self._update_references(uuid_mapping)
    
    def _update_references(self, uuid_mapping: Dict[str, str]):
        """Met à jour toutes les références d'UUIDs"""
        # Mettre à jour les relations
        for relation in self.relations:
            if relation.source_uuid in uuid_mapping:
                relation.source_uuid = uuid_mapping[relation.source_uuid]
            if relation.target_uuid in uuid_mapping:
                relation.target_uuid = uuid_mapping[relation.target_uuid]
            if relation.event_uuid and relation.event_uuid in uuid_mapping:
                relation.event_uuid = uuid_mapping[relation.event_uuid]
        
        # Mettre à jour les événements
        for event in self.events:
            if event.organizer_uuid and event.organizer_uuid in uuid_mapping:
                event.organizer_uuid = uuid_mapping[event.organizer_uuid]
    
    def _clean_orphaned_relations(self):
        """Supprime les relations orphelines (pointant vers des entités inexistantes)"""
        valid_entity_uuids = {entity.uuid for entity in self.entities}
        valid_event_uuids = {event.uuid for event in self.events}
        
        cleaned_relations = []
        for relation in self.relations:
            # Vérifier que les entités source et cible existent
            if (relation.source_uuid in valid_entity_uuids and 
                relation.target_uuid in valid_entity_uuids):
                
                # Vérifier l'event_uuid si présent
                if relation.event_uuid:
                    if relation.event_uuid in valid_event_uuids:
                        cleaned_relations.append(relation)
                    else:
                        # Garder la relation mais supprimer l'event_uuid invalide
                        relation.event_uuid = ""
                        cleaned_relations.append(relation)
                        logging.warning(f"⚠️ Event_uuid invalide supprimé de la relation {relation.source_uuid} -> {relation.target_uuid}")
                else:
                    cleaned_relations.append(relation)
            else:
                logging.warning(f"❌ Relation orpheline supprimée: {relation.source_uuid} -> {relation.target_uuid}")
        
        removed_count = len(self.relations) - len(cleaned_relations)
        if removed_count > 0:
            logging.info(f"🧹 {removed_count} relations orphelines supprimées")
        
        self.relations = cleaned_relations
    
    def _final_validation(self):
        """Validation finale des données"""
        # Vérifier que toutes les entités ont des noms valides
        for entity in self.entities:
            if not entity.name or entity.name.strip().lower() == 'unknown':
                raise ValueError(f"Entité avec nom invalide détectée: {entity.uuid}")
        
        # Vérifier que toutes les relations pointent vers des entités existantes
        valid_entity_uuids = {entity.uuid for entity in self.entities}
        for relation in self.relations:
            if relation.source_uuid not in valid_entity_uuids:
                raise ValueError(f"Relation avec source_uuid invalide: {relation.source_uuid}")
            if relation.target_uuid not in valid_entity_uuids:
                raise ValueError(f"Relation avec target_uuid invalide: {relation.target_uuid}")
    
    def _is_valid_uuid(self, uuid_string: str) -> bool:
        """Vérifie si une chaîne est un UUID valide"""
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    def get_quality_metrics(self) -> Dict[str, float]:
        """Retourne les métriques de qualité des données"""
        total_entities = len(self.entities)
        valid_uuids = sum(1 for e in self.entities if self._is_valid_uuid(e.uuid))
        
        # Calculer la connectivité
        connected_entities = set()
        for relation in self.relations:
            connected_entities.add(relation.source_uuid)
            connected_entities.add(relation.target_uuid)
        
        connectivity_ratio = len(connected_entities) / max(total_entities, 1)
        
        return {
            'entity_count': total_entities,
            'relation_count': len(self.relations),
            'event_count': len(self.events),
            'uuid_validity_percent': (valid_uuids / max(total_entities, 1)) * 100,
            'connectivity_percent': connectivity_ratio * 100,
            'relation_density': len(self.relations) / max(total_entities, 1),
            'avg_intentions_per_entity': sum(len(e.intentions) for e in self.entities) / max(total_entities, 1)
        }
    
    def export_for_neo4j(self) -> Dict:
        """Exporte les données au format optimisé pour Neo4j"""
        return {
            'entities': [entity.dict() for entity in self.entities],
            'relations': [relation.dict() for relation in self.relations],
            'events': [event.dict() for event in self.events],
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'quality_metrics': self.get_quality_metrics(),
                'neo4j_ready': True
            }
        }
    
    def create_entity_name_mapping(self) -> Dict[str, str]:
        """Crée un mapping nom_normalisé -> UUID pour la cohérence"""
        return {
            entity.get_normalized_name(): entity.uuid 
            for entity in self.entities
        }
    
    def assign_all_unique_uuids(self, deduplicator=None):
        """Assigne des UUIDs uniques à toutes les entités et événements (méthode legacy)"""
        logging.warning("⚠️ Utilisation de la méthode legacy assign_all_unique_uuids. Utilisez validate_and_fix_data() à la place.")
        
        # Mapper les anciens UUIDs vers les nouveaux
        uuid_mapping = {}
        
        # Assigner des UUIDs aux entités avec déduplication
        for entity in self.entities:
            old_uuid = entity.uuid
            entity.assign_unique_uuid(deduplicator)
            if old_uuid and old_uuid != entity.uuid:
                uuid_mapping[old_uuid] = entity.uuid
        
        # Assigner des UUIDs aux événements
        for event in self.events:
            old_uuid = event.uuid
            event.assign_unique_uuid(deduplicator)
            if old_uuid and old_uuid != event.uuid:
                uuid_mapping[old_uuid] = event.uuid
        
        # Mettre à jour les références dans les relations
        for relation in self.relations:
            if relation.source_uuid in uuid_mapping:
                relation.source_uuid = uuid_mapping[relation.source_uuid]
            if relation.target_uuid in uuid_mapping:
                relation.target_uuid = uuid_mapping[relation.target_uuid]
            if relation.event_uuid and relation.event_uuid in uuid_mapping:
                relation.event_uuid = uuid_mapping[relation.event_uuid]
        
        # Mettre à jour les organizer_uuid dans les événements
        for event in self.events:
            if event.organizer_uuid and event.organizer_uuid in uuid_mapping:
                event.organizer_uuid = uuid_mapping[event.organizer_uuid]
        
        return uuid_mapping
    
class DataQualityManager:
    """Gestionnaire de la qualité des données pour assurer la cohérence Neo4j ↔ Dashboard"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @staticmethod
    def clean_prompt_uuids_from_llm_output(llm_output: Dict) -> Dict:
        """
        Nettoie les UUIDs d'exemple du prompt que le LLM pourrait réutiliser
        """
        # UUIDs d'exemple à éviter (ceux du prompt)
        FORBIDDEN_UUIDS = {
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8", 
            "7ba7b811-9dad-11d1-80b4-00c04fd430c8",
            "8ca7b812-9dad-11d1-80b4-00c04fd430c8"
        }
        
        # Mapping pour remplacer les UUIDs interdits
        uuid_replacements = {}
        
        def get_clean_uuid(old_uuid):
            if old_uuid in FORBIDDEN_UUIDS:
                if old_uuid not in uuid_replacements:
                    uuid_replacements[old_uuid] = str(uuid.uuid4())
                return uuid_replacements[old_uuid]
            return old_uuid
        
        # Nettoyer les entités
        for entity in llm_output.get('entities', []):
            old_uuid = entity.get('uuid', '')
            entity['uuid'] = get_clean_uuid(old_uuid)
        
        # Nettoyer les événements
        for event in llm_output.get('events', []):
            old_uuid = event.get('uuid', '')
            event['uuid'] = get_clean_uuid(old_uuid)
            
            # Nettoyer l'organizer_uuid aussi
            old_organizer_uuid = event.get('organizer_uuid', '')
            if old_organizer_uuid in uuid_replacements:
                event['organizer_uuid'] = uuid_replacements[old_organizer_uuid]
        
        # Nettoyer les relations
        for relation in llm_output.get('relations', []):
            old_source = relation.get('source_uuid', '')
            old_target = relation.get('target_uuid', '')
            old_event = relation.get('event_uuid', '')
            
            if old_source in uuid_replacements:
                relation['source_uuid'] = uuid_replacements[old_source]
            if old_target in uuid_replacements:
                relation['target_uuid'] = uuid_replacements[old_target]
            if old_event in uuid_replacements:
                relation['event_uuid'] = uuid_replacements[old_event]
        
        logging.info(f"🧹 Nettoyage UUIDs prompt: {len(uuid_replacements)} UUIDs remplacés")
        return llm_output
    
    @staticmethod
    def clean_entity_from_llm_output(entity_data: Dict) -> Optional[Entity]:
        """Nettoie et valide une entité provenant de la sortie LLM"""
        try:
            # Nettoyer le nom
            name = entity_data.get('name', '').strip()
            if not name or name.lower() == 'unknown':
                return None
            
            # Valider et corriger le type
            entity_type = entity_data.get('type', 'autre')
            valid_types = ['association', 'entreprise', 'institution', 'personne', 'autre']
            if entity_type not in valid_types:
                entity_type = 'autre'
            
            # Nettoyer les intentions
            intentions = entity_data.get('intentions', [])
            if not intentions:
                # Générer des intentions par défaut selon le type
                intentions = DataQualityManager._generate_default_intentions(entity_type, name)
            
            # Nettoyer l'UUID
            entity_uuid = entity_data.get('uuid', '')
            if not entity_uuid:
                entity_uuid = str(uuid.uuid4())
            else:
                try:
                    uuid.UUID(entity_uuid)
                except ValueError:
                    entity_uuid = str(uuid.uuid4())
            
            return Entity(
                uuid=entity_uuid,
                name=name,
                type=entity_type,
                description=entity_data.get('description', ''),
                intentions=intentions
            )
        
        except Exception as e:
            logging.warning(f"❌ Impossible de nettoyer l'entité {entity_data}: {e}")
            return None
    
    @staticmethod
    def clean_relation_from_llm_output(relation_data: Dict, valid_entity_ids: Set[str]) -> Optional[Relation]:
        """Nettoie et valide une relation provenant de la sortie LLM"""
        try:
            # Gérer les différents formats de relations
            if 'entity_1' in relation_data and 'entity_2' in relation_data:
                # Nouveau format
                entity_1 = relation_data['entity_1']
                entity_2 = relation_data['entity_2']
                
                if isinstance(entity_1, dict) and isinstance(entity_2, dict):
                    source_uuid = entity_1.get('uuid', '')
                    target_uuid = entity_2.get('uuid', '')
                    source_name = entity_1.get('name', '')
                    target_name = entity_2.get('name', '')
                else:
                    return None
            else:
                # Format legacy
                source_uuid = relation_data.get('source_uuid', '')
                target_uuid = relation_data.get('target_uuid', '')
                source_name = "Legacy format"
                target_name = "Legacy format"
            
            # Vérifier que les entités existent
            if source_uuid not in valid_entity_ids or target_uuid not in valid_entity_ids:
                logging.warning(f"⚠️ Relation ignorée: entités {source_name} -> {target_name} non trouvées")
                return None
            
            # Valider le type de relation
            relation_type = relation_data.get('relation_type', 'autre')
            valid_types = ['collaboration', 'intention', 'événement', 'appartenance', 'autre']
            if relation_type not in valid_types:
                relation_type = 'autre'
            
            return Relation(
                source_uuid=source_uuid,
                target_uuid=target_uuid,
                relation_type=relation_type,
                description=relation_data.get('description', ''),
                date=relation_data.get('date', ''),
                event_uuid=relation_data.get('event_uuid', '')
            )
        
        except Exception as e:
            logging.warning(f"❌ Impossible de nettoyer la relation {relation_data}: {e}")
            return None
    
    @staticmethod
    def _generate_default_intentions(entity_type: str, entity_name: str) -> List[str]:
        """Génère des intentions par défaut selon le type d'entité"""
        defaults = {
            'association': [
                "Promouvoir la culture musicale",
                "Soutenir les artistes locaux",
                "Organiser des événements culturels"
            ],
            'entreprise': [
                "Développer l'économie culturelle",
                "Créer des expériences musicales uniques",
                "Innover dans le secteur musical"
            ],
            'institution': [
                "Soutenir la création artistique",
                "Démocratiser l'accès à la culture",
                "Préserver le patrimoine musical"
            ],
            'personne': [
                "Partager sa passion musicale",
                "Créer et innover artistiquement",
                "Connecter avec le public"
            ],
            'autre': [
                "Contribuer à la scène musicale",
                "Développer des projets culturels"
            ]
        }
        return defaults.get(entity_type, defaults['autre'])
    
    @staticmethod
    def validate_graph_data(graph_data: GraphData) -> Tuple[bool, List[str]]:
        """Valide complètement un GraphData et retourne les erreurs"""
        errors = []
        
        # Vérifier les entités
        entity_uuids = set()
        for entity in graph_data.entities:
            if entity.uuid in entity_uuids:
                errors.append(f"UUID d'entité dupliqué: {entity.uuid}")
            entity_uuids.add(entity.uuid)
            
            if not entity.name or entity.name.strip().lower() == 'unknown':
                errors.append(f"Entité avec nom invalide: {entity.uuid}")
            
            if not entity.intentions:
                errors.append(f"Entité sans intentions: {entity.name}")
        
        # Vérifier les relations
        for relation in graph_data.relations:
            if relation.source_uuid not in entity_uuids:
                errors.append(f"Relation avec source invalide: {relation.source_uuid}")
            if relation.target_uuid not in entity_uuids:
                errors.append(f"Relation avec target invalide: {relation.target_uuid}")
        
        # Vérifier les événements
        event_uuids = set()
        for event in graph_data.events:
            if event.uuid in event_uuids:
                errors.append(f"UUID d'événement dupliqué: {event.uuid}")
            event_uuids.add(event.uuid)
        
        return len(errors) == 0, errors
    

class Prompt(BaseModel):
    prompt : str = """Tu es un système d'extraction d'information qui transforme un texte en un graphe d'entités, de relations et d'événements.
                    Ta tâche est de lire un texte donné et de produire une réponse strictement au format JSON, conforme au modèle suivant :
                    
                    🚨 RÈGLES CRITIQUES - PRIORITÉS ABSOLUES 🚨
                    
                    0. **GESTION TEXTES RÉPÉTITIFS - NOUVELLE PRIORITÉ** :
                       - IGNORE complètement les listes répétitives de productions/événements (ex: "/\\/\\ PRODUCTIONS Les Eurockéennes...")
                       - CONCENTRE-TOI uniquement sur les sections descriptives et narratives
                       - RECHERCHE les connecteurs explicites : "organisé par", "en collaboration avec", "créé par", "fondé par", "dirigé par"
                       - IDENTIFIE les relations cachées dans les descriptions détaillées
                       - Si tu vois la même liste se répéter, ne l'analyse qu'UNE SEULE FOIS
                       - PRIORISE les sections avec des noms propres et des verbes d'action
                    
                    1. **INTENTIONS - PRIORITÉ ABSOLUE** :
                       - Pour CHAQUE entité, tu DOIS identifier au minimum une intention/objectif
                       - Les intentions sont OBLIGATOIRES, jamais une liste vide []
                       - Analyse le contexte, la mission, les activités pour déduire les intentions
                       - Si non explicites, déduis-les du type d'activité (ex: "Organiser des événements musicaux", "Promouvoir les artistes locaux")
                       - Sois créatif et analytique pour identifier les motivations sous-jacentes
                    
                    2. **RELATIONS EXPLICITES - PRIORITÉ CRITIQUE** :
                       - RECHERCHE activement les phrases qui décrivent des collaborations
                       - IDENTIFIE qui fait quoi avec qui : "X organise Y", "A collabore avec B", "C est dirigé par D"
                       - EXTRAIT les relations même si elles sont implicites : "Pour lille3000, Fanny Bouyagui imagine..." = relation "collaboration"
                       - NE PAS créer de relations "Unknown" - si tu ne connais pas l'entité, mets le nom réel trouvé dans le texte
                       - CHAQUE relation doit avoir des entités source et cible bien identifiées
                    
                    3. **ÉVÉNEMENTS ET STYLES MUSICAUX - PRIORITÉ CRITIQUE** :
                       - Extrais TOUS les événements mentionnés, même les plus petits
                       - Pour CHAQUE concert/spectacle musical, le champ concert_style est OBLIGATOIRE
                       - Sois TRÈS précis sur les styles : Rock, Jazz, Électro, Hip-hop, Classique, Folk, Métal, Reggae, etc.
                       - Détecte les sous-genres : Rock alternatif, Jazz fusion, Électro ambient, Hip-hop conscient, etc.
                       - Si le style n'est pas explicite, déduis-le du contexte, des artistes, du lieu
                       - Capture tous les détails : date précise, lieu exact, description complète
                       - Lie chaque événement à son organisateur via organizer_id
                    
                    4. **Autres règles importantes** :
                       - Tu dois extraire toutes les entités nommées pertinentes (associations, entreprises, institutions, personnes, autres).
                       - Chaque entité doit avoir un identifiant unique généré aléatoirement (UUID).
                       - Tu dois détecter les relations explicites ou implicites entre ces entités (collaboration, intention, événement, appartenance, autre).
                       - Extrais tous les événements mentionnés avec leurs détails (nom, date, lieu, description).
                       - Si un événement est un concert ou spectacle musical, précise le style musical dans concert_style.
                       - Pour les événements, utilise un identifiant unique généré aléatoirement (UUID).
                       - Si la date est mentionnée dans le texte, l'indiquer au format AAAA-MM-JJ. Sinon, laisse null.
                       - Lie les relations aux événements via event_id quand c'est pertinent.
                       - La sortie doit être uniquement un objet JSON valide, sans texte additionnel.
                       - IMPÉRATIF : Le JSON produit doit être parfaitement compatible avec json.loads() en Python.
                       - Aucun caractère d'échappement invalide, guillemets correctement formés, virgules appropriées.
                    
                    🎯 EXEMPLES D'INTENTIONS OBLIGATOIRES :
                    - Association musicale → ["Démocratiser l'accès à la musique", "Soutenir la création artistique locale"]
                    - Entreprise événementielle → ["Créer des expériences musicales uniques", "Développer l'économie culturelle"]
                    - Label → ["Découvrir de nouveaux talents", "Diffuser des styles musicaux émergents"]
                    - Artiste → ["Partager sa vision artistique", "Connecter avec son public"]
                    
                    🔗 EXEMPLES DE RELATIONS À DÉTECTER :
                    - "Fanny Bouyagui crée Art Point M" → relation "appartenance" entre Fanny Bouyagui et Art Point M
                    - "Art Point M collabore avec lille3000" → relation "collaboration" entre Art Point M et lille3000
                    - "Pour les Eurockéennes, Art Point M imagine..." → relation "collaboration" entre Art Point M et Les Eurockéennes
                    - "Art Point M initie le NAME Festival" → relation "appartenance" entre Art Point M et NAME Festival
                    
                    🎪 EXEMPLES D'ÉVÉNEMENTS AVEC STYLES OBLIGATOIRES :
                    - Concert rock → concert_style: "Rock alternatif"
                    - Soirée DJ → concert_style: "Électro house"
                    - Showcase → concert_style: "Hip-hop indépendant"
                    - Festival → concert_style: "Multi-genres" (si plusieurs styles)
                    - Session jazz → concert_style: "Jazz fusion"
                    - Spectacle → concert_style: "Chanson française" (si musical)
                    
                    Exemple de structure attendue :
                    {
                        "entities": [
                            {
                                "id": "GENERE_UN_UUID_UNIQUE",
                                "type": "association",
                                "name": "Festival Rock",
                                "description": "Organisation de concerts",
                                "intentions": ["Promouvoir la diversité musicale rock", "Créer des liens entre artistes émergents et public", "Développer la scène culturelle locale"]
                            }
                        ],
                        "relations": [
                            {
                                "source_uuid": "UUID_DE_L_ENTITE_SOURCE",
                                "target_uuid": "UUID_DE_L_ENTITE_CIBLE",
                                "relation_type": "événement",
                                "description": "organise le concert",
                                "date": "2024-06-15",
                                "event_uuid": "UUID_DE_L_EVENEMENT"
                            }
                        ],
                        "events": [
                            {
                                "uuid": "GENERE_UN_UUID_UNIQUE",
                                "name": "Concert Rock Summer",
                                "date": "2024-06-15",
                                "location": "Salle de spectacle Mars, Lille",
                                "description": "Concert de rock avec trois groupes émergents de la région Nord",
                                "concert_style": "Rock alternatif",
                                "organizer_uuid": "UUID_DE_L_ENTITE_ORGANISATRICE"
                            }
                        ]
                    }
                    
                    ⚠️ IMPORTANT POUR LES UUIDs:
                    - Pour chaque entité, génère un UUID unique aléatoire (pas ceux de l'exemple)
                    - Pour chaque événement, génère un UUID unique aléatoire  
                    - Dans les relations, utilise les vrais UUIDs des entités que tu viens de créer
                    - Dans les événements, utilise le vrai UUID de l'entité organisatrice
                    - NE RÉUTILISE JAMAIS les UUIDs d'exemple du prompt"""


def create_clean_graph_data_from_llm_output(llm_output: Dict) -> Optional[GraphData]:
    """
    Crée un GraphData nettoyé à partir de la sortie brute du LLM
    Applique toutes les corrections pour assurer la cohérence Neo4j ↔ Dashboard
    """
    try:
        # ÉTAPE 0: Nettoyer les UUIDs du prompt que le LLM pourrait avoir réutilisés
        llm_output = DataQualityManager.clean_prompt_uuids_from_llm_output(llm_output)
        # Nettoyer les entités
        clean_entities = []
        for entity_data in llm_output.get('entities', []):
            clean_entity = DataQualityManager.clean_entity_from_llm_output(entity_data)
            if clean_entity:
                clean_entities.append(clean_entity)
        
        if not clean_entities:
            logging.warning("⚠️ Aucune entité valide trouvée dans la sortie LLM")
            return None
        
        # Créer un mapping des UUIDs valides
        valid_entity_ids = {entity.uuid for entity in clean_entities}
        
        # Nettoyer les relations
        clean_relations = []
        for relation_data in llm_output.get('relations', []):
            clean_relation = DataQualityManager.clean_relation_from_llm_output(relation_data, valid_entity_ids)
            if clean_relation:
                clean_relations.append(clean_relation)
        
        # Nettoyer les événements
        clean_events = []
        for event_data in llm_output.get('events', []):
            try:
                # Nettoyer l'UUID
                event_uuid = event_data.get('uuid', '')
                if not event_uuid:
                    event_uuid = str(uuid.uuid4())
                else:
                    try:
                        uuid.UUID(event_uuid)
                    except ValueError:
                        event_uuid = str(uuid.uuid4())
                
                clean_event = Event(
                    uuid=event_uuid,
                    name=event_data.get('name', ''),
                    date=event_data.get('date', ''),
                    location=event_data.get('location', ''),
                    description=event_data.get('description', ''),
                    concert_style=event_data.get('concert_style', ''),
                    organizer_uuid=event_data.get('organizer_uuid', '')
                )
                clean_events.append(clean_event)
            except Exception as e:
                logging.warning(f"❌ Impossible de nettoyer l'événement {event_data}: {e}")
        
        # Créer le GraphData et le valider
        graph_data = GraphData(
            entities=clean_entities,
            relations=clean_relations,
            events=clean_events
        )
        
        # Appliquer le nettoyage complet
        graph_data = graph_data.validate_and_fix_data()
        
        # Validation finale
        is_valid, errors = DataQualityManager.validate_graph_data(graph_data)
        if not is_valid:
            logging.error(f"❌ GraphData invalide après nettoyage: {errors}")
            return None
        
        logging.info(f"✅ GraphData nettoyé créé: {len(graph_data.entities)} entités, {len(graph_data.relations)} relations")
        return graph_data
        
    except Exception as e:
        logging.error(f"❌ Erreur lors du nettoyage de la sortie LLM: {e}")
        return None


def merge_multiple_graph_data(graph_data_list: List[GraphData]) -> GraphData:
    """
    Fusionne plusieurs GraphData en un seul, avec déduplication complète
    """
    if not graph_data_list:
        return GraphData(entities=[], relations=[], events=[])
    
    if len(graph_data_list) == 1:
        return graph_data_list[0].validate_and_fix_data()
    
    logging.info(f"🔀 Fusion de {len(graph_data_list)} GraphData")
    
    # Collecter toutes les entités, relations et événements
    all_entities = []
    all_relations = []
    all_events = []
    
    for graph_data in graph_data_list:
        all_entities.extend(graph_data.entities)
        all_relations.extend(graph_data.relations)
        all_events.extend(graph_data.events)
    
    # Créer le GraphData fusionné
    merged_graph = GraphData(
        entities=all_entities,
        relations=all_relations,
        events=all_events
    )
    
    # Appliquer le nettoyage complet (incluant la déduplication)
    return merged_graph.validate_and_fix_data()

