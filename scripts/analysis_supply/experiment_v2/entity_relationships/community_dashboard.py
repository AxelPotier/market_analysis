import streamlit as st
import pickle
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import plotly.express as px
from collections import Counter, defaultdict
import numpy as np
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime
import re
import tempfile
import os
import json

# Imports pour les nouvelles visualisations
try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

try:
    from streamlit_agraph import agraph, Node, Edge, Config
    AGRAPH_AVAILABLE = True
except ImportError:
    AGRAPH_AVAILABLE = False

try:
    from streamlit_echarts import st_echarts
    ECHARTS_AVAILABLE = True
except ImportError:
    ECHARTS_AVAILABLE = False

try:
    import graphviz
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False

try:
    from streamlit_vis_network import vis_network
    VIS_NETWORK_AVAILABLE = True
except ImportError:
    VIS_NETWORK_AVAILABLE = False

try:
    from streamlit_cytoscape import cytoscape
    CYTOSCAPE_AVAILABLE = True
except ImportError:
    CYTOSCAPE_AVAILABLE = False

import streamlit.components.v1 as components

# Configuration de la page
st.set_page_config(
    page_title="Dashboard Communauté Musicale",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data
def load_data():
    """Charge et traite les données du fichier pickle avec nouveau format"""
    try:
        with open('scripts/analysis_supply/experiment_v2/entity_relationships/batch_graphdata_chunked_results.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # with open("dataset_cleaned_for_neo4j_dashboard.json", "r", encoding="utf-8") as f:
        #     data = json.load(f)
        
        # Agrégation de toutes les données avec gestion des métadonnées
        all_entities = []
        all_relations = []
        all_events = []
        processing_stats = {
            'total_files': 0,
            'chunked_files': 0,
            'direct_files': 0,
            'total_chunks': 0,
            'file_sources': []
        }
        
        filtered_files = []
        
        for item in data:
            if isinstance(item, dict):
                # Filtrer les fichiers problématiques (rapports JSON)
                file_name = item.get('file_name', 'Unknown')
                
                # Exclure les fichiers de rapport et de nettoyage
                if any(pattern in file_name.lower() for pattern in [
                    'cleaning_report', 'rapport', 'report', '_report_', 
                    '.json', 'analyze', 'analysis', 'suspicious', 'duplicat'
                ]):
                    filtered_files.append(file_name)
                    continue
                
                # Collecter les statistiques de traitement
                processing_stats['total_files'] += 1
                processing_method = item.get('processing_method', 'unknown')
                if processing_method == 'chunked':
                    processing_stats['chunked_files'] += 1
                    processing_stats['total_chunks'] += item.get('chunks_processed', 0)
                elif processing_method == 'direct':
                    processing_stats['direct_files'] += 1
                
                # Ajouter info sur le fichier source
                file_info = {
                    'file_name': file_name,
                    'text_length': item.get('text_length', 0),
                    'processing_method': processing_method,
                    'processed_at': item.get('processed_at', ''),
                    'chunks_processed': item.get('chunks_processed', 0)
                }
                processing_stats['file_sources'].append(file_info)
                
                # Déduplication des entités par UUID
                entities = item.get('entities', [])
                for entity in entities:
                    # Vérifier si l'entité existe déjà (par UUID)
                    entity_uuid = entity.get('uuid', entity.get('id'))  # Compatibilité
                    entity_name = entity.get('name', '')
                    
                    # Exclure les entités avec des noms suspects (outils de nettoyage, etc.)
                    if any(pattern in entity_name.lower() for pattern in [
                        'système de nettoyage', 'cleaning', 'rapport', 'analyzer', 
                        'tool', 'script', 'processor', 'outil'
                    ]):
                        continue
                    
                    if entity_uuid and not any(e.get('uuid', e.get('id')) == entity_uuid for e in all_entities):
                        # Ajouter métadonnées source
                        entity_with_source = entity.copy()
                        entity_with_source['uuid'] = entity_uuid  # S'assurer que uuid existe
                        entity_with_source['source_file'] = file_name
                        entity_with_source['processing_method'] = processing_method
                        all_entities.append(entity_with_source)
                
                # Déduplication des événements par UUID
                events = item.get('events', [])
                for event in events:
                    event_uuid = event.get('uuid', event.get('id'))  # Compatibilité
                    event_name = event.get('name', '')
                    
                    # Exclure les événements avec des noms suspects
                    if any(pattern in event_name.lower() for pattern in [
                        'cleaning', 'rapport', 'analyzer', 'tool', 'script', 
                        'processor', 'nettoyage', 'analyse'
                    ]):
                        continue
                    
                    if event_uuid and not any(e.get('uuid', e.get('id')) == event_uuid for e in all_events):
                        # Ajouter métadonnées source
                        event_with_source = event.copy()
                        event_with_source['uuid'] = event_uuid  # S'assurer que uuid existe
                        event_with_source['source_file'] = file_name
                        event_with_source['processing_method'] = processing_method
                        all_events.append(event_with_source)
                
                # Déduplication des relations (plus complexe car pas d'UUID unique)
                relations = item.get('relations', [])
                for relation in relations:
                    # Vérifier que les UUIDs source et target existent dans nos entités valides
                    source_uuid = relation.get('source_uuid', relation.get('source_id', ''))  # Compatibilité
                    target_uuid = relation.get('target_uuid', relation.get('target_id', ''))  # Compatibilité
                    
                    # Vérifier que les entités source et target existent et sont valides
                    source_valid = any(e.get('uuid', e.get('id')) == source_uuid for e in all_entities)
                    target_valid = any(e.get('uuid', e.get('id')) == target_uuid for e in all_entities)
                    
                    if not (source_valid and target_valid):
                        continue
                    
                    # Créer une clé unique pour la relation
                    relation_key = f"{source_uuid}_{target_uuid}_{relation.get('relation_type', '')}"
                    if not any(f"{r.get('source_uuid', r.get('source_id', ''))}_{r.get('target_uuid', r.get('target_id', ''))}_{r.get('relation_type', '')}" == relation_key for r in all_relations):
                        # Ajouter métadonnées source
                        relation_with_source = relation.copy()
                        relation_with_source['source_uuid'] = source_uuid  # S'assurer que source_uuid existe
                        relation_with_source['target_uuid'] = target_uuid  # S'assurer que target_uuid existe
                        relation_with_source['source_file'] = file_name
                        relation_with_source['processing_method'] = processing_method
                        all_relations.append(relation_with_source)
        
        # Stocker les statistiques dans le cache pour usage ultérieur
        processing_stats['filtered_files'] = filtered_files
        st.session_state['processing_stats'] = processing_stats
        
        return all_entities, all_relations, all_events
    except Exception as e:
        st.error(f"Erreur lors du chargement des données: {e}")
        return [], [], []

def create_network_graph(entities, relations, selected_types=None):
    """Crée un graphe de réseau avec NetworkX et Plotly"""
    G = nx.Graph()
    
    # Filtrer les entités selon les types sélectionnés
    if selected_types:
        filtered_entities = [e for e in entities if e.get('type') in selected_types]
    else:
        filtered_entities = entities
    
    entity_uuids = {e.get('uuid', e.get('id')) for e in filtered_entities}
    
    # Ajouter les nœuds
    for entity in filtered_entities:
        entity_uuid = entity.get('uuid', entity.get('id'))
        G.add_node(
            entity_uuid,
            name=entity.get('name', 'Sans nom'),
            type=entity.get('type', 'autre'),
            description=entity.get('description', ''),
            intentions=entity.get('intentions', [])
        )
    
    # Ajouter les arêtes
    for relation in relations:
        source = relation.get('source_uuid', relation.get('source_id'))
        target = relation.get('target_uuid', relation.get('target_id'))
        if source in entity_uuids and target in entity_uuids:
            G.add_edge(source, target, 
                      relation_type=relation.get('relation_type', ''),
                      description=relation.get('description', ''))
    
    if len(G.nodes()) == 0:
        return go.Figure()
    
    # Positionnement des nœuds
    pos = nx.spring_layout(G, k=1, iterations=50)
    
    # Couleurs par type d'entité
    color_map = {
        'association': '#FF6B6B',
        'entreprise': '#4ECDC4',
        'institution': '#45B7D1',
        'personne': '#96CEB4',
        'autre': '#FFEAA7'
    }
    
    # Préparation des données pour Plotly
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_size = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        node_info = G.nodes[node]
        node_text.append(f"{node_info['name']}<br>Type: {node_info['type']}<br>Connexions: {len(list(G.neighbors(node)))}")
        node_color.append(color_map.get(node_info['type'], '#FFEAA7'))
        node_size.append(max(10, len(list(G.neighbors(node))) * 5))
    
    # Création du graphique Plotly
    fig = go.Figure()
    
    # Arêtes
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines'
    ))
    
    # Nœuds
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        text=node_text,
        marker=dict(
            size=node_size,
            color=node_color,
            line=dict(width=2, color='white')
        )
    ))
    
    fig.update_layout(
        title="Réseau des Entités",
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20,l=5,r=5,t=40),
        annotations=[ dict(
            text="Cliquez et faites glisser pour explorer le réseau",
            showarrow=False,
            xref="paper", yref="paper",
            x=0.005, y=-0.002,
            xanchor='left', yanchor='bottom',
            font=dict(color="gray", size=12)
        )],
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=600
    )
    
    return fig

