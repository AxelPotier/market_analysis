#!/usr/bin/env python3
"""
Analyseur d'UUIDs pour batch_graphdata_chunked_results.pkl
Analyse la structure et la validité des UUIDs dans le fichier de résultats
"""

import pickle
import json
import uuid
from collections import defaultdict, Counter
from pathlib import Path
import pandas as pd
from datetime import datetime

def is_valid_uuid(uuid_string):
    """Vérifie si une chaîne est un UUID valide"""
    if not uuid_string or not isinstance(uuid_string, str):
        return False
    try:
        uuid.UUID(uuid_string)
        return True
    except ValueError:
        return False

def analyze_uuid_patterns(uuid_list):
    """Analyse les patterns dans une liste d'UUIDs"""
    if not uuid_list:
        return {}
    
    # Analyser les versions d'UUID
    versions = Counter()
    variants = Counter()
    
    for uuid_str in uuid_list:
        if is_valid_uuid(uuid_str):
            try:
                uuid_obj = uuid.UUID(uuid_str)
                versions[uuid_obj.version] += 1
                variants[uuid_obj.variant] += 1
            except:
                pass
    
    return {
        'versions': dict(versions),
        'variants': dict(variants)
    }

def analyze_batch_results(file_path="batch_graphdata_chunked_results.pkl"):
    """Analyse complète des UUIDs dans le fichier de résultats"""
    
    print("🔍 ANALYSE DES UUIDs DANS LES DONNÉES BATCH")
    print("="*60)
    
    # Charger les données
    try:
        with open(file_path, 'rb') as f:
            data = pickle.load(f)
        print(f"✅ Fichier chargé: {len(data)} éléments")
    except Exception as e:
        print(f"❌ Erreur chargement: {e}")
        return
    
    # Statistiques générales
    stats = {
        'total_files': len(data),
        'entities_total': 0,
        'events_total': 0,
        'relations_total': 0,
        'entities_with_uuid': 0,
        'entities_with_id': 0,
        'entities_with_both': 0,
        'events_with_uuid': 0,
        'events_with_id': 0,
        'events_with_both': 0,
        'relations_with_new_format': 0,
        'relations_with_old_format': 0,
        'uuid_issues': [],
        'duplicate_uuids': defaultdict(list),
        'all_entity_uuids': [],
        'all_event_uuids': [],
        'all_relation_source_uuids': [],
        'all_relation_target_uuids': [],
        'files_analysis': []
    }
    
    print("\n📊 Analyse détaillée par fichier...")
    
    for i, item in enumerate(data):
        file_name = item.get('file_name', f'file_{i}')
        file_analysis = {
            'file_name': file_name,
            'entities_count': 0,
            'events_count': 0,
            'relations_count': 0,
            'uuid_format_consistency': 'unknown',
            'issues': []
        }
        
        # Analyser les entités
        entities = item.get('entities', [])
        file_analysis['entities_count'] = len(entities)
        stats['entities_total'] += len(entities)
        
        for entity in entities:
            has_uuid = 'uuid' in entity and entity['uuid']
            has_id = 'id' in entity and entity['id']
            
            if has_uuid and has_id:
                stats['entities_with_both'] += 1
                if entity['uuid'] != entity['id']:
                    file_analysis['issues'].append(f"Entité {entity.get('name', 'unknown')}: uuid != id")
            elif has_uuid:
                stats['entities_with_uuid'] += 1
                stats['all_entity_uuids'].append(entity['uuid'])
            elif has_id:
                stats['entities_with_id'] += 1
                stats['all_entity_uuids'].append(entity['id'])
            
            # Vérifier la validité des UUIDs
            uuid_field = entity.get('uuid', entity.get('id'))
            if uuid_field:
                if not is_valid_uuid(uuid_field):
                    stats['uuid_issues'].append(f"UUID invalide dans {file_name}: {uuid_field}")
                else:
                    # Tracker les doublons
                    stats['duplicate_uuids'][uuid_field].append(f"{file_name}:entity:{entity.get('name', 'unknown')}")
        
        # Analyser les événements
        events = item.get('events', [])
        file_analysis['events_count'] = len(events)
        stats['events_total'] += len(events)
        
        for event in events:
            has_uuid = 'uuid' in event and event['uuid']
            has_id = 'id' in event and event['id']
            
            if has_uuid and has_id:
                stats['events_with_both'] += 1
                if event['uuid'] != event['id']:
                    file_analysis['issues'].append(f"Événement {event.get('name', 'unknown')}: uuid != id")
            elif has_uuid:
                stats['events_with_uuid'] += 1
                stats['all_event_uuids'].append(event['uuid'])
            elif has_id:
                stats['events_with_id'] += 1
                stats['all_event_uuids'].append(event['id'])
            
            # Vérifier la validité des UUIDs
            uuid_field = event.get('uuid', event.get('id'))
            if uuid_field:
                if not is_valid_uuid(uuid_field):
                    stats['uuid_issues'].append(f"UUID invalide dans {file_name}: {uuid_field}")
                else:
                    stats['duplicate_uuids'][uuid_field].append(f"{file_name}:event:{event.get('name', 'unknown')}")
        
        # Analyser les relations
        relations = item.get('relations', [])
        file_analysis['relations_count'] = len(relations)
        stats['relations_total'] += len(relations)
        
        new_format_count = 0
        old_format_count = 0
        
        for relation in relations:
            has_new_format = 'source_uuid' in relation and 'target_uuid' in relation
            has_old_format = 'source_id' in relation and 'target_id' in relation
            
            if has_new_format:
                new_format_count += 1
                stats['all_relation_source_uuids'].append(relation['source_uuid'])
                stats['all_relation_target_uuids'].append(relation['target_uuid'])
                
                # Vérifier validité
                if not is_valid_uuid(relation['source_uuid']):
                    stats['uuid_issues'].append(f"source_uuid invalide dans {file_name}: {relation['source_uuid']}")
                if not is_valid_uuid(relation['target_uuid']):
                    stats['uuid_issues'].append(f"target_uuid invalide dans {file_name}: {relation['target_uuid']}")
                    
            if has_old_format:
                old_format_count += 1
            
            if has_new_format and has_old_format:
                # Vérifier cohérence
                if relation['source_uuid'] != relation['source_id']:
                    file_analysis['issues'].append("Relation: source_uuid != source_id")
                if relation['target_uuid'] != relation['target_id']:
                    file_analysis['issues'].append("Relation: target_uuid != target_id")
        
        stats['relations_with_new_format'] += new_format_count
        stats['relations_with_old_format'] += old_format_count
        
        # Déterminer la cohérence du format
        if new_format_count > old_format_count:
            file_analysis['uuid_format_consistency'] = 'nouveau_format'
        elif old_format_count > new_format_count:
            file_analysis['uuid_format_consistency'] = 'ancien_format'
        else:
            file_analysis['uuid_format_consistency'] = 'mixte'
        
        stats['files_analysis'].append(file_analysis)
        
        if i < 5 or len(file_analysis['issues']) > 0:
            print(f"  📄 {file_name}: {file_analysis['entities_count']} entités, {file_analysis['events_count']} événements, {file_analysis['relations_count']} relations - Format: {file_analysis['uuid_format_consistency']}")
            if file_analysis['issues']:
                for issue in file_analysis['issues'][:3]:  # Max 3 issues par fichier
                    print(f"    ⚠️  {issue}")
    
    # Analyse des doublons
    duplicates = {k: v for k, v in stats['duplicate_uuids'].items() if len(v) > 1}
    
    # Analyse des patterns UUID
    entity_patterns = analyze_uuid_patterns(stats['all_entity_uuids'])
    event_patterns = analyze_uuid_patterns(stats['all_event_uuids'])
    
    # Affichage des résultats
    print("\n" + "="*60)
    print("📈 RÉSULTATS DE L'ANALYSE")
    print("="*60)
    
    print(f"📁 Fichiers analysés: {stats['total_files']}")
    print(f"👥 Total entités: {stats['entities_total']}")
    print(f"🎪 Total événements: {stats['events_total']}")
    print(f"🔗 Total relations: {stats['relations_total']}")
    
    print(f"\n📋 ÉTAT DES CHAMPS UUID/ID:")
    print(f"  Entités avec UUID: {stats['entities_with_uuid']}")
    print(f"  Entités avec ID: {stats['entities_with_id']}")
    print(f"  Entités avec les deux: {stats['entities_with_both']}")
    print(f"  Événements avec UUID: {stats['events_with_uuid']}")
    print(f"  Événements avec ID: {stats['events_with_id']}")
    print(f"  Événements avec les deux: {stats['events_with_both']}")
    print(f"  Relations nouveau format: {stats['relations_with_new_format']}")
    print(f"  Relations ancien format: {stats['relations_with_old_format']}")
    
    print(f"\n🔍 QUALITÉ DES UUID:")
    print(f"  UUIDs invalides: {len(stats['uuid_issues'])}")
    print(f"  UUIDs dupliqués: {len(duplicates)}")
    
    if stats['uuid_issues']:
        print(f"\n❌ PROBLÈMES D'UUID (premiers 10):")
        for issue in stats['uuid_issues'][:10]:
            print(f"    • {issue}")
    
    if duplicates:
        print(f"\n🔄 UUIDS DUPLIQUÉS (premiers 5):")
        for uuid_val, locations in list(duplicates.items())[:5]:
            print(f"    • {uuid_val}: {len(locations)} occurrences")
            for loc in locations[:3]:
                print(f"      - {loc}")
    
    print(f"\n📊 PATTERNS UUID ENTITÉS:")
    if entity_patterns.get('versions'):
        print(f"  Versions: {entity_patterns['versions']}")
    
    print(f"\n📊 PATTERNS UUID ÉVÉNEMENTS:")
    if event_patterns.get('versions'):
        print(f"  Versions: {event_patterns['versions']}")
    
    # Format consistency summary
    format_summary = Counter(f['uuid_format_consistency'] for f in stats['files_analysis'])
    print(f"\n🎯 COHÉRENCE DU FORMAT:")
    for format_type, count in format_summary.items():
        percentage = (count / len(stats['files_analysis'])) * 100
        print(f"  {format_type}: {count} fichiers ({percentage:.1f}%)")
    
    # Sauvegarder l'analyse détaillée
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"uuid_analysis_report_{timestamp}.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        # Préparer les données pour JSON (enlever les defaultdict)
        json_stats = {
            'analysis_timestamp': datetime.now().isoformat(),
            'file_analyzed': file_path,
            'summary': {
                'total_files': stats['total_files'],
                'entities_total': stats['entities_total'],
                'events_total': stats['events_total'],
                'relations_total': stats['relations_total'],
                'entities_with_uuid': stats['entities_with_uuid'],
                'entities_with_id': stats['entities_with_id'],
                'entities_with_both': stats['entities_with_both'],
                'events_with_uuid': stats['events_with_uuid'],
                'events_with_id': stats['events_with_id'],
                'events_with_both': stats['events_with_both'],
                'relations_with_new_format': stats['relations_with_new_format'],
                'relations_with_old_format': stats['relations_with_old_format'],
                'uuid_issues_count': len(stats['uuid_issues']),
                'duplicates_count': len(duplicates)
            },
            'uuid_issues': stats['uuid_issues'][:50],  # Limiter à 50
            'duplicates': {k: v for k, v in list(duplicates.items())[:20]},  # Limiter à 20
            'entity_patterns': entity_patterns,
            'event_patterns': event_patterns,
            'format_consistency': dict(format_summary),
            'files_analysis': stats['files_analysis']
        }
        
        json.dump(json_stats, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Rapport détaillé sauvegardé: {report_file}")
    
    # Recommandations
    print(f"\n🎯 RECOMMANDATIONS:")
    
    if stats['entities_with_id'] > stats['entities_with_uuid']:
        print("  ⚠️  Beaucoup d'entités utilisent encore 'id' au lieu de 'uuid'")
        print("     → Exécuter le remapping des UUIDs")
    
    if stats['relations_with_old_format'] > stats['relations_with_new_format']:
        print("  ⚠️  Beaucoup de relations utilisent l'ancien format")
        print("     → Exécuter le remapping des UUIDs")
    
    if len(duplicates) > 0:
        print("  ⚠️  UUIDs dupliqués détectés")
        print("     → Vérifier la logique de génération d'UUID")
    
    if len(stats['uuid_issues']) > 0:
        print("  ❌  UUIDs invalides détectés")
        print("     → Nettoyer les données avec validate_and_fix_data()")
    
    if len(duplicates) == 0 and len(stats['uuid_issues']) == 0 and stats['entities_with_uuid'] > stats['entities_with_id']:
        print("  ✅  Données UUID en bon état!")
        print("     → Prêt pour l'insertion Neo4j")

if __name__ == "__main__":
    analyze_batch_results()