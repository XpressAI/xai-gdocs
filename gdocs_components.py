from xai_components.base import InArg, OutArg, Component, xai_component
import json
import os
from google.auth.transport import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from xai_components.base import InArg, OutArg, Component, xai_component
import re
from xai_components.base import InCompArg, Component, OutArg, xai_component
import json
import os
from google.auth.transport import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from xai_components.base import InArg, OutArg, Component, xai_component
import markdown
from xai_components.base import InArg, OutArg, Component, xai_component
import json
import os
from google.auth.transport import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from bs4 import BeautifulSoup


### - Markdown to gdocs

def get_document_end_index(service, document_id):
    # Retrieve the current document to get its content
    document = service.documents().get(documentId=document_id).execute()
    content = document.get('body').get('content')
    
    # Find the last index of the text content
    end_index = 1  # Start after the document start
    for element in content:
        if 'endIndex' in element:
            end_index = element['endIndex'] - 1  # Set to the last valid position
    
    return end_index

def markdown_to_docs_requests(service, document_id, markdown_content):
    # Get the end index of the document
    current_index = get_document_end_index(service, document_id)

    html = markdown.markdown(markdown_content)
    html = '<html><body>' + html + '</body></html>'
    soup = BeautifulSoup(html, 'html.parser')
    requests = []

    for element in soup.body.children:
        if element.name == 'p':
            paragraph_elements = []
            for child in element.children:
                text_run = {}
                if child.name == 'strong' or child.name == 'b':
                    text_run['text'] = child.text
                    text_run['textStyle'] = {'bold': True}
                elif child.name == 'em' or child.name == 'i':
                    text_run['text'] = child.text
                    text_run['textStyle'] = {'italic': True}
                elif child.name == 'a':
                    text_run['text'] = child.text
                    text_run['textStyle'] = {'link': {'url': child['href']}}
                elif child.name == 'code':
                    text_run['text'] = child.text
                    text_run['textStyle'] = {'code': True}
                else:
                    text_run['text'] = child.string if child.string else str(child)

                if text_run:
                    paragraph_elements.append(text_run)

            text_to_insert = ""
            for text_run in paragraph_elements:
                text_to_insert += text_run.get('text', "")

            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text_to_insert + '\n'
                }
            })

            char_index = 0
            for text_run in paragraph_elements:
                text = text_run.get('text', "")
                if 'textStyle' in text_run:
                    requests.append({
                        'updateTextStyle': {
                            'range': {
                                'startIndex': current_index + char_index,
                                'endIndex': current_index + char_index + len(text)
                            },
                            'textStyle': text_run['textStyle'],
                            'fields': ','.join(text_run['textStyle'].keys())
                        }
                    })
                char_index += len(text)

            current_index += len(text_to_insert) + 1

        elif element.name == 'h1':
            requests.extend(create_heading_request(element.text, 'HEADING_1', current_index))
            current_index += len(element.text) + 1
        elif element.name == 'h2':
            requests.extend(create_heading_request(element.text, 'HEADING_2', current_index))
            current_index += len(element.text) + 1
        elif element.name == 'h3':
            requests.extend(create_heading_request(element.text, 'HEADING_3', current_index))
            current_index += len(element.text) + 1
        elif element.name == 'ul':
            for li in element.find_all('li'):
                requests.extend(create_list_item_request(li.text, 'LIST_BULLET', current_index))
                current_index += len(li.text) + 1
        elif element.name == 'ol':
            for li in element.find_all('li'):
                requests.extend(create_list_item_request(li.text, 'LIST_NUMBERED', current_index))
                current_index += len(li.text) + 1
        elif element.name == 'hr':
            requests.append({
                'insertHorizontalRule': {
                    'location': {'index': current_index}
                }
            })
            current_index += 1
        elif element.name == 'blockquote':
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': element.text + '\n'
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'paragraphStyle': {
                        'indentation': {
                            'left': {
                                'unit': 'PT',
                                'value': 36
                            }
                        }
                    },
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(element.text)
                    },
                    'fields': 'indentation'
                }
            })
            current_index += len(element.text) + 1

    return requests