def create_pyvis_network(entities, relations, selected_types=None):
    """Crée un réseau interactif avec Pyvis"""
    if not PYVIS_AVAILABLE:
        st.error("⚠️ Pyvis n'est pas installé. Installez-le avec: pip install pyvis")
        return None
    
    # Filtrer les entités selon les types sélectionnés
    if selected_types:
        filtered_entities = [e for e in entities if e.get('type') in selected_types]
    else:
        filtered_entities = entities
    
    entity_uuids = {e.get('uuid', e.get('id')) for e in filtered_entities}
    
    if len(filtered_entities) == 0:
        return None
    
    # Créer le réseau Pyvis
    net = Network(
        height="600px", 
        width="100%", 
        bgcolor="#ffffff", 
        font_color="black",
        directed=False
    )
    
    # Configuration de la physique pour une meilleure interaction
    net.set_options("""
    var options = {
      "physics": {
        "enabled": true,
        "stabilization": {"iterations": 100},
        "barnesHut": {
          "gravitationalConstant": -80000,
          "springConstant": 0.001,
          "springLength": 200
        }
      }
    }
    """)
    
    # Couleurs par type d'entité
    color_map = {
        'association': '#FF6B6B',
        'entreprise': '#4ECDC4', 
        'institution': '#45B7D1',
        'personne': '#96CEB4',
        'autre': '#FFEAA7'
    }
    
    # Ajouter les nœuds
    for entity in filtered_entities:
        entity_uuid = entity.get('uuid', entity.get('id'))
        entity_name = entity.get('name', 'Sans nom')
        entity_type = entity.get('type', 'autre')
        intentions = entity.get('intentions', [])
        source_file = entity.get('source_file', 'Unknown')
        
        # Taille basée sur le nombre de connexions
        connections = sum(1 for r in relations 
                         if r.get('source_uuid', r.get('source_id')) == entity_uuid or r.get('target_uuid', r.get('target_id')) == entity_uuid)
        
        # Tooltip avec informations détaillées
        tooltip = f"""
        <b>{entity_name}</b><br>
        Type: {entity_type}<br>
        Connexions: {connections}<br>
        Source: {source_file}<br>
        Intentions: {'; '.join(intentions[:3])}{'...' if len(intentions) > 3 else ''}
        """
        
        net.add_node(
            entity_uuid,
            label=entity_name,
            color=color_map.get(entity_type, '#FFEAA7'),
            size=max(20, connections * 3),
            title=tooltip,
            font={'size': 14}
        )
    
    # Ajouter les arêtes
    for relation in relations:
        source = relation.get('source_uuid', relation.get('source_id'))
        target = relation.get('target_uuid', relation.get('target_id'))
        if source in entity_uuids and target in entity_uuids:
            relation_type = relation.get('relation_type', '')
            description = relation.get('description', '')
            
            # Couleur selon le type de relation
            edge_colors = {
                'collaboration': '#FF6B6B',
                'intention': '#4ECDC4',
                'événement': '#45B7D1',
                'appartenance': '#96CEB4',
                'autre': '#CCCCCC'
            }
            
            net.add_edge(
                source, 
                target,
                color=edge_colors.get(relation_type, '#CCCCCC'),
                title=f"{relation_type}: {description}",
                width=2
            )
    
    return net

