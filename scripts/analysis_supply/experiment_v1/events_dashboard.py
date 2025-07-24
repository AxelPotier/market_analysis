import pandas as pd
import streamlit as st
import pickle
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import seaborn as sns

df_simple = pickle.load(open('df_simple.p','rb'))
complex_dfs = pickle.load(open('complex_dfs.p','rb'))

df = complex_dfs['events'].drop_duplicates()
st.title("Visualisation des évènements par thématique")


# # Histogramme des événements en fonction de la date
# st.subheader("Histogramme des événements par date")
# # Convertir les dates en format plus simple si nécessaire
# df['date'] = pd.to_datetime(df['date']).dt.date
# fig, ax = plt.subplots()
# sns.histplot(df['date'], kde=False, bins=10, color='skyblue', ax=ax)
# ax.set_title('Histogramme des événements par date')
# ax.set_xlabel('Date')
# ax.set_ylabel('Nombre d\'événements')
# st.pyplot(fig)


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