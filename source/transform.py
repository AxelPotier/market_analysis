import pandas as pd
from typing import List, Dict

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
                complex_dfs[col] = complex_df

            ## si tous les exemples sont des listes de dict
            elif all(isinstance(val,list) and all(isinstance(item,dict) for item in val) \
                     for val in sample_values):
                 complex_df = (df[[self.id_column, col]].copy().explode(col)
                               )
                 complex_df = complex_df.join(pd.json_normalize(complex_df[col] , sep = '_')).drop(col,axis=1)
                 complex_dfs[col] = complex_df

            ## si tous les exemples sont des dictionnaires
            elif all(isinstance(val,dict) for val in sample_values):
                complex_df = df[[self.id_column, col]].copy()
                complex_df = complex_df.join(pd.json_normalize(complex_df[col] , sep = '_')).drop(col,axis=1)
                complex_dfs[col] = complex_df

            elif (col in [ dic['col'] for dic in self.list_dic_col_split_str]  ) :
                sep = next((d for d in self.list_dic_col_split_str if d.get('col') == col), None)['sep']

                complex_df = df[[self.id_column, col]].copy()
                complex_df[col] = complex_df.apply(lambda r: r[col].split(sep=sep), axis=1)
                complex_df = ( 
                    complex_df[[self.id_column, col]]
                    .explode(col).reset_index(drop=True)
                )
                complex_dfs[col] = complex_df

            else:
                # Sinon, on crée un DataFrame individuel pour cette colonne
                complex_df = df[[self.id_column, col]].copy()
                complex_dfs[col] = complex_df

        df_simple = df[simple_cols].copy()
        return df_simple, complex_dfs


# class Transform:


    # def __init__(self):
    #     self.