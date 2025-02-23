import os
import re
import markdown
from bs4 import BeautifulSoup

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Xircuits component decorators and port definitions
from xai_components.base import InArg, OutArg, Component, xai_component, InCompArg

# ----------------- Utility Functions -----------------

def get_document_end_index(service, document_id):
    """
    Retrieve the current end index of the document.
    Returns an integer index that serves as an insertion point.
    """
    document = service.documents().get(documentId=document_id).execute()
    content = document.get("body", {}).get("content", [])
    # Default insertion index is 1 (start after document start)
    end_index = 1
    for element in content:
        if "endIndex" in element:
            end_index = element["endIndex"] - 1
    return end_index

def parse_markdown_to_requests(markdown_content, base_index):
    """
    Convert markdown into a continuous text block and generate a list of style update requests.
    The new text is assumed to be inserted at base_index, so all update request ranges are offset accordingly.
    Supports basic inline formatting in paragraphs/headings (bold, italic, links, code).
    
    Returns:
       (insertion_text, style_requests)
    """
    html = markdown.markdown(markdown_content)
    soup = BeautifulSoup("<html><body>" + html + "</body></html>", "html.parser")
    
    insertion_text = ""
    style_requests = []
    current_offset = 0  # Offset within the new text block
    
    for element in soup.body.children:
        if element.name in ["p", "blockquote"]:
            block_text = ""
            inline_requests = []
            for child in element.children:
                child_text = ""
                style = {}
                if child.name in ["strong", "b"]:
                    child_text = child.get_text()
                    style = {"bold": True}
                elif child.name in ["em", "i"]:
                    child_text = child.get_text()
                    style = {"italic": True}
                elif child.name == "a":
                    child_text = child.get_text()
                    style = {"link": {"url": child.get("href")}}
                elif child.name == "code":
                    child_text = child.get_text()
                    style = {"code": True}
                else:
                    child_text = child.string if child.string is not None else child.get_text()
                start = len(block_text)
                block_text += child_text
                if style and child_text.strip():
                    inline_requests.append({
                        "range_offset": start,
                        "length": len(child_text),
                        "textStyle": style,
                        "fields": ",".join(style.keys())
                    })
            insertion_text += block_text + "\n"
            for req in inline_requests:
                style_requests.append({
                    "updateTextStyle": {
                        "range": {
                            "startIndex": base_index + current_offset + req["range_offset"],
                            "endIndex": base_index + current_offset + req["range_offset"] + req["length"]
                        },
                        "textStyle": req["textStyle"],
                        "fields": req["fields"]
                    }
                })
            current_offset += len(block_text) + 1
        elif element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            text = element.get_text()
            insertion_text += text + "\n"
            # Apply bold styling for headings as an example.
            style_requests.append({
                "updateTextStyle": {
                    "range": {
                        "startIndex": base_index + current_offset,
                        "endIndex": base_index + current_offset + len(text)
                    },
                    "textStyle": {"bold": True},
                    "fields": "bold"
                }
            })
            current_offset += len(text) + 1
        elif element.name in ["ul", "ol"]:
            bullet = "- " if element.name=="ul" else "1. "
            for li in element.find_all("li"):
                li_text = li.get_text()
                line = bullet + li_text
                insertion_text += line + "\n"
                current_offset += len(line) + 1
        elif element.name == "hr":
            line = "----------\n"
            insertion_text += line
            current_offset += len(line)
        else:
            text = element.get_text()
            insertion_text += text + "\n"
            current_offset += len(text) + 1

    return insertion_text, style_requests

def find_marker_range(document: dict, marker: str):
    """
    Search the document's body for the first occurrence of marker.
    Returns a tuple (start_index, end_index) for the marker, or (None, None) if not found.
    """
    content = document.get("body", {}).get("content", [])
    for element in content:
        if "paragraph" in element:
            para = element["paragraph"]
            elements = para.get("elements", [])
            # Use paragraph startIndex if present.
            current_index = element.get("startIndex", 0)
            for el in elements:
                text_run = el.get("textRun")
                if not text_run:
                    continue
                text = text_run.get("content", "")
                marker_pos = text.find(marker)
                if marker_pos != -1:
                    # Use the element's startIndex (if available) to compute absolute index.
                    element_start = el.get("startIndex", current_index)
                    start_index = element_start + marker_pos
                    end_index = start_index + len(marker)
                    return start_index, end_index
    return None, None

# ----------------- Components -----------------

