import os
import re
import subprocess
import sys
import zipfile
import shutil
import tempfile
import xml.etree.ElementTree as ET

def strip_heading_numbering(markdown_raw_content):
    # Regex to match Markdown headings with numbers: e.g. "## 1. INTRODUCTION" or "### 1.1 Purpose"
    # Matches:
    # 1. Start of line
    # 2. One or more hashes (#+)
    # 3. Leading whitespace (\s+)
    # 4. Numbers separated by dots (e.g., 1.2.3 or 1.)
    # 5. Whitespace (\s+)
    # 6. Heading text
    heading_regex_pattern = re.compile(r'^(#+)\s+(\d+(?:\.\d+)*\.?)\s+(.*)$')
    
    document_lines = markdown_raw_content.splitlines()
    cleaned_document_lines = []
    for line_content in document_lines:
        regex_match = heading_regex_pattern.match(line_content)
        if regex_match:
            markdown_heading_hashes = regex_match.group(1)
            heading_title_text = regex_match.group(3)
            cleaned_document_lines.append(f"{markdown_heading_hashes} {heading_title_text}")
        else:
            cleaned_document_lines.append(line_content)
            
    return "\n".join(cleaned_document_lines)

def post_process_odt(odt_file_path):
    """
    Modifies the generated ODT zip file's XML contents to:
    1. Set the font-family of all text styles to Arial.
    2. Set line spacing to 1.5 (150% line height) for normal paragraphs.
    3. Style the Document Control (Table 1) and Revision History (Table 2) tables
       with the Navy Blue (#000080) header color and solid black borders (0.5pt solid #000000).
    4. Style all other tables (Introduction tables onwards) with a light grey background
       (#dddddd) for all cells (headers and body) and thin white borders (0.5pt solid #ffffff)
       matching the template style.
    5. Add a subtle shadow effect (#808080 0.04in 0.04in) to all tables.
    """
    temporary_extract_dir = tempfile.mkdtemp()
    try:
        # Extract the generated ODT zip file
        with zipfile.ZipFile(odt_file_path, 'r') as zip_reference:
            zip_reference.extractall(temporary_extract_dir)
            
        content_xml_path = os.path.join(temporary_extract_dir, 'content.xml')
        styles_xml_path = os.path.join(temporary_extract_dir, 'styles.xml')
        
        # ODF XML namespaces used in ODT files
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
        
        # Register namespaces to prevent automatic ns0, ns1 prefixes during saving
        for prefix, uri in namespace_map.items():
            ET.register_namespace(prefix, uri)
            
        # Process both styles.xml and content.xml
        for xml_file_path in [content_xml_path, styles_xml_path]:
            if not os.path.exists(xml_file_path):
                continue
                
            xml_tree = ET.parse(xml_file_path)
            xml_root = xml_tree.getroot()
            is_modified = False
            
            is_content_xml = (os.path.basename(xml_file_path) == 'content.xml')
            
            # Inject custom cell and heading paragraph styles into content.xml
            if is_content_xml:
                automatic_styles_elem = xml_root.find('office:automatic-styles', namespace_map)
                if automatic_styles_elem is not None:
                    # Let's define the custom styles to inject
                    custom_styles_to_inject = [
                        # 1. NavyTableHeaderCell: for Document Control & Revision History header cells
                        ('NavyTableHeaderCell', 'table-cell', {
                            'background-color': '#000080',
                            'border': '0.5pt solid #000000',
                            'padding-left': '0.075in',
                            'padding-right': '0.075in',
                            'padding-top': '0.04in',
                            'padding-bottom': '0.04in',
                            'vertical-align': 'middle'
                        }, 'style:table-cell-properties', None),
                        
                        # 2. NavyTableRowCell: for Document Control & Revision History body cells
                        ('NavyTableRowCell', 'table-cell', {
                            'background-color': 'transparent',
                            'border': '0.5pt solid #000000',
                            'padding-left': '0.075in',
                            'padding-right': '0.075in',
                            'padding-top': '0.04in',
                            'padding-bottom': '0.04in',
                            'vertical-align': 'middle'
                        }, 'style:table-cell-properties', None),
                        
                        # 3a. GreyTableHeaderCell: for non-navy table headers
                        ('GreyTableHeaderCell', 'table-cell', {
                            'background-color': '#dddddd',
                            'border': '0.5pt solid #ffffff',
                            'padding': '0.05in',
                            'vertical-align': 'middle'
                        }, 'style:table-cell-properties', None),

                        # 3b. GreyTableBodyCell: for non-navy table body cells
                        ('GreyTableBodyCell', 'table-cell', {
                            'background-color': '#dddddd',
                            'border': '0.5pt solid #ffffff',
                            'padding': '0.05in',
                            'vertical-align': 'middle'
                        }, 'style:table-cell-properties', None),
                        
                        # 4. NavyTableHeadingText: paragraph style for white bold text inside navy headers
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
                        
                        # 5. Heading_1_PageBreak: paragraph style for Level 1 headings with page break
                        ('Heading_1_PageBreak', 'paragraph', {
                            'break-before': 'page'
                        }, 'style:paragraph-properties', 'Heading_20_1'),
                        
                        # 6. Heading_2_PageBreak: paragraph style for Level 2 headings with page break
                        ('Heading_2_PageBreak', 'paragraph', {
                            'break-before': 'page'
                        }, 'style:paragraph-properties', 'Heading_20_2'),
                        
                        # 7. Heading_1_NoNumber: paragraph style for Level 1 headings without numbering but in outline (for TOC)
                        ('Heading_1_NoNumber', 'paragraph', {
                            'list-style-name': '',
                            'default-outline-level': '1'
                        }, 'style:paragraph-properties', 'Heading_20_1'),
                        
                        # 8. Heading_2_NoNumber: paragraph style for Level 2 headings without numbering but in outline (for TOC)
                        ('Heading_2_NoNumber', 'paragraph', {
                            'list-style-name': '',
                            'default-outline-level': '2'
                        }, 'style:paragraph-properties', 'Heading_20_2'),
                        
                        # 9. TOC_PageBreak: paragraph style for Table of Contents page break
                        ('TOC_PageBreak', 'paragraph', {
                            'break-before': 'page'
                        }, 'style:paragraph-properties', 'Standard')
                    ]
                    
                    for name, family, attrs, prop_tag, parent_style_name in custom_styles_to_inject:
                        # Check if style already exists
                        style_exists = False
                        for s_elem in automatic_styles_elem.findall('style:style', namespace_map):
                            if s_elem.get('{' + namespace_map['style'] + '}name') == name:
                                style_exists = True
                                break
                                
                        if not style_exists:
                            s_elem = ET.Element('style:style')
                            s_elem.set('{' + namespace_map['style'] + '}name', name)
                            s_elem.set('{' + namespace_map['style'] + '}family', family)
                            if parent_style_name:
                                s_elem.set('{' + namespace_map['style'] + '}parent-style-name', parent_style_name)
                                
                            p_elem = ET.Element(prop_tag)
                            for key, value in attrs.items():
                                if key in ['list-style-name', 'default-outline-level']:
                                    s_elem.set('{' + namespace_map['style'] + '}' + key, value)
                                # Distinguish between FO and Style properties
                                elif key in ['background-color', 'border', 'padding', 'padding-left', 'padding-right', 'padding-top', 'padding-bottom', 'color', 'font-weight', 'font-family', 'line-height', 'break-before']:
                                    p_elem.set('{' + namespace_map['fo'] + '}' + key, value)
                                else:
                                    p_elem.set('{' + namespace_map['style'] + '}' + key, value)
                                    
                            s_elem.append(p_elem)
                            automatic_styles_elem.append(s_elem)
                            is_modified = True
            
            # Walk and modify existing style definitions
            for style_element in xml_root.findall('.//style:style', namespace_map):
                style_name = style_element.get('{' + namespace_map['style'] + '}name')
                style_family = style_element.get('{' + namespace_map['style'] + '}family')
                
                # Set table drop shadows
                if style_family == 'table':
                    table_properties_elem = style_element.find('style:table-properties', namespace_map)
                    if table_properties_elem is None:
                        table_properties_elem = ET.Element('style:table-properties')
                        style_element.append(table_properties_elem)
                    # Subtle shadow: grey (#808080), offset by 0.04in right and down
                    table_properties_elem.set('{' + namespace_map['style'] + '}shadow', '#808080 0.04in 0.04in')
                    is_modified = True
                
                # 1. Update font-family of text properties to Arial
                text_properties_elem = style_element.find('style:text-properties', namespace_map)
                if text_properties_elem is not None:
                    text_properties_elem.set('{' + namespace_map['fo'] + '}font-family', 'Arial')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-name', 'Arial')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-family-generic', 'swiss')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-pitch', 'variable')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-name-asian', 'Arial')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-family-asian', 'Arial')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-name-complex', 'Arial')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-family-complex', 'Arial')
                    is_modified = True
                    
                # 2. Update paragraph line-height to 150% (1.5 line spacing) and set text-align to justify
                # Excludes Title, Subtitle, Headings, and Table_20_Heading to keep titles/headers structured properly
                if style_family == 'paragraph' and style_name not in ['Title', 'Subtitle', 'Heading', 'Table_20_Heading']:
                    if style_name is None or not style_name.startswith('Heading'):
                        paragraph_properties_elem = style_element.find('style:paragraph-properties', namespace_map)
                        if paragraph_properties_elem is None:
                            paragraph_properties_elem = ET.Element('style:paragraph-properties')
                            style_element.append(paragraph_properties_elem)
                        paragraph_properties_elem.set('{' + namespace_map['fo'] + '}line-height', '150%')
                        paragraph_properties_elem.set('{' + namespace_map['fo'] + '}text-align', 'justify')
                        paragraph_properties_elem.set('{' + namespace_map['style'] + '}justify-single-word', 'false')
                        is_modified = True
                        
                # 2b. Force page breaks before Heading_20_1 (removed; now handled dynamically in content.xml)
                pass
                        
                # 3. Modify standard Table_20_Heading to use black text, bold, and Arial (used in grey tables)
                if style_name == 'Table_20_Heading' and style_family == 'paragraph':
                    text_properties_elem = style_element.find('style:text-properties', namespace_map)
                    if text_properties_elem is None:
                        text_properties_elem = ET.Element('style:text-properties')
                        style_element.append(text_properties_elem)
                    text_properties_elem.set('{' + namespace_map['fo'] + '}color', '#000000')  # Standard black text
                    text_properties_elem.set('{' + namespace_map['fo'] + '}font-weight', 'bold')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-weight-asian', 'bold')
                    text_properties_elem.set('{' + namespace_map['style'] + '}font-weight-complex', 'bold')
                    is_modified = True
                    
            # 4. Map the table styles to correct cells depending on the table index in content.xml
            if is_content_xml:
                body_elem = xml_root.find('office:body', namespace_map)
                if body_elem is not None:
                    table_tag = "{" + namespace_map['table'] + "}table"
                    table_cell_tag = "{" + namespace_map['table'] + "}table-cell"
                    text_p_tag = "{" + namespace_map['text'] + "}p"
                    
                    tables_in_body = body_elem.findall('.//' + table_tag, namespace_map)
                    
                    for table_index, table in enumerate(tables_in_body):
                        # Table index 0 = Document Control, Table index 1 = Revision History
                        is_navy_table = (table_index in [0, 1])
                        
                        # Collect header rows and cells
                        header_rows_elems = table.findall('.//table:table-header-rows', namespace_map)
                        header_cells_set = set()
                        for hr_elem in header_rows_elems:
                            for cell_elem in hr_elem.findall('.//' + table_cell_tag, namespace_map):
                                header_cells_set.add(cell_elem)
                                
                        # Walk and style all cells in this table
                        for cell_elem in table.findall('.//' + table_cell_tag, namespace_map):
                            if cell_elem in header_cells_set:
                                # Header cell styling
                                if is_navy_table:
                                    cell_elem.set('{' + namespace_map['table'] + '}style-name', 'NavyTableHeaderCell')
                                    # Set text inside navy headers to white, bold paragraph style
                                    for p_elem in cell_elem.findall('.//' + text_p_tag, namespace_map):
                                        p_elem.set('{' + namespace_map['text'] + '}style-name', 'NavyTableHeadingText')
                                else:
                                    # Grey table headers matching preview style
                                    cell_elem.set('{' + namespace_map['table'] + '}style-name', 'GreyTableHeaderCell')
                                    # Set text inside grey headers to standard black, bold paragraph style
                                    for p_elem in cell_elem.findall('.//' + text_p_tag, namespace_map):
                                        p_elem.set('{' + namespace_map['text'] + '}style-name', 'Table_20_Heading')
                            else:
                                # Body cell styling
                                if is_navy_table:
                                    cell_elem.set('{' + namespace_map['table'] + '}style-name', 'NavyTableRowCell')
                                    # Standard text body paragraph style for cell contents
                                    for p_elem in cell_elem.findall('.//' + text_p_tag, namespace_map):
                                        p_elem.set('{' + namespace_map['text'] + '}style-name', 'Table_20_Contents')
                                else:
                                    # Grey table body cells matching preview style
                                    cell_elem.set('{' + namespace_map['table'] + '}style-name', 'GreyTableBodyCell')
                                    for p_elem in cell_elem.findall('.//' + text_p_tag, namespace_map):
                                        # Leave standard paragraph styling for body
                                        pass
                            
                            is_modified = True
                            
                    # 4b. Map dynamic page breaks for headings starting from INTRODUCTION
                    h_elements = body_elem.findall('.//text:h', namespace_map)
                    has_level_1 = False
                    for h_elem in h_elements:
                        level = h_elem.get('{' + namespace_map['text'] + '}outline-level')
                        if level == '1':
                            has_level_1 = True
                            break
                            
                    target_major_level = '1' if has_level_1 else '2'
                    target_break_style = 'Heading_1_PageBreak' if has_level_1 else 'Heading_2_PageBreak'
                    
                    for h_elem in h_elements:
                        level = h_elem.get('{' + namespace_map['text'] + '}outline-level')
                        if level == target_major_level:
                            text_content = "".join(h_elem.itertext()).strip().upper()
                            is_ignored = ("DOCUMENT CONTROL" in text_content) or ("REVISION HISTORY" in text_content)
                            if is_ignored:
                                # Keep as text:h but set unnumbered style (still in TOC, but no number)
                                target_style = 'Heading_1_NoNumber' if target_major_level == '1' else 'Heading_2_NoNumber'
                                h_elem.set('{' + namespace_map['text'] + '}style-name', target_style)
                                is_modified = True
                            else:
                                h_elem.set('{' + namespace_map['text'] + '}style-name', target_break_style)
                                is_modified = True
                                
                    # 4c. Insert Table of Contents right before INTRODUCTION
                    office_text = body_elem.find('office:text', namespace_map)
                    if office_text is not None and office_text.find('text:table-of-content', namespace_map) is None:
                        h_elements = office_text.findall('.//text:h', namespace_map)
                        intro_elem = None
                        for h_elem in h_elements:
                            text_content = "".join(h_elem.itertext()).strip().upper()
                            if "INTRODUCTION" in text_content:
                                intro_elem = h_elem
                                break
                        if intro_elem is not None:
                            # Trace back to find direct child of office:text containing intro_elem
                            direct_child = intro_elem
                            while direct_child is not None and direct_child not in office_text:
                                found = False
                                for c in office_text:
                                    if c == direct_child or direct_child in c.iter():
                                        direct_child = c
                                        found = True
                                        break
                                if not found:
                                    direct_child = None
                                    break
                            
                            if direct_child is not None:
                                idx = list(office_text).index(direct_child)
                                
                                # Insert page-break paragraph
                                p_pb = ET.Element('{' + namespace_map['text'] + '}p')
                                p_pb.set('{' + namespace_map['text'] + '}style-name', 'TOC_PageBreak')
                                office_text.insert(idx, p_pb)
                                
                                # Insert TOC container
                                toc_xml_str = """<text:table-of-content xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" text:style-name="Sect1" text:protected="true" text:name="Table of Contents1"><text:table-of-content-source text:outline-level="10"><text:index-title-template text:style-name="TOCEntry">Table of Contents</text:index-title-template><text:table-of-content-entry-template text:outline-level="1" text:style-name="Contents_20_1"><text:index-entry-link-start text:style-name="Internet_20_link" /><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /><text:index-entry-link-end /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="2" text:style-name="Contents_20_2"><text:index-entry-link-start text:style-name="Internet_20_link" /><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /><text:index-entry-link-end /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="3" text:style-name="Contents_20_3"><text:index-entry-link-start text:style-name="Internet_20_link" /><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /><text:index-entry-link-end /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="4" text:style-name="Contents_20_4"><text:index-entry-link-start text:style-name="Internet_20_link" /><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /><text:index-entry-link-end /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="5" text:style-name="Contents_20_5"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="6" text:style-name="Contents_20_6"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="7" text:style-name="Contents_20_7"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="8" text:style-name="Contents_20_8"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="9" text:style-name="Contents_20_9"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template><text:table-of-content-entry-template text:outline-level="10" text:style-name="Contents_20_10"><text:index-entry-chapter /><text:index-entry-text /><text:index-entry-tab-stop style:type="right" style:leader-char="." /><text:index-entry-page-number /></text:table-of-content-entry-template></text:table-of-content-source><text:index-body><text:index-title text:style-name="Sect1" text:name="Table of Contents1_Head" text:protected="true"><text:p text:style-name="TOCEntry">Table of Contents</text:p></text:index-title></text:index-body></text:table-of-content>"""
                                toc_elem = ET.fromstring(toc_xml_str)
                                index_body = toc_elem.find('text:index-body', namespace_map)
                                
                                # Populate index_body with all headings sequentially
                                counters = [0] * 10
                                start_index = 0 if has_level_1 else 1
                                
                                for h_elem in h_elements:
                                    level_str = h_elem.get('{' + namespace_map['text'] + '}outline-level')
                                    level = int(level_str) if level_str else 1
                                    
                                    heading_text_raw = "".join(h_elem.itertext()).strip()
                                    text_content_upper = heading_text_raw.upper()
                                    
                                    # Identify ignored headings
                                    is_ignored = ("DOCUMENT CONTROL" in text_content_upper) or ("REVISION HISTORY" in text_content_upper)
                                    
                                    num_prefix = ""
                                    if not is_ignored:
                                        counters[level - 1] += 1
                                        for i in range(level, 10):
                                            counters[i] = 0
                                        active_parts = counters[start_index : level]
                                        num_prefix = ".".join(str(x) for x in active_parts) + " "
                                        
                                    # Find bookmark start
                                    bookmark_start = h_elem.find('text:bookmark-start', namespace_map)
                                    if bookmark_start is not None:
                                        bookmark_name = bookmark_start.get('{' + namespace_map['text'] + '}name')
                                    else:
                                        import uuid
                                        bookmark_name = f"_toc_bookmark_{uuid.uuid4().hex[:8]}"
                                        b_start = ET.Element('{' + namespace_map['text'] + '}bookmark-start')
                                        b_start.set('{' + namespace_map['text'] + '}name', bookmark_name)
                                        b_end = ET.Element('{' + namespace_map['text'] + '}bookmark-end')
                                        b_end.set('{' + namespace_map['text'] + '}name', bookmark_name)
                                        h_elem.insert(0, b_start)
                                        h_elem.append(b_end)
                                        
                                    # Create TOC entry paragraph
                                    p_entry = ET.Element('{' + namespace_map['text'] + '}p')
                                    p_entry.set('{' + namespace_map['text'] + '}style-name', f'Contents_20_{level}')
                                    
                                    a_link = ET.Element('{' + namespace_map['text'] + '}a')
                                    a_link.set('{' + namespace_map['xlink'] + '}type', 'simple')
                                    a_link.set('{' + namespace_map['xlink'] + '}href', f'#{bookmark_name}')
                                    a_link.set('{' + namespace_map['text'] + '}style-name', 'Internet_20_link')
                                    a_link.set('{' + namespace_map['text'] + '}visited-style-name', 'Internet_20_link')
                                    a_link.text = f"{num_prefix}{heading_text_raw}"
                                    
                                    tab_elem = ET.Element('{' + namespace_map['text'] + '}tab')
                                    tab_elem.tail = "1"
                                    
                                    a_link.append(tab_elem)
                                    p_entry.append(a_link)
                                    index_body.append(p_entry)
                                    
                                office_text.insert(idx + 1, toc_elem)
                                is_modified = True
                                
                    # 4d. Ensure the first element has master-page-name="Standard" to apply headers/footers
                    if office_text is not None:
                        valid_tags = ['{' + namespace_map['text'] + '}p', '{' + namespace_map['text'] + '}h', '{' + namespace_map['table'] + '}table']
                        for child in office_text:
                            if child.tag in valid_tags:
                                original_style = child.get('{' + namespace_map['text'] + '}style-name') or child.get('{' + namespace_map['table'] + '}style-name') or 'Standard'
                                family = 'table' if 'table' in child.tag else 'paragraph'
                                
                                auto_styles = xml_root.find('office:automatic-styles', namespace_map)
                                if auto_styles is not None:
                                    s_elem = ET.Element('{' + namespace_map['style'] + '}style')
                                    s_elem.set('{' + namespace_map['style'] + '}name', 'MasterPageStarter')
                                    s_elem.set('{' + namespace_map['style'] + '}family', family)
                                    s_elem.set('{' + namespace_map['style'] + '}parent-style-name', original_style)
                                    s_elem.set('{' + namespace_map['style'] + '}master-page-name', 'Standard')
                                    auto_styles.append(s_elem)
                                    
                                    if family == 'table':
                                        child.set('{' + namespace_map['table'] + '}style-name', 'MasterPageStarter')
                                    else:
                                        child.set('{' + namespace_map['text'] + '}style-name', 'MasterPageStarter')
                                    is_modified = True
                                break
            
            if is_modified:
                xml_tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                
        # Re-pack the modified files back into the ODT zip archive
        with zipfile.ZipFile(odt_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for root_dir, _, files in os.walk(temporary_extract_dir):
                for file in files:
                    full_path = os.path.join(root_dir, file)
                    rel_path = os.path.relpath(full_path, temporary_extract_dir)
                    zip_out.write(full_path, rel_path)
                    
    finally:
        # Clean up temporary extraction folder
        shutil.rmtree(temporary_extract_dir)

def convert_markdown_to_odt(markdown_content: str, output_odt_file_path: str, reference_template_odt_path: str = None) -> bool:
    """
    Converts markdown content to an ODT file using pandoc and applies custom styling.
    Returns True if successful, False otherwise.
    """
    if not reference_template_odt_path:
        script_directory_path = os.path.dirname(os.path.abspath(__file__))
        reference_template_odt_path = os.path.normpath(os.path.join(
            script_directory_path, 
            "..", "..", "Document_Section", "SRS_Section", "SRS_Reference", "DP-VPX-0227-V1-01-SRS-1V00.odt"
        ))
        
    temporary_markdown_file_path = output_odt_file_path + ".temp.md"
    
    try:
        # Clean heading numbers
        cleaned_markdown_content = strip_heading_numbering(markdown_content)
        
        # Save the clean content to temporary markdown file
        with open(temporary_markdown_file_path, 'w', encoding='utf-8') as temporary_file:
            temporary_file.write(cleaned_markdown_content)
            
        # Run pandoc
        pandoc_command_arguments = [
            "pandoc", "-s",
            "-f", "markdown",
            "-t", "odt"
        ]
        
        if reference_template_odt_path and os.path.exists(reference_template_odt_path):
            pandoc_command_arguments.extend(["--reference-doc", reference_template_odt_path])
            
        pandoc_command_arguments.extend(["-o", output_odt_file_path, temporary_markdown_file_path])
        
        subprocess_execution_result = subprocess.run(pandoc_command_arguments, capture_output=True, text=True)
        
        if subprocess_execution_result.returncode == 0:
            # Post-process the generated ODT to apply line spacing, font, and custom table styles
            post_process_odt(output_odt_file_path)
            return True
        else:
            print(f"Error converting file: {subprocess_execution_result.stderr}", file=sys.stderr)
            return False
            
    except Exception as exception_error:
        print(f"Exception encountered during conversion: {exception_error}", file=sys.stderr)
        return False
        
    finally:
        # Clean up the temporary file if it was created
        if os.path.exists(temporary_markdown_file_path):
            os.remove(temporary_markdown_file_path)