def create_heading_request(text, heading_type, index):
    return [
        {
            'insertText': {
                'location': {'index': index},
                'text': text + '\n'
            },
        },
        {
            'updateParagraphStyle': {
                'paragraphStyle': {
                    'namedStyleType': heading_type
                },
                'range': {
                    'startIndex': index,
                    'endIndex': index + len(text)
                },
                'fields': 'namedStyleType'
            }
        }
    ]

def create_list_item_request(text, list_type, index):
    return [
        {
            'insertText': {
                'location': {'index': index},
                'text': text + '\n'
            },
        },
        {
            'updateParagraphStyle': {
                'paragraphStyle': {
                    'bulletPreset': list_type
                },
                'range': {
                    'startIndex': index,
                    'endIndex': index + len(text)
                },
                'fields': 'bulletPreset'
            }
        }
    ]



### - gdoc to markdown

def fetch_google_docs_files(files):
    """
    Downloads documents (by documentId) using the Docs API and writes them as Markdown files.
    The documentId may contain a colon; if so, the portion after the colon is used as the filename.
    """
    for document_id in files:
        print("\nDownloading document", document_id)
        try:
            # If the provided id contains a colon, use what is before it as the actual documentId.
            doc_id = document_id.split(":")[0]
            result = docs.documents().get(documentId=doc_id).execute()

            # Determine the output filename.
            if ":" in document_id:
                title = document_id.split(":")[1]
            else:
                # Fall back to: document title with an .md extension.
                title = f"{result.get('title', 'untitled')}.md"

            if not title:
                raise Exception("Title not found")

            # Write the Markdown file.
            md_text = google_docs_to_markdown(result)
            with open(join(".", title), "w", encoding="utf-8") as out_file:
                out_file.write(md_text)
            print("Downloaded document", result.get("title"))
        except Exception as error:
            print("Got an error", error)


def google_docs_to_markdown(file: dict) -> str:
    """
    Converts a Google Docs JSON response object to a Markdown formatted string.
    """
    file_title = file.get("title", "")
    file_id = file.get("documentId", "")
    revision_id = file.get("revisionId", "")
    text = (f"---\n"
            f"title: {file_title}\n"
            f"documentId: {file_id}\n"
            f"revisionId: {revision_id}\n"
            f"---\n\n")

    content_list = file.get("body", {}).get("content", [])
    for item in content_list:
        # PROCESS TABLES
        if "table" in item and item["table"].get("tableRows"):
            table = item["table"]
            table_rows = table.get("tableRows", [])
            # Create a blank header row if there are cells in the first row.
            first_row_cells = table_rows[0].get("tableCells", []) if table_rows else []
            blank_cells = [""] * len(first_row_cells)
            text += "|" + "|".join(blank_cells) + "|\n"
            text += "|" + "|".join(["-" for _ in blank_cells]) + "|\n"
            # Process each row.
            for row in table_rows:
                row_cells = row.get("tableCells", [])
                text_rows = []
                for cell in row_cells:
                    # The cell content is a list; process each content element.
                    for content_item in cell.get("content", []):
                        paragraph = content_item.get("paragraph")
                        if paragraph:
                            style_type = paragraph.get("paragraphStyle", {}).get("namedStyleType")
                            # Process each paragraph element.
                            for element in paragraph.get("elements", []):
                                elem_str = style_element(element, style_type)
                                # In the original TS code, whitespace is removed.
                                if elem_str:
                                    elem_str = "".join(elem_str.split())
                                    text_rows.append(elem_str)
                # Join cell text with pipe separators.
                text += f"| {' | '.join(text_rows)} |\n"

        # PROCESS PARAGRAPHS & LISTS
        if "paragraph" in item and "elements" in item["paragraph"]:
            paragraph = item["paragraph"]
            style_type = paragraph.get("paragraphStyle", {}).get("namedStyleType")
            bullet = paragraph.get("bullet")
            # If this is part of a list.
            if bullet and bullet.get("listId"):
                list_id = bullet.get("listId")
                list_details = file.get("lists", {}).get(list_id, {})
                nesting_levels = list_details.get("listProperties", {}).get("nestingLevels", [])
                glyph_format = ""
                if nesting_levels:
                    glyph_format = nesting_levels[0].get("glyphFormat", "")
                # Create a padding: two spaces per nesting level.
                nesting_level = bullet.get("nestingLevel", 0)
                padding = "  " * nesting_level
                if glyph_format in ["[%0]", "%0."]:
                    text += f"{padding}1. "
                else:
                    text += f"{padding}- "

            # Process each paragraph element.
            for element in paragraph.get("elements", []):
                # Only add element text if there is content and it is not just a newline.
                element_text = content(element)
                if element_text and element_text != "\n":
                    text += style_element(element, style_type)

            # Append newlines.
            if bullet and bullet.get("listId"):
                # If part of a bullet list, ensure the last line ends with a newline.
                if not text.endswith("\n"):
                    text += "\n"
            else:
                text += "\n\n"

    # Remove any extra blank lines that may appear between list items.
    lines = text.split("\n")
    lines_to_delete = []
    for index in range(len(lines)):
        if index > 2:
            prev_line = lines[index - 1] if index - 1 >= 0 else ""
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if (not lines[index].strip() and
                (prev_line.strip().startswith("1. ") or prev_line.strip().startswith("- ")) and
                (next_line.strip().startswith("1. ") or next_line.strip().startswith("- "))):
                lines_to_delete.append(index)
    text = "\n".join([line for i, line in enumerate(lines) if i not in lines_to_delete])
    # Remove lines that are totally empty and collapse multiple empty lines.
    text = re.sub(r'\n\s*\n\s*\n', "\n\n", text)
    # Ensure the final output ends with a newline.
    return text.rstrip() + "\n"


