# 🎵 Pipeline GraphData → Neo4j

Ce pipeline extrait automatiquement les entités, relations et événements musicaux de tous les fichiers texte et les insère dans une base de données Neo4j pour analyse et visualisation.

## 📋 Vue d'ensemble

```
Fichiers textes → Extraction LLM → Format GraphData → Base Neo4j → Visualisation
     📄              🤖                🔄              🗄️           📊
```

## 🚀 Démarrage rapide

### 1. Installation des dépendances

```bash
pip install neo4j mistralai pandas tqdm pathlib hashlib
```

### 2. Démarrer Neo4j

```bash
# Docker (recommandé)
docker run -d \
  --name neo4j-music \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Ou installation locale
# Suivre les instructions sur https://neo4j.com/download/
```

### 3. Lancer le pipeline complet

```bash
python run_complete_pipeline.py
```

## 📁 Structure des fichiers

```
entity_relationships/
├── 🎯 run_complete_pipeline.py     # Script principal d'orchestration
├── 🔄 run_batch_processor.py       # Traitement batch des fichiers textes
├── 🗄️ neo4j_inserter.py           # Insertion dans Neo4j
├── 🔍 neo4j_queries.cypher         # Collection de requêtes utiles
├── 📊 classGraphData.py            # Modèles de données GraphData
├── 📈 graph_interactive_widget.ipynb # Visualisation interactive
├── 📋 README.md                    # Ce fichier
└── 📄 rapport_pipeline.html        # Rapport généré (après exécution)
```

## 🔧 Utilisation détaillée

### Option 1: Pipeline automatique complet
```bash
python run_complete_pipeline.py
```

### Option 2: Étapes séparées

#### Étape 1: Extraction des données
```bash
python run_batch_processor.py
```
Génère: `batch_graphdata_results.pkl` et `batch_graphdata_results.json`

#### Étape 2: Insertion Neo4j
```bash
python neo4j_inserter.py
```

### Option 3: Utilisation avec arguments
```bash
# Ignorer l'extraction (utiliser données existantes)
python run_complete_pipeline.py --skip-extraction

# Ignorer Neo4j (extraction seulement)
python run_complete_pipeline.py --skip-neo4j

# Fichier de résultats personnalisé
python run_complete_pipeline.py --results-file mon_fichier.pkl
```

## 🎨 Modèle de données Neo4j

### Nœuds

**Entity** (Entités musicales)
- `id` : Identifiant unique
- `name` : Nom de l'entité
- `type` : association | entreprise | institution | personne | autre
- `description` : Description
- `intentions` : Liste des objectifs/intentions
- `source_file` : Fichier source

**Event** (Événements musicaux)
- `id` : Identifiant unique
- `name` : Nom de l'événement
- `date` : Date (AAAA-MM-JJ)
- `location` : Lieu
- `description` : Description
- `concert_style` : Style musical
- `organizer_id` : ID de l'organisateur
- `source_file` : Fichier source

### Relations

- **ORGANIZES** : Entité → Événement
- **COLLABORATES_WITH** : Entité ↔ Entité
- **PARTICIPATES_IN** : Entité → Événement
- **BELONGS_TO** : Entité → Entité
- **RELATED_TO** : Relation générique

## 🔍 Requêtes utiles

### Statistiques générales
```cypher
MATCH (n) OPTIONAL MATCH ()-[r]->() 
RETURN count(DISTINCT n) as nodes, count(DISTINCT r) as relations;
```

### Top organisateurs d'événements
```cypher
MATCH (e:Entity)-[:ORGANIZES]->(ev:Event)
RETURN e.name, e.type, count(ev) as events_organized
ORDER BY events_organized DESC LIMIT 10;
```

### Événements par style musical
```cypher
MATCH (ev:Event)
WHERE ev.concert_style <> ""
RETURN ev.concert_style, count(ev) as count
ORDER BY count DESC;
```

### Recherche textuelle
```cypher
MATCH (e:Entity)
WHERE toLower(e.name) CONTAINS toLower("rock")
RETURN e.name, e.type, e.intentions;
```

## 📊 Visualisation et analyse

### 1. Neo4j Browser
- URL: http://localhost:7474
- Exploration graphique interactive
- Exécution de requêtes Cypher

### 2. Notebook Jupyter interactif
```bash
jupyter notebook graph_interactive_widget.ipynb
```

### 3. Export vers outils externes
```cypher
// Export CSV pour Gephi/Cytoscape
MATCH (n)-[r]->(m)
RETURN n.name as source, type(r) as relationship, m.name as target
```

## 🛠️ Configuration

### Variables d'environnement Neo4j
```bash
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password
```

### Configuration Mistral AI
- Clé API dans `run_batch_processor.py`
- Modèle: `mistral-large-latest`

## 📈 Résultats attendus

Pour ~9 fichiers textes dans `/data/data_supply/textes/` :
- **Entités** : 30-100 organisations/personnes
- **Événements** : 10-50 concerts/spectacles  
- **Relations** : 50-200 connexions
- **Styles musicaux** : Rock, Jazz, Électro, etc.

## 🚨 Dépannage

### Erreur connexion Neo4j
```bash
# Vérifier que Neo4j est démarré
docker ps | grep neo4j

# Tester la connexion
curl http://localhost:7474
```

### Erreur API Mistral
- Vérifier la clé API
- Vérifier les quotas/crédits
- Réduire la taille des fichiers si timeout

### Erreur de parsing JSON
- Vérifier le prompt dans `classGraphData.py`
- Ajouter validation des réponses LLM

## 📚 Documentation supplémentaire

- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
- [NetworkX Documentation](https://networkx.org/documentation/stable/)
- [Mistral AI API](https://docs.mistral.ai/)

## 🎯 Extensions possibles

1. **API REST** pour requêtes dynamiques
2. **Dashboard web** avec visualisations
3. **Détection de communautés** algorithmique
4. **Analyse temporelle** des événements
5. **Recommandations** basées sur le graphe
6. **Import/Export** autres formats de données

---

🎵 **Bon voyage dans votre réseau musical !** 🎵