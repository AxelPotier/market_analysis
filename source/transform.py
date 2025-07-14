import pandas as pd
from typing import List, Dict
from bertopic import BERTopic
from bertopic.representation import KeyBERTInspired
import nltk
from nltk.corpus import stopwords
from mistralai import Mistral



class TooManyColumnsError(Exception):
    """Exception raised when there is more than 2 columns."""
    pass

class AllAreNotString(Exception):
    """Exception raised when there is a field with a non string element"""
    pass



class SplitComplexColumns:
    def __init__(self, id_column='id',list_dic_col_split_str = [] ):
        '''
        list_col_field_separated_by_coma : is a list of dict refering to columns 
        where the values are str and the values to extract are separated by a delimiter
        specified in the dictionnary.
        '''
        
        self.id_column = id_column
        self.list_dic_col_split_str = list_dic_col_split_str

    def transform( self, df ):
        if self.id_column not in df.columns:
            raise ValueError(f"Column '{self.id_column}' not found in DataFrame.")

        simple_cols = [self.id_column]
        complex_dfs = {}

        for col in df.columns:
            if col == self.id_column:
                continue

            sample_values = df[col].dropna().head(10)

            # Si tous les exemples sont primitifs, on garde dans simple
            if (all(isinstance(v, (str, int, float, bool)) for v in sample_values) 
                and (col not in [ dic['col'] for dic in self.list_dic_col_split_str]) ):
                simple_cols.append(col)
            
            ## si tous les exemples sont des listes de str
            elif all(isinstance(val, list) and all(isinstance(item, str) \
                    for item in val) for val in sample_values):
                complex_df = df[[self.id_column, col]].copy().explode(col)
                complex_dfs[col] = complex_df.dropna( subset=[col for col in complex_df.columns if col != self.id_column],
                                                     how ='all' ).reset_index(drop = True)

            ## si tous les exemples sont des listes de dict
            elif all(isinstance(val,list) and all(isinstance(item,dict) for item in val) \
                     for val in sample_values):
                 complex_df = (df[[self.id_column, col]].copy().explode(col)
                               )
                 complex_df = complex_df.join(pd.json_normalize(complex_df[col] , sep = '_')).drop(col,axis=1)
                 complex_dfs[col] = complex_df.dropna( subset=[col for col in complex_df.columns if col != self.id_column],
                                                     how ='all' ).reset_index(drop = True)

            ## si tous les exemples sont des dictionnaires
            elif all(isinstance(val,dict) for val in sample_values):
                complex_df = df[[self.id_column, col]].copy()
                complex_df = complex_df.join(pd.json_normalize(complex_df[col] , sep = '_')).drop(col,axis=1)
                complex_dfs[col] = complex_df.dropna( subset=[col for col in complex_df.columns if col != self.id_column],
                                                     how ='all' ).reset_index(drop = True)

            elif (col in [ dic['col'] for dic in self.list_dic_col_split_str]  ) :
                sep = next((d for d in self.list_dic_col_split_str if d.get('col') == col), None)['sep']

                complex_df = df[[self.id_column, col]].copy()
                complex_df[col] = complex_df.apply(lambda r: r[col].split(sep=sep), axis=1)
                complex_df = ( 
                    complex_df[[self.id_column, col]]
                    .explode(col).reset_index(drop=True)
                )
                complex_dfs[col] = complex_df.dropna( subset=[col for col in complex_df.columns if col != self.id_column],
                                                     how ='all' ).reset_index(drop = True)

            else:
                # Sinon, on crée un DataFrame individuel pour cette colonne
                complex_df = df[[self.id_column, col]].copy()
                complex_dfs[col] = complex_df.reset_index(drop = True)

        df_simple = df[simple_cols].copy()
        return df_simple, complex_dfs
    

