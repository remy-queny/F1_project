# 🏎️ Pipeline F1 & Tableau de Bord (Modern Data Stack)

**[ Voir le tableau de bord interactif Streamlit en ligne](https://f1project-lwpry5yajdlmzppgnjhqts.streamlit.app/)**

## À propos du projet
Ce projet est une architecture Data Engineering "de bout en bout" (End-to-End) 100% cloud-native. L'objectif est d'extraire des données sur la Formule 1 depuis une API externe, de les nettoyer, de les transformer de manière automatisée, et de les exposer via une application web publique. 

Il démontre la mise en place d'une **architecture Medallion** rigoureuse, associée à des pratiques CI/CD modernes.

---

## Architecture Medallion

Le traitement des données est divisé en trois couches distinctes hébergées sur **Azure Data Lake** au format optimisé **Parquet** :

*  **Couche Bronze (Ingestion) :** Récupération des données brutes depuis l'API publique (Jolpi F1) via une **Azure Function** développée en Python.
*  **Couche Silver (Nettoyage) :** Transformation, typage et nettoyage des données via **dbt** et **DuckDB**. Application stricte de règles métiers (ex: filtrage et suppression automatique des pilotes ne possédant pas de numéro de course permanent).
*  **Couche Gold (Agrégation) :** Création de tables prêtes pour l'analyse, avec des indicateurs métiers calculés (ex: regroupement des pilotes par nationalité).

---

## Stack Technique

| Catégorie | Technologies Utilisées |
| :--- | :--- |
| **Langage principal** | Python 3 |
| **Cloud Provider** | Microsoft Azure (Data Lake Storage, Azure Functions) |
| **Transformation (T)** | dbt (Data Build Tool), DuckDB |
| **Visualisation** | Streamlit, Pandas |
| **CI/CD & Automatisation** | GitHub Actions |

---

## Fonctionnalités clés

*   **Pipeline Automatisé :** Les workflows GitHub Actions s'assurent que la pipeline s'exécute de manière fiable et planifiée.
*   **Data Quality :** Intégration de tests dbt (`not_null`, `unique`) pour garantir l'intégrité de la donnée tout au long de la chaîne.
*   **Sécurité :** Gestion stricte des variables d'environnement et des secrets de connexion, que ce soit en local (via `.streamlit/secrets.toml`) ou en production sur Streamlit Cloud.
*   **Frontend Performant :** Tableau de bord dynamique avec KPIs et graphiques interactifs se mettant à jour automatiquement avec la couche Gold.

---

## Installation et exécution en local

Si vous souhaitez faire tourner ce projet sur votre machine :

**1. Cloner le dépôt**
```bash
git clone https://github.com/remy-queny/F1_project.git
cd TonRepo
```

**2. Créer l'environnement virtuel et installer les dépendances**

```bash
python -m venv .venv
source .venv/bin/activate  # Sur Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configurer les clés de sécurité**
Créer un dossier `.streamlit` à la racine et y ajouter un fichier `secrets.toml` contenant la chaîne de connexion Azure :

```toml
AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=..."
```

**4. Lancer l'application**

```bash
streamlit run app.py
```
