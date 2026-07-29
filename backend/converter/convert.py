"""
Markdown to ODT Conversion Module
=================================

This module is responsible for converting Markdown documents into properly formatted
OpenDocument Text (ODT) files. It acts as a wrapper around Pandoc, providing significant
custom post-processing to meet specific styling requirements that Pandoc cannot handle natively.

Key Features:
- Strips hardcoded heading numbers from Markdown to allow native ODT numbering.
- Uses Pandoc for the initial structural conversion (Markdown -> ODT).
- Post-processes the generated ODT zip archive (modifying `content.xml` and `styles.xml`) to:
    - Inject custom styles (e.g., Navy Blue and Grey table styling).
    - Enforce the Arial font family and 150% line spacing across paragraphs.
    - Dynamically insert a native Table of Contents (TOC) right before the "INTRODUCTION" section.
    - Setup Table and Figure caption sequences (e.g., "Table X.X:").
    - Ensure Page Breaks occur correctly before major headings.
"""

import os
import re
import subprocess
import sys
import zipfile
import shutil
import tempfile
import xml.etree.ElementTree as ET

def strip_heading_numbering(markdown_raw_content):
    """
    Removes hardcoded numbers from Markdown headings.
    
    Pandoc/ODT has its own list and outline numbering systems. If the Markdown
    already contains hardcoded numbers (e.g., "## 1.1 Purpose"), they will clash
    with the auto-generated numbering in the final document.
    
    Args:
        markdown_raw_content (str): The raw markdown string read from the source file.
        
    Returns:
        str: Cleaned markdown string with heading numbers removed.
    """
    # Regex to match Markdown headings with numbers: e.g. "## 1. INTRODUCTION" or "### 1.1 Purpose"
    # Breakdown:
    # ^(#+)                : Matches the start of line and captures the hash marks.
    # \s+                  : Matches spaces after the hashes.
    # (\d+(?:\.\d+)*\.?)   : Matches number sequences like "1", "1.1", "1.1.2", "1.".
    # \s+                  : Matches spaces after the numbers.
    # (.*)$                : Matches and captures the actual heading title text.
    heading_regex_pattern = re.compile(r'^(#+)\s+(\d+(?:\.\d+)*\.?)\s+(.*)$')
    
    document_lines = markdown_raw_content.splitlines()
    cleaned_document_lines = []
    
    for line_content in document_lines:
        regex_match = heading_regex_pattern.match(line_content)
        if regex_match:
            markdown_heading_hashes = regex_match.group(1)
            heading_title_text = regex_match.group(3)
            # Reconstruct the heading without the numbering part
            cleaned_document_lines.append(f"{markdown_heading_hashes} {heading_title_text}")
        else:
            # Leave normal lines untouched
            cleaned_document_lines.append(line_content)
            
    return "\n".join(cleaned_document_lines)

# Regex to identify manually written table captions in the markdown text
CAPTION_REGEX = re.compile(r'^(?:Table|Figure)(?:\s+\d+(?:\.\d+)*)?\s*[:\.-]?\s*(.*)$', re.IGNORECASE)

def inject_sequence_caption(parent_paragraph_element, sequence_name, chapter_num, item_num, caption_text, namespace_map):
    """
    Transforms a standard paragraph into a dynamic, chapter-aware auto-incrementing caption.
    Output display example: "Table 1.1: System Requirements"
    
    Args:
        parent_paragraph_element: The `<text:p>` element to mutate.
        sequence_name: 'Table' or 'Figure'
        chapter_num (int): The current major chapter number.
        item_num (int): The index of the item within the current chapter.
        caption_text (str): The descriptive caption text.
        namespace_map (dict): A dictionary mapping XML namespace prefixes to their URIs.
    """
    # 1. Clear any existing child nodes and raw text from the paragraph
    parent_paragraph_element.text = ""
    for child in list(parent_paragraph_element):
        parent_paragraph_element.remove(child)
        
    # 2. Apply a specific custom style to the caption paragraph
    style_name = 'DP_Table_Caption' if sequence_name == 'Table' else 'DP_Figure_Caption'
    parent_paragraph_element.set('{' + namespace_map['text'] + '}style-name', style_name)

    # 3. Create a wrapper span to enforce bold and non-italic (defeats MS Word's built-in Caption style override)
    span_element = ET.Element('{' + namespace_map['text'] + '}span')
    span_element.set('{' + namespace_map['text'] + '}style-name', 'DP_Caption_Char')
    span_element.text = f"{sequence_name} "

    # 4a. Create the Chapter field (X) which automatically tracks the Heading 1 number
    chapter_element = ET.Element('{' + namespace_map['text'] + '}chapter')
    chapter_element.set('{' + namespace_map['text'] + '}display', 'number')
    chapter_element.set('{' + namespace_map['text'] + '}outline-level', '1')
    chapter_element.text = str(chapter_num)
    span_element.append(chapter_element)

    # 4b. Create the Sequence field (Y) for the auto-incrementing item number
    sequence_element = ET.Element('{' + namespace_map['text'] + '}sequence')
    sequence_element.set('{' + namespace_map['text'] + '}name', sequence_name)
    
    # Restart the sequence at 1 for the first item in each chapter
    if item_num == 1:
        sequence_element.set('{' + namespace_map['text'] + '}formula', f'{sequence_name}=1')
    else:
        sequence_element.set('{' + namespace_map['text'] + '}formula', f'{sequence_name}+1')
        
    sequence_element.set('{' + namespace_map['style'] + '}num-format', '1')
    sequence_element.set('{' + namespace_map['text'] + '}ref-name', f'ref{sequence_name}_{chapter_num}_{item_num}')
    
    # 5. Set the display text and trailing description
    sequence_element.text = str(item_num)
    sequence_element.tail = f": {caption_text}"
    span_element.append(sequence_element)
    
    parent_paragraph_element.append(span_element)