def create_agraph_network(entities, relations, selected_types=None):
    """Crée un réseau avec Streamlit-Agraph"""
    if not AGRAPH_AVAILABLE:
        st.error("⚠️ Streamlit-Agraph n'est pas installé. Installez-le avec: pip install streamlit-agraph")
        return None, None
    
    # Filtrer les entités selon les types sélectionnés
    if selected_types:
        filtered_entities = [e for e in entities if e.get('type') in selected_types]
    else:
        filtered_entities = entities
    
    entity_uuids = {e.get('uuid', e.get('id')) for e in filtered_entities}
    
    if len(filtered_entities) == 0:
        return [], []
    
    # Couleurs par type d'entité
    color_map = {
        'association': '#FF6B6B',
        'entreprise': '#4ECDC4',
        'institution': '#45B7D1', 
        'personne': '#96CEB4',
        'autre': '#FFEAA7'
    }
    
    # Créer les nœuds
    nodes = []
    for entity in filtered_entities:
        entity_uuid = entity.get('uuid', entity.get('id'))
        entity_name = entity.get('name', 'Sans nom')
        entity_type = entity.get('type', 'autre')
        intentions = entity.get('intentions', [])
        
        # Compter les connexions
        connections = sum(1 for r in relations 
                         if r.get('source_uuid', r.get('source_id')) == entity_uuid or r.get('target_uuid', r.get('target_id')) == entity_uuid)
        
        nodes.append(Node(
            id=entity_uuid,
            label=entity_name,
            size=max(20, connections * 2),
            color=color_map.get(entity_type, '#FFEAA7'),
            title=f"{entity_name} ({entity_type})"
        ))
    
    # Créer les arêtes
    edges = []
    for relation in relations:
        source = relation.get('source_uuid', relation.get('source_id'))
        target = relation.get('target_uuid', relation.get('target_id'))
        if source in entity_uuids and target in entity_uuids:
            relation_type = relation.get('relation_type', '')
            
            # Couleur selon le type de relation
            edge_colors = {
                'collaboration': '#FF6B6B',
                'intention': '#4ECDC4',
                'événement': '#45B7D1',
                'appartenance': '#96CEB4',
                'autre': '#CCCCCC'
            }
            
            edges.append(Edge(
                source=source,
                target=target,
                color=edge_colors.get(relation_type, '#CCCCCC'),
                width=2
            ))
    
    # Configuration
    config = Config(
        width=800,
        height=600,
        directed=False,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=False,
        node={'labelProperty': 'label'},
        link={'labelProperty': 'label', 'renderLabel': True}
    )
    
    return nodes, edges, config

def analyze_intentions(entities):
    """Analyse les intentions des entités"""
    all_intentions = []
    intentions_by_type = defaultdict(list)
    
    for entity in entities:
        intentions = entity.get('intentions', [])
        entity_type = entity.get('type', 'autre')
        
        for intention in intentions:
            all_intentions.append(intention)
            intentions_by_type[entity_type].append(intention)
    
    return all_intentions, intentions_by_type

def create_wordcloud(intentions):
    """Crée un nuage de mots des intentions avec filtrage des stop words"""
    if not intentions:
        return None
    
    # Définir les stop words français et anglais
    french_stop_words = {
        'le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir', 'que', 'pour',
        'dans', 'ce', 'son', 'une', 'sur', 'avec', 'ne', 'se', 'pas', 'tout', 'plus',
        'par', 'grand', 'me', 'même', 'te', 'si', 'leur', 'dire', 'elle', 'ou', 'où',
        'nous', 'vous', 'la', 'les', 'des', 'du', 'au', 'aux', 'cette', 'ces',
        'celui', 'celle', 'ceux', 'celles', 'dont', 'donc', 'très', 'bien', 'encore',
        'comme', 'sans', 'sous', 'entre', 'après', 'avant', 'depuis', 'pendant',
        'mais', 'car', 'parce', 'lorsque', 'quand', 'alors', 'aussi', 'ainsi',
        'être', 'avoir', 'faire', 'aller', 'venir', 'voir', 'savoir', 'pouvoir',
        'vouloir', 'devoir', 'dire', 'prendre', 'donner', 'mettre', 'tenir',
        'premier', 'dernier', 'nouveau', 'grand', 'petit', 'gros', 'bon', 'mauvais'
    }
    
    english_stop_words = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
        'above', 'below', 'between', 'among', 'under', 'over', 'is', 'are', 'was',
        'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'cannot',
        'this', 'that', 'these', 'those', 'a', 'an', 'as', 'if', 'when', 'where',
        'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
        'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
        'too', 'very', 'get', 'go', 'come', 'take', 'give', 'make', 'know', 'think',
        'see', 'want', 'use', 'find', 'work', 'call', 'try', 'ask', 'need', 'feel',
        'become', 'leave', 'put', 'mean', 'keep', 'let', 'begin', 'seem', 'help',
        'talk', 'turn', 'start', 'show', 'hear', 'play', 'run', 'move', 'live',
        'believe', 'hold', 'bring', 'happen', 'write', 'provide', 'sit', 'stand',
        'lose', 'pay', 'meet', 'include', 'continue', 'set', 'learn', 'change',
        'lead', 'understand', 'watch', 'follow', 'stop', 'create', 'speak', 'read'
    }
    
    # Mots spécifiques au contexte musical/culturel à filtrer
    context_stop_words = {
        'music', 'musique', 'musical', 'musicale', 'musicaux', 'musicales',
        'culture', 'culturel', 'culturelle', 'culturels', 'culturelles',
        'association', 'groupe', 'band', 'concert', 'événement', 'event',
        'artiste', 'artist', 'scene', 'scène', 'production', 'festival',
        'organisation', 'organization', 'organiser', 'organize'
    }
    
    # Combiner tous les stop words
    all_stop_words = french_stop_words.union(english_stop_words).union(context_stop_words)
    
    text = ' '.join(intentions)
    wordcloud = WordCloud(
        width=800, height=400,
        background_color='white',
        colormap='viridis',
        max_words=100,
        stopwords=all_stop_words,
        collocations=False,  # Éviter les répétitions de mots identiques
        min_font_size=10,
        max_font_size=80,
        relative_scaling=0.5,
        min_word_length=3  # Mots d'au moins 3 caractères
    ).generate(text)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    return fig

