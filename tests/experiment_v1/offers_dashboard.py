import pandas as pd
import streamlit as st
import pickle
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt

df_simple = pickle.load(open('df_simple.p','rb'))
complex_dfs = pickle.load(open('complex_dfs.p','rb'))

df = complex_dfs['offers']
st.title("Visualisation des offres par thématique")

# Compter le nombre de fois que chaque label apparaît
topic_counts = df['description_topic_label'].value_counts().reset_index()
topic_counts.columns = ['description_topic_label', 'count']

# Création du pie chart avec Plotly
fig = px.pie(
    topic_counts,
    names='description_topic_label',
    values='count',
    title='Répartition des objectifs par thématique'
)

# Affichage du pie chart
selected = st.plotly_chart(fig, use_container_width=True)


# --- SELECTION ---
selected_topic = st.selectbox(
    "Sélectionnez une thématique pour voir les détails :",
    topic_counts['description_topic_label'].unique()
)

# --- FILTRAGE ---
filtered_df = df[df['description_topic_label'] == selected_topic]

# --- WORD CLOUD ---
st.subheader(f"Nuage de mots pour : {selected_topic}")

# Fusionner tous les textes en un seul corpus
text = " ".join(filtered_df['description_topic_representation'].dropna().astype(str))

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
st.subheader("Offres associées")
st.dataframe(filtered_df[['id', 'description_topic_representation']])

#----- shows entities --------------
# Sélection via clic simulé : on utilise un selectbox comme alternative simple
st.subheader("Sélectionne une thématique pour afficher les entités associées")
selected_topic = st.selectbox("Choisis une thématique :", topic_counts['description_topic_label'].unique())

# Filtrer les IDs associés à ce label
selected_ids = df[df['description_topic_label'] == selected_topic]['id']

# Filtrer df_simple
filtered_df = df_simple[df_simple['id'].isin(selected_ids)][['id','name','status','localisation','description','url','nb_events_sibil']]

# Afficher les entités associées
st.write(f"Objectifs liés à la thématique **{selected_topic}** :")
st.dataframe(filtered_df)