# example-jfrog-xray-alerts
Python Script for Ingesting JFrog Xray alerts in Port

## Getting started
In this example, you will ingest JFrog Xray alerts into Port. Doing this requires blueprints for JFrog Repositories and Artifacts. Repositories, Artifacts and Xray Alerts bluprints will be created to ingest the data from your Jfrog installation into Port. You will then use a Python script to make API calls to Jfrog's REST API to fetch the data from your account.


### Blueprints
Create the following blueprints in Port using the schemas:

#### Repository
```json
{
  "identifier": "jfrogRepository",
  "description": "This blueprint represents a repository on Jfrog",
  "title": "JFrog Repository",
  "icon": "JfrogXray",
  "schema": {
    "properties": {
      "key": {
        "type": "string",
        "title": "Key",
        "description": "Name of the repository"
      },
      "description": {
        "type": "string",
        "title": "Description",
        "description": "Description of the repository"
      },
      "type": {
        "type": "string",
        "title": "Repository Type",
        "description": "Type of the repository",
        "enum": [
          "LOCAL",
          "REMOTE",
          "VIRTUAL",
          "FEDERATED",
          "DISTRIBUTION"
        ],
        "enumColors": {
          "LOCAL": "blue",
          "REMOTE": "bronze",
          "VIRTUAL": "darkGray",
          "FEDERATED": "green",
          "DISTRIBUTION": "lightGray"
        }
      },
      "url": {
        "type": "string",
        "title": "Repository URL",
        "description": "URL to the repository",
        "format": "url"
      },
      "packageType": {
        "type": "string",
        "title": "Package type",
        "description": "Type of the package"
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "aggregationProperties": {},
  "relations": {}
}
```

#### Artifact
```json
{
  "identifier": "jfrogArtifact",
  "description": "This blueprint represents an artifact in our JFrog catalog",
  "title": "JFrog Artifact",
  "icon": "JfrogXray",
  "schema": {
    "properties": {
      "name": {
        "type": "string",
        "title": "Name",
        "description": "Name of the artifact"
      },
      "path": {
        "type": "string",
        "title": "Path",
        "description": "Path to artifact"
      },
      "sha256": {
        "type": "string",
        "title": "SHA 256",
        "description": "SHA256 of the artifact"
      },
      "size": {
        "type": "number",
        "title": "Size",
        "description": "Size of the artifact"
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "aggregationProperties": {},
  "relations": {
    "repository": {
      "title": "Repository",
      "description": "Repository of the artifact",
      "target": "jfrogRepository",
      "required": false,
      "many": false
    }
  }
}
```

#### Xray Alert
```json
{
  "identifier": "jfrogXrayAlert",
  "description": "This blueprint represents security scans for a JFrog artifact in Xray",
  "title": "JFrog Xray Alert",
  "icon": "JfrogXray",
  "schema": {
    "properties": {
      "id": {
        "type": "string",
        "title": "ID",
        "description": "ID of the alert"
      },
      "severity": {
        "type": "string",
        "title": "Severity",
        "description": "Severity of the scans"
      },
      "description": {
        "type": "string",
        "title": "Description",
        "description": "Description of the scans"
      },
      "abbreviation": {
        "type": "string",
        "title": "Abbreviation",
        "description": "Abbreviation of the scans"
      },
      "status": {
        "type": "string",
        "title": "Status",
        "description": "Status of the scans"
      },
      "cweId": {
        "type": "string",
        "title": "CWE ID",
        "description": "CWE ID of the scans"
      },
      "cweName": {
        "type": "string",
        "title": "CWE Name",
        "description": "CWE Name of the scans"
      },
      "outcomes": {
        "type": "string",
        "title": "Outcomes",
        "description": "Outcomes of the scans"
      },
      "fixCost": {
        "type": "string",
        "title": "Fix Cost",
        "description": "Fix Cost of the scans"
      },
      "artifactPath": {
        "type": "string",
        "title": "Artifact Path",
        "description": "Artifact Path of the scans"
      },
      "scanService": {
        "type": "string",
        "title": "Scan Service",
        "description": "Service where the scans were performed",
        "enum": [
          "SERVICES",
          "APPLICATIONS",
          "IAC"
        ],
        "enumColors": {
          "SERVICES": "blue",
          "APPLICATIONS": "green",
          "IAC": "yellow"
        }
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "aggregationProperties": {},
  "relations": {
    "repository": {
      "title": "Repository",
      "description": "Repository of the artifact",
      "target": "jfrogRepository",
      "required": true,
      "many": false
    },
    "artifact": {
      "title": "Artifact",
      "description": "Artifact of the alert",
      "target": "jfrogArtifact",
      "required": true,
      "many": false
    }
  }
}
```

### Running the Python script
First clone the repository and cd into the work directory with:
```bash
$ git clone git@github.com:port-labs/example-jfrog-xray-alerts.git
$ cd example-jfrog-xray-alerts
```

Ensure you are using Python version > 3.6. Install the needed dependencies within the context of a virtual environment with:
```bash
$ virtualenv venv
$ source venv/bin/activate
$ pip3 install -r requirements.txt
```

To ingest your data, you need to populate some environment variables. You can do that by either duplicating the `.example.env` file and renaming the copy as `.env`, then edit the values as needed; or run the commands below in your terminal:

```bash
export JFROG_ACCESS_TOKEN=access_token_here
export PORT_CLIENT_ID=port_client_id
export PORT_CLIENT_SECRET=port_client_secret
export JFROG_HOST_URL=https://subdomain.jfrog.io
```

Each variable required are:
- JFROG_ACCESS_TOKEN: You can get that by following instructions in the [Jfrog documentation](https://jfrog.com/help/r/jfrog-platform-administration-documentation/access-tokens)
- PORT_CLIENT_ID: Port Client ID
- PORT_CLIENT_SECRET: Port Client secret
- JFROG_HOST_URL: The host URL of your Jfrog instance