class TopicExtractor:

    def __init__(self, stop_words_language='french'):
        # Créer un modèle BERTopic
        self.representation_model = KeyBERTInspired()
        self.api_key= "wm1af0pJ92Pj1tLbTSztHxeey62ru479"
        self.client_mistral= Mistral(api_key=self.api_key)
        self.model_mistral = "mistral-large-latest"

        #defining stop words
        nltk.download('stopwords')
        self.stop_words = set(stopwords.words(stop_words_language)) # Liste des stopwords en français
    
    @staticmethod
    def contains_heterogenous_str(df ):
        '''
        for df that contains 2 columns including 'id'.
        '''

        if len(df.columns)>2:
            raise TooManyColumnsError(f"Le DataFrame contient {df.shape[1]} colonnes, limite = 2.")
        
        col = [col for col in df.columns if col != 'id'][0]
        samples_values = df[col].dropna().head(int(max(len(df)*0.1,10)))

        if any([type(item)!=str for item in list(df[col].dropna())]):
            raise AllAreNotString(f"Not all fields of {df.columns} are string")
        
        def uniqueness_ratio(strings):
            return len(set(strings)) / len(strings)
        
        if not len(samples_values) :
            return False
        
        score = uniqueness_ratio(samples_values)

        print(f'score {score}')
        if score > 0.9:
            return True
        else :
            return False
        
    # Fonction de mise à jour des noms avec mistral
    def update_topic_name(self, topic_model : BERTopic):
        '''
        Update the label with mistral.
        
        '''
            # Étape 2: Extrais les top words de chaque topic
        topic_info = topic_model.get_topic_info()
        topic_names = {}

        for topic_id in topic_info.Topic:
            if topic_id == -1:
                continue  # Ignore les "outliers"
            words = [word for word, _ in topic_model.get_topic(topic_id)]
            prompt = f"Voici des mots clés pour un sujet : {', '.join(words)}. Donne un nom court et pertinent pour ce sujet."
            
            response = self.client_mistral.chat.complete(
                model=self.model_mistral,
                messages=[{"role": "user", "content": prompt}]
            )
            
            generated_name = response.choices[0].message.content.strip()
            topic_names[topic_id] = generated_name

        # Étape 3: Remplacer les noms de topics
        for topic_id, name in topic_names.items():
            topic_model.set_topic_labels({topic_id: name})

        return topic_model

            

    def extract_topic(self, df : pd.DataFrame, target_col : str = None, drop_na : bool = False):
        '''

        '''
        if drop_na:
            df = df.dropna()
        
        if target_col is None: # assume that there is only one additional column except id_column.
            target_col = [ col for col in df.columns if col != 'id' ][0]
        
        # Exemple de texte
        textes = list(map(str, df[ target_col ].tolist())) 

        # Supprimer les stopwords
        list_mots_filtres = [[mot for mot in texte.split() if mot.lower() not in self.stop_words] for texte in textes ]
        resultats = [" ".join(mots_filtres).lower() for mots_filtres in list_mots_filtres ]

        # Créer un modèle BERTopic
        topic_model = BERTopic(representation_model = self.representation_model )
        # Extraire les topics
        topics, probs = topic_model.fit_transform( resultats )
        topic_model = self.update_topic_name(topic_model)

        # Ajouter les catégories au dataframe
        df[target_col+'_topic'] = topics
        df = df.merge(topic_model.get_topic_info().rename(columns={'Name':target_col+'_topic_label','Representation': target_col+'_topic_representation',
                                                                   'Representative_Docs': target_col + '_Representative_Docs' }),
                                                        right_on = 'Topic',
                                                        left_on = target_col +'_topic', how = 'left').drop(columns = ['Topic'])
        return df
    

    def extract_topics( self, df ):
        '''
        Will extract topics based on each columns with heterogeneous strings.
        '''
        ## loop over the columns
        df_result = df[['id']].copy()
        for col in df.columns:
            if col != 'id':
                df_temp = df[[col]].copy()

                if (self.is_column_string(df_temp,col)) and (self.contains_heterogenous_str(df_temp) or ('description' in col)):
                    print(df_temp.columns)
                    df_temp = self.extract_topic(df_temp, drop_na= True)

                df_result = df_result.merge(df_temp, left_index=True, right_index=True) #how='left',on='')
        return df_result
    
    @staticmethod
    def is_column_string(df,col):
        return df[col].apply(lambda x: isinstance(x, str)).all()


class Transform:

    def __init__(self, lisst_dic_col_split_str = [] ):
        self.id_column ='id'
        self.list_dic_col_split_str = list_dic_col_split_str
    

    def transform(self,df):
        '''
        Assuming that there each rows is specific to an entity construct a
        column id.
        '''
        # construct an id column (delete if level_0 already exists)
        if 'level_0' in df.columns:
            df = df.drop(columns='level_0')

        df.reset_index(inplace=True)

        df['id'] = df.index
        list_columns = ['id' ]+ list(df.columns[:-1])#put it in first column.
        df = df[list_columns]

        # split complex columns in data frames
        splitter = SplitComplexColumns( id_column = 'id', list_dic_col_split_str = self.list_dic_col_split_str )
        df_simple, complex_dfs =  splitter.transform( df )

        # long string columns extract topics
        for key,df_ in complex_dfs.items():
            topic_extractor = TopicExtractor()
            # if topic_extractor.contains_heterogenous_str(df_):
            
&            df_temp = topic_extractor.extract_topics(df_)
            print(df_temp)
            complex_dfs[key] = df_temp

        return df_simple, complex_dfs

