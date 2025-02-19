# CAHIER DES CHARGES :

## Contexte :
Dans le cadre de  l'association du fungi on mène une enquête pour mieux comprendre 
l'écosystème des musiques actuelles dans les hauts de france et plus particulièrement dans 
l'agglomération de Lille.

## Objectif : 
L'algorithme doit pouvoir sur la base d'une liste de lien url de pouvoir aller
récupérer le texte des pages et puis en extraire sous un format structuré les informations
qui nous intéresse soit les offres, la différenciation, les prix ainsi que la présence sur les réseaux sociaux.
Une fois extrait il doit pouvoir restituer sous la forme d'un data frame ou csv les données pour une analyse ultérieure.

## Description Fonctionnelle :

L'algorithme prend en entrée une liste d'url (List[str]), puis avec BeautifullSoup il doit aller récupérer les textes de toutes les pages ainsi que des pages ayant le même url de base puis les concaténer par entité puis être enregistrées au format .txt.
Les données sont ensuite fournies à Mistral texte par texte. La requête passe par l'API et fournie un prompt explicitant les champs à remplir. Le format de sortie est du json avec des champs structuré et décrit par pydantic.
Les fonctions sont :
get_text_from_urls : List[str] -> .txt
study_text : folder_name -> .json
make_df : .json -> pd.DataFrame


## Contrainte et exigeance :

Limites de performances: 
- Doit pouvoir tourner en local

Légal et réglementaire :
- Vérifier la CGU pour le scrapping
- anonymiser les adresse mails et les nom propres

## Critères de Performance :

## Données d'Entrée et de Sortie :

Entrée: liste d'url
sortie : dataframe

## Environnement Technique :

Code en python
API MISTRAL

## Tests et Validation :

- valider sur lefungi, artpointM l'algorithe.
    test
- le dataframe doit être cohérent

## Plan de Développement :

14/02-15/02 : get_text_from_urls() et scrapping de hdf.
16/02-19/02 : study_texts() et make_df()
20/02 : test([url_fungi,url_artpointM])
22/02 : montrer les résultats à Orlane pour validation.

## Maintenance et Évolutions :

Mis sur github.

## Annexes :

Incluez des documents supplémentaires, comme des schémas, des diagrammes, des exemples de données, etc.
Un cahier des charges bien rédigé permet de s'assurer que toutes les parties prenantes sont alignées sur les objectifs et les attentes du projet, facilitant ainsi le développement et la validation de l'algorithme