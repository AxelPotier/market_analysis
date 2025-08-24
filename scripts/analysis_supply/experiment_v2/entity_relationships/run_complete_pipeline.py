#!/usr/bin/env python3
"""
PIPELINE COMPLET : EXTRACTION GRAPHDATA + INSERTION NEO4J
Script d'orchestration pour traiter tous les textes et créer la base Neo4j
"""

import sys
import os
import subprocess
from pathlib import Path
import argparse
from datetime import datetime
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline_complete.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def clean_text_files():
    """
    Étape 0: Nettoyage préalable des fichiers textes
    """
    print("🧹 ÉTAPE 0: NETTOYAGE DES FICHIERS TEXTES")
    print("🔧 Suppression navigation web, contenu répétitif, correction encodage")
    print("="*60)
    
    try:
        # Importer et lancer le nettoyeur
        from text_cleaner import IntelligentTextCleaner
        
        cleaner = IntelligentTextCleaner()
        input_dir = "../../../../data/data_supply/textes"
        output_dir = "../../../../data/data_supply/textes_cleaned"
        
        logger.info(f"🧹 Nettoyage: {input_dir} → {output_dir}")
        results = cleaner.clean_directory(input_dir, output_dir)
        
        # Vérifier les résultats
        successful_files = [r for r in results if r.get('success', False)]
        failed_files = [r for r in results if not r.get('success', False)]
        
        logger.info(f"✅ Nettoyage terminé: {len(successful_files)} succès, {len(failed_files)} échecs")
        
        if failed_files:
            logger.warning("⚠️ Certains fichiers n'ont pas pu être nettoyés")
            for failed in failed_files[:3]:  # Afficher les 3 premières erreurs
                logger.warning(f"   • {failed['input_file']}: {failed.get('error', 'Erreur inconnue')}")
        
        return len(successful_files) > 0
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du nettoyage: {str(e)}")
        return False

def run_batch_processing():
    """
    Étape 1: Traitement batch des fichiers textes nettoyés (avec support chunking)
    """
    print("🔄 ÉTAPE 1: TRAITEMENT BATCH DES FICHIERS TEXTES NETTOYÉS")
    print("📚 Support automatique des gros fichiers (chunking > 100k caractères)")
    print("="*60)
    
    try:
        # Modifier temporairement le processeur pour utiliser les fichiers nettoyés
        from run_batch_processor_chunked import ChunkedBatchGraphDataProcessor
        
        processor = ChunkedBatchGraphDataProcessor()
        
        # Traiter les fichiers nettoyés au lieu des originaux
        directory_path = "../../../../data/data_supply/textes_cleaned"
        results = processor.process_directory(directory_path)
        
        # Sauvegarder les résultats
        processor.save_results("batch_graphdata_chunked_results.pkl")
        
        # Afficher le résumé
        processor.print_summary()
        
        logger.info("✅ Traitement batch chunked terminé avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement batch chunked: {str(e)}")
        return False

def setup_neo4j():
    """
    Étape 2: Configuration de Neo4j (vérification et setup)
    """
    print("\\n🔧 ÉTAPE 2: CONFIGURATION NEO4J")
    print("="*60)
    
    # Vérifier si Neo4j est accessible
    try:
        from neo4j import GraphDatabase
        
        # Demander les paramètres de connexion
        neo4j_config = {
            'uri': input("URI Neo4j (défaut: bolt://localhost:7687): ") or "bolt://localhost:7687",
            'user': input("Utilisateur Neo4j (défaut: neo4j): ") or "neo4j",
            'password': input("Mot de passe Neo4j: ") or "password"
        }
        
        # Tester la connexion
        driver = GraphDatabase.driver(neo4j_config['uri'], auth=(neo4j_config['user'], neo4j_config['password']))
        with driver.session() as session:
            result = session.run("RETURN 1")
            result.single()
        driver.close()
        
        logger.info("✅ Connexion Neo4j vérifiée")
        return neo4j_config
        
    except ImportError:
        logger.error("❌ Module neo4j non installé. Installez avec: pip install neo4j")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur connexion Neo4j: {str(e)}")
        logger.info("💡 Assurez-vous que Neo4j est démarré et accessible")
        return None

