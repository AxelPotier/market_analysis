#!/usr/bin/env python3
"""
NEO4J INSERTER - GRAPHDATA (VERSION CORRIGÉE)
Module pour insérer les données GraphData dans Neo4j avec gestion des problèmes d'IDs
"""

import pickle
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
from neo4j import GraphDatabase

# Configuration logging
logging.basicConfig(level=logging.INFO, encoding='utf-8')
logger = logging.getLogger(__name__)

class Neo4jGraphDataInserterFixed:
    """
    Classe pour insérer des données GraphData dans Neo4j avec correction des problèmes d'IDs
    """
    
    def __init__(self, uri: str, user: str, password: str):
        """
        Initialise l'inserter Neo4j
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.stats = {
            'files_processed': 0,
            'entities_created': 0,
            'events_created': 0,
            'relations_created': 0,
            'relations_skipped': 0,
            'ids_fixed': 0,
            'errors': []
        }
        # Cache des entités et événements créés pour validation des relations
        self.created_entities: Set[str] = set()
        self.created_events: Set[str] = set()
    
    # Fonction clean_id supprimée - nous utilisons maintenant les IDs d'entités directement
    
    def connect(self) -> bool:
        """
        Etablit la connexion à Neo4j
        """
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test de connexion
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Connexion Neo4j etablie avec succes")
            return True
        except Exception as e:
            logger.error(f"Erreur connexion Neo4j: {str(e)}")
            return False
    
    def close(self):
        """
        Ferme la connexion Neo4j
        """
        if self.driver:
            self.driver.close()
            logger.info("Connexion Neo4j fermee")
    
    def clear_database(self):
        """
        Vide complètement la base de données (ATTENTION!)
        """
        try:
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("Base de donnees videe")
            # Réinitialiser les caches
            self.created_entities.clear()
            self.created_events.clear()
        except Exception as e:
            logger.error(f"Erreur vidage base: {str(e)}")
    
    def create_constraints_and_indexes(self):
        """
        Crée les contraintes et index nécessaires avec index unique sur id
        """
        constraints_and_indexes = [
            # Contrainte unique sur le champ uuid pour toutes les entités et événements
            "CREATE CONSTRAINT unique_uuid IF NOT EXISTS FOR (n) REQUIRE n.uuid IS UNIQUE",
            
            # Index pour améliorer les performances de recherche
            "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON e.name",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON e.type", 
            "CREATE INDEX event_name IF NOT EXISTS FOR (ev:Event) ON ev.name",
            "CREATE INDEX event_date IF NOT EXISTS FOR (ev:Event) ON ev.date",
            "CREATE INDEX concert_style IF NOT EXISTS FOR (ev:Event) ON ev.concert_style",
            "CREATE INDEX source_file IF NOT EXISTS FOR (n) ON n.source_file",
            
            # Index spécifiques pour chaque type d'entité
            "CREATE INDEX association_name IF NOT EXISTS FOR (a:Association) ON a.name",
            "CREATE INDEX entreprise_name IF NOT EXISTS FOR (e:Entreprise) ON e.name",
            "CREATE INDEX institution_name IF NOT EXISTS FOR (i:Institution) ON i.name",
            "CREATE INDEX personne_name IF NOT EXISTS FOR (p:Personne) ON p.name"
        ]
        
        with self.driver.session() as session:
            for constraint in constraints_and_indexes:
                try:
                    session.run(constraint)
                    logger.info(f"Contrainte/index cree: {constraint.split()[1]}")
                except Exception as e:
                    # Ignore si déjà existant
                    logger.debug(f"Contrainte/index existe deja: {str(e)}")
    
    def insert_entity(self, entity: Dict, source_file: str) -> bool:
        """
        Insère une entité dans Neo4j avec l'UUID comme index unique et le type comme label
        """
        # Utiliser l'UUID de l'entité directement
        entity_uuid = entity.get('uuid', entity.get('id', ''))  # Compatibilité avec ancien format
        entity_type = entity.get('type', 'autre')
        
        if not entity_uuid:
            logger.warning(f"Entité ignorée - UUID vide ou invalide")
            return False
        
        # Mapper les types vers des labels Neo4j valides (PascalCase)
        type_mapping = {
            'association': 'Association',
            'entreprise': 'Entreprise', 
            'institution': 'Institution',
            'personne': 'Personne',
            'autre': 'Autre'
        }
        
        type_label = type_mapping.get(entity_type, 'Autre')
        
        # Utiliser l'UUID comme index unique et ajouter le type comme label
        # Créer le nœud sans retourner l'UUID Neo4j interne
        cypher = f"""
        MERGE (e:Entity:{type_label} {{uuid: $entity_uuid}})
        SET e.name = $name,
            e.type = $type,
            e.description = $description,
            e.intentions = $intentions,
            e.source_file = $source_file,
            e.updated_at = datetime()
        """
        
        try:
            with self.driver.session() as session:
                session.run(cypher, 
                    entity_uuid=entity_uuid,
                    name=entity.get('name', ''),
                    type=entity_type,
                    description=entity.get('description', ''),
                    intentions=entity.get('intentions', []),
                    source_file=source_file
                )
                self.stats['entities_created'] += 1
                self.created_entities.add(entity_uuid)
                logger.debug(f"Entité créée: {entity.get('name')} ({type_label}) - UUID: {entity_uuid}")
                return True
        except Exception as e:
            logger.error(f"Erreur insertion entite {entity_uuid}: {str(e)}")
            self.stats['errors'].append(f"Entity {entity_uuid}: {str(e)}")
            return False
    
    def insert_event(self, event: Dict, source_file: str) -> bool:
        """
        Insère un événement dans Neo4j avec l'UUID comme index unique et Event comme label
        """
        # Utiliser l'UUID de l'événement directement
        event_uuid = event.get('uuid', event.get('id', ''))  # Compatibilité avec ancien format
        
        if not event_uuid:
            logger.warning(f"Événement ignoré - UUID vide ou invalide")
            return False
        
        # Les événements auront toujours le label Event
        # Créer le nœud sans retourner l'UUID Neo4j interne
        cypher = """
        MERGE (ev:Event {uuid: $event_uuid})
        SET ev.name = $name,
            ev.date = $date,
            ev.location = $location,
            ev.description = $description,
            ev.concert_style = $concert_style,
            ev.organizer_uuid = $organizer_uuid,
            ev.source_file = $source_file,
            ev.updated_at = datetime()
        """
        
        try:
            with self.driver.session() as session:
                # Utiliser l'organizer_uuid directement
                organizer_uuid = event.get('organizer_uuid', event.get('organizer_id', ''))  # Compatibilité
                
                session.run(cypher,
                    event_uuid=event_uuid,
                    name=event.get('name', ''),
                    date=event.get('date', ''),
                    location=event.get('location', ''),
                    description=event.get('description', ''),
                    concert_style=event.get('concert_style', ''),
                    organizer_uuid=organizer_uuid,
                    source_file=source_file
                )
                self.stats['events_created'] += 1
                self.created_events.add(event_uuid)
                logger.debug(f"Événement créé: {event.get('name')} - UUID: {event_uuid}")
                
                # Créer la relation ORGANIZES si organizer_uuid existe et est valide
                if organizer_uuid and organizer_uuid in self.created_entities:
                    self.create_organizes_relation(organizer_uuid, event_uuid, source_file)
                elif organizer_uuid:
                    logger.warning(f"Organisateur {organizer_uuid} non trouvé pour l'événement {event_uuid}")
                
                return True
        except Exception as e:
            logger.error(f"Erreur insertion evenement {event_uuid}: {str(e)}")
            self.stats['errors'].append(f"Event {event_uuid}: {str(e)}")
            return False
    
    def create_organizes_relation(self, organizer_uuid: str, event_uuid: str, source_file: str):
        """
        Crée une relation ORGANIZES entre une entité et un événement
        """
        cypher = """
        MATCH (e:Entity {uuid: $organizer_uuid})
        MATCH (ev:Event {uuid: $event_uuid})
        MERGE (e)-[r:ORGANIZES]->(ev)
        SET r.source_file = $source_file,
            r.updated_at = datetime()
        """
        
        try:
            with self.driver.session() as session:
                session.run(cypher,
                    organizer_uuid=organizer_uuid,
                    event_uuid=event_uuid,
                    source_file=source_file
                )
                self.stats['relations_created'] += 1
        except Exception as e:
            logger.warning(f"Erreur creation relation ORGANIZES {organizer_uuid}->{event_uuid}: {str(e)}")
    
    def insert_relation(self, relation: Dict, source_file: str) -> bool:
        """
        Insère une relation dans Neo4j en utilisant les UUIDs d'entités
        """
        # Utiliser les UUIDs directement
        source_uuid = relation.get('source_uuid', relation.get('source_id', ''))  # Compatibilité
        target_uuid = relation.get('target_uuid', relation.get('target_id', ''))  # Compatibilité
        
        if not source_uuid or not target_uuid:
            logger.warning(f"Relation ignorée - UUIDs invalides: {source_uuid} -> {target_uuid}")
            self.stats['relations_skipped'] += 1
            return False
        
        # Vérifier que les entités/événements existent
        if source_uuid not in self.created_entities and source_uuid not in self.created_events:
            logger.warning(f"Relation ignorée - source {source_uuid} non trouvée")
            self.stats['relations_skipped'] += 1
            return False
        
        if target_uuid not in self.created_entities and target_uuid not in self.created_events:
            logger.warning(f"Relation ignorée - target {target_uuid} non trouvée")
            self.stats['relations_skipped'] += 1
            return False
        
        # Mapper les types de relations vers des labels Neo4j
        relation_mapping = {
            'collaboration': 'COLLABORATES_WITH',
            'intention': 'INTENDS',
            'événement': 'PARTICIPATES_IN',
            'appartenance': 'BELONGS_TO',
            'autre': 'RELATED_TO'
        }
        
        relation_type = relation_mapping.get(relation.get('relation_type', 'autre'), 'RELATED_TO')
        
        cypher = f"""
        MATCH (source) WHERE (source:Entity OR source:Event) AND source.uuid = $source_uuid
        MATCH (target) WHERE (target:Entity OR target:Event) AND target.uuid = $target_uuid
        MERGE (source)-[r:{relation_type}]->(target)
        SET r.description = $description,
            r.date = $date,
            r.event_uuid = $event_uuid,
            r.source_file = $source_file,
            r.updated_at = datetime()
        """
        
        try:
            with self.driver.session() as session:
                session.run(cypher,
                    source_uuid=source_uuid,
                    target_uuid=target_uuid,
                    description=relation.get('description', ''),
                    date=relation.get('date', ''),
                    event_uuid=relation.get('event_uuid', relation.get('event_id', '')),  # Compatibilité
                    source_file=source_file
                )
                self.stats['relations_created'] += 1
                return True
        except Exception as e:
            logger.error(f"Erreur insertion relation {source_uuid}->{target_uuid}: {str(e)}")
            self.stats['errors'].append(f"Relation {source_uuid}->{target_uuid}: {str(e)}")
            return False
    
    def insert_graphdata(self, graph_data: Dict) -> bool:
        """
        Insère un dictionnaire GraphData complet dans Neo4j
        """
        source_file = graph_data.get('file_name', 'unknown')
        logger.info(f"Traitement du fichier: {source_file}")
        
        success = True
        
        # Insérer les entités d'abord
        entities = graph_data.get('entities', [])
        logger.info(f"  Insertion de {len(entities)} entites...")
        for entity in entities:
            if not self.insert_entity(entity, source_file):
                success = False
        
        # Insérer les événements
        events = graph_data.get('events', [])
        logger.info(f"  Insertion de {len(events)} evenements...")
        for event in events:
            if not self.insert_event(event, source_file):
                success = False
        
        # Insérer les relations (après avoir créé entités et événements)
        relations = graph_data.get('relations', [])
        logger.info(f"  Insertion de {len(relations)} relations...")
        for relation in relations:
            if not self.insert_relation(relation, source_file):
                success = False
        
        if success:
            self.stats['files_processed'] += 1
            logger.info(f"  {source_file} traite avec succes")
        else:
            logger.warning(f"  {source_file} traite avec des erreurs")
        
        return success
    
    def load_and_insert_batch_results(self, results_file: str = "batch_graphdata_chunked_results.pkl"):
        """
        Charge et insère tous les résultats du traitement batch
        """
        if not Path(results_file).exists():
            logger.error(f"Fichier de resultats non trouve: {results_file}")
            return False
        
        # Charger les données
        try:
            with open(results_file, 'rb') as f:
                batch_results = pickle.load(f)
            logger.info(f"{len(batch_results)} fichiers GraphData charges depuis {results_file}")
        except Exception as e:
            logger.error(f"Erreur chargement {results_file}: {str(e)}")
            return False
        
        # Insérer chaque résultat
        logger.info("Debut de l'insertion batch dans Neo4j...")
        start_time = datetime.now()
        
        for i, graph_data in enumerate(batch_results, 1):
            logger.info(f"[{i}/{len(batch_results)}] {graph_data.get('file_name', 'unknown')}")
            self.insert_graphdata(graph_data)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Afficher le résumé
        self.print_insertion_summary(duration)
        
        return True
    
    def print_insertion_summary(self, duration_seconds: float):
        """
        Affiche un résumé de l'insertion
        """
        print("\n" + "="*60)
        print("RESUME DE L'INSERTION NEO4J (VERSION CORRIGEE)")
        print("="*60)
        print(f"Duree totale: {duration_seconds:.2f} secondes")
        print(f"Fichiers traites: {self.stats['files_processed']}")
        print(f"Entites creees: {self.stats['entities_created']}")
        print(f"Evenements crees: {self.stats['events_created']}")
        print(f"Relations creees: {self.stats['relations_created']}")
        print(f"Relations ignorees: {self.stats['relations_skipped']}")
        print(f"IDs corriges: {self.stats['ids_fixed']}")
        
        if self.stats['errors']:
            print(f"\nErreurs ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Afficher les 10 premières erreurs
                print(f"   • {error}")
            if len(self.stats['errors']) > 10:
                print(f"   ... et {len(self.stats['errors']) - 10} autres erreurs")
    
    def get_database_stats(self) -> Dict:
        """
        Obtient des statistiques sur la base de données Neo4j
        """
        queries = {
            'total_entities': "MATCH (e:Entity) RETURN count(e) as count",
            'total_events': "MATCH (ev:Event) RETURN count(ev) as count", 
            'total_relations': "MATCH ()-[r]->() RETURN count(r) as count",
            'entity_types': "MATCH (e:Entity) RETURN e.type as type, count(e) as count ORDER BY count DESC",
            'entity_labels': "MATCH (n) WHERE n:Entity RETURN labels(n) as labels, count(n) as count ORDER BY count DESC",
            'music_styles': "MATCH (ev:Event) WHERE ev.concert_style <> '' RETURN ev.concert_style as style, count(ev) as count ORDER BY count DESC",
            'source_files': "MATCH (n) WHERE n.source_file IS NOT NULL RETURN n.source_file as file, count(n) as count ORDER BY count DESC",
            'sample_entities': "MATCH (e:Entity) RETURN e.uuid as uuid, e.name as name, labels(e) as labels LIMIT 5",
            'sample_events': "MATCH (ev:Event) RETURN ev.uuid as uuid, ev.name as name LIMIT 5",
            'associations': "MATCH (a:Association) RETURN count(a) as count",
            'entreprises': "MATCH (e:Entreprise) RETURN count(e) as count", 
            'institutions': "MATCH (i:Institution) RETURN count(i) as count",
            'personnes': "MATCH (p:Personne) RETURN count(p) as count"
        }
        
        stats = {}
        
        with self.driver.session() as session:
            for stat_name, query in queries.items():
                try:
                    result = session.run(query)
                    if stat_name in ['total_entities', 'total_events', 'total_relations']:
                        stats[stat_name] = result.single()['count']
                    else:
                        stats[stat_name] = [{record['type'] if 'type' in record else record.get('style', record.get('file')): record['count']} for record in result]
                except Exception as e:
                    logger.error(f"Erreur calcul statistique {stat_name}: {str(e)}")
                    stats[stat_name] = 0 if stat_name.startswith('total_') else []
        
        return stats


def main():
    """
    Fonction principale pour l'insertion Neo4j corrigée
    """
    print("NEO4J INSERTER - GRAPHDATA (VERSION CORRIGEE)")
    print("="*60)
    
    # Configuration Neo4j (à adapter selon votre installation)
    neo4j_config = {
        'uri': input("URI Neo4j (defaut: bolt://localhost:7687): ") or "bolt://localhost:7687",
        'user': input("Utilisateur (defaut: neo4j): ") or "neo4j",
        'password': input("Mot de passe: ") or "password"
    }
    
    # Initialiser l'inserter
    inserter = Neo4jGraphDataInserterFixed(**neo4j_config)
    
    # Connexion
    if not inserter.connect():
        print("Impossible de se connecter a Neo4j")
        return
    
    try:
        # Options
        print("\nOptions disponibles:")
        print("1. Creer contraintes et index")
        print("2. Vider la base de donnees (ATTENTION!)")
        print("3. Inserer les donnees batch")
        print("4. Afficher les statistiques de la base")
        
        choice = input("\nChoix (1-4, ou 'all' pour tout faire): ")
        
        if choice == '1' or choice == 'all':
            print("\nCreation des contraintes et index...")
            inserter.create_constraints_and_indexes()
        
        if choice == '2':
            print("\nVidage de la base de donnees...")
            inserter.clear_database()
        
        if choice == '3' or choice == 'all':
            print("\nInsertion des donnees...")
            results_file = input("Fichier de resultats (defaut: batch_graphdata_chunked_results.pkl): ") or "batch_graphdata_chunked_results.pkl"
            inserter.load_and_insert_batch_results(results_file)
        
        if choice == '4' or choice == 'all':
            print("\nStatistiques de la base de donnees...")
            db_stats = inserter.get_database_stats()
            
            print(f"\nSTATISTIQUES NEO4J:")
            print(f"   Entites: {db_stats.get('total_entities', 0)}")
            print(f"   Evenements: {db_stats.get('total_events', 0)}")
            print(f"   Relations: {db_stats.get('total_relations', 0)}")
            
            print(f"\nRépartition par labels:")
            print(f"   • Associations: {db_stats.get('associations', 0)}")
            print(f"   • Entreprises: {db_stats.get('entreprises', 0)}")
            print(f"   • Institutions: {db_stats.get('institutions', 0)}")
            print(f"   • Personnes: {db_stats.get('personnes', 0)}")
            
            print(f"\nTypes d'entites:")
            for item in db_stats.get('entity_types', [])[:5]:
                for entity_type, count in item.items():
                    print(f"   • {entity_type}: {count}")
            
            print(f"\nStyles musicaux:")
            for item in db_stats.get('music_styles', [])[:5]:
                for style, count in item.items():
                    print(f"   • {style}: {count}")
            
            print(f"\nExemples d'entités avec labels:")
            for item in db_stats.get('sample_entities', []):
                if isinstance(item, dict):
                    labels = item.get('labels', [])
                    name = item.get('name', 'Sans nom')
                    print(f"   • {name} ({', '.join(labels)})")
    
    finally:
        inserter.close()
    
    print("\nTraitement termine!")
    print("Vous pouvez maintenant explorer la base Neo4j avec Neo4j Browser")
    print("URL: http://localhost:7474")

if __name__ == "__main__":
    main()