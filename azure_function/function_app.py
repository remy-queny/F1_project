import azure.functions as func
import logging
import requests
import pandas as pd
import os
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()

# Le Declencheur (Tous les jours à 2h00)
@app.timer_trigger(schedule="0 */2 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def IngestF1Data(myTimer: func.TimerRequest) -> None:
    logging.info('--- Demarrage du pipeline d\'ingestion F1 ---')

    # Gestion des erreurs
    try:
        # EXTRACTION
        logging.info("1. Appel de l'API OpenF1...")
        url = "https://api.openf1.org/v1/drivers?session_key=latest"
        response = requests.get(url)
        response.raise_for_status() 
        
        data = response.json()
        df_drivers = pd.DataFrame(data)
        logging.info(f"-> Succes : {len(df_drivers)} pilotes recuperes.")

        # TRANSFORMATION (Parquet)
        logging.info("2. Conversion au format Parquet...")
        local_file_path = "/tmp/drivers_latest.parquet" # seul le dossier '/tmp' autorise l'ecriture de fichiers temporaires
        df_drivers.to_parquet(local_file_path, index=False)
        logging.info("-> Succès : Fichier temporaire cree dans /tmp.")

        # CHARGEMENT (Azure Blob Storage)
        logging.info("3. Envoi vers le Data Lake Azure...")
        connection_string = os.environ.get("AZURE_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("La chaine de connexion Azure est introuvable !")

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container="bronze", blob="drivers/drivers_latest.parquet")

        with open(local_file_path, "rb") as file_data:
            blob_client.upload_blob(file_data, overwrite=True)

        logging.info("-> SUCCES FINAL : Donnees ingerees dans la couche Bronze !")

    except Exception as e:
        # Si la moindre chose plante au-dessus, on arrive ici
        logging.error(f"ERREUR CRITIQUE DANS LE PIPELINE ! Details : {e}")