def post_process_odt(odt_file_path):
    """
    Modifies the generated ODT zip file's internal XML contents to apply advanced styles.
    
    Since ODT is fundamentally a ZIP archive containing XML files, this function extracts
    the archive, modifies `content.xml` and `styles.xml`, and zips it back up.
    
    Key modifications applied:
    1. Font Family: Sets Arial as the global font for all text styles.
    2. Line Spacing: Applies 150% (1.5) line height and justified alignment to standard paragraphs.
    3. Custom Navy Tables: Styles "Document Control" and "Revision History" tables with Navy Blue
       headers and specific borders.
    4. Custom Grey Tables: Styles all other standard tables with a light grey background and white borders.
    5. Drop Shadows: Adds a subtle shadow effect (`#808080`) to all tables.
    6. Dynamic TOC: Constructs and injects a fully functional Table of Contents XML block right before
       the "INTRODUCTION" heading.
       
    Args:
        odt_file_path (str): The absolute path to the ODT file generated by Pandoc.
    """
    # Create a temporary directory to unpack the ODT contents
    temporary_extract_dir = tempfile.mkdtemp()
    try:
        # Extract the ODT zip archive
        with zipfile.ZipFile(odt_file_path, 'r') as zip_reference:
            zip_reference.extractall(temporary_extract_dir)
        
        # Define paths for the two primary ODT XML files we need to modify
        content_xml_path = os.path.join(temporary_extract_dir, 'content.xml')
        styles_xml_path = os.path.join(temporary_extract_dir, 'styles.xml')
        
        # ODF XML uses heavily namespaced tags. We define the map here so ElementTree
        # can locate and create elements correctly.
        namespace_map = {
            'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
            'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
            'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
            'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
            'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
            'svg': 'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0',
            'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
            'meta': 'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
            'number': 'urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'xlink': 'http://www.w3.org/1999/xlink',
        }
        
        # Register namespaces to prevent ElementTree from generating ugly ns0, ns1 prefixes during saving
        for prefix, uri in namespace_map.items():
            ET.register_namespace(prefix, uri)
            
        # We need to process both styles.xml (for global styles) and content.xml (for automatic local styles and document body)
        for xml_file_path in [content_xml_path, styles_xml_path]:
            if not os.path.exists(xml_file_path):
                continue
                
            xml_tree = ET.parse(xml_file_path)
            xml_root = xml_tree.getroot()
            is_modified = False
            
            is_content_xml = (os.path.basename(xml_file_path) == 'content.xml')
            
            # -------------------------------------------------------------------------
            # PHASE 1: Style Injection (styles.xml only)
            # Inject custom cell, table, and heading paragraph styles into <office:styles>
            # -------------------------------------------------------------------------
            if not is_content_xml:
                automatic_styles_element = xml_root.find('.//office:styles', namespace_map)
                if automatic_styles_element is not None:
                    # Define a list of custom styles to inject. Each tuple contains:
                    # (Style Name, Style Family, Style Attributes Dict, Property Element Tag, Parent Style)
                    custom_styles_to_inject = [
                        # 1. NavyTableHeaderCell: Dark blue background, solid borders (for Document Control tables)
                        ('NavyTableHeaderCell', 'table-cell', {
                            'background-color': '#000080',
                            'border': '0.5pt solid #000000',
                            'padding-left': '0.075in',
                            'padding-right': '0.075in',
                            'padding-top': '0.04in',
                            'padding-bottom': '0.04in',
                            'vertical-align': 'middle'
                        }, 'style:table-cell-properties', None),
                        
                        # 2. NavyTableRowCell: Transparent background, solid borders (for Document Control body)
                        ('NavyTableRowCell', 'table-cell', {
                            'background-color': 'transparent',
                            'border': '0.5pt solid #000000',
                            'padding-left': '0.075in',
                            'padding-right': '0.075in',
                            'padding-top': '0.04in',
                            'padding-bottom': '0.04in',
                            'vertical-align': 'middle'
                        }, 'style:table-cell-properties', None),
                        
                        # 3a. GreyTableHeaderCell: Grey background, white borders (for standard tables)
                        ('GreyTableHeaderCell', 'table-cell', {
                            'background-color': '#dddddd',
                            'border': '0.5pt solid #ffffff',
                            'padding': '0.05in',
                            'vertical-align': 'middle'
                        }, 'style:table-cell-properties', None),

                        # 3b. GreyTableBodyCell: Grey background, white borders (for standard tables)
                        ('GreyTableBodyCell', 'table-cell', {
                            'background-color': '#dddddd',
                            'border': '0.5pt solid #ffffff',
                            'padding': '0.05in',
                            'vertical-align': 'middle'
                        }, 'style:table-cell-properties', None),
                        
                        # 4. NavyTableHeadingText: White Arial text to contrast against Navy backgrounds
                        ('NavyTableHeadingText', 'paragraph', {
                            'color': '#ffffff',
                            'font-weight': 'bold',
                            'font-weight-asian': 'bold',
                            'font-weight-complex': 'bold',
                            'font-family': 'Arial',
                            'font-name': 'Arial',
                            'font-family-generic': 'swiss',
                            'font-pitch': 'variable'
                        }, 'style:text-properties', 'Table_20_Heading'),
                        
                        # 5-6. Heading Page Breaks: Forces a new page before Level 1 and 2 headings
                        ('Heading_1_PageBreak', 'paragraph', {
                            'break-before': 'page'
                        }, 'style:paragraph-properties', 'Heading_20_1'),
                        
                        ('Heading_2_PageBreak', 'paragraph', {
                            'break-before': 'page'
                        }, 'style:paragraph-properties', 'Heading_20_2'),
                        
                        # 7-8. Unnumbered Headings: Used for Document Control/Revision History so they appear in TOC but have no number prefix
                        ('Heading_1_NoNumber', 'paragraph', {
                            'list-style-name': '',
                            'default-outline-level': '1'
                        }, 'style:paragraph-properties', 'Heading_20_1'),
                        
                        ('Heading_2_NoNumber', 'paragraph', {
                            'list-style-name': '',
                            'default-outline-level': '2'
                        }, 'style:paragraph-properties', 'Heading_20_2'),
                        
                        # 9. TOC_PageBreak: Forces the TOC onto its own page
                        ('TOC_PageBreak', 'paragraph', {
                            'break-before': 'page'
                        }, 'style:paragraph-properties', 'Standard'),

                        # 10. Table Caption Style (No parent to prevent MS Word italic override)
                        ('DP_Table_Caption', 'paragraph', {}, 'style:paragraph-properties', None),

                        # 11. Figure Caption Style (No parent to prevent MS Word italic override)
                        ('DP_Figure_Caption', 'paragraph', {}, 'style:paragraph-properties', None),

                        # 12. Caption Character Style (Forces bold, non-italic on inner text for MS Word)
                        ('DP_Caption_Char', 'text', {
                            'font-weight': 'bold',
                            'font-weight-asian': 'bold',
                            'font-weight-complex': 'bold',
                            'font-style': 'normal',
                            'font-style-asian': 'normal',
                            'font-style-complex': 'normal',
                            'color': '#000000'
                        }, 'style:text-properties', None)
                    ]
                    
                    # Iterate over the definitions and construct XML nodes to insert into the document
                    for style_name, style_family, style_attrs, property_element_tag, parent_style in custom_styles_to_inject:
                        # Check if style already exists to avoid duplicates
                        style_exists = False
                        for existing_style_element in automatic_styles_element.findall('style:style', namespace_map):
                            if existing_style_element.get('{' + namespace_map['style'] + '}name') == style_name:
                                style_exists = True
                                break

                        if not style_exists:
                            new_style_element = ET.Element('{' + namespace_map['style'] + '}style')
                            new_style_element.set('{' + namespace_map['style'] + '}name', style_name)
                            new_style_element.set('{' + namespace_map['style'] + '}family', style_family)
                            if parent_style:
                                new_style_element.set('{' + namespace_map['style'] + '}parent-style-name', parent_style)

                            # Construct the property payload (differentiating FO vs Style namespace attributes)
                            prop_prefix, prop_tag = property_element_tag.split(':')
                            properties_element = ET.Element('{' + namespace_map[prop_prefix] + '}' + prop_tag)
                            for key, value in style_attrs.items():
                                if key in ['list-style-name', 'default-outline-level']:
                                    new_style_element.set('{' + namespace_map['style'] + '}' + key, value)
                                # Display formatting attributes belong in the 'fo' namespace
                                elif key in ['background-color', 'border', 'padding', 'padding-left', 'padding-right', 'padding-top', 'padding-bottom', 'color', 'font-weight', 'font-family', 'line-height', 'break-before', 'text-align']:
                                    properties_element.set('{' + namespace_map['fo'] + '}' + key, value)
                                else:
                                    properties_element.set('{' + namespace_map['style'] + '}' + key, value)

                            new_style_element.append(properties_element)
                            automatic_styles_element.append(new_style_element)
                            is_modified = True
            
            # -------------------------------------------------------------------------
            # PHASE 2: Global Document Modifications
            # Modify existing style definitions across both content.xml and styles.xml
            # -------------------------------------------------------------------------
            for style_element in xml_root.findall('.//style:style', namespace_map):
                style_name = style_element.get('{' + namespace_map['style'] + '}name')
                style_family = style_element.get('{' + namespace_map['style'] + '}family')
                
                # 2A. Set Table Drop Shadows
                if style_family == 'table':
                    table_properties_element = style_element.find('style:table-properties', namespace_map)
                    if table_properties_element is None:
                        table_properties_element = ET.Element('{' + namespace_map['style'] + '}table-properties')
                        style_element.append(table_properties_element)
                    # Apply a subtle grey shadow (#808080) offset by 0.04 inches right and down
                    table_properties_element.set('{' + namespace_map['style'] + '}shadow', '#808080 0.04in 0.04in')
                    is_modified = True
                
                # 2B. Force Arial Font Globally
                text_properties_element = style_element.find('style:text-properties', namespace_map)
                if text_properties_element is not None:
                    text_properties_element.set('{' + namespace_map['fo'] + '}font-family', 'Arial')
                    text_properties_element.set('{' + namespace_map['style'] + '}font-name', 'Arial')
                    text_properties_element.set('{' + namespace_map['style'] + '}font-family-generic', 'swiss')
                    text_properties_element.set('{' + namespace_map['style'] + '}font-pitch', 'variable')
                    text_properties_element.set('{' + namespace_map['style'] + '}font-name-asian', 'Arial')
                    text_properties_element.set('{' + namespace_map['style'] + '}font-family-asian', 'Arial')
                    text_properties_element.set('{' + namespace_map['style'] + '}font-name-complex', 'Arial')
                    text_properties_element.set('{' + namespace_map['style'] + '}font-family-complex', 'Arial')
                    is_modified = True
                    
                # 2C. Update Paragraph Line Height & Alignment
                # Apply 1.5 line spacing and justify alignment to ALL paragraphs (including headings, tables, figures, text)
                if style_family == 'paragraph':
                    paragraph_properties_element = style_element.find('style:paragraph-properties', namespace_map)
                    if paragraph_properties_element is None:
                        paragraph_properties_element = ET.Element('{' + namespace_map['style'] + '}paragraph-properties')
                        style_element.append(paragraph_properties_element)
                    paragraph_properties_element.set('{' + namespace_map['fo'] + '}line-height', '150%') # 1.5 line spacing
                    
                    if style_name in ['DP_Table_Caption', 'DP_Figure_Caption']:
                        paragraph_properties_element.set('{' + namespace_map['fo'] + '}text-align', 'center')
                    else:
                        paragraph_properties_element.set('{' + namespace_map['fo'] + '}text-align', 'justify')
                        
                    paragraph_properties_element.set('{' + namespace_map['style'] + '}justify-single-word', 'false')
                    is_modified = True
                    
                    # 2D. Enforce font sizes for Headings, Tables, and Figures
                    if style_name:
                        text_properties_element = style_element.find('style:text-properties', namespace_map)
                        if text_properties_element is None:
                            text_properties_element = ET.Element('{' + namespace_map['style'] + '}text-properties')
                            style_element.append(text_properties_element)
                            
                        # Set font sizes for Headings
                        if style_name.startswith('Heading_20_1') or style_name in ['Heading_1_PageBreak', 'Heading_1_NoNumber']:
                            text_properties_element.set('{' + namespace_map['fo'] + '}font-size', '18pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-asian', '18pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-complex', '18pt')
                        elif style_name.startswith('Heading_20_2') or style_name in ['Heading_2_PageBreak', 'Heading_2_NoNumber']:
                            text_properties_element.set('{' + namespace_map['fo'] + '}font-size', '16pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-asian', '16pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-complex', '16pt')
                        elif style_name.startswith('Heading_20_3'):
                            text_properties_element.set('{' + namespace_map['fo'] + '}font-size', '14pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-asian', '14pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-complex', '14pt')
                        elif style_name.startswith('Heading_20_4') or style_name.startswith('Heading_20_5') or style_name.startswith('Heading_20_6'):
                            text_properties_element.set('{' + namespace_map['fo'] + '}font-size', '12pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-asian', '12pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-complex', '12pt')
                            
                        # Set font sizes for Tables and Figures
                        elif 'Table' in style_name or 'Figure' in style_name:
                            text_properties_element.set('{' + namespace_map['fo'] + '}font-size', '12pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-asian', '12pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-complex', '12pt')
                            
                            # Force captions to be bold, non-italic, and black
                            if style_name in ['DP_Table_Caption', 'DP_Figure_Caption']:
                                text_properties_element.set('{' + namespace_map['fo'] + '}font-style', 'normal')
                                text_properties_element.set('{' + namespace_map['style'] + '}font-style-asian', 'normal')
                                text_properties_element.set('{' + namespace_map['style'] + '}font-style-complex', 'normal')
                                text_properties_element.set('{' + namespace_map['fo'] + '}font-weight', 'bold')
                                text_properties_element.set('{' + namespace_map['style'] + '}font-weight-asian', 'bold')
                                text_properties_element.set('{' + namespace_map['style'] + '}font-weight-complex', 'bold')
                                text_properties_element.set('{' + namespace_map['fo'] + '}color', '#000000')
                            
                        # Ensure Table Headings are Bold and Black (Used primarily in Grey tables)
                        if style_name == 'Table_20_Heading':
                            if text_properties_element is None:
                                text_properties_element = ET.Element('{' + namespace_map['style'] + '}text-properties')
                                style_element.append(text_properties_element)
                            text_properties_element.set('{' + namespace_map['fo'] + '}color', '#000000')
                            text_properties_element.set('{' + namespace_map['fo'] + '}font-weight', 'bold')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-weight-asian', 'bold')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-weight-complex', 'bold')
                    
            # -------------------------------------------------------------------------
            # PHASE 3: Apply Content and Structure Mapping (content.xml only)
            # -------------------------------------------------------------------------
            if is_content_xml:
                body_element = xml_root.find('office:body', namespace_map)
                if body_element is not None:
                    
                    # 3A. Map table styles to specific tables based on their index
                    table_xml_tag = "{" + namespace_map['table'] + "}table"
                    table_cell_xml_tag = "{" + namespace_map['table'] + "}table-cell"
                    text_paragraph_xml_tag = "{" + namespace_map['text'] + "}p"
                    tables_in_body_element = body_element.findall('.//' + table_xml_tag, namespace_map)
                    
                    for table_index, table in enumerate(tables_in_body_element):
                        # The first two tables (Index 0 and 1) are always assumed to be "Document Control" and "Revision History"
                        is_navy_table = (table_index in [0, 1])
                        
                        # Extract header rows to differentiate header cells from body cells
                        header_rows_elements = table.findall('.//table:table-header-rows', namespace_map)
                        header_cells_set = set()
                        for header_row_element in header_rows_elements:
                            for table_cell_element in header_row_element.findall('.//' + table_cell_xml_tag, namespace_map):
                                header_cells_set.add(table_cell_element)
                                
                        # Walk and apply styling to all cells in the table
                        for table_cell_element in table.findall('.//' + table_cell_xml_tag, namespace_map):
                            if table_cell_element in header_cells_set:
                                # Header cell styling logic
                                if is_navy_table:
                                    table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'NavyTableHeaderCell')
                                    # Set text inside navy headers to white, bold paragraph style
                                    for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                        paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'NavyTableHeadingText')
                                else:
                                    # Grey table headers matching standard template
                                    table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'GreyTableHeaderCell')
                                    for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                        paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'Table_20_Heading')
                            else:
                                # Body cell styling logic
                                if is_navy_table:
                                    table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'NavyTableRowCell')
                                    for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                        paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'Table_20_Contents')
                                else:
                                    # Standard grey table body cells
                                    table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'GreyTableBodyCell')
                            
                            is_modified = True
                            
                    # 3B. Map dynamic page breaks and unnumbered styles to specific headings
                    heading_elements = body_element.findall('.//text:h', namespace_map)
                    has_level_1 = False
                    for heading_element in heading_elements:
                        level = heading_element.get('{' + namespace_map['text'] + '}outline-level')
                        if level == '1':
                            has_level_1 = True
                            break
                            
                    target_major_level = '1' if has_level_1 else '2'
                    target_break_style = 'Heading_1_PageBreak' if has_level_1 else 'Heading_2_PageBreak'
                    
                    for heading_element in heading_elements:
                        level = heading_element.get('{' + namespace_map['text'] + '}outline-level')
                        if level == target_major_level:
                            text_content = "".join(heading_element.itertext()).strip().upper()
                            # Document Control and Revision History shouldn't have numbering prefixes
                            is_ignored = ("DOCUMENT CONTROL" in text_content) or ("REVISION HISTORY" in text_content)
                            if is_ignored:
                                target_style = 'Heading_1_NoNumber' if target_major_level == '1' else 'Heading_2_NoNumber'
                                heading_element.set('{' + namespace_map['text'] + '}style-name', target_style)
                                is_modified = True
                            else:
                                # Normal major headings receive page breaks before them
                                heading_element.set('{' + namespace_map['text'] + '}style-name', target_break_style)
                                is_modified = True

                    # 3C. Map predefined styles to explicitly declared Figure and Table Captions
                    office_text = body_element.find('office:text', namespace_map)
                    if office_text is not None:
                        # Ensure sequence declarations are configured to display Chapter numbers (outline-level 1)
                        seq_decls = office_text.find('text:sequence-decls', namespace_map)
                        if seq_decls is None:
                            seq_decls = ET.Element('{' + namespace_map['text'] + '}sequence-decls')
                            office_text.insert(0, seq_decls)
                            
                        for seq_name in ['Table', 'Figure']:
                            found = False
                            for decl in seq_decls.findall('{' + namespace_map['text'] + '}sequence-decl'):
                                if decl.get('{' + namespace_map['text'] + '}name') == seq_name:
                                    if '{' + namespace_map['text'] + '}display-outline-level' in decl.attrib:
                                        del decl.attrib['{' + namespace_map['text'] + '}display-outline-level']
                                    found = True
                                    break
                            if not found:
                                decl = ET.Element('{' + namespace_map['text'] + '}sequence-decl')
                                decl.set('{' + namespace_map['text'] + '}name', seq_name)
                                seq_decls.append(decl)

                        current_chapter = 0
                        table_counter = 0
                        figure_counter = 0
                        
                        # Iterate sequentially over all descendants of office_text to track chapter
                        for element in office_text.iter():
                            if element.tag == '{' + namespace_map['text'] + '}h':
                                level = element.get('{' + namespace_map['text'] + '}outline-level')
                                if level == '1':
                                    heading_text = "".join(element.itertext()).strip().upper()
                                    if not ("DOCUMENT CONTROL" in heading_text or "REVISION HISTORY" in heading_text):
                                        current_chapter += 1
                                        table_counter = 0
                                        figure_counter = 0
                            elif element.tag == '{' + namespace_map['text'] + '}p':
                                text_content = "".join(element.itertext()).strip()
                                if text_content.startswith("Table "):
                                    match = CAPTION_REGEX.match(text_content)
                                    caption_text = match.group(1) if match else text_content
                                    table_counter += 1
                                    inject_sequence_caption(element, 'Table', current_chapter, table_counter, caption_text, namespace_map)
                                    is_modified = True
                                elif text_content.startswith("Figure "):
                                    match = CAPTION_REGEX.match(text_content)
                                    caption_text = match.group(1) if match else text_content
                                    figure_counter += 1
                                    inject_sequence_caption(element, 'Figure', current_chapter, figure_counter, caption_text, namespace_map)
                                    is_modified = True
                    if office_text is not None and office_text.find('text:table-of-content', namespace_map) is None:
                        heading_elements = office_text.findall('.//text:h', namespace_map)
                        introduction_heading_element = None
                        
                        # Find the first heading containing "INTRODUCTION"
                        for heading_element in heading_elements:
                            text_content = "".join(heading_element.itertext()).strip().upper()
                            if "INTRODUCTION" in text_content:
                                introduction_heading_element = heading_element
                                break
                                
                        if introduction_heading_element is not None:
                            # Trace the DOM tree back up to find the direct child of <office:text> that contains the Introduction heading
                            direct_child_element = introduction_heading_element
                            while direct_child_element is not None and direct_child_element not in office_text:
                                found = False
                                for child_element in office_text:
                                    if child_element == direct_child_element or direct_child_element in child_element.iter():
                                        direct_child_element = child_element
                                        found = True
                                        break
                                if not found:
                                    direct_child_element = None
                                    break
                            
                            # If we successfully located the injection point
                            if direct_child_element is not None:
                                introduction_element_index = list(office_text).index(direct_child_element)
                                
                                # Insert a page-break paragraph to isolate the TOC
                                page_break_paragraph_element = ET.Element('{' + namespace_map['text'] + '}p')
                                page_break_paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'TOC_PageBreak')
                                office_text.insert(introduction_element_index, page_break_paragraph_element)
                                
                                # Insert the base TOC XML container structure with outline templates
                                table_of_contents_xml_string = """<text:table-of-content xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" text:style-name="Sect1" text:protected="true" text:name="Table of Contents1"><text:table-of-content-source text:outline-level="10"><text:index-title-template text:style-name="TOCEntry">Table of Contents</text:index-title-template><text:table-of-content-entry-template text:outline-level="1" text:style-name="Contents_20_1"><text:index-entry-link-start text:style-name="Internet_20_link" /><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /><text:index-entry-link-end /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="2" text:style-name="Contents_20_2"><text:index-entry-link-start text:style-name="Internet_20_link" /><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /><text:index-entry-link-end /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="3" text:style-name="Contents_20_3"><text:index-entry-link-start text:style-name="Internet_20_link" /><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /><text:index-entry-link-end /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="4" text:style-name="Contents_20_4"><text:index-entry-link-start text:style-name="Internet_20_link" /><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /><text:index-entry-link-end /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="5" text:style-name="Contents_20_5"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="6" text:style-name="Contents_20_6"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="7" text:style-name="Contents_20_7"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="8" text:style-name="Contents_20_8"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="9" text:style-name="Contents_20_9"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="10" text:style-name="Contents_20_10"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template></text:table-of-content-source><text:index-body><text:index-title text:style-name="Sect1" text:name="Table of Contents1_Head" text:protected="true"><text:p text:style-name="TOCEntry">Table of Contents</text:p></text:index-title></text:index-body></text:table-of-content>"""
                                table_of_contents_element = ET.fromstring(table_of_contents_xml_string)
                                table_of_contents_index_body = table_of_contents_element.find('text:index-body', namespace_map)
                                
                                # Populate index_body iteratively with all identified document headings
                                outline_level_counters = [0] * 10
                                start_index = 0 if has_level_1 else 1
                                
                                for heading_element in heading_elements:
                                    level_str = heading_element.get('{' + namespace_map['text'] + '}outline-level')
                                    level = int(level_str) if level_str else 1
                                    
                                    heading_text_raw = "".join(heading_element.itertext()).strip()
                                    text_content_upper = heading_text_raw.upper()
                                    
                                    # Certain structural headings don't get outline numbering prefixes
                                    is_ignored = ("DOCUMENT CONTROL" in text_content_upper) or ("REVISION HISTORY" in text_content_upper)
                                    
                                    num_prefix = ""
                                    if not is_ignored:
                                        outline_level_counters[level - 1] += 1
                                        for i in range(level, 10):
                                            outline_level_counters[i] = 0
                                        active_outline_parts = outline_level_counters[start_index : level]
                                        num_prefix = ".".join(str(x) for x in active_outline_parts) + " "
                                        
                                    # Create or discover bookmark references for clickable links within the TOC
                                    bookmark_start_element = heading_element.find('text:bookmark-start', namespace_map)
                                    if bookmark_start_element is not None:
                                        bookmark_name = bookmark_start_element.get('{' + namespace_map['text'] + '}name')
                                    else:
                                        import uuid
                                        bookmark_name = f"_toc_bookmark_{uuid.uuid4().hex[:8]}"
                                        bookmark_start_element = ET.Element('{' + namespace_map['text'] + '}bookmark-start')
                                        bookmark_start_element.set('{' + namespace_map['text'] + '}name', bookmark_name)
                                        bookmark_end_element = ET.Element('{' + namespace_map['text'] + '}bookmark-end')
                                        bookmark_end_element.set('{' + namespace_map['text'] + '}name', bookmark_name)
                                        heading_element.insert(0, bookmark_start_element)
                                        heading_element.append(bookmark_end_element)
                                        
                                    # Build out the entry paragraph mimicking Word's outline styles
                                    table_of_contents_entry_paragraph = ET.Element('{' + namespace_map['text'] + '}p')
                                    table_of_contents_entry_paragraph.set('{' + namespace_map['text'] + '}style-name', f'Contents_20_{level}')
                                    
                                    # Construct the clickable link structure
                                    table_of_contents_entry_link = ET.Element('{' + namespace_map['text'] + '}a')
                                    table_of_contents_entry_link.set('{' + namespace_map['xlink'] + '}type', 'simple')
                                    table_of_contents_entry_link.set('{' + namespace_map['xlink'] + '}href', f'#{bookmark_name}')
                                    table_of_contents_entry_link.set('{' + namespace_map['text'] + '}style-name', 'Internet_20_link')
                                    table_of_contents_entry_link.set('{' + namespace_map['text'] + '}visited-style-name', 'Internet_20_link')
                                    table_of_contents_entry_link.text = f"{num_prefix}{heading_text_raw}"
                                    
                                    # Add trailing tab space used by LibreOffice/Word to push page numbers to the right margin
                                    tab_space_element = ET.Element('{' + namespace_map['text'] + '}tab')
                                    tab_space_element.tail = "1"
                                    
                                    table_of_contents_entry_link.append(tab_space_element)
                                    table_of_contents_entry_paragraph.append(table_of_contents_entry_link)
                                    table_of_contents_index_body.append(table_of_contents_entry_paragraph)
                                    
                                # Finalize TOC insertion
                                office_text.insert(introduction_element_index + 1, table_of_contents_element)
                                is_modified = True
                                
                    # 3E. Header/Footer Activation
                    # Ensure the first element has master-page-name="Standard" to instruct ODT to apply headers/footers to the first page onwards
                    if office_text is not None:
                        valid_tags = ['{' + namespace_map['text'] + '}p', '{' + namespace_map['text'] + '}h', '{' + namespace_map['table'] + '}table']
                        for child in office_text:
                            if child.tag in valid_tags:
                                original_style = child.get('{' + namespace_map['text'] + '}style-name') or child.get('{' + namespace_map['table'] + '}style-name') or 'Standard'
                                family = 'table' if 'table' in child.tag else 'paragraph'
                                
                                automatic_styles_collection = xml_root.find('office:automatic-styles', namespace_map)
                                if automatic_styles_collection is not None:
                                    master_page_style = ET.Element('{' + namespace_map['style'] + '}style')
                                    master_page_style.set('{' + namespace_map['style'] + '}name', 'MasterPageStarter')
                                    master_page_style.set('{' + namespace_map['style'] + '}family', family)
                                    master_page_style.set('{' + namespace_map['style'] + '}parent-style-name', original_style)
                                    master_page_style.set('{' + namespace_map['style'] + '}master-page-name', 'Standard')
                                    automatic_styles_collection.append(master_page_style)
                                    
                                    if family == 'table':
                                        child.set('{' + namespace_map['table'] + '}style-name', 'MasterPageStarter')
                                    else:
                                        child.set('{' + namespace_map['text'] + '}style-name', 'MasterPageStarter')
                                    is_modified = True
                                break
            
            # Save any modifications back to the temporary XML files
            if is_modified:
                xml_tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                
        # Re-pack the modified XML files back into the original ODT zip archive layout
        with zipfile.ZipFile(odt_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for root_dir, _, files in os.walk(temporary_extract_dir):
                for file in files:
                    full_path = os.path.join(root_dir, file)
                    rel_path = os.path.relpath(full_path, temporary_extract_dir)
                    zip_out.write(full_path, rel_path)
                    
    finally:
        # Guarantee cleanup of temporary extraction folder to prevent disk space leaks
        shutil.rmtree(temporary_extract_dir)

def convert_markdown_to_odt(markdown_content: str, output_odt_file_path: str, reference_template_odt_path: str = None) -> bool:
    """
    Main entry point for document conversion. Orchestrates cleaning, Pandoc execution, and post-processing.
    
    Args:
        markdown_content (str): The raw markdown string to convert.
        output_odt_file_path (str): The absolute path where the final .odt file should be saved.
        reference_template_odt_path (str, optional): A path to a reference ODT file providing base styles.
            If None, attempts to use a predefined internal template.
            
    Returns:
        bool: True if the conversion pipeline executed completely without errors, False otherwise.
    """
    # Fallback to predefined template if not explicitly provided
    if not reference_template_odt_path:
        script_directory_path = os.path.dirname(os.path.abspath(__file__))
        reference_template_odt_path = os.path.normpath(os.path.join(
            script_directory_path, 
            "..", "..", "Document_Section", "SRS_Section", "SRS_Reference", "DP-VPX-0227-V1-01-SRS-1V00.odt"
        ))
        
    temporary_markdown_file_path = output_odt_file_path + ".temp.md"
    
    try:
        # Step 1: Clean raw markdown to prevent Pandoc numbering conflicts
        cleaned_markdown_content = strip_heading_numbering(markdown_content)
        
        # Step 2: Save the clean content to a temporary markdown file required by Pandoc CLI
        with open(temporary_markdown_file_path, 'w', encoding='utf-8') as temporary_file:
            temporary_file.write(cleaned_markdown_content)
            
        # Step 3: Construct and execute the Pandoc command
        pandoc_command_arguments = [
            "pandoc", "-s",
            "-f", "markdown",
            "-t", "odt"
        ]
        
        if reference_template_odt_path and os.path.exists(reference_template_odt_path):
            pandoc_command_arguments.extend(["--reference-doc", reference_template_odt_path])
            
        pandoc_command_arguments.extend(["-o", output_odt_file_path, temporary_markdown_file_path])
        
        # Capture stdout/stderr natively so we don't spam the standard console unless requested
        subprocess_execution_result = subprocess.run(pandoc_command_arguments, capture_output=True, text=True)
        
        # Step 4: Validate Pandoc exit code and initiate XML Post Processing
        if subprocess_execution_result.returncode == 0:
            post_process_odt(output_odt_file_path)
            return True
        else:
            print(f"Error converting file: {subprocess_execution_result.stderr}", file=sys.stderr)
            return False
            
    except Exception as exception_error:
        print(f"Exception encountered during conversion: {exception_error}", file=sys.stderr)
        return False
        
    finally:
        # Step 5: Always clean up the temporary markdown file artifact
        if os.path.exists(temporary_markdown_file_path):
            os.remove(temporary_markdown_file_path)