def insert_into_neo4j(neo4j_config, results_file="batch_graphdata_chunked_results.pkl"):
    """
    Étape 3: Insertion des données dans Neo4j (avec labels et index unique)
    """
    print("\\n📤 ÉTAPE 3: INSERTION DANS NEO4J (AVEC LABELS)")
    print("🏷️ Utilisation de la structure optimisée : index unique sur ID + labels par type")
    print("="*60)
    
    try:
        # Importer et utiliser le nouvel inserter Neo4j avec labels (version sans IDs internes)
        from neo4j_inserter_fixed import Neo4jGraphDataInserterFixed
        
        # Initialiser l'inserter avec la nouvelle structure (IDs personnalisés uniquement)
        inserter = Neo4jGraphDataInserterFixed(**neo4j_config)
        
        if not inserter.connect():
            logger.error("❌ Impossible de se connecter à Neo4j")
            return False
        
        try:
            # 1. Créer contraintes et index (structure optimisée sans IDs internes)
            logger.info("🏗️ Création des contraintes et index (IDs personnalisés uniquement)...")
            inserter.create_constraints_and_indexes()
            
            # 2. Option de vidage (optionnel)
            clear_db = input("\\n🗑️ Vider la base de données avant insertion? (o/N): ").lower()
            if clear_db in ['o', 'oui', 'y', 'yes']:
                logger.info("🗑️ Vidage de la base de données...")
                inserter.clear_database()
            
            # 3. Insérer les données
            logger.info("📤 Insertion des données batch (IDs personnalisés uniquement)...")
            if not Path(results_file).exists():
                logger.error(f"❌ Fichier de résultats introuvable: {results_file}")
                return False
            
            success = inserter.load_and_insert_batch_results(results_file)
            
            if success:
                logger.info("✅ Insertion Neo4j terminée avec succès")
                
                # 4. Afficher les statistiques finales (structure optimisée)
                db_stats = inserter.get_database_stats()
                print("\\n📊 STATISTIQUES FINALES NEO4J (IDs PERSONNALISÉS UNIQUEMENT):")
                print(f"   🏢 Entités: {db_stats.get('total_entities', 0)}")
                print(f"   🎪 Événements: {db_stats.get('total_events', 0)}")
                print(f"   🔗 Relations: {db_stats.get('total_relations', 0)}")
                
                # Afficher la répartition par labels
                print(f"\\n🏷️ Répartition par labels (sans <elementId> ni <id> internes):")
                print(f"   • Associations: {db_stats.get('associations', 0)}")
                print(f"   • Entreprises: {db_stats.get('entreprises', 0)}")
                print(f"   • Institutions: {db_stats.get('institutions', 0)}")
                print(f"   • Personnes: {db_stats.get('personnes', 0)}")
                
                return True
            else:
                logger.error("❌ Erreurs lors de l'insertion")
                return False
                
        finally:
            inserter.close()
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'insertion Neo4j: {str(e)}")
        return False

