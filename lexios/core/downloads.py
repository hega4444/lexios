# downloads.py
import os
import re
import openai

from admin.verify_folder import find_project_folder
from lexios.core.logger import CustomLogger, DEBUG, INFO
from lexios.core.exceptions import LexiException

PROJECT_FOLDER = find_project_folder()

def manage_downloads(self, message: str):
    """
    It handles the parsing of messages containing attachments. It recovers files from 
    openAI endpoint.
    """
    # Extract the message content

    message_content = message.content[0].text.value
    annotations = message.content[0].text.annotations
    citations = []
    attachments = {}

    try:
        # Iterate over the annotations and add footnotes
        for index, annotation in enumerate(annotations):

            # Remove the annotations (for now)
            message_content = message_content.replace(annotation.text, "")

            # Regular expression to match text starting with "[Download" and ending with "]"
            message_content = re.sub(r'\[Download[^\]]*\](?:\(\))?$', '', message_content)
            
            # Gather citations based on annotation attributes
            if (file_citation := getattr(annotation, 'file_citation', None)):
                cited_file = openai.files.retrieve(file_citation.file_id)
                citations.append(f'[{index}] {file_citation.quote} from {cited_file.filename}')
                    
            # File references
            if (file_path := getattr(annotation, 'file_path', None)):   
                cited_file = openai.files.retrieve(file_path.file_id)
                ext_file_path = cited_file.filename

                # Extract the file name from the full path
                filename = os.path.basename(ext_file_path)
                    
                # File download
                try:
                    
                    file_content =  openai.files.content(cited_file.id).content

                    # Create the user directory if it doesn't exist
                    user_folder = os.path.join(PROJECT_FOLDER, "temp", "downloads", str(self.user_id).zfill(5))
                    os.makedirs(user_folder, exist_ok=True)

                    # Create the file path inside the subfolder
                    save_file_path = os.path.join(user_folder, filename)

                    # Write the content to the file
                    with open(save_file_path, "wb") as output_file:
                        output_file.write(file_content)
                    
                    # Update the filename using the static folder of the fronted "downloads"
                    attachments[filename] = {'link': os.path.join("downloads", str(self.user_id).zfill(5), filename)}

                    with CustomLogger("lexios") as log:
                        log.info(f"User: {self.user_id} File name:{filename} Status: Downloaded.")

                except Exception as e:
                    raise LexiException(f"User: {self.user_id} File name:{filename} Status: Fail - Details: {e}", DEBUG)

        # Return the messages with the found attachments
        return message_content, attachments
    
    except Exception as e:
        raise LexiException(f"At manage downloads. User: {self.user_id} File name:{filename} Status: Fail - Details: {e}")
    

def manage_links(text: str) -> str:
    """ 
    Identify links and create appropiate containers.
    
    """
    try:
        # Define a regular expression pattern for matching URLs and text within square brackets
        pattern = re.compile(r'(?P<text>[^\[]+)(?:\[(?P<text_in_brackets>[^\]]+)\])?(?:\((?P<link>https?://[^\)]+)\))?')

        # Search for the pattern in the input text
        match = re.search(pattern, text)

        if match:
            # Extract the matched groups
            modified_text = match.group('text').strip()
            text_in_brackets = match.group('text_in_brackets')
            link = match.group('link')

            if link:

                link_data = {
                    'text': text_in_brackets,
                    'link' : link, 
                }

                return modified_text, link_data
        
        
        return text, None
    except Exception as e:
        raise LexiException(f"At downloads.py manage_links: {e}", DEBUG)