def style_element(element, style_type=None):
    """
    Apply Markdown formatting to a single element based on the style type or text style.
    """
    elem_content = content(element)
    if not elem_content:
        return ""
    if style_type == "TITLE":
        return "# " + elem_content
    elif style_type == "SUBTITLE":
        return "_" + elem_content.strip() + "_"
    elif style_type == "HEADING_1":
        return "## " + elem_content
    elif style_type == "HEADING_2":
        return "### " + elem_content
    elif style_type == "HEADING_3":
        return "#### " + elem_content
    elif style_type == "HEADING_4":
        return "##### " + elem_content
    elif style_type == "HEADING_5":
        return "###### " + elem_content
    elif style_type == "HEADING_6":
        return "####### " + elem_content
    # Check for inline formatting: bold and italic.
    text_style = element.get("textRun", {}).get("textStyle", {})
    is_bold = text_style.get("bold")
    is_italic = text_style.get("italic")
    if is_bold and is_italic:
        return f"**_{elem_content}_**"
    elif is_italic:
        return f"_{elem_content}_"
    elif is_bold:
        return f"**{elem_content}**"
    return elem_content


def content(element):
    """
    Extract the text content from an element.
    If the textRun contains a link, formats it as a Markdown link.
    """
    text_run = element.get("textRun")
    if not text_run:
        return ""
    text = text_run.get("content", "")
    link = text_run.get("textStyle", {}).get("link", {}).get("url")
    if link:
        return f"[{text}]{link}"
    return text


### - Components

@xai_component
class GoogleDocAuth(Component):
    """A component to authenticate the user with Google Docs and generate a client object.

    ##### inPorts:
    - json_path: The path to the JSON key file for OAuth2 authentication.

    ##### outPorts:
    - gc: A Gspread client object.
    """

    json_path: InArg[str]
    client: OutArg[any]

    def execute(self, ctx) -> None:
        # Load credentials from the specified JSON file
        credentials_path = self.json_path.value
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Credentials file not found: {credentials_path}")

        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/documents']
        )

        # Create the service
        service = build('docs', 'v1', credentials=creds)

        self.client.value = service
        
        ctx.update({'gdocs': service})


@xai_component
class GoogleDocGetDocIdFromUrl(Component):
    """A component that extracts the document ID from a full Google Docs URL.

    ##### inPorts:
    - gdoc_url (str): The full URL of the Google Doc.

    ##### outPorts:
    - doc_id (str): The extracted document ID.
    """
    gdoc_url: InArg[str]
    doc_id: OutArg[str]

    def execute(self, ctx) -> None:
        # Extract the document ID using a regular expression
        url = self.gdoc_url.value
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)

        if match:
            self.doc_id.value = match.group(1)  # Extracted document ID
        else:
            raise ValueError("Invalid Google Docs URL. Unable to extract document ID.")


