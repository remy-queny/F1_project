import json
import logging
import os

import azure.functions as func
import pandas as pd
import requests
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()


def ingest_drivers() -> dict:
    """
    Récupère les pilotes depuis l'API Jolpica,
    crée un fichier Parquet et le charge dans Azure Blob Storage.
    """

    logging.info("--- Début de l'ingestion F1 / Jolpica ---")

    url = "https://api.jolpi.ca/ergast/f1/current/drivers.json"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()

    try:
        drivers = data["MRData"]["DriverTable"]["Drivers"]
    except KeyError as error:
        raise ValueError(
            "Structure JSON Jolpica inattendue : "
            "MRData → DriverTable → Drivers introuvable."
        ) from error

    if not drivers:
        raise ValueError("L'API Jolpica n'a retourné aucun pilote.")

    df_drivers = pd.DataFrame(drivers)

    expected_columns = [
        "driverId",
        "permanentNumber",
        "code",
        "url",
        "givenName",
        "familyName",
        "dateOfBirth",
        "nationality",
    ]

    for column in expected_columns:
        if column not in df_drivers.columns:
            logging.warning(
                "Colonne absente dans la réponse Jolpica : %s",
                column
            )
            df_drivers[column] = None

    df_drivers = df_drivers[expected_columns]

    logging.info(
        "Nombre de pilotes récupérés : %s",
        len(df_drivers)
    )

    logging.info(
        "Colonnes du DataFrame : %s",
        df_drivers.columns.tolist()
    )

    local_file_path = "/tmp/drivers_latest.parquet"

    df_drivers.to_parquet(
        local_file_path,
        index=False
    )

    logging.info(
        "Fichier Parquet temporaire créé : %s",
        local_file_path
    )

    connection_string = os.environ.get(
        "AZURE_STORAGE_CONNECTION_STRING"
    )

    if not connection_string:
        raise ValueError(
            "La variable AZURE_STORAGE_CONNECTION_STRING "
            "est absente des variables d'environnement Azure."
        )

    blob_service_client = BlobServiceClient.from_connection_string(
        connection_string
    )

    blob_client = blob_service_client.get_blob_client(
        container="bronze",
        blob="drivers/drivers_latest.parquet"
    )

    with open(local_file_path, "rb") as parquet_file:
        blob_client.upload_blob(
            parquet_file,
            overwrite=True
        )

    logging.info(
        "Parquet Bronze envoyé avec succès : "
        "bronze/drivers/drivers_latest.parquet"
    )

    return {
        "status": "success",
        "message": "La couche Bronze a été actualisée avec Jolpica.",
        "source": "https://api.jolpi.ca/ergast/f1/current/drivers.json",
        "blob": "bronze/drivers/drivers_latest.parquet",
        "driver_count": len(df_drivers),
        "columns": df_drivers.columns.tolist(),
    }


@app.timer_trigger(
    schedule="0 0 2 * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=True
)
def scheduled_ingestion(myTimer: func.TimerRequest) -> None:
    """
    Exécution automatique quotidienne.
    Met seulement à jour la couche Bronze.
    """

    try:
        logging.info("--- Déclenchement planifié ---")
        ingest_drivers()

    except Exception:
        logging.exception(
            "Échec de l'ingestion F1 planifiée."
        )
        raise


@app.route(
    route="refresh-f1",
    methods=["POST"],
    auth_level=func.AuthLevel.FUNCTION
)
def refresh_f1(req: func.HttpRequest) -> func.HttpResponse:
    """
    Exécution manuelle HTTP.

    Dans Azure Portal :
    refresh_f1 → Code + test → Test/exécution → POST → Exécuter.
    """

    try:
        logging.info("--- Déclenchement manuel HTTP ---")

        result = ingest_drivers()

        return func.HttpResponse(
            body=json.dumps(
                result,
                ensure_ascii=False,
                indent=2
            ),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as error:
        logging.exception(
            "Échec du rafraîchissement manuel F1."
        )

        response_body = {
            "status": "error",
            "message": str(error)
        }

        return func.HttpResponse(
            body=json.dumps(
                response_body,
                ensure_ascii=False,
                indent=2
            ),
            status_code=500,
            mimetype="application/json"
        )