def create_echarts_network(entities, relations, selected_types=None):
    """Crée un réseau interactif avec ECharts"""
    if not ECHARTS_AVAILABLE:
        st.error("⚠️ streamlit-echarts n'est pas installé. Installez-le avec: pip install streamlit-echarts")
        return None
    
    # Filtrer les entités selon les types sélectionnés
    if selected_types:
        filtered_entities = [e for e in entities if e.get('type') in selected_types]
    else:
        filtered_entities = entities
    
    entity_uuids = {e.get('uuid', e.get('id')) for e in filtered_entities}
    
    if len(filtered_entities) == 0:
        return None
    
    # Couleurs par type
    color_map = {
        'association': '#FF6B6B',
        'entreprise': '#4ECDC4',
        'institution': '#45B7D1',
        'personne': '#96CEB4',
        'autre': '#FFEAA7'
    }
    
    # Créer les nœuds
    nodes = []
    categories = []
    category_names = set()
    
    for entity in filtered_entities:
        entity_uuid = entity.get('uuid', entity.get('id'))
        entity_type = entity.get('type', 'autre')
        
        if entity_type not in category_names:
            categories.append({
                "name": entity_type,
                "itemStyle": {"color": color_map.get(entity_type, '#FFEAA7')}
            })
            category_names.add(entity_type)
        
        # Calculer la taille basée sur les connexions
        connections = sum(1 for r in relations 
                         if r.get('source_uuid', r.get('source_id')) == entity_uuid or 
                            r.get('target_uuid', r.get('target_id')) == entity_uuid)
        
        nodes.append({
            "id": entity_uuid,
            "name": entity.get('name', 'Sans nom'),
            "category": entity_type,
            "value": max(20, connections * 5),
            "symbolSize": max(20, connections * 3),
            "itemStyle": {"color": color_map.get(entity_type, '#FFEAA7')}
        })
    
    # Créer les liens
    links = []
    for relation in relations:
        source_uuid = relation.get('source_uuid', relation.get('source_id'))
        target_uuid = relation.get('target_uuid', relation.get('target_id'))
        
        if source_uuid in entity_uuids and target_uuid in entity_uuids:
            links.append({
                "source": source_uuid,
                "target": target_uuid,
                "value": relation.get('relation_type', ''),
                "lineStyle": {"width": 2, "opacity": 0.6}
            })
    
    option = {
        "title": {
            "text": "Réseau Communauté Musicale",
            "left": "center",
            "textStyle": {"fontSize": 16}
        },
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}<br/>Type: {c}<br/>Connexions: {c}"
        },
        "legend": {
            "orient": "horizontal",
            "bottom": "5%",
            "data": [cat["name"] for cat in categories]
        },
        "series": [{
            "name": "Réseau Musical",
            "type": "graph",
            "layout": "force",
            "data": nodes,
            "links": links,
            "categories": categories,
            "roam": True,
            "focusNodeAdjacency": True,
            "draggable": True,
            "force": {
                "repulsion": 4000,
                "edgeLength": [50, 200],
                "gravity": 0.1
            },
            "emphasis": {
                "focus": "adjacency"
            },
            "lineStyle": {
                "color": "source"
            }
        }]
    }
    
    return st_echarts(options=option, height="600px", key="echarts_network")

def create_graphviz_network(entities, relations, selected_types=None):
    """Crée un réseau avec Graphviz"""
    if not GRAPHVIZ_AVAILABLE:
        st.error("⚠️ graphviz n'est pas installé. Installez-le avec: pip install graphviz")
        return None
    
    # Filtrer les entités selon les types sélectionnés
    if selected_types:
        filtered_entities = [e for e in entities if e.get('type') in selected_types]
    else:
        filtered_entities = entities
    
    entity_uuids = {e.get('uuid', e.get('id')) for e in filtered_entities}
    
    if len(filtered_entities) == 0:
        return None
    
    # Couleurs par type
    color_map = {
        'association': 'lightcoral',
        'entreprise': 'lightblue',
        'institution': 'lightgreen',
        'personne': 'lightyellow',
        'autre': 'lightgray'
    }
    
    # Sélection du layout
    layout_engine = st.selectbox(
        "Layout Graphviz",
        ["dot", "neato", "fdp", "sfdp", "circo", "twopi"],
        key="graphviz_layout"
    )
    
    dot = graphviz.Digraph(engine=layout_engine)
    dot.attr(rankdir='TB', size='12,8', dpi='300')
    
    # Ajouter les nœuds
    for entity in filtered_entities:
        entity_uuid = entity.get('uuid', entity.get('id'))
        entity_name = entity.get('name', 'Sans nom')
        entity_type = entity.get('type', 'autre')
        
        # Tronquer le nom si trop long
        display_name = entity_name[:20] + "..." if len(entity_name) > 20 else entity_name
        
        dot.node(
            entity_uuid, 
            display_name,
            color=color_map.get(entity_type, 'lightgray'),
            style='filled',
            shape='ellipse'
        )
    
    # Ajouter les arêtes
    for relation in relations:
        source_uuid = relation.get('source_uuid', relation.get('source_id'))
        target_uuid = relation.get('target_uuid', relation.get('target_id'))
        
        if source_uuid in entity_uuids and target_uuid in entity_uuids:
            relation_type = relation.get('relation_type', '')
            dot.edge(source_uuid, target_uuid, label=relation_type[:10])
    
    return st.graphviz_chart(dot.source, use_container_width=True)

