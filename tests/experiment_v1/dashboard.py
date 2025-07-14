import streamlit as st
import pandas as pd
import streamlit as st
import pickle
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt

## ------ Retrieve parameters ------------
# Lire les paramètres de l'URL
# params = st.experimental_get_query_params()

# arg1 = params.get("arg1", ["default1"])[0]
# arg2 = params.get("arg2", ["default2"])[0]
# arg3 = params.get("arg3", ["default3"])[0]

dic_keys = {'Objectifs' : 'objectives',
            'Offres' : "Offers" }

dic_df = {'objectifs': { 'arg1' : 'objectives', 'arg2':  'objectives_topic_label' ,
                         'arg3':'objectives_topic_representation','arg4': 'objectives' },
            'offres' : { 'arg1' : 'offers', 'arg2':  'description_topic_label' ,
                         'arg3':'description_topic_representation', 'arg4': 'description' },
        'évènements' : { 'arg1': 'events', 'arg2': None, 'arg3' : None, 'arg4': None}

          }

# st.write("arg1:", arg1)
# st.write("arg2:", arg2)
# st.write("arg3:", arg3)

df_simple = pickle.load(open('df_simple.p','rb'))
complex_dfs = pickle.load(open('complex_dfs.p','rb'))



## Choose from 
# --- SELECTION ---
selected_subject = st.selectbox(
    "Sélectionnez une thématique pour voir les détails :",
    dic_df.keys()
)


arg1 = dic_df[selected_subject]['arg1']## name of the dataframe
arg2 = dic_df[selected_subject]['arg2']## column with the topics
arg3 = dic_df[selected_subject]['arg3']# column with the representation of the topics
arg4 = dic_df[selected_subject]['arg4']# column with the raw information 

if (arg1 == 'objectives') or (arg1 == 'offers'):
    # df = complex_dfs[dic_keys[arg1]]
    st.title("Visualisation des " + selected_subject + " par thématique")

    df = complex_dfs[arg1]#.drop_duplicates()
    ## ---- Pie chart ----------------
    # Compter le nombre de fois que chaque label apparaît
    topic_counts = df[arg2].value_counts().reset_index()
    topic_counts.columns = [arg2, 'count']

    # Création du pie chart avec Plotly
    fig = px.pie(
        topic_counts,
        names=arg2,
        values='count',
        title= f'Répartition des {selected_subject} par thématique'
    )

    # Affichage du pie chart
    selected = st.plotly_chart(fig, use_container_width=True)

    ## --- Word cloud and details for a specific topic.-------

    st.subheader(f"Informations associées à une thématique")
    selected_topic = st.selectbox(
        "Sélectionnez une thématique pour voir les détails :",
        topic_counts[arg2].unique()
    )

    filtered_df = df[df[arg2] == selected_topic]

    # st.subheader(f"Nuage de mots pour : {selected_topic}")

    # Fusionner tous les textes en un seul corpus
    text = " ".join(filtered_df[arg3].dropna().astype(str))

    # Générer le WordCloud
    if text.strip():  # Vérifie qu'il y a bien du texte
        wordcloud = WordCloud(
            width=800, height=400,
            background_color='white',
            colormap='tab10'
        ).generate(text)

        # Affichage avec matplotlib
        fig_wc, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis("off")
        st.pyplot(fig_wc)
    else:
        st.info("Aucune donnée textuelle disponible pour ce sujet.")

    # Affichage des objectifs filtrés
    st.write("Champ " + selected_subject +" associées")
    # st.write(filtered_df.columns)
    st.dataframe(filtered_df[['id', arg4]])

    #----- shows entities --------------
    # Filtrer les IDs associés à ce label
    selected_ids = df[df[arg2] == selected_topic]['id']
    # Filtrer df_simple
    filtered_df = df_simple[df_simple['id'].isin(selected_ids)][['id','name','status','localisation','description','url','nb_events_sibil']]
        # Afficher les entités associées
    st.write(f"Entités par thématique")
    st.dataframe(filtered_df)


    # #----- shows entities --------------
    # # Sélection via clic simulé : on utilise un selectbox comme alternative simple
    # st.subheader("Sélectionne une thématique pour afficher les entités associées")
    # selected_topic = st.selectbox("Choisis une thématique :", topic_counts[arg2].unique())

    # # Filtrer les IDs associés à ce label
    # selected_ids = df[df[arg2] == selected_topic]['id']

    # # Filtrer df_simple
    # filtered_df = df_simple[df_simple['id'].isin(selected_ids)][['id','name','status','localisation','description','url','nb_events_sibil']]

    # # Afficher les entités associées
    # st.write(f"Objectifs liés à la thématique **{selected_topic}** :")
    # st.dataframe(filtered_df)

if arg1 == 'events':
    df = complex_dfs['events'].drop_duplicates()
    st.title("Visualisation des évènements par thématique")

    # Pie chart sur le type de musique
    st.subheader("Répartition des événements par type de musique")
    fig, ax = plt.subplots()
    music_type_counts = df['music_type'].value_counts()
    music_type_counts.plot.pie(autopct='%1.1f%%', colors=['#ff9999','#66b3ff','#99ff99'], startangle=90, ax=ax)
    ax.set_title('Répartition des événements par type de musique')
    st.pyplot(fig)


    #----- shows entities --------------
    # Sélecteur pour afficher les entités en fonction de l'id
    st.subheader("Sélection d'une entité")
    selected_topic = st.selectbox('Choisir un type de musique', df['music_type'].unique())

    # Filtrer les IDs associés à ce label
    selected_ids = df[df['music_type'] == selected_topic]['id']

    # Filtrer df_simple
    filtered_df = df_simple[df_simple['id'].isin(selected_ids)][['id','name','status','localisation','description','url','nb_events_sibil']]

    # Afficher les entités associées
    st.write(f"Objectifs liés à la thématique **{selected_topic}** :")
    st.dataframe(filtered_df)
