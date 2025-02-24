# Xircuits Google Docs Component Library

A Xircuits Component Library for interacting with Google Docs API. This library provides components for reading, creating, and modifying Google Docs documents programmatically through Xircuits workflows.

## Features

- Authenticate with Google Docs API
- Extract document IDs from Google Docs URLs
- Read content from Google Docs
- Append content to existing documents
- Update document content
- Convert between Markdown and Google Docs formats
- Delete document content

## Prerequisites

1. A Google Cloud Project with the Google Docs API enabled
2. Service Account credentials (JSON key file) with appropriate permissions
3. Python 3.7 or later
4. Required Python packages (installed automatically):
   - google-auth
   - google-auth-oauthlib
   - google-auth-httplib2
   - google-api-python-client
   - beautifulsoup4
   - markdown

## Installation

To use this component library, ensure you have Xircuits installed, then run:

```
xircuits install https://github.com/XpressAI/xai-gdocs
```

Alternatively, you can manually clone the repository to your Xircuits project directory and install dependencies:

```
pip install -r requirements.txt
```

## Authentication Setup

1. Create a project in Google Cloud Console
2. Enable the Google Docs API
3. Create a Service Account and download the JSON key file
4. Store the JSON key file securely and provide its path to the GoogleDocAuth component

## Available Components

- **GoogleDocAuth**: Authenticates with Google Docs API using service account credentials
- **GoogleDocGetDocIdFromUrl**: Extracts document ID from a Google Docs URL
- **GoogleDocGetContent**: Retrieves content from a Google Doc
- **GoogleDocAppendContent**: Appends formatted markdown content to a document
- **GoogleDocUpdateContent**: Updates existing content in a document
- **GoogleDocDeleteContent**: Deletes existing content in a document

## Tests

A github action to test your workflow runs has been provided. Simply add the path of your workflows [here](.github/workflows/run-workflow-tests.yml#L11).