def create_vis_network(entities, relations, selected_types=None):
    """Crée un réseau avec vis-network"""
    if not VIS_NETWORK_AVAILABLE:
        st.error("⚠️ streamlit-vis-network n'est pas installé. Installez-le avec: pip install streamlit-vis-network")
        return None
    
    # Filtrer les entités selon les types sélectionnés
    if selected_types:
        filtered_entities = [e for e in entities if e.get('type') in selected_types]
    else:
        filtered_entities = entities
    
    entity_uuids = {e.get('uuid', e.get('id')) for e in filtered_entities}
    
    if len(filtered_entities) == 0:
        return None
    
    # Couleurs par type
    color_map = {
        'association': '#FF6B6B',
        'entreprise': '#4ECDC4',
        'institution': '#45B7D1',
        'personne': '#96CEB4',
        'autre': '#FFEAA7'
    }
    
    # Créer les nœuds
    nodes = []
    for entity in filtered_entities:
        entity_uuid = entity.get('uuid', entity.get('id'))
        entity_name = entity.get('name', 'Sans nom')
        entity_type = entity.get('type', 'autre')
        
        # Calculer la taille basée sur les connexions
        connections = sum(1 for r in relations 
                         if r.get('source_uuid', r.get('source_id')) == entity_uuid or 
                            r.get('target_uuid', r.get('target_id')) == entity_uuid)
        
        nodes.append({
            "id": entity_uuid,
            "label": entity_name,
            "color": color_map.get(entity_type, '#FFEAA7'),
            "size": max(20, connections * 3),
            "title": f"{entity_name}<br>Type: {entity_type}<br>Connexions: {connections}",
            "group": entity_type
        })
    
    # Créer les arêtes
    edges = []
    for relation in relations:
        source_uuid = relation.get('source_uuid', relation.get('source_id'))
        target_uuid = relation.get('target_uuid', relation.get('target_id'))
        
        if source_uuid in entity_uuids and target_uuid in entity_uuids:
            edges.append({
                "from": source_uuid,
                "to": target_uuid,
                "title": relation.get('relation_type', ''),
                "arrows": "to"
            })
    
    return vis_network(
        nodes, 
        edges, 
        height="600px",
        physics=True,
        interaction={"hover": True, "selectConnectedEdges": True},
        options={
            "physics": {
                "enabled": True,
                "stabilization": {"iterations": 100}
            }
        }
    )

def create_cytoscape_network(entities, relations, selected_types=None):
    """Crée un réseau avec Cytoscape"""
    if not CYTOSCAPE_AVAILABLE:
        st.error("⚠️ streamlit-cytoscape n'est pas installé. Installez-le avec: pip install streamlit-cytoscape")
        return None
    
    # Filtrer les entités selon les types sélectionnés
    if selected_types:
        filtered_entities = [e for e in entities if e.get('type') in selected_types]
    else:
        filtered_entities = entities
    
    entity_uuids = {e.get('uuid', e.get('id')) for e in filtered_entities}
    
    if len(filtered_entities) == 0:
        return None
    
    # Sélection du layout
    layout_options = [
        "cose", "breadthfirst", "circle", "concentric", 
        "grid", "random", "dagre", "klay", "cola"
    ]
    selected_layout = st.selectbox(
        "Layout Cytoscape",
        layout_options,
        key="cytoscape_layout"
    )
    
    elements = []
    
    # Ajouter les nœuds
    for entity in filtered_entities:
        entity_uuid = entity.get('uuid', entity.get('id'))
        entity_name = entity.get('name', 'Sans nom')
        entity_type = entity.get('type', 'autre')
        
        # Calculer la taille basée sur les connexions
        connections = sum(1 for r in relations 
                         if r.get('source_uuid', r.get('source_id')) == entity_uuid or 
                            r.get('target_uuid', r.get('target_id')) == entity_uuid)
        
        elements.append({
            "data": {
                "id": entity_uuid,
                "label": entity_name,
                "type": entity_type,
                "connections": connections
            },
            "classes": entity_type
        })
    
    # Ajouter les arêtes
    for relation in relations:
        source_uuid = relation.get('source_uuid', relation.get('source_id'))
        target_uuid = relation.get('target_uuid', relation.get('target_id'))
        
        if source_uuid in entity_uuids and target_uuid in entity_uuids:
            elements.append({
                "data": {
                    "source": source_uuid,
                    "target": target_uuid,
                    "relation_type": relation.get('relation_type', '')
                }
            })
    
    # Styles CSS pour Cytoscape
    stylesheet = [
        {
            "selector": "node",
            "style": {
                "content": "data(label)",
                "text-valign": "center",
                "text-halign": "center",
                "background-color": "#4ECDC4",
                "width": "mapData(connections, 0, 10, 20, 60)",
                "height": "mapData(connections, 0, 10, 20, 60)",
                "font-size": "12px"
            }
        },
        {
            "selector": "node.association",
            "style": {"background-color": "#FF6B6B"}
        },
        {
            "selector": "node.entreprise",
            "style": {"background-color": "#4ECDC4"}
        },
        {
            "selector": "node.institution",
            "style": {"background-color": "#45B7D1"}
        },
        {
            "selector": "node.personne",
            "style": {"background-color": "#96CEB4"}
        },
        {
            "selector": "node.autre",
            "style": {"background-color": "#FFEAA7"}
        },
        {
            "selector": "edge",
            "style": {
                "curve-style": "bezier",
                "target-arrow-shape": "triangle",
                "width": 2,
                "line-color": "#9dbaea",
                "target-arrow-color": "#9dbaea"
            }
        }
    ]
    
    return cytoscape(
        elements, 
        stylesheet=stylesheet,
        layout={"name": selected_layout},
        style={"width": "100%", "height": "600px"},
        key="cytoscape_network"
    )

def analyze_events(events):
    """Analyse les événements"""
    events_by_style = Counter()
    events_by_month = defaultdict(int)
    events_by_location = Counter()
    
    for event in events:
        # Style musical
        style = event.get('concert_style', 'Non spécifié')
        if style:
            events_by_style[style] += 1
        
        # Date
        date_str = event.get('date', '')
        if date_str and date_str != '':
            try:
                # Extraction du mois-année
                if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                    month_year = date_str[:7]  # YYYY-MM
                    events_by_month[month_year] += 1
            except:
                pass
        
        # Localisation
        location = event.get('location', 'Non spécifié')
        if location:
            events_by_location[location] += 1
    
    return events_by_style, events_by_month, events_by_location

def cleanup_temp_files():
    """Nettoie les fichiers temporaires en attente"""
    if 'temp_files_to_clean' in st.session_state:
        files_to_remove = []
        for temp_file in st.session_state.temp_files_to_clean:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                files_to_remove.append(temp_file)
            except (PermissionError, FileNotFoundError):
                # Fichier encore verrouillé, on essaiera plus tard
                pass
        
        # Supprimer les fichiers nettoyés de la liste
        for file_to_remove in files_to_remove:
            st.session_state.temp_files_to_clean.remove(file_to_remove)

