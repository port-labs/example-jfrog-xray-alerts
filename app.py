import asyncio
import logging
import os
from typing import Any

import aiohttp
import dotenv
import requests

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

PORT_API_URL = "https://api.getport.io/v1"
PORT_CLIENT_ID = os.getenv("PORT_CLIENT_ID")
PORT_CLIENT_SECRET = os.getenv("PORT_CLIENT_SECRET")
JFROG_ACCESS_TOKEN = os.getenv("JFROG_ACCESS_TOKEN")
JFROG_HOST_URL = os.getenv("JFROG_HOST_URL")


REPOSITORY_BLUEPRINT = "jfrogRepository"
ARTIFACT_BLUEPRINT = "jfrogArtifact"
XRAY_ALERT_BLUEPRINT = "jfrogXrayAlert"
SERVICES = ["services", "applications", "iac", "secrets"]


## Get Port Access Token
credentials = {"clientId": PORT_CLIENT_ID, "clientSecret": PORT_CLIENT_SECRET}
token_response = requests.post(f"{PORT_API_URL}/auth/access_token", json=credentials)
access_token = token_response.json()["accessToken"]

# You can now use the value in access_token when making further requests
headers = {"Authorization": f"Bearer {access_token}"}


async def add_entity_to_port(
    session: aiohttp.ClientSession, blueprint_id, entity_object
):
    """A function to create the passed entity in Port

    Params
    --------------
    blueprint_id: str
        The blueprint id to create the entity in Port

    entity_object: dict
        The entity to add in your Port catalog

    Returns
    --------------
    response: dict
        The response object after calling the webhook
    """
    logger.info(f"Adding entity to Port: {entity_object}")
    response = await session.post(
        (
            f"{PORT_API_URL}/blueprints/"
            f"{blueprint_id}/entities?upsert=true&merge=true"
        ),
        json=entity_object,
        headers=headers,
    )
    if not response.ok:
        logger.info("Ingesting {blueprint_id} entity to port failed, skipping...")
    logger.info(f"Added entity to Port: {entity_object}")


async def get_all_repositories(session: aiohttp.ClientSession):
    logger.info("Getting all repositories")
    url = f"{JFROG_HOST_URL}/artifactory/api/repositories"
    async with session.get(
        url, headers={"Authorization": "Bearer " + JFROG_ACCESS_TOKEN}
    ) as response:
        if not response.ok:
            return []
        repositories: list[dict[str, str]] = await response.json()
        return repositories


async def get_artifacts_from_folder(session: aiohttp.ClientSession, url: str):
    artifacts: list[dict[str, any]] = []
    logger.info(f"Getting artifacts content for {url}")
    async with session.get(
        url, headers={"Authorization": "Bearer " + JFROG_ACCESS_TOKEN}
    ) as response:
        if not response.ok:
            return []
        children: list[dict[str, str]] = (await response.json())["children"]
        for child in children:
            if not child["folder"]:
                artifacts.append({"parent_url": url, **child})
            else:
                artifacts.extend(
                    await get_artifacts_from_folder(session, url + child["uri"])
                )
        return artifacts


async def get_artifact_info(
    session: aiohttp.ClientSession, url: str
) -> list[dict[str, str]]:
    logger.info(f"Getting artifact info for {url}")
    async with session.get(
        url, headers={"Authorization": "Bearer " + JFROG_ACCESS_TOKEN}
    ) as response:
        if not response.ok:
            return None
        return await response.json()


async def get_scans(session: aiohttp.ClientSession, url: str):
    logger.info(f"Getting scans for {url}")
    while url:
        async with session.get(
            url, headers={"Authorization": "Bearer " + JFROG_ACCESS_TOKEN}
        ) as response:
            if not response.ok:
                yield []
                url = None
                continue
            scan = await response.json()
            if scan.get("error"):
                yield []
                url = None
                continue
            yield scan["data"]
            url = f"{JFROG_HOST_URL}/xray{scan.get('next_page')}"