@xai_component
class GoogleDocGetContent(Component):
    """A component that retrieves the content of a Google Doc.

    ##### inPorts:
    - doc_id (str): The ID of the Google Doc to retrieve content from.
    - credentials_path (str): The path to the JSON file containing Google API credentials.

    ##### outPorts:
    - content (str): The content of the Google Doc.
    """

    client: InArg[any]
    doc_id: InCompArg[str]
    content: OutArg[str]

    def execute(self, ctx) -> None:
        if self.client.value is not None:
            service = self.client.value
        else:
            service = ctx['gdocs']

        document = service.documents().get(documentId=self.doc_id.value).execute()
        md_text = google_docs_to_markdown(document)        
        self.content.value = md_text


@xai_component
class GoogleDocAppendContent(Component):
    """A component that appends formatted markdown content to a Google Doc."""

    client: InArg[any]
    doc_id: InCompArg[str]
    content_to_append: InCompArg[str]
    success: OutArg[bool]

    def execute(self, ctx) -> None:
        if self.client.value is not None:
            service = self.client.value
        else:
            service = ctx['gdocs']

        # Prepare the request to append content
        document_id = self.doc_id.value
        markdown_content = self.content_to_append.value

        # Get the end index of the document
        current_index = get_document_end_index(service, document_id)

        # Convert markdown to Google Docs requests
        requests = markdown_to_docs_requests(service, document_id, markdown_content)

        # Variable to track the length of the last inserted text
        last_insert_length = 0

        for request in requests:
            if 'insertText' in request:
                # Set the location index for insertText to the current end of the document
                request['insertText']['location']['index'] = current_index

                # Get the text to be inserted
                inserted_text = request['insertText']['text']
                inserted_length = len(inserted_text)

                # Update the current index based on the inserted text length
                current_index += inserted_length

                # Store the length of the last inserted text
                last_insert_length = inserted_length

            elif 'updateTextStyle' in request or 'updateParagraphStyle' in request:
                # Determine which type of update this is
                if 'updateTextStyle' in request:
                    style_request = request['updateTextStyle']
                else:
                    style_request = request['updateParagraphStyle']

                # Adjust the range indices based on the last insertion
                style_request['range']['startIndex'] += current_index - last_insert_length
                style_request['range']['endIndex'] += current_index - last_insert_length

        # Execute the batch update request
        try:
            service.documents().batchUpdate(documentId=document_id, body={'requests': requests}).execute()
            self.success.value = True
        except Exception as e:
            print(f"An error occurred: {e}")
            raise e
            self.success.value = False


@xai_component
class GoogleDocUpdateContent(Component):
    """A component that updates text in a Google Doc by replacing specified content.

    ##### inPorts:
    - doc_id (str): The ID of the Google Doc to update.
    - text_to_replace (str): The text to be replaced in the document.
    - new_content (str): The new content to replace the old text.
    - credentials_path (str): The path to the JSON file containing Google API credentials.

    ##### outPorts:
    - success (bool): Indicates whether the text was successfully updated.
    """
    client: InArg[any]
    doc_id: InArg[str]
    text_to_replace: InArg[str]
    new_content: InArg[str]
    success: OutArg[bool]

    def execute(self, ctx) -> None:
        if self.client.value is not None:
            service = self.client.value
        else:
            service = ctx['gdocs']

        # Prepare the request to replace text
        document_id = self.doc_id.value
        text_to_replace = self.text_to_replace.value
        new_content = self.new_content.value

        print("new_content:")
        print(new_content)
        
        requests = markdown_to_docs_requests(service, document_id, new_content)
        print("requests:")
        print(requests)

        # Optional: Replace existing text first
        if text_to_replace:
            replace_requests = [{
                'replaceAllText': {
                    'replaceText': '',
                    'containsText': {
                        'text': text_to_replace,
                        'matchCase': True
                    }
                }
            }]
            try:
                service.documents().batchUpdate(documentId=document_id, body={'requests': replace_requests}).execute()
            except Exception as e:
                print(f"An error occurred: {e}", flush=True)
                self.success.value = False
        else:
            try:
                for request in requests:
                    service.documents().batchUpdate(documentId=document_id, body={'requests': [request]}).execute()
                self.success.value = True
            except Exception as e:
                print(f"An error occurred: {e}", flush=True)
                self.success.value = False
