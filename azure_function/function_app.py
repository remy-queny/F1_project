import json
import logging
import os

import azure.functions as func
import pandas as pd
import requests
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()


def ingest_drivers() -> dict:
    """Récupère les pilotes Jolpica et écrase le Parquet Bronze Azure."""

    logging.info("--- Début ingestion des pilotes F1 ---")

    url = "https://api.jolpi.ca/ergast/f1/current/drivers.json"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()
    drivers = data["MRData"]["DriverTable"]["Drivers"]

    if not drivers:
        raise ValueError("L'API Jolpica n'a retourné aucun pilote.")

    df_drivers = pd.DataFrame(drivers)

    required_columns = {
        "driverId",
        "permanentNumber",
        "givenName",
        "familyName",
        "code",
        "dateOfBirth",
        "nationality",
    }

    missing_columns = required_columns - set(df_drivers.columns)

    if missing_columns:
        raise ValueError(
            "Colonnes Jolpica manquantes : "
            + ", ".join(sorted(missing_columns))
        )

    local_file_path = "/tmp/drivers_latest.parquet"
    df_drivers.to_parquet(local_file_path, index=False)

    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    if not connection_string:
        raise ValueError(
            "La variable AZURE_STORAGE_CONNECTION_STRING est absente."
        )

    blob_service_client = BlobServiceClient.from_connection_string(
        connection_string
    )

    blob_client = blob_service_client.get_blob_client(
        container="bronze",
        blob="drivers/drivers_latest.parquet"
    )

    with open(local_file_path, "rb") as parquet_file:
        blob_client.upload_blob(parquet_file, overwrite=True)

    result = {
        "message": "Parquet Bronze mis à jour.",
        "source": "Jolpica / Ergast",
        "blob": "bronze/drivers/drivers_latest.parquet",
        "driver_count": len(df_drivers),
        "columns": df_drivers.columns.tolist(),
    }

    logging.info(result["message"])
    logging.info("Pilotes : %s", result["driver_count"])
    logging.info("Colonnes : %s", result["columns"])

    return result


def trigger_dbt_workflow() -> None:
    """Déclenche le workflow dbt GitHub Actions via workflow_dispatch."""

    github_token = os.environ.get("GITHUB_PAT")
    github_repository = os.environ.get("GITHUB_REPOSITORY_NAME")
    github_branch = os.environ.get("GITHUB_BRANCH", "main")

    if not github_token:
        raise ValueError("La variable GITHUB_PAT est absente.")

    if not github_repository:
        raise ValueError(
            "La variable GITHUB_REPOSITORY_NAME est absente. "
            "Format attendu : proprietaire/nom-du-depot"
        )

    workflow_file = "dbt_pipeline.yml"

    url = (
        f"https://api.github.com/repos/{github_repository}"
        f"/actions/workflows/{workflow_file}/dispatches"
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {
        "ref": github_branch
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code != 204:
        raise RuntimeError(
            "Impossible de déclencher GitHub Actions : "
            f"{response.status_code} - {response.text}"
        )

    logging.info(
        "Workflow GitHub Actions '%s' déclenché sur '%s'.",
        workflow_file,
        github_branch
    )


@app.timer_trigger(
    schedule="0 0 2 * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=True
)
def scheduled_ingestion(myTimer: func.TimerRequest) -> None:
    """Ingestion quotidienne : elle ne déclenche pas dbt automatiquement."""

    try:
        ingest_drivers()
    except Exception:
        logging.exception("Échec de l'ingestion planifiée F1.")
        raise


@app.route(
    route="refresh-f1",
    methods=["POST"],
    auth_level=func.AuthLevel.FUNCTION
)
def refresh_f1(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint manuel :
    POST https://<function-app>.azurewebsites.net/api/refresh-f1?code=<FUNCTION_KEY>
    """

    try:
        ingestion_result = ingest_drivers()
        trigger_dbt_workflow()

        response_body = {
            "status": "accepted",
            "message": (
                "Bronze a été mis à jour. "
                "Le workflow dbt GitHub Actions a été déclenché : "
                "Silver et Gold seront générés par ce workflow."
            ),
            "ingestion": ingestion_result,
        }

        return func.HttpResponse(
            body=json.dumps(response_body, ensure_ascii=False),
            status_code=202,
            mimetype="application/json"
        )

    except Exception as error:
        logging.exception("Échec du rafraîchissement manuel F1.")

        return func.HttpResponse(
            body=json.dumps(
                {
                    "status": "error",
                    "message": str(error)
                },
                ensure_ascii=False
            ),
            status_code=500,
            mimetype="application/json"
        )