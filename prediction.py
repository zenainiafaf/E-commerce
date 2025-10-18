import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib
import numpy as np

# Charger les données
df = pd.read_csv("dataset/clean_data.csv")

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

def afficher_caracteristiques(df):
    print("\n📌 Informations générales sur le dataset :")
    print(df.info())

    print("\n🔍 Aperçu des premières lignes :")
    print(df.head())

    print("\n📋 Statistiques descriptives (numériques) :")
    print(df.describe())

    print("\n📋 Statistiques descriptives (catégoriques) :")
    print(df.describe(include='object'))

    print("\n🔎 Valeurs uniques par colonne :")
    for col in df.columns:
        print(f"\n🧩 Colonne : {col}")
        print(df[col].value_counts())
        print("-" * 40)


# Sélection des colonnes utiles
features = ['brand', 'bag style', 'skin type', 'inner material', 'major color', 'volume', 'accessories']
target = 'price'

# Garder uniquement les colonnes nécessaires
df = df[features + [target]]

# Affichage des informations de départ
print("\n📊 Aperçu des données :")
print(df)
print("\n✅ Colonnes utilisées pour la prédiction :", features)

# Gestion des valeurs manquantes
initial_shape = df.shape[0]
df = df.dropna()
final_shape = df.shape[0]
print(f"\n🧹 Lignes supprimées pour nettoyage : {initial_shape - final_shape}")
print(f"📈 Nombre d'exemples utilisés après nettoyage : {final_shape}")

# Séparation des variables catégorielles et numériques
categorical_features = [col for col in features if df[col].dtype == 'object']
numerical_features = [col for col in features if df[col].dtype != 'object']

# Préprocesseur avec OneHotEncoder pour gérer les catégories inconnues
preprocessor = ColumnTransformer(
    transformers=[
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features),
        ('num', 'passthrough', numerical_features)
    ])

# Création du pipeline avec RandomForest
model = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
])

# Séparer les données
X = df[features]
y = df[target]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Entraînement du modèle
model.fit(X_train, y_train)


# Sauvegarde du pipeline complet
joblib.dump(model, 'model_pipeline.pkl')
print("\n✅ Pipeline (modèle + encodage) sauvegardé avec succès !")