@xai_component
class GoogleDocAuth(Component):
    """
    Authenticate with Google Docs using the JSON key file.
    inPorts:
      - json_path (str): Path to the credentials JSON.
    outPorts:
      - client: The authenticated Docs service client.
    """
    json_path: InArg[str]
    client: OutArg[any]

    def execute(self, ctx) -> None:
        credentials_path = self.json_path.value
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/documents"]
        )
        service = build("docs", "v1", credentials=creds)
        self.client.value = service
        ctx.update({"gdocs": service})

@xai_component
class GoogleDocGetDocIdFromUrl(Component):
    """
    Extract the document ID from a full Google Docs URL.
    inPorts:
      - gdoc_url (str): The document's URL.
    outPorts:
      - doc_id (str): The extracted document ID.
    """
    gdoc_url: InArg[str]
    doc_id: OutArg[str]

    def execute(self, ctx) -> None:
        url = self.gdoc_url.value
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
        if match:
            self.doc_id.value = match.group(1)
        else:
            raise ValueError("Invalid Google Docs URL. Unable to extract document ID.")

@xai_component
class GoogleDocGetContent(Component):
    """
    Retrieve the content of a Google Doc as plain text for review.
    inPorts:
      - client
      - doc_id
    outPorts:
      - content (str)
    """
    client: InArg[any]
    doc_id: InCompArg[str]
    content: OutArg[str]

    def execute(self, ctx) -> None:
        service = self.client.value if self.client.value is not None else ctx["gdocs"]
        document = service.documents().get(documentId=self.doc_id.value).execute()
        doc_title = document.get("title", "Untitled")
        content_text = ""
        for element in document.get("body", {}).get("content", []):
            if "paragraph" in element:
                for el in element["paragraph"].get("elements", []):
                    try:
                        content_text += el["textRun"]["content"]
                    except KeyError:
                        pass
        self.content.value = f"# {doc_title}\n\n{content_text}"

@xai_component
class GoogleDocUpdateContent(Component):
    """
    Targeted update of a Google Doc by replacing the first occurrence of a marker with new text.
    The marker is replaced in place (with its original formatting preserved if possible).
    
    inPorts:
      - client
      - doc_id
      - marker (str): Text to search for in the document.
      - new_text (str): Replacement text.
    outPorts:
      - success (bool)
    """
    client: InArg[any]
    doc_id: InArg[str]
    marker: InArg[str]
    new_text: InArg[str]
    success: OutArg[bool]

    def execute(self, ctx) -> None:
        service = self.client.value if self.client.value is not None else ctx["gdocs"]
        document_id = self.doc_id.value
        marker = self.marker.value
        replacement = self.new_text.value
        
        document = service.documents().get(documentId=document_id).execute()
        start_index, end_index = find_marker_range(document, marker)
        if start_index is None:
            print(f"Marker '{marker}' not found in the document.")
            self.success.value = False
            return
        
        requests = [
            {
                "deleteContentRange": {
                    "range": {"startIndex": start_index, "endIndex": end_index}
                }
            },
            {
                "insertText": {
                    "location": {"index": start_index},
                    "text": replacement
                }
            }
            # Optionally: add an updateTextStyle request here to apply specific formatting.
        ]
        try:
            service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
            self.success.value = True
        except Exception as e:
            print(f"Error during targeted update: {e}")
            self.success.value = False

@xai_component
class GoogleDocAppendContent(Component):
    """
    Append new markdown content to the end of a Google Doc while preserving existing formatting.
    inPorts:
      - client
      - doc_id
      - content_to_append (str): Markdown content to append.
    outPorts:
      - success (bool)
    """
    client: InArg[any]
    doc_id: InCompArg[str]
    content_to_append: InArg[str]
    success: OutArg[bool]

    def execute(self, ctx) -> None:
        service = self.client.value if self.client.value is not None else ctx["gdocs"]
        document_id = self.doc_id.value
        
        # Get the document's current end index.
        current_index = get_document_end_index(service, document_id)
        
        # Convert markdown to text block and inline style update requests.
        new_text, style_requests = parse_markdown_to_requests(self.content_to_append.value, base_index=current_index)
        
        # Build batchUpdate: first insert text, then update text style.
        batch_requests = [{
            "insertText": {
                "location": {"index": current_index},
                "text": new_text
            }
        }]
        batch_requests.extend(style_requests)
        
        try:
            service.documents().batchUpdate(documentId=document_id, body={"requests": batch_requests}).execute()
            self.success.value = True
        except Exception as e:
            print(f"Error during appending content: {e}")
            self.success.value = False