def main():
    st.title("🎵 Dashboard Communauté Musicale")
    st.markdown("Exploration du réseau des acteurs culturels et de leurs activités")
    
    # Bouton de rafraîchissement pour nettoyer les données
    col1, col2, col3 = st.columns([1, 1, 8])
    with col1:
        if st.button("🔄 Rafraîchir"):
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        st.info("Les rapports JSON sont automatiquement filtrés")
    
    # Nettoyer les fichiers temporaires en attente
    cleanup_temp_files()
    
    # Chargement des données
    entities, relations, events = load_data()
    
    if not entities:
        st.warning("Aucune donnée disponible. Vérifiez le fichier batch_graphdata_chunked_results.pkl")
        return
    
    # Sidebar avec filtres
    st.sidebar.header("🎛️ Filtres")
    
    # Types d'entités disponibles
    entity_types = list(set(e.get('type', 'autre') for e in entities))
    selected_types = st.sidebar.multiselect(
        "Types d'entités",
        entity_types,
        default=entity_types
    )
    
    # Filtre par fichier source
    source_files = sorted(list(set(e.get('source_file', 'Unknown') for e in entities)))
    selected_sources = st.sidebar.multiselect(
        "Fichiers sources",
        source_files,
        default=source_files
    )
    
    # Filtre par méthode de traitement
    processing_methods = sorted(list(set(e.get('processing_method', 'unknown') for e in entities)))
    selected_methods = st.sidebar.multiselect(
        "Méthodes de traitement",
        processing_methods,
        default=processing_methods
    )
    
    # Métriques principales avec info sur les UUIDs et le traitement
    st.sidebar.header("📊 Métriques")
    # Appliquer tous les filtres
    filtered_entities = entities
    if selected_types:
        filtered_entities = [e for e in filtered_entities if e.get('type') in selected_types]
    if selected_sources:
        filtered_entities = [e for e in filtered_entities if e.get('source_file') in selected_sources]
    if selected_methods:
        filtered_entities = [e for e in filtered_entities if e.get('processing_method') in selected_methods]
    
    # Filtrer les relations et événements en conséquence
    filtered_entity_uuids = {e.get('uuid', e.get('id')) for e in filtered_entities}
    filtered_relations = [r for r in relations if r.get('source_uuid', r.get('source_id')) in filtered_entity_uuids or r.get('target_uuid', r.get('target_id')) in filtered_entity_uuids]
    filtered_events = events  # Les événements ne sont pas directement liés aux filtres d'entités pour l'instant
    
    st.sidebar.metric("Entités", len(filtered_entities))
    st.sidebar.metric("Relations", len(filtered_relations))
    st.sidebar.metric("Événements", len(filtered_events))
    st.sidebar.metric("Types d'entités", len(entity_types))
    
    # Afficher des métriques UUID spécifiques
    if filtered_entities:
        unique_uuids = len(set(e.get('uuid', e.get('id')) for e in filtered_entities if e.get('uuid', e.get('id'))))
        st.sidebar.metric("UUIDs uniques", unique_uuids)
    
    # Afficher les statistiques de traitement si disponibles
    if 'processing_stats' in st.session_state:
        stats = st.session_state['processing_stats']
        st.sidebar.header("🔧 Traitement")
        st.sidebar.metric("Fichiers sources", stats['total_files'])
        st.sidebar.metric("Fichiers chunked", stats['chunked_files'])
        st.sidebar.metric("Fichiers directs", stats['direct_files'])
        if stats['total_chunks'] > 0:
            st.sidebar.metric("Total chunks", stats['total_chunks'])
        
        # Afficher les fichiers filtrés si il y en a
        if 'filtered_files' in stats and stats['filtered_files']:
            st.sidebar.header("🚫 Fichiers filtrés")
            st.sidebar.metric("Rapports exclus", len(stats['filtered_files']))
            with st.sidebar.expander("Voir les fichiers filtrés"):
                for file in stats['filtered_files']:
                    st.text(f"• {file}")
    
    # Layout principal
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.header("🕸️ Réseau d'Entités")
        
        # Sélecteur de type de visualisation
        available_options = ["Plotly (Standard)"]
        
        if PYVIS_AVAILABLE:
            available_options.append("Pyvis (Interactif)")
        if AGRAPH_AVAILABLE:
            available_options.append("Streamlit-Agraph (Performance)")
        if ECHARTS_AVAILABLE:
            available_options.append("ECharts (Professionnel)")
        if GRAPHVIZ_AVAILABLE:
            available_options.append("Graphviz (Hiérarchique)")
        if VIS_NETWORK_AVAILABLE:
            available_options.append("Vis-Network (Avancé)")
        if CYTOSCAPE_AVAILABLE:
            available_options.append("Cytoscape (Scientifique)")
        
        selected_viz = st.selectbox(
            "Type de visualisation",
            available_options,
            help="Choisissez le moteur de visualisation pour le réseau"
        )
        
        # Afficher des informations sur les options
        if selected_viz == "Plotly (Standard)":
            st.info("📊 Visualisation standard avec zoom et pan basiques")
        elif selected_viz == "Pyvis (Interactif)":
            st.info("🎮 Visualisation interactive avec physique de simulation - Cliquez et glissez les nœuds!")
            with st.expander("ℹ️ Instructions Pyvis"):
                st.markdown("""
                **Interactions disponibles :**
                - 🖱️ **Clic + Glisser** : Déplacer les nœuds
                - 🔍 **Molette** : Zoom in/out
                - 👆 **Hover** : Voir les détails des nœuds
                - 🎯 **Clic sur nœud** : Sélectionner/fixer le nœud
                - ⏸️ **Barre d'espace** : Pause/reprise de la simulation
                """)
        elif selected_viz == "Streamlit-Agraph (Performance)":
            st.info("⚡ Visualisation haute performance optimisée pour les gros réseaux")
            with st.expander("ℹ️ Instructions Agraph"):
                st.markdown("""
                **Interactions disponibles :**
                - 🖱️ **Clic sur nœud** : Sélectionner et voir les détails
                - 🔍 **Molette** : Zoom in/out
                - 👆 **Drag** : Naviguer dans le graphe
                - 🎨 **Highlight** : Mise en évidence automatique
                """)
        elif selected_viz == "ECharts (Professionnel)":
            st.info("🎨 Visualisation professionnelle avec animations fluides et légendes")
            with st.expander("ℹ️ Instructions ECharts"):
                st.markdown("""
                **Interactions disponibles :**
                - 🖱️ **Clic + Glisser** : Déplacer les nœuds
                - 🔍 **Molette** : Zoom in/out
                - 👆 **Hover** : Voir les informations détaillées
                - 🎯 **Focus adjacency** : Mise en évidence des connexions
                - 📍 **Légende interactive** : Filtrer par type d'entité
                """)
        elif selected_viz == "Graphviz (Hiérarchique)":
            st.info("🌳 Visualisation hiérarchique avec layouts algorithmiques")
            with st.expander("ℹ️ Instructions Graphviz"):
                st.markdown("""
                **Layouts disponibles :**
                - **dot** : Hiérarchique dirigé (top-down)
                - **neato** : Spring model (positions basées sur forces)
                - **fdp** : Force-directed placement
                - **sfdp** : Multiscale force-directed (grands graphes)
                - **circo** : Disposition circulaire
                - **twopi** : Disposition radiale
                """)
        elif selected_viz == "Vis-Network (Avancé)":
            st.info("🔬 Visualisation avancée avec physique réaliste et groupements")
            with st.expander("ℹ️ Instructions Vis-Network"):
                st.markdown("""
                **Interactions disponibles :**
                - 🖱️ **Clic + Glisser** : Déplacer les nœuds
                - 🔍 **Molette** : Zoom in/out
                - 👆 **Hover** : Tooltips informatifs
                - 🎯 **Sélection** : Highlight des connexions
                - ⚡ **Physique** : Simulation physique en temps réel
                """)
        elif selected_viz == "Cytoscape (Scientifique)":
            st.info("🧬 Visualisation scientifique avec layouts biologiques et analyse de réseaux")
            with st.expander("ℹ️ Instructions Cytoscape"):
                st.markdown("""
                **Layouts scientifiques :**
                - **cose** : Compound Spring Embedder (recommandé)
                - **dagre** : Directed Acyclic Graph
                - **breadthfirst** : Largeur d'abord
                - **circle** : Disposition circulaire
                - **concentric** : Cercles concentriques
                - **grid** : Grille régulière
                - **klay** : Layered layout (Klay)
                - **cola** : Constraint-based layout
                """)
        
        # Légende des couleurs
        with st.expander("🎨 Légende des couleurs"):
            col_legend1, col_legend2 = st.columns(2)
            with col_legend1:
                st.markdown("**Types d'entités :**")
                st.markdown("🔴 Association")
                st.markdown("🟢 Entreprise") 
                st.markdown("🔵 Institution")
                st.markdown("🟣 Personne")
                st.markdown("🟡 Autre")
            
            with col_legend2:
                st.markdown("**Types de relations :**")
                st.markdown("🔴 Collaboration")
                st.markdown("🟢 Intention")
                st.markdown("🔵 Événement")
                st.markdown("🟣 Appartenance")
                st.markdown("⚪ Autre")
        
        # Générer la visualisation selon le choix
        if selected_viz == "Pyvis (Interactif)" and PYVIS_AVAILABLE:
            pyvis_net = create_pyvis_network(filtered_entities, filtered_relations, selected_types)
            if pyvis_net:
                # Méthode alternative : Générer HTML en mémoire
                try:
                    # Générer le HTML directement en string
                    html_content = pyvis_net.generate_html()
                    
                    # Afficher dans Streamlit
                    components.html(html_content, height=620)
                    
                except AttributeError:
                    # Fallback pour les versions plus anciennes de Pyvis
                    # Utiliser un nom de fichier unique basé sur le timestamp
                    import time
                    temp_filename = f"temp_network_{int(time.time() * 1000)}.html"
                    
                    try:
                        pyvis_net.save_graph(temp_filename)
                        
                        # Lire le contenu HTML
                        with open(temp_filename, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                        
                        # Afficher dans Streamlit
                        components.html(html_content, height=620)
                        
                        # Nettoyer avec gestion d'erreur
                        try:
                            os.unlink(temp_filename)
                        except (PermissionError, FileNotFoundError):
                            # Programmer le nettoyage pour plus tard
                            if 'temp_files_to_clean' not in st.session_state:
                                st.session_state.temp_files_to_clean = []
                            st.session_state.temp_files_to_clean.append(temp_filename)
                    
                    except Exception as e:
                        st.error(f"Erreur lors de la génération Pyvis: {e}")
                        st.info("Basculement vers la visualisation Plotly...")
                        network_fig = create_network_graph(filtered_entities, filtered_relations, selected_types)
                        st.plotly_chart(network_fig, use_container_width=True)
                        
            else:
                st.warning("Aucune donnée à afficher")
                
        elif selected_viz == "Streamlit-Agraph (Performance)" and AGRAPH_AVAILABLE:
            nodes, edges, config = create_agraph_network(filtered_entities, filtered_relations, selected_types)
            if nodes and edges:
                # Afficher le graphe avec agraph
                return_value = agraph(nodes=nodes, edges=edges, config=config)
                
                # Afficher les détails du nœud sélectionné
                if return_value:
                    st.subheader("🔍 Nœud sélectionné")
                    selected_entity = next((e for e in filtered_entities if e.get('uuid', e.get('id')) == return_value), None)
                    if selected_entity:
                        st.json(selected_entity)
            else:
                st.warning("Aucune donnée à afficher")
        else:
            # Visualisation Plotly par défaut
            network_fig = create_network_graph(filtered_entities, filtered_relations, selected_types)
            st.plotly_chart(network_fig, use_container_width=True)
    
    with col2:
        st.header("🎯 Analyse des Intentions")
        
        # Analyse des intentions
        all_intentions, intentions_by_type = analyze_intentions(filtered_entities)
        
        if all_intentions:
            # Top intentions
            intention_counts = Counter(all_intentions)
            top_intentions = intention_counts.most_common(10)
            
            if top_intentions:
                df_intentions = pd.DataFrame(top_intentions, columns=['Intention', 'Fréquence'])
                fig_intentions = px.bar(
                    df_intentions, 
                    x='Fréquence', 
                    y='Intention',
                    orientation='h',
                    title="Top 10 des Intentions"
                )
                fig_intentions.update_layout(height=400)
                st.plotly_chart(fig_intentions, use_container_width=True)
        
        # Distribution par type d'entité
        st.subheader("🏢 Répartition par Type")
        type_counts = Counter(e.get('type', 'autre') for e in filtered_entities)
        if type_counts:
            df_types = pd.DataFrame(list(type_counts.items()), columns=['Type', 'Nombre'])
            fig_types = px.pie(
                df_types, 
                values='Nombre', 
                names='Type',
                title="Répartition des Types d'Entités"
            )
            st.plotly_chart(fig_types, use_container_width=True)
    
    # Section Événements
    st.header("🎪 Analyse des Événements")
    
    if events:
        col3, col4, col5 = st.columns(3)
        
        # Analyse des événements
        events_by_style, events_by_month, events_by_location = analyze_events(filtered_events)
        
        with col3:
            st.subheader("🎵 Styles Musicaux")
            if events_by_style:
                df_styles = pd.DataFrame(
                    list(events_by_style.most_common(10)), 
                    columns=['Style', 'Nombre']
                )
                fig_styles = px.bar(
                    df_styles, 
                    x='Style', 
                    y='Nombre',
                    title="Top 10 des Styles Musicaux"
                )
                fig_styles.update_xaxes(tickangle=45)
                st.plotly_chart(fig_styles, use_container_width=True)
        
        with col4:
            st.subheader("📅 Événements par Mois")
            if events_by_month:
                df_months = pd.DataFrame(
                    list(events_by_month.items()), 
                    columns=['Mois', 'Nombre']
                ).sort_values('Mois')
                fig_months = px.line(
                    df_months, 
                    x='Mois', 
                    y='Nombre',
                    title="Évolution Temporelle"
                )
                fig_months.update_xaxes(tickangle=45)
                st.plotly_chart(fig_months, use_container_width=True)
        
        with col5:
            st.subheader("📍 Lieux d'Événements")
            if events_by_location:
                df_locations = pd.DataFrame(
                    list(events_by_location.most_common(10)), 
                    columns=['Lieu', 'Nombre']
                )
                fig_locations = px.bar(
                    df_locations, 
                    x='Lieu', 
                    y='Nombre',
                    title="Top 10 des Lieux"
                )
                fig_locations.update_xaxes(tickangle=45)
                st.plotly_chart(fig_locations, use_container_width=True)
    
    # Nuage de mots des intentions
    st.header("☁️ Nuage de Mots des Intentions")
    if all_intentions:
        wordcloud_fig = create_wordcloud(all_intentions)
        if wordcloud_fig:
            st.pyplot(wordcloud_fig)
    
    # Section détails avec informations sur les sources et métadonnées
    with st.expander("🔍 Données Détaillées"):
        tab1, tab2, tab3, tab4 = st.tabs(["Entités", "Relations", "Événements", "Sources & Métadonnées"])
        
        with tab1:
            if filtered_entities:
                df_entities = pd.DataFrame(filtered_entities)
                # Réorganiser les colonnes pour mettre les UUIDs et sources en évidence
                cols = ['uuid', 'id', 'name', 'type', 'source_file', 'processing_method'] + [c for c in df_entities.columns if c not in ['uuid', 'id', 'name', 'type', 'source_file', 'processing_method']]
                df_entities = df_entities.reindex(columns=[c for c in cols if c in df_entities.columns])
                st.dataframe(df_entities, use_container_width=True)
        
        with tab2:
            if filtered_relations:
                df_relations = pd.DataFrame(filtered_relations)
                # Réorganiser les colonnes pour mettre les UUIDs et sources en évidence
                cols = ['source_uuid', 'target_uuid', 'source_id', 'target_id', 'relation_type', 'source_file', 'processing_method'] + [c for c in df_relations.columns if c not in ['source_uuid', 'target_uuid', 'source_id', 'target_id', 'relation_type', 'source_file', 'processing_method']]
                df_relations = df_relations.reindex(columns=[c for c in cols if c in df_relations.columns])
                st.dataframe(df_relations, use_container_width=True)
        
        with tab3:
            if filtered_events:
                df_events = pd.DataFrame(filtered_events)
                # Réorganiser les colonnes pour mettre les UUIDs et sources en évidence
                cols = ['uuid', 'id', 'name', 'date', 'concert_style', 'source_file', 'processing_method'] + [c for c in df_events.columns if c not in ['uuid', 'id', 'name', 'date', 'concert_style', 'source_file', 'processing_method']]
                df_events = df_events.reindex(columns=[c for c in cols if c in df_events.columns])
                st.dataframe(df_events, use_container_width=True)
        
        with tab4:
            # Afficher les informations sur les fichiers sources
            if 'processing_stats' in st.session_state:
                stats = st.session_state['processing_stats']
                st.subheader("📂 Fichiers Sources")
                
                df_sources = pd.DataFrame(stats['file_sources'])
                if not df_sources.empty:
                    # Formater les colonnes
                    df_sources['text_length'] = df_sources['text_length'].apply(lambda x: f"{x:,} chars")
                    df_sources['processed_at'] = pd.to_datetime(df_sources['processed_at']).dt.strftime('%Y-%m-%d %H:%M')
                    
                    st.dataframe(df_sources, use_container_width=True)
                    
                    # Statistiques récapitulatives
                    st.subheader("📊 Récapitulatif")
                    col_stats1, col_stats2, col_stats3 = st.columns(3)
                    
                    with col_stats1:
                        st.metric("Total fichiers", stats['total_files'])
                        st.metric("Fichiers chunked", stats['chunked_files'])
                    
                    with col_stats2:
                        st.metric("Fichiers directs", stats['direct_files'])
                        if stats['total_chunks'] > 0:
                            st.metric("Total chunks", stats['total_chunks'])
                    
                    with col_stats3:
                        avg_length = sum(f['text_length'] for f in stats['file_sources']) / len(stats['file_sources']) if stats['file_sources'] else 0
                        st.metric("Taille moy. fichier", f"{avg_length:,.0f} chars")
                        
                        # Pourcentage de fichiers traités par chunks
                        chunk_percentage = (stats['chunked_files'] / stats['total_files']) * 100 if stats['total_files'] > 0 else 0
                        st.metric("% Fichiers chunked", f"{chunk_percentage:.1f}%")

if __name__ == "__main__":
    main()