def generate_report(neo4j_config):
    """
    Étape 4: Génération d'un rapport final
    """
    print("\\n📋 ÉTAPE 4: GÉNÉRATION DU RAPPORT FINAL")
    print("="*60)
    
    try:
        from neo4j_inserter import Neo4jGraphDataInserter
        
        inserter = Neo4jGraphDataInserter(**neo4j_config)
        if inserter.connect():
            stats = inserter.get_database_stats()
            inserter.close()
            
            # Générer un rapport HTML simple
            report_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Rapport Pipeline GraphData → Neo4j</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-box {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }}
        .queries {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎵 Rapport Pipeline GraphData → Neo4j</h1>
        <p><strong>Généré le:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Base Neo4j:</strong> {neo4j_config['uri']}</p>
    </div>
    
    <h2>📊 Statistiques de la base de données</h2>
    <div class="stats">
        <div class="stat-box">
            <h3>🏢 Entités</h3>
            <p><strong>{stats.get('total_entities', 0)}</strong> entités au total</p>
        </div>
        <div class="stat-box">
            <h3>🎪 Événements</h3>
            <p><strong>{stats.get('total_events', 0)}</strong> événements au total</p>
        </div>
        <div class="stat-box">
            <h3>🔗 Relations</h3>
            <p><strong>{stats.get('total_relations', 0)}</strong> relations au total</p>
        </div>
    </div>
    
    <h2>🚀 Accès à Neo4j</h2>
    <div class="queries">
        <p><strong>🌐 Neo4j Browser:</strong> <a href="http://localhost:7474">http://localhost:7474</a></p>
        <p><strong>📁 Fichier de requêtes:</strong> neo4j_queries.cypher</p>
        
        <h3>🔍 Requêtes utiles pour commencer:</h3>
        <pre><code>// Statistiques générales
MATCH (n) OPTIONAL MATCH ()-[r]->() 
RETURN count(DISTINCT n) as nodes, count(DISTINCT r) as relations;

// Top 10 des entités les plus connectées
MATCH (e:Entity) OPTIONAL MATCH (e)-[r]-() 
WITH e, count(r) as connections 
RETURN e.name, e.type, connections 
ORDER BY connections DESC LIMIT 10;

// Tous les événements avec organisateurs
MATCH (ev:Event) OPTIONAL MATCH (org)-[:ORGANIZES]->(ev) 
RETURN ev.name, ev.concert_style, org.name as organizer;</code></pre>
    </div>
    
    <h2>📁 Fichiers générés</h2>
    <ul>
        <li><strong>batch_graphdata_results.pkl</strong> - Données GraphData extraites</li>
        <li><strong>batch_graphdata_results.json</strong> - Version JSON lisible</li>
        <li><strong>neo4j_queries.cypher</strong> - Collection de requêtes Cypher</li>
        <li><strong>pipeline_complete.log</strong> - Log complet du traitement</li>
    </ul>
</body>
</html>
"""
            
            with open('rapport_pipeline.html', 'w', encoding='utf-8') as f:
                f.write(report_html)
            
            logger.info("✅ Rapport généré: rapport_pipeline.html")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erreur génération rapport: {str(e)}")
        return False

def main():
    """
    Pipeline principal
    """
    parser = argparse.ArgumentParser(description="Pipeline complet GraphData → Neo4j")
    parser.add_argument("--skip-extraction", action="store_true", help="Ignorer l'extraction et utiliser les données existantes")
    parser.add_argument("--skip-neo4j", action="store_true", help="Ignorer l'insertion Neo4j")
    parser.add_argument("--results-file", default="batch_graphdata_chunked_results.pkl", help="Fichier de résultats GraphData")
    
    args = parser.parse_args()
    
    print("🎵 PIPELINE COMPLET : GRAPHDATA → NEO4J")
    print("="*60)
    print(f"⏰ Début du traitement: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = datetime.now()
    
    # Étape 0: Nettoyage (sauf si explicitement ignoré)
    skip_cleaning = input("Ignorer le nettoyage des fichiers? (o/N): ").lower() in ['o', 'oui', 'y', 'yes']
    
    if not skip_cleaning:
        if not clean_text_files():
            logger.error("❌ Échec du nettoyage. Arrêt du pipeline.")
            return 1
    else:
        logger.info("⏩ Nettoyage ignoré")

    # Étape 1: Extraction GraphData
    if not args.skip_extraction:
        if not run_batch_processing():
            logger.error("❌ Échec du traitement batch. Arrêt du pipeline.")
            return 1
    else:
        logger.info("⏩ Extraction ignorée, utilisation des données existantes")
    
    # Étape 2 & 3: Neo4j
    if not args.skip_neo4j:
        neo4j_config = setup_neo4j()
        if not neo4j_config:
            logger.error("❌ Échec de la configuration Neo4j. Arrêt du pipeline.")
            return 1
        
        if not insert_into_neo4j(neo4j_config, args.results_file):
            logger.error("❌ Échec de l'insertion Neo4j.")
            return 1
        
        # Étape 4: Rapport
        generate_report(neo4j_config)
    else:
        logger.info("⏩ Insertion Neo4j ignorée")
    
    # Résumé final
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\\n" + "="*60)
    print("🎉 PIPELINE TERMINÉ AVEC SUCCÈS!")
    print("="*60)
    print(f"⏱️ Durée totale: {duration:.2f} secondes")
    print("\\n📋 Prochaines étapes:")
    print("   1. 🌐 Ouvrir Neo4j Browser: http://localhost:7474")
    print("   2. 📖 Consulter rapport_pipeline.html")
    print("   3. 🔍 Utiliser les requêtes dans neo4j_queries.cypher")
    print("   4. 📊 Explorer votre réseau musical!")
    
    return 0

if __name__ == "__main__":
    exit(main())