async def ingest_scan(
    session: aiohttp.ClientSession,
    scan: dict[str, any],
    artifact_object: dict[str, any],
    repository_object: dict[str, any],
    service: str,
):
    scan_object = {
        "identifier": scan["id"],
        "title": scan["id"],
        "properties": {
            "id": scan["id"],
            "severity": scan["jfrog_severity"],
            "description": scan["description"],
            "abbreviation": scan["abbreviation"],
            "status": scan["status"],
            "cweId": scan["cwe"]["cwe_id"],
            "cweName": scan["cwe"]["cwe_name"],
            "outcomes": ", ".join(scan["outcomes"]),
            "fixCost": scan["fix_cost"],
            "artifactPath": scan.get("file_path"),
            "scanService": service.upper(),
        },
        "relations": {
            "artifact": artifact_object["identifier"],
            "repository": repository_object["identifier"],
        },
    }
    await add_entity_to_port(session, XRAY_ALERT_BLUEPRINT, scan_object)


async def ingest_scans_for_service(
    session: aiohttp.ClientSession,
    artifact_object: dict[str, Any],
    repository_object: dict[str, Any],
    service: str,
):
    url = (
        f"{JFROG_HOST_URL}/xray/api/v1/{service}/"
        f"results?repo={artifact_object['relations']['repository']}&path={artifact_object['properties']['path']}"
    )
    # scans = await get_scans(session, url)
    async for scans in get_scans(session, url):
        for scan in scans:
            await ingest_scan(
                session, scan, artifact_object, repository_object, service
            )


async def ingest_artifact(
    session: aiohttp.ClientSession,
    artifact: dict[str, any],
    repository_object: dict[str, any],
):
    artifact_info = await get_artifact_info(
        session, artifact["parent_url"] + artifact["uri"]
    )
    if not artifact_info:
        return
    full_path = f"{JFROG_HOST_URL}/artifactory/{repository_object['identifier']}{artifact_info['path']}"
    artifact_object = {
        "identifier": artifact_info["path"],
        "title": artifact_info["path"].split("/")[-1],
        "properties": {
            "name": artifact_info["path"].split("/")[-1],
            "path": artifact_info["path"],
            "sha256": artifact_info["checksums"]["sha256"],
            "size": int(artifact_info["size"]),
        },
        "relations": {"repository": repository_object["identifier"]},
    }
    await add_entity_to_port(session, ARTIFACT_BLUEPRINT, artifact_object)
    logger.info(f"Added artifact: {artifact_object['properties']['path']}")

    for service in SERVICES:
        await ingest_scans_for_service(
            session, artifact_object, repository_object, service
        )


async def get_scanned_artifacts(session: aiohttp.ClientSession, url: str):
    logger.info(f"Getting scanned artifacts for {url}")
    offset = 0
    while offset >= 0:
        async with session.get(
            f"{url}&offset={offset}",
            headers={"Authorization": "Bearer " + JFROG_ACCESS_TOKEN},
        ) as response:
            if not response.ok:
                yield []
            response_data = await response.json()
            artifacts: list[dict[str, str]] = await response_data["data"]
            yield artifacts
            offset = response_data["offset"]


async def ingest_artifacts(
    session: aiohttp.ClientSession, repository_object: dict[str, any]
):
    folder_url = f"{JFROG_HOST_URL}/artifactory/api/storage/{repository_object['properties']['key']}"
    # url = f"{JFROG_HOST_URL}/xray/api/v1/artifacts?repo={repository_object['key']}"
    artifacts = await get_artifacts_from_folder(session, folder_url)
    # async for artifact in await get_scanned_artifacts(session, url):
    for artifact in artifacts:
        await ingest_artifact(session, artifact, repository_object)
    logger.info("Finished ingesting artifacts")


async def main():
    logger.info("Starting Port integration")
    async with aiohttp.ClientSession() as session:
        repositories = await get_all_repositories(session)
        for repository in repositories:
            repository_object = {
                "identifier": repository["key"],
                "title": repository["key"],
                "properties": {
                    "key": repository["key"],
                    "description": repository.get("description", ""),
                    "type": repository["type"].upper(),
                    "url": repository["url"],
                    "packageType": repository["packageType"].upper(),
                },
            }
            logger.info(f"Added repository: {repository_object['properties']['key']}")
            add_entity_to_port(session, REPOSITORY_BLUEPRINT, repository_object)

            logger.info("Starting to ingest artifacts")
            await ingest_artifacts(session, repository_object)


if __name__ == "__main__":
    asyncio.run(main())
