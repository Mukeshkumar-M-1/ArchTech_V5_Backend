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
import zipfile
import shutil
import tempfile
import xml.etree.ElementTree as ET
import logging
import copy

# Register all namespaces upfront so ElementTree uses correct prefixes
# when parsing AND writing XML (must happen before any parse/write calls)
ET.register_namespace(prefix='loext', uri='urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0')
ET.register_namespace(prefix='number', uri='urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0')

log = logging.getLogger(__name__)

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
    heading_regex_pattern = re.compile(r'^(#+)\s+(\d+(?:\.\d+)*\.?)\s+(.*)$')

    document_lines = markdown_raw_content.splitlines()
    cleaned_document_lines = []
    stripped_count = 0

    for line_content in document_lines:
        regex_match = heading_regex_pattern.match(line_content)
        if regex_match:
            markdown_heading_hashes = regex_match.group(1)
            heading_title_text = regex_match.group(3)
            stripped_count += 1
            log.info(
                "[strip_heading_numbering] Stripped '%s' from '%s' -> '%s'",
                regex_match.group(2), line_content.strip(), heading_title_text,
            )
            cleaned_document_lines.append(f"{markdown_heading_hashes} {heading_title_text}")
        else:
            cleaned_document_lines.append(line_content)

    log.info("[strip_heading_numbering] Total headings stripped: %d / %d lines", stripped_count, len(document_lines))
    return "\n".join(cleaned_document_lines)

# Regex to identify manually written table captions in the markdown text
CAPTION_REGEX = re.compile(r'^(?:Table|Figure)(?:\s+\d+(?:\.\d+)*)?\s*[:\.-]?\s*(.*)$', re.IGNORECASE)

TEMPLATE_CONFIGS: dict[str, dict] = {
    "srs": {
        "navy_table_section_prefixes": {"02_revision_history"},
        "unnumbered_headings": set(),
        "sections_with_page_break": {"02_revision_history", "03_introduction"},
        "toc_insertion_target": "INTRODUCTION",
        "reference_document_filename": "DP-VPX-0227-V1-01-SRS-1V00.odt",
        "navy_table_positional_fallback": False,
        "heading_font_sizes": {1: "18pt", 2: "16pt", 3: "14pt", 4: "12pt", 5: "12pt", 6: "12pt"},
    },
    "sdd": {
        "navy_table_section_prefixes": {"02_revision_history"},
        "unnumbered_headings": set(),
        "sections_with_page_break": set(),
        "toc_insertion_target": "INTRODUCTION",
        "reference_document_filename": "DP-VPX-0227-V1-01-SRS-1V00.odt",
        "navy_table_positional_fallback": False,
        "heading_font_sizes": {1: "18pt", 2: "16pt", 3: "14pt", 4: "12pt", 5: "12pt", 6: "12pt"},
    },
}


def get_template_config(template_type: str) -> dict:
    """Return styling config for template_type, falling back to 'srs'."""
    tt = (template_type or "srs").lower()
    if tt in TEMPLATE_CONFIGS:
        return TEMPLATE_CONFIGS[tt]
    log.warning(f"[TemplateConfig] Unknown template_type '{tt}', falling back to 'srs'")
    return TEMPLATE_CONFIGS["srs"]


def _build_section_heading_map(sections):
    """Map ALL heading texts → section filename for section-aware styling.

    Extracts every markdown heading (## or ### etc.) from each section's content
    so that tables preceded by sub-headings like 'PURPOSE' still resolve to the
    correct section file.
    """
    heading_map = {}
    if not sections:
        return heading_map
    for sec in sections:
        content = sec.get("content", "")
        if not content:
            continue
        # Collect all markdown headings (any level) from this section
        raw_headings = re.findall(
            r"^#+\s*(.*?)$", content, re.MULTILINE,
        )
        # If no headings found, try bold text as fallback
        if not raw_headings:
            bold_match = re.match(r"^\*\*(.+?)\*\*", content.strip(), re.MULTILINE)
            if bold_match:
                raw_headings = [bold_match.group(1)]
        for raw in raw_headings:
            heading_text = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", raw).strip().upper()
            if heading_text:
                heading_map[heading_text] = sec["section_filename"]
    log.info("[SectionMap] Built heading→section map: %s", heading_map)
    return heading_map


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

    # 4. Create the Sequence field (Y) for the auto-incrementing item number
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
    log.info(
        "[inject_caption] %s %d.%d: '%s'", sequence_name, chapter_num, item_num, caption_text[:60],
    )

def post_process_odt(odt_file_path, sections=None, template_type="srs", document_metadata=None, reference_template_odt_path=None):
    """Modify ODT zip's internal XML for advanced section-aware styling.

    Uses section metadata to apply Navy/Grey table styles based on section
    identity rather than table position in the document.

    Args:
        odt_file_path (str): Path to the ODT file generated by Pandoc.
        sections (list[dict], optional): Section metadata with filenames.
        template_type (str): Document type, "srs" or "sdd".
    """
    log.info("[post_process_odt] Starting for %s (template=%s, sections=%s)", odt_file_path, template_type, len(sections) if sections else 0)
    temporary_extract_dir = tempfile.mkdtemp()
    try:
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
        for prefix_name, uri_data in namespace_map.items():
            ET.register_namespace(prefix=prefix_name, uri=uri_data)
            
        # We need to process both styles.xml (for global styles) and content.xml (for automatic local styles and document body)
        for xml_file_path in [content_xml_path, styles_xml_path]:
            if not os.path.exists(xml_file_path):
                continue
                
            xml_tree = ET.parse(xml_file_path)
            xml_root = xml_tree.getroot()
            is_modified = False
            
            is_content_xml = (os.path.basename(xml_file_path) == 'content.xml')
            
            # -------------------------------------------------------------------------
            # PHASE 1A: Custom Style Injection (both content.xml and styles.xml)
            # Inject cell, table, heading, caption, and TOC styles.
            # content.xml → <office:automatic-styles> (table-cell styles)
            # styles.xml → <office:styles> (paragraph styles)
            # -------------------------------------------------------------------------
            log.info("[Phase1A] Injecting custom styles (%s)", "content.xml" if is_content_xml else "styles.xml")
            if is_content_xml:
                target_styles_element = xml_root.find('office:automatic-styles', namespace_map)
            else:
                target_styles_element = xml_root.find('office:styles', namespace_map)
            if target_styles_element is not None:
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
                        'padding-left': '0.05in',
                        'padding-right': '0.05in',
                        'padding-top': '0.1in',
                        'padding-bottom': '0.1in',
                        'vertical-align': 'middle'
                    }, 'style:table-cell-properties', None),

                    # 3b. GreyTableBodyCell: Grey background, white borders (for standard tables)
                    ('GreyTableBodyCell', 'table-cell', {
                        'background-color': '#dddddd',
                        'border': '0.5pt solid #ffffff',
                        'padding-left': '0.05in',
                        'padding-right': '0.05in',
                        'padding-top': '0.1in',
                        'padding-bottom': '0.1in',
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

                    # 5. Heading Page Break: Forces a new page before Level 1 headings
                    ('Heading_1_PageBreak', 'paragraph', {
                        'break-before': 'page',
                        'default-outline-level': '1',
                        'class': 'chapter'
                    }, 'style:paragraph-properties', 'Heading_20_1'),

                    # 6. TOC_PageBreak: Forces the TOC onto its own page with TOCPage master (resets numbering to 1)
                    ('TOC_PageBreak', 'paragraph', {
                        'break-before': 'page',
                        'master-page-name': 'TOCPage'
                    }, 'style:paragraph-properties', 'Standard'),

                    # 7. Table Caption Style (No parent to prevent MS Word italic override)
                    ('DP_Table_Caption', 'paragraph', {}, 'style:paragraph-properties', None),

                    # 8. Figure Caption Style (No parent to prevent MS Word italic override)
                    ('DP_Figure_Caption', 'paragraph', {}, 'style:paragraph-properties', None),

                    # 9. DocControlTableCell: Transparent background, solid borders (for Document Control tables)
                    ('DocControlTableCell', 'table-cell', {
                        'background-color': 'transparent',
                        'border': '0.5pt solid #000000',
                        'padding-left': '0.1in',
                        'padding-right': '0.1in',
                        'padding-top': '0.1in',
                        'padding-bottom': '0.1in',
                        'vertical-align': 'middle'
                    }, 'style:table-cell-properties', None),

                    # 10. DocControlHeadingText: Bold text with extra paragraph spacing
                    ('DocControlHeadingText', 'paragraph', {
                        'margin-top': '0.2in',
                        'margin-bottom': '0.2in'
                    }, 'style:paragraph-properties', 'Table_20_Heading'),

                    # 11. DocControlContentText: Normal text with extra paragraph spacing
                    ('DocControlContentText', 'paragraph', {
                        'margin-top': '0.2in',
                        'margin-bottom': '0.2in'
                    }, 'style:paragraph-properties', 'Table_20_Contents'),

                    # 9. Caption Character Style (Forces bold, non-italic on inner text for MS Word)
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
                    for existing_style_element in target_styles_element.findall('style:style', namespace_map):
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
                        for style_key_attr, style_value_attr in style_attrs.items():
                            if style_key_attr in ['list-style-name', 'default-outline-level', 'class', 'master-page-name']:
                                new_style_element.set('{' + namespace_map['style'] + '}' + style_key_attr, style_value_attr)
                            # Display formatting attributes belong in the 'fo' namespace
                            elif style_key_attr in ['background-color', 'border', 'padding', 'padding-left', 'padding-right', 'padding-top', 'padding-bottom', 'color', 'font-weight', 'font-family', 'line-height', 'break-before', 'text-align']:
                                properties_element.set('{' + namespace_map['fo'] + '}' + style_key_attr, style_value_attr)
                            else:
                                properties_element.set('{' + namespace_map['style'] + '}' + style_key_attr, style_value_attr)

                        new_style_element.append(properties_element)
                        target_styles_element.append(new_style_element)
                        is_modified = True
                        log.info("[Phase1A] Injected style: %s (family=%s, parent=%s)", style_name, style_family, parent_style)

                log.info("[Phase1A] Custom style injection complete")

            # -------------------------------------------------------------------------
            # PHASE 1B: Outline-style definition (styles.xml only)
            # text:outline-style belongs in <office:styles>, not <office:automatic-styles>
            # -------------------------------------------------------------------------
            if not is_content_xml:
                outline_style_name = 'Outline'
                outline_style_exists = False
                for existing in xml_root.findall('.//text:outline-style', namespace_map):
                    if existing.get('{' + namespace_map['style'] + '}name') == outline_style_name:
                        outline_style_exists = True
                        break

                if not outline_style_exists:
                    outline_style = ET.Element('{' + namespace_map['text'] + '}outline-style')
                    outline_style.set('{' + namespace_map['style'] + '}name', outline_style_name)

                    loext_uri = 'urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0'

                    for level in range(1, 11):
                        if level == 1:
                            num_list_format = "%1%."
                            display_levels = None
                        elif level < 10:
                            format_parts = ".".join(f"%{i}" for i in range(1, level + 1))
                            num_list_format = format_parts + "%"
                            display_levels = str(level)
                        else:
                            num_list_format = "%10%"
                            display_levels = None

                        lvl_style = ET.Element('{' + namespace_map['text'] + '}outline-level-style')
                        lvl_style.set('{' + namespace_map['text'] + '}level', str(level))
                        lvl_style.set(f'{{{loext_uri}}}num-list-format', num_list_format)
                        if display_levels:
                            lvl_style.set('{' + namespace_map['text'] + '}display-levels', display_levels)

                        outline_style.append(lvl_style)

                    office_styles = xml_root.find('office:styles', namespace_map)
                    if office_styles is None:
                        office_styles = ET.Element('{' + namespace_map['office'] + '}styles')
                        xml_root.insert(0, office_styles)
                    office_styles.append(outline_style)
                    is_modified = True
                    log.info("[Phase1B] Injected text:outline-style '%s' with 10 levels", outline_style_name)
                else:
                    log.info("[Phase1B] text:outline-style '%s' already exists — skipping", outline_style_name)

            # -------------------------------------------------------------------------
            # PHASE 2: Global Document Modifications
            # Modify existing style definitions across both content.xml and styles.xml
            # -------------------------------------------------------------------------
            log.info("[Phase2] Starting global document modifications (%s)", "content.xml" if is_content_xml else "styles.xml")
            for style_element in xml_root.findall('.//style:style', namespace_map):
                style_name = style_element.get('{' + namespace_map['style'] + '}name')
                style_family = style_element.get('{' + namespace_map['style'] + '}family')
                
                # 2A. Force Arial Font Globally
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

                # 2B. Set Table Drop Shadows
                if style_family == 'table':
                    table_properties_element = style_element.find('style:table-properties', namespace_map)
                    if table_properties_element is None:
                        table_properties_element = ET.Element('{' + namespace_map['style'] + '}table-properties')
                        style_element.append(table_properties_element)
                    # Apply a subtle grey shadow (#808080) offset by 0.04 inches right and down
                    table_properties_element.set('{' + namespace_map['style'] + '}shadow', '#808080 0.04in 0.04in')
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
                        paragraph_properties_element.set('{' + namespace_map['fo'] + '}margin-top', '0.1in')
                    elif style_name == 'TOCEntry':
                        paragraph_properties_element.set('{' + namespace_map['fo'] + '}text-align', 'center')
                    else:
                        paragraph_properties_element.set('{' + namespace_map['fo'] + '}text-align', 'justify')
                        
                    paragraph_properties_element.set('{' + namespace_map['style'] + '}justify-single-word', 'false')

                    # 2E. Ensure ALL heading styles have class="chapter" — required for LibreOffice
                    # to display outline-style numbers.
                    class_attr = '{' + namespace_map['style'] + '}class'
                    if style_name and 'class' not in style_name.lower():
                        if style_name.startswith('Heading_20_') or style_name == 'Heading_1_PageBreak':
                            existing_class = style_element.get(class_attr)
                            if existing_class != 'chapter':
                                style_element.set(class_attr, 'chapter')
                                is_modified = True
                                log.info("[Phase2E] Added class='chapter' to heading style '%s'", style_name)

                    is_modified = True
                    
                    # 2D. Enforce font sizes for Headings, Tables, and Figures
                    if style_name:
                        text_properties_element = style_element.find('style:text-properties', namespace_map)
                        if text_properties_element is None:
                            text_properties_element = ET.Element('{' + namespace_map['style'] + '}text-properties')
                            style_element.append(text_properties_element)
                            
                        # Set font sizes for Headings
                        if style_name.startswith('Heading_20_1') or style_name == 'Heading_1_PageBreak':
                            text_properties_element.set('{' + namespace_map['fo'] + '}font-size', '18pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-asian', '18pt')
                            text_properties_element.set('{' + namespace_map['style'] + '}font-size-complex', '18pt')
                        elif style_name.startswith('Heading_20_2'):
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
                    
            # 2F. Handle run-level heading style overrides (both content.xml and styles.xml)
            # Run-level styles like P56/P57 inherit from Heading_20_N and are used by
            # heading elements in content.xml. They need both default-outline-level AND
            # class="chapter" to display outline numbers.
            for _rs in xml_root.findall('.//style:style', namespace_map):
                _sfam = _rs.get('{' + namespace_map['style'] + '}family')
                if _sfam != 'paragraph':
                    continue
                _parent = _rs.get('{' + namespace_map['style'] + '}parent-style-name')
                if _parent and _parent.startswith('Heading_20_'):
                    _rs_name = _rs.get('{' + namespace_map['style'] + '}name')
                    _m = re.search(r'Heading_20_(\d+)', _parent)
                    if _m:
                        # Add default-outline-level if missing
                        if '{' + namespace_map['style'] + '}default-outline-level' not in _rs.attrib:
                            _rs.set(
                                '{' + namespace_map['style'] + '}default-outline-level',
                                _m.group(1),
                            )
                            is_modified = True
                            log.info("[Phase2F] Added default-outline-level '%s' to run-level style '%s' (parent=%s)", _m.group(1), _rs_name, _parent)

                        # Add class="chapter" — required for LibreOffice to show outline numbers
                        _class_attr = '{' + namespace_map['style'] + '}class'
                        _existing_class = _rs.get(_class_attr)
                        if _existing_class != 'chapter':
                            _rs.set(_class_attr, 'chapter')
                            is_modified = True
                            log.info("[Phase2F] Added class='chapter' to run-level style '%s' (parent=%s)", _rs_name, _parent)

            # -------------------------------------------------------------------------
            # PHASE 2G: Create ContentPage master page (styles.xml, when document_metadata provided)
            # Header with document ID fields; Footer from Standard master page
            # -------------------------------------------------------------------------
            if not is_content_xml and document_metadata:
                log.info("[Phase2G] Creating ContentPage master page with header fields")
                text_uri = namespace_map['text']
                style_uri = namespace_map['style']
                draw_uri = namespace_map['draw']
                office_uri = namespace_map['office']

                master_styles = xml_root.find('office:master-styles', namespace_map)
                if master_styles is not None:
                    style_name_attr = '{' + style_uri + '}name'
                    style_display_attr = '{' + style_uri + '}display-name'
                    style_page_layout_attr = '{' + style_uri + '}page-layout-name'
                    draw_style_attr = '{' + draw_uri + '}style-name'
                    text_name_attr = '{' + text_uri + '}name'
                    office_value_type_attr = '{' + office_uri + '}value-type'
                    office_string_value_attr = '{' + office_uri + '}string-value'

                    # Check if ContentPage already exists
                    content_page_exists = False
                    for mp in master_styles.findall('style:master-page', namespace_map):
                        if mp.get(style_name_attr) == 'ContentPage':
                            content_page_exists = True
                            break

                    if not content_page_exists:
                        # Clone Convert_20_5 master page as base
                        base_mp = None
                        all_mp = master_styles.findall('style:master-page', namespace_map)
                        log.info("[Phase2G] Found %d master pages: %s", len(all_mp), [m.get(style_name_attr) for m in all_mp])
                        for mp in all_mp:
                            if mp.get(style_name_attr) == 'Convert_20_5':
                                base_mp = mp
                                break

                        if base_mp is not None:
                            content_page = copy.deepcopy(base_mp)
                            content_page.set(style_name_attr, 'ContentPage')
                            content_page.set(style_display_attr, 'Content Page')
                            content_page.set(style_page_layout_attr, 'Mpm1')  # same as Standard
                            content_page.set(draw_style_attr, 'Mdp1')

                            # Rebuild header with new field names
                            header = ET.Element('{' + style_uri + '}header')

                            # user-field-decls with document_metadata values
                            header_decls = ET.Element('{' + text_uri + '}user-field-decls')
                            for field_name, field_value in document_metadata.items():
                                decl = ET.Element('{' + text_uri + '}user-field-decl')
                                decl.set(text_name_attr, field_name)
                                decl.set(office_value_type_attr, 'string')
                                decl.set(office_string_value_attr, field_value)
                                header_decls.append(decl)
                            header.append(header_decls)

                            # Header paragraph with user-field-get elements
                            # Layout: PRJ_ID - PRJ_VERSION - TYPE_ID - DOC_TYPE - DOC_VER_MAJOR V DOC_VER_MINOR
                            header_p = ET.Element('{' + text_uri + '}p')
                            header_p.set('{' + text_uri + '}style-name', 'MP10')

                            # Leading tab span
                            lead_span = ET.Element('{' + text_uri + '}span')
                            lead_span.set('{' + text_uri + '}style-name', 'MT12')
                            tab_elem = ET.Element('{' + text_uri + '}tab')
                            lead_span.append(tab_elem)
                            header_p.append(lead_span)

                            header_fields = [
                                'PRJ_ID', 'PRJ_FG', 'PRJ_VERSION', 'TYPE_ID', 'DOC_TYPE',
                                'DOC_VER_MAJOR', 'DOC_VER_MINOR',
                            ]

                            for i, field in enumerate(header_fields):
                                # Add separator before field (not first)
                                if i > 0:
                                    if i == 6:
                                        sep_text = 'V'  # between DOC_VER_MAJOR and DOC_VER_MINOR
                                    else:
                                        sep_text = '-'
                                    sep_span = ET.Element('{' + text_uri + '}span')
                                    sep_span.set('{' + text_uri + '}style-name', 'MT13')
                                    sep_span.text = sep_text
                                    header_p.append(sep_span)

                                val_span = ET.Element('{' + text_uri + '}span')
                                val_span.set('{' + text_uri + '}style-name', 'MT13')
                                ufg = ET.Element('{' + text_uri + '}user-field-get')
                                ufg.set(text_name_attr, field)
                                ufg.text = document_metadata.get(field, '')
                                val_span.append(ufg)
                                header_p.append(val_span)

                            header.append(header_p)
                            content_page[0] = header  # Replace original header

                            # Build custom footer with doc title, version, date, page numbers
                            footer = ET.Element('{' + style_uri + '}footer')

                            # Footer user-field-decls for footer-specific fields
                            footer_decls = ET.Element('{' + text_uri + '}user-field-decls')
                            for fname in ['DOC_VER_DATE', 'DOC_VER_MAJOR', 'DOC_VER_MINOR']:
                                fval = document_metadata.get(fname, '')
                                decl = ET.Element('{' + text_uri + '}user-field-decl')
                                decl.set(text_name_attr, fname)
                                decl.set(office_value_type_attr, 'string')
                                decl.set(office_string_value_attr, fval)
                                footer_decls.append(decl)
                            footer.append(footer_decls)

                            # Line 1: Left = "Software Requirement Specification" | Right = DOC_VER_DATE
                            footer_p1 = ET.Element('{' + text_uri + '}p')
                            footer_p1.set('{' + text_uri + '}style-name', 'MP11')
                            footer_p1.text = 'Software Requirement Specification'
                            tab1 = ET.Element('{' + text_uri + '}tab')
                            footer_p1.append(tab1)
                            uf_doc_date = ET.Element('{' + text_uri + '}user-field-get')
                            uf_doc_date.set(text_name_attr, 'DOC_VER_DATE')
                            uf_doc_date.text = document_metadata.get('DOC_VER_DATE', '')
                            footer_p1.append(uf_doc_date)
                            footer.append(footer_p1)

                            # Line 2: Left = DOC_VER_MAJOR V DOC_VER_MINOR | Right = Page N of M
                            footer_p2 = ET.Element('{' + text_uri + '}p')
                            footer_p2.set('{' + text_uri + '}style-name', 'MP12')

                            # Version: DOC_VER_MAJOR V DOC_VER_MINOR
                            span_maj = ET.Element('{' + text_uri + '}span')
                            span_maj.set('{' + text_uri + '}style-name', 'MT16')
                            uf_major = ET.Element('{' + text_uri + '}user-field-get')
                            uf_major.set(text_name_attr, 'DOC_VER_MAJOR')
                            uf_major.text = document_metadata.get('DOC_VER_MAJOR', '0')
                            span_maj.append(uf_major)
                            footer_p2.append(span_maj)

                            span_v = ET.Element('{' + text_uri + '}span')
                            span_v.set('{' + text_uri + '}style-name', 'MT16')
                            span_v.text = 'V'
                            footer_p2.append(span_v)

                            span_min = ET.Element('{' + text_uri + '}span')
                            span_min.set('{' + text_uri + '}style-name', 'MT16')
                            uf_minor = ET.Element('{' + text_uri + '}user-field-get')
                            uf_minor.set(text_name_attr, 'DOC_VER_MINOR')
                            uf_minor.text = document_metadata.get('DOC_VER_MINOR', '01')
                            span_min.append(uf_minor)
                            footer_p2.append(span_min)

                            # Tab separator for left-right split
                            tab2 = ET.Element('{' + text_uri + '}tab')
                            footer_p2.append(tab2)

                            # "Page " text
                            span_page = ET.Element('{' + text_uri + '}span')
                            span_page.set('{' + text_uri + '}style-name', 'Page_20_Number')
                            span_page_inner = ET.Element('{' + text_uri + '}span')
                            span_page_inner.set('{' + text_uri + '}style-name', 'MT17')
                            span_page_inner.text = 'Page '
                            span_page.append(span_page_inner)
                            footer_p2.append(span_page)

                            # Current page number
                            span_pnum = ET.Element('{' + text_uri + '}span')
                            span_pnum.set('{' + text_uri + '}style-name', 'Page_20_Number')
                            span_pnum_inner = ET.Element('{' + text_uri + '}span')
                            span_pnum_inner.set('{' + text_uri + '}style-name', 'MT17')
                            page_num = ET.Element('{' + text_uri + '}page-number')
                            page_num.set('{' + text_uri + '}select-page', 'current')
                            page_num.text = '1'
                            span_pnum_inner.append(page_num)
                            span_pnum.append(span_pnum_inner)
                            footer_p2.append(span_pnum)

                            # " of " text
                            span_of = ET.Element('{' + text_uri + '}span')
                            span_of.set('{' + text_uri + '}style-name', 'Page_20_Number')
                            span_of_inner = ET.Element('{' + text_uri + '}span')
                            span_of_inner.set('{' + text_uri + '}style-name', 'MT17')
                            span_of_inner.text = ' of '
                            span_of.append(span_of_inner)
                            footer_p2.append(span_of)

                            # Total pages
                            span_total = ET.Element('{' + text_uri + '}span')
                            span_total.set('{' + text_uri + '}style-name', 'Page_20_Number')
                            
                            span_total_inner = ET.Element('{' + text_uri + '}span')
                            span_total_inner.set('{' + text_uri + '}style-name', 'MT17')
                            
                            # The correct ODT tag for total page count is <text:page-count>
                            total_pages = ET.Element('{' + text_uri + '}page-count')
                            style_uri = namespace_map['style']
                            total_pages.set('{' + style_uri + '}num-format', '1')
                            total_pages.text = '1'
                            
                            span_total_inner.append(total_pages)
                            span_total.append(span_total_inner)
                            footer_p2.append(span_total)

                            footer.append(footer_p2)

                            # Replace footer in ContentPage
                            if len(content_page) > 1:
                                content_page[1] = footer
                            else:
                                content_page[1] = footer  # Replace original footer

                            master_styles.append(content_page)
                            is_modified = True
                            log.info("[Phase2G] Created ContentPage master page")
                        else:
                            log.warning("[Phase2G] Convert_20_5 master page not found — cannot create ContentPage")
                    else:
                        log.info("[Phase2G] ContentPage master page already exists — skipping")

            # -------------------------------------------------------------------------
            # PHASE 2H: Create TOCPage master page (page numbering resets to 1)
            # -------------------------------------------------------------------------
            if not is_content_xml:
                log.info("[Phase2H] Checking for TOCPage master page")
                master_styles = xml_root.find('office:master-styles', namespace_map)
                if master_styles is not None:
                    style_uri = namespace_map['style']
                    text_uri = namespace_map['text']
                    draw_uri = namespace_map['draw']
                    fo_uri = namespace_map['fo']
                    office_uri = namespace_map['office']
                    style_name_attr = '{' + style_uri + '}name'
                    style_display_attr = '{' + style_uri + '}display-name'
                    style_page_layout_attr = '{' + style_uri + '}page-layout-name'
                    style_parent_attr = '{' + style_uri + '}parent-style-name'

                    # Check if TOCPage already exists
                    toc_page_exists = False
                    for mp in master_styles.findall('style:master-page', namespace_map):
                        if mp.get(style_name_attr) == 'TOCPage':
                            toc_page_exists = True
                            break

                    if not toc_page_exists:
                        # Find a base master page to clone (Convert_20_5 or first available)
                        base_mp = None
                        for name in ['Convert_20_5', 'Convert_20_1', 'MP1']:
                            for mp in master_styles.findall('style:master-page', namespace_map):
                                if mp.get(style_name_attr) == name:
                                    base_mp = mp
                                    break
                            if base_mp is not None:
                                break

                        # Fallback: use the first master page
                        if base_mp is None:
                            for mp in master_styles.findall('style:master-page', namespace_map):
                                base_mp = mp
                                break

                        if base_mp is not None:
                            # Clone the master page
                            toc_master = copy.deepcopy(base_mp)
                            toc_master.set(style_name_attr, 'TOCPage')
                            toc_master.set(style_display_attr, 'TOC Page')

                            # Remove existing footers from TOCPage (which contain unwanted text)
                            for child in list(toc_master):
                                if child.tag.endswith('footer') or child.tag.endswith('footer-left'):
                                    toc_master.remove(child)

                            # Extract Shape1's paragraph from reference document styles.xml
                            shape1_p = None
                            if reference_template_odt_path and os.path.exists(reference_template_odt_path):
                                try:
                                    with zipfile.ZipFile(reference_template_odt_path, 'r') as ref_zip:
                                        if 'styles.xml' in ref_zip.namelist():
                                            ref_styles_root = ET.fromstring(ref_zip.read('styles.xml'))
                                            for p in ref_styles_root.findall('.//{' + namespace_map['text'] + '}p'):
                                                if p.find('.//*[@{' + namespace_map['draw'] + '}name="Shape1"]') is not None:
                                                    shape1_p = copy.deepcopy(p)
                                                    break
                                            
                                            # Copy associated automatic styles for Shape1's paragraph
                                            if shape1_p is not None:
                                                import copy
                                                styles_to_copy = set()
                                                for elem in shape1_p.iter():
                                                    for k, v in elem.attrib.items():
                                                        if k.endswith('style-name'):
                                                            styles_to_copy.add(v)
                                                ref_auto_styles = ref_styles_root.find('.//{' + namespace_map['office'] + '}automatic-styles')
                                                our_auto_styles = xml_root.find('.//{' + namespace_map['office'] + '}automatic-styles')
                                                if ref_auto_styles is not None and our_auto_styles is not None:
                                                    for style_name in styles_to_copy:
                                                        for style_elem in ref_auto_styles.iter():
                                                            if style_elem.get('{' + namespace_map['style'] + '}name') == style_name:
                                                                our_auto_styles.append(copy.deepcopy(style_elem))
                                except Exception as e:
                                    log.error("[Phase2H] Error extracting Shape1 for TOC footer: %s", e)

                            # Clean the paragraph: remove all text content and text child nodes
                            if shape1_p is not None:
                                shape1_p.text = None
                                shape1_p.tail = None
                                elements_to_remove = []
                                for child in shape1_p:
                                    if child.tag.startswith('{' + namespace_map['text'] + '}'):
                                        elements_to_remove.append(child)
                                    else:
                                        child.tail = None
                                for el in elements_to_remove:
                                    shape1_p.remove(el)

                            # Add a clean footer containing ONLY Shape1's cleaned paragraph
                            clean_footer = ET.Element('{' + style_uri + '}footer')
                            if shape1_p is not None:
                                clean_footer.append(shape1_p)
                            else:
                                clean_p = ET.Element('{' + text_uri + '}p')
                                clean_p.set('{' + text_uri + '}style-name', 'Footer')
                                clean_footer.append(clean_p)
                                
                            toc_master.append(clean_footer)

                            # Create a dedicated page layout with first-page-number="1"
                            auto_styles = xml_root.find('office:automatic-styles', namespace_map)
                            if auto_styles is not None:
                                existing_page_layout = None
                                for ps in auto_styles.findall('style:style', namespace_map):
                                    if ps.get(style_name_attr) == 'TOCPageLayout' and ps.get(style_parent_attr) == 'pm1':
                                        existing_page_layout = ps
                                        break

                                if existing_page_layout is None:
                                    # Clone the page layout from base_mp to preserve footer activation
                                    base_layout_name = base_mp.get(style_page_layout_attr)
                                    base_layout = None
                                    for ps in auto_styles.findall('style:style', namespace_map):
                                        if ps.get(style_name_attr) == base_layout_name:
                                            base_layout = ps
                                            break
                                            
                                    if base_layout is not None:
                                        page_layout = copy.deepcopy(base_layout)
                                        page_layout.set(style_name_attr, 'TOCPageLayout')
                                        page_props = page_layout.find('{' + style_uri + '}page-layout-properties')
                                        if page_props is not None:
                                            page_props.set('{' + text_uri + '}first-page-number', '1')
                                        auto_styles.append(page_layout)

                                toc_master.set(style_page_layout_attr, 'TOCPageLayout')

                            # Remove header (TOC pages shouldn't have the doc-id header)
                            toc_header = toc_master.find('{' + style_uri + '}header')
                            if toc_header is not None:
                                toc_master.remove(toc_header)

                            # Keep footer for page numbers
                            master_styles.append(toc_master)
                            is_modified = True
                            log.info("[Phase2H] Created TOCPage master page with first-page-number=1")
                        else:
                            log.warning("[Phase2H] Standard master page not found — cannot create TOCPage")
                    else:
                        log.info("[Phase2H] TOCPage master page already exists — skipping")


            # -------------------------------------------------------------------------
            # PHASE 3: Apply Content and Structure Mapping (content.xml only)
            # -------------------------------------------------------------------------
            if is_content_xml:
                cfg = get_template_config(template_type)
                log.info("[Phase3] Processing content.xml (template=%s, navy_prefixes=%s, unnumbered=%s)", template_type, cfg["navy_table_section_prefixes"], cfg["unnumbered_headings"])
                body_element = xml_root.find('office:body', namespace_map)
                if body_element is not None:
                    office_text = body_element.find('office:text', namespace_map)

                    # 3A-prep. Remove <table:table-header-rows> wrapper so LibreOffice
                    # does NOT repeat headers on every page. Reference doc has 0 tables
                    # with header-rows out of 109. Phase 3A fallback handles first-row styling.
                    table_xml_tag = "{" + namespace_map['table'] + "}table"
                    tables_in_body_element = body_element.findall('.//' + table_xml_tag, namespace_map)
                    removed_header_rows = 0
                    for table in tables_in_body_element:
                        hdr_rows = table.find("{" + namespace_map['table'] + "}table-header-rows")
                        if hdr_rows is not None:
                            idx = None
                            for i, child in enumerate(table):
                                if child is hdr_rows:
                                    idx = i
                                    break
                            if idx is not None:
                                # Insert all row children in place of the wrapper element
                                for row in list(hdr_rows):
                                    table.insert(idx, row)
                                table.remove(hdr_rows)
                                removed_header_rows += 1
                    if removed_header_rows:
                        is_modified = True
                        log.info("[Phase3A-prep] Removed table-header-rows from %d tables", removed_header_rows)

                    # 3A. Map table styles to specific tables based on section identity
                    table_cell_xml_tag = "{" + namespace_map['table'] + "}table-cell"
                    text_paragraph_xml_tag = "{" + namespace_map['text'] + "}p"
                    log.info("[Phase3A] Found %d tables in document", len(tables_in_body_element))

                    # Build heading → section mapping for section-aware styling
                    heading_to_section = _build_section_heading_map(sections or [])
                    log.info("[Phase3A] heading_to_section map: %s", heading_to_section)

                    # Build a map: table element id → preceding heading text (by document order)
                    table_to_heading = {}
                    if office_text is not None:
                        last_heading_text = None
                        for child in office_text.iter():
                            if child.tag == '{' + namespace_map['text'] + '}h':
                                last_heading_text = "".join(child.itertext()).strip().upper()
                            elif child.tag == '{' + namespace_map['text'] + '}p':
                                p_text = "".join(child.itertext()).strip().upper()
                                if p_text in heading_to_section or p_text in ['REVISION HISTORY', 'DOCUMENT CONTROL']:
                                    last_heading_text = p_text
                            elif child.tag == table_xml_tag and last_heading_text:
                                table_to_heading[id(child)] = last_heading_text

                    log.info("[Phase3A] table_to_heading — %d tables mapped to preceding headings", len(table_to_heading))

                    doc_control_table_element = None
                    for table_index, table in enumerate(tables_in_body_element):
                        # Find the heading that precedes this table
                        preceding_text = table_to_heading.get(id(table))
                        section_filename = heading_to_section.get(preceding_text) if preceding_text else None

                        # Navy blue tables for specific section filename prefixes or known heading texts
                        is_navy_table = False
                        is_doc_control_table = False
                        if section_filename:
                            is_navy_table = any(section_filename.startswith(prefix) for prefix in cfg["navy_table_section_prefixes"])
                        if not is_navy_table and preceding_text:
                            if any(keyword in preceding_text for keyword in ['REVISION HISTORY']):
                                is_navy_table = True
                        if not is_navy_table and preceding_text:
                            if any(keyword in preceding_text for keyword in ['DOCUMENT CONTROL']):
                                is_doc_control_table = True
                                doc_control_table_element = table

                        # Fallback: if no section data, use positional logic for navy tables
                        if not is_navy_table and not section_filename and cfg["navy_table_positional_fallback"]:
                            is_navy_table = (table_index < len(cfg["navy_table_section_prefixes"]))
                            
                        # Remove drop shadows applied globally in Phase 2B for Navy and Doc Control tables
                        if is_navy_table or is_doc_control_table:
                            t_style_name = table.get('{' + namespace_map['table'] + '}style-name')
                            if t_style_name:
                                auto_styles = xml_root.find('.//{' + namespace_map['office'] + '}automatic-styles')
                                if auto_styles is not None:
                                    for t_style in auto_styles.findall('.//{' + namespace_map['style'] + '}style'):
                                        if t_style.get('{' + namespace_map['style'] + '}name') == t_style_name:
                                            t_props = t_style.find('.//{' + namespace_map['style'] + '}table-properties')
                                            if t_props is not None and '{' + namespace_map['style'] + '}shadow' in t_props.attrib:
                                                del t_props.attrib['{' + namespace_map['style'] + '}shadow']
                                                log.info("[Phase3A] Removed drop shadow from %s", t_style_name)

                        log.info(
                            "[Phase3A] Table #%d: preceding_heading='%s' section='%s' navy=%s",
                            table_index, preceding_text, section_filename, is_navy_table,
                        )

                        # Extract header rows to differentiate header cells from body cells
                        header_rows_elements = table.findall('.//table:table-header-rows', namespace_map)
                        header_cells_set = set()
                        for header_row_element in header_rows_elements:
                            for table_cell_element in header_row_element.findall('.//' + table_cell_xml_tag, namespace_map):
                                header_cells_set.add(table_cell_element)

                        # If Pandoc didn't generate header rows, treat first row as header
                        table_row_tag = "{" + namespace_map['table'] + "}table-row"
                        if not header_cells_set:
                            first_row = table.find(table_row_tag)
                            if first_row is not None:
                                for table_cell_element in first_row.findall(table_cell_xml_tag):
                                    header_cells_set.add(table_cell_element)

                        # Walk and apply styling to all cells in the table by row and column
                        for row_element in table.findall('.//{' + namespace_map['table'] + '}table-row', namespace_map):
                            for col_idx, table_cell_element in enumerate(row_element.findall('./{' + namespace_map['table'] + '}table-cell', namespace_map)):
                                if table_cell_element in header_cells_set:
                                    # Header cell styling logic
                                    if is_navy_table:
                                        table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'NavyTableHeaderCell')
                                        for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                            paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'NavyTableHeadingText')
                                    elif is_doc_control_table:
                                        table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'DocControlTableCell')
                                        for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                            paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'DocControlHeadingText' if col_idx == 0 else 'DocControlContentText')
                                    else:
                                        table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'GreyTableHeaderCell')
                                        for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                            paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'Table_20_Heading')
                                else:
                                    # Body cell styling logic
                                    if is_navy_table:
                                        table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'NavyTableRowCell')
                                        for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                            paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'Table_20_Contents')
                                    elif is_doc_control_table:
                                        table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'DocControlTableCell')
                                        for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                            paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'DocControlHeadingText' if col_idx == 0 else 'DocControlContentText')
                                    else:
                                        table_cell_element.set('{' + namespace_map['table'] + '}style-name', 'GreyTableBodyCell')
                                        for paragraph_element in table_cell_element.findall('.//' + text_paragraph_xml_tag, namespace_map):
                                            paragraph_element.set('{' + namespace_map['text'] + '}style-name', 'Table_20_Contents')

                    # -------------------------------------------------------------------------
                    # PHASE 3G: Inject Shape5 after Document Control table
                    # -------------------------------------------------------------------------
                    import copy
                    if doc_control_table_element is not None and reference_template_odt_path and os.path.exists(reference_template_odt_path):
                        log.info("[Phase3G] Extracting Shape5 from reference document")
                        try:
                            with zipfile.ZipFile(reference_template_odt_path, 'r') as ref_zip:
                                if 'content.xml' in ref_zip.namelist():
                                    ref_root = ET.fromstring(ref_zip.read('content.xml'))
                                    
                                    shape5_p = None
                                    for p in ref_root.findall('.//{' + namespace_map['text'] + '}p'):
                                        if p.find('.//*[@{' + namespace_map['draw'] + '}name="Shape5"]') is not None:
                                            shape5_p = p
                                            break
                                            
                                    if shape5_p is not None:
                                        # Copy automatic styles referenced by shape5_p
                                        styles_to_copy = set()
                                        for elem in shape5_p.iter():
                                            for k, v in elem.attrib.items():
                                                if k.endswith('style-name'):
                                                    styles_to_copy.add(v)
                                                    
                                        ref_auto_styles = ref_root.find('.//{' + namespace_map['office'] + '}automatic-styles')
                                        our_auto_styles = xml_root.find('.//{' + namespace_map['office'] + '}automatic-styles')
                                        if ref_auto_styles is not None and our_auto_styles is not None:
                                            for style_name in styles_to_copy:
                                                for style_elem in ref_auto_styles.iter():
                                                    if style_elem.get('{' + namespace_map['style'] + '}name') == style_name:
                                                        copied_style = copy.deepcopy(style_elem)
                                                        
                                                        # Force Arial font for any text inside the shape
                                                        text_props = copied_style.find('.//{' + namespace_map['style'] + '}text-properties')
                                                        if text_props is None:
                                                            text_props = ET.Element('{' + namespace_map['style'] + '}text-properties')
                                                            copied_style.append(text_props)
                                                        text_props.set('{' + namespace_map['fo'] + '}font-family', 'Arial')
                                                        text_props.set('{' + namespace_map['style'] + '}font-name', 'Arial')
                                                        text_props.set('{' + namespace_map['style'] + '}font-name-asian', 'Arial')
                                                        text_props.set('{' + namespace_map['style'] + '}font-name-complex', 'Arial')
                                                        
                                                        our_auto_styles.append(copied_style)
                                                        
                                        # Insert after doc_control_table_element
                                        for idx, child in enumerate(list(office_text)):
                                            if child == doc_control_table_element:
                                                # Insert an empty spacer paragraph using Standard style so it doesn't collapse
                                                spacer_p = ET.Element('{' + namespace_map['text'] + '}p')
                                                spacer_p.set('{' + namespace_map['text'] + '}style-name', 'Standard')
                                                office_text.insert(idx + 1, spacer_p)
                                                office_text.insert(idx + 2, copy.deepcopy(shape5_p))
                                                log.info("[Phase3G] Inserted Shape5 after Document Control table with spacer")
                                                is_modified = True
                                                break
                        except Exception as e:
                            log.error("[Phase3G] Error extracting Shape5: %s", e)

                            is_modified = True
                            
                    # 3B. Map dynamic page breaks and unnumbered styles to specific headings
                    heading_elements = body_element.findall('.//text:h', namespace_map)
                    log.info("[Phase3B] Found %d headings in document", len(heading_elements))

                    # Ensure ALL headings have explicit text:outline-level (required for outline-style mechanism)
                    for heading_element in heading_elements:
                        level = heading_element.get('{' + namespace_map['text'] + '}outline-level')
                        if not level:
                            h_style = heading_element.get('{' + namespace_map['text'] + '}style-name') or ''
                            m = re.search(r'(\d+)(?:_20_(\d+))?', str(h_style))
                            if m:
                                level = m.group(2) or m.group(1)
                                heading_element.set('{' + namespace_map['text'] + '}outline-level', level)
                                h_text = "".join(heading_element.itertext())[:40]
                                log.info("[Phase3B] Added outline-level='%s' to heading '%s' (style=%s)", level, h_text, h_style)

                    for heading_element in heading_elements:
                        level = heading_element.get('{' + namespace_map['text'] + '}outline-level')
                        if level == '1':
                            heading_element.set('{' + namespace_map['text'] + '}style-name', 'Heading_1_PageBreak')
                            is_modified = True

                    # 3C. Map predefined styles to explicitly declared Figure and Table Captions
                    if office_text is not None:
                        log.info("[Phase3C] Starting table/figure caption processing")
                        # Ensure sequence declarations are configured to display Chapter numbers (outline-level 1)
                        seq_decls = office_text.find('text:sequence-decls', namespace_map)
                        if seq_decls is None:
                            seq_decls = ET.Element('{' + namespace_map['text'] + '}sequence-decls')
                            office_text.insert(0, seq_decls)

                        for seq_name in ['Table', 'Figure']:
                            found = False
                            for decl in seq_decls.findall('{' + namespace_map['text'] + '}sequence-decl'):
                                if decl.get('{' + namespace_map['text'] + '}name') == seq_name:
                                    decl.set('{' + namespace_map['text'] + '}display-outline-level', '1')
                                    found = True
                                    break
                            if not found:
                                decl = ET.Element('{' + namespace_map['text'] + '}sequence-decl')
                                decl.set('{' + namespace_map['text'] + '}name', seq_name)
                                decl.set('{' + namespace_map['text'] + '}display-outline-level', '1')
                                seq_decls.append(decl)
                                log.info("[Phase3C] Created sequence-decl for '%s' with display-outline-level=1", seq_name)

                        current_chapter = 0
                        table_counter = 0
                        figure_counter = 0
                        
                        # Iterate sequentially over all descendants of office_text to track chapter
                        for element in office_text.iter():
                            if element.tag == '{' + namespace_map['text'] + '}h':
                                level = element.get('{' + namespace_map['text'] + '}outline-level')
                                if level == '1':
                                    heading_text = "".join(element.itertext()).strip().upper()
                                    if not any(uh in heading_text for uh in cfg["unnumbered_headings"]):
                                        current_chapter += 1
                                        table_counter = 0
                                        figure_counter = 0
                                        log.info("[Phase3C] New chapter %d: '%s'", current_chapter, heading_text)
                            elif element.tag == '{' + namespace_map['text'] + '}p':
                                text_content = "".join(element.itertext()).strip()
                                if text_content.startswith("Table "):
                                    match = CAPTION_REGEX.match(text_content)
                                    caption_text = match.group(1) if match else text_content
                                    table_counter += 1
                                    inject_sequence_caption(element, 'Table', current_chapter, table_counter, caption_text, namespace_map)
                                    is_modified = True
                                    log.info("[Phase3C] Table caption ch=%d idx=%d -> '%s'", current_chapter, table_counter, caption_text[:50])
                                elif text_content.startswith("Figure "):
                                    match = CAPTION_REGEX.match(text_content)
                                    caption_text = match.group(1) if match else text_content
                                    figure_counter += 1
                                    inject_sequence_caption(element, 'Figure', current_chapter, figure_counter, caption_text, namespace_map)
                                    is_modified = True
                                    log.info("[Phase3C] Figure caption ch=%d idx=%d -> '%s'", current_chapter, figure_counter, caption_text[:50])
                    
                    if office_text is not None and office_text.find('text:table-of-content', namespace_map) is None:
                        log.info("[Phase3-TOC] No existing TOC found — inserting Table of Contents")
                        heading_elements = office_text.findall('.//text:h', namespace_map)
                        introduction_heading_element = None
                        
                        # Find the first heading containing "INTRODUCTION"
                        for heading_element in heading_elements:
                            text_content = "".join(heading_element.itertext()).strip().upper()
                            if cfg["toc_insertion_target"] in text_content:
                                introduction_heading_element = heading_element
                                break
                                
                        if introduction_heading_element is not None:
                            log.info("[Phase3-TOC] Found insertion target heading — TOC will be placed before '%s'", cfg["toc_insertion_target"])
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
                                start_index = 0
                                
                                for heading_element in heading_elements:
                                    level_str = heading_element.get('{' + namespace_map['text'] + '}outline-level')
                                    level = int(level_str) if level_str else 1
                                    
                                    heading_text_raw = "".join(heading_element.itertext()).strip()
                                    text_content_upper = heading_text_raw.upper()
                                    
                                    # Certain structural headings don't get outline numbering prefixes
                                    is_ignored = any(uh in text_content_upper for uh in cfg["unnumbered_headings"])
                                    
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
                                log.info("[Phase3-TOC] TOC inserted with %d heading entries", len(heading_elements))
                                
                    # 3E. Header/Footer Activation (modified for ContentPage master page switching)
                    if office_text is not None:
                        log.info("[Phase3E] office_text found, checking for automatic-styles")
                        automatic_styles_collection = xml_root.find('office:automatic-styles', namespace_map)
                        style_uri = namespace_map['style']
                        text_uri = namespace_map['text']

                        # Collect all level-1 headings to decide master page per chapter
                        h1_headings = []
                        text_h_tag = '{' + text_uri + '}h'
                        text_outline_attr = '{' + text_uri + '}outline-level'
                        text_style_attr = '{' + text_uri + '}style-name'
                        for child in office_text:
                            if child.tag == text_h_tag:
                                level = child.get(text_outline_attr)
                                if level == '1':
                                    h1_headings.append(child)

                        # If document_metadata provided, switch chapters to ContentPage master and handle Revision History
                        if document_metadata:
                            log.info("[Phase3E] document_metadata set, %d H1 headings found", len(h1_headings))
                            if automatic_styles_collection is None:
                                automatic_styles_collection = xml_root.find('office:automatic-styles', namespace_map)

                            if automatic_styles_collection is not None:
                                # Create ContentPageStart and ContentPageStartFirst paragraph styles (parent=Heading_20_1, master-page-name=ContentPage)
                                # Inherit directly from Heading_20_1 (not Heading_1_PageBreak) to preserve outline-style numbering chain
                                # Reference doc uses Heading_20_1-based inline styles that work with LibreOffice's auto-numbering
                                fo_uri = namespace_map['fo']
                                
                                # Style for the very first chapter heading (resets page number to 1)
                                cps_first_style = ET.Element('{' + style_uri + '}style')
                                cps_first_style.set('{' + style_uri + '}name', 'ContentPageStartFirst')
                                cps_first_style.set('{' + style_uri + '}family', 'paragraph')
                                cps_first_style.set('{' + style_uri + '}parent-style-name', 'Heading_20_1')
                                cps_first_style.set('{' + style_uri + '}master-page-name', 'ContentPage')
                                cps_first_style.set('{' + style_uri + '}default-outline-level', '1')
                                cps_first_style.set('{' + style_uri + '}class', 'chapter')

                                cps_first_para_props = ET.Element('{' + style_uri + '}paragraph-properties')
                                cps_first_para_props.set('{' + fo_uri + '}break-before', 'page')
                                cps_first_para_props.set('{' + style_uri + '}page-number', '1')
                                cps_first_style.append(cps_first_para_props)

                                # Style for subsequent chapter headings (does not reset page number)
                                cps_style = ET.Element('{' + style_uri + '}style')
                                cps_style.set('{' + style_uri + '}name', 'ContentPageStart')
                                cps_style.set('{' + style_uri + '}family', 'paragraph')
                                cps_style.set('{' + style_uri + '}parent-style-name', 'Heading_20_1')
                                cps_style.set('{' + style_uri + '}master-page-name', 'ContentPage')
                                cps_style.set('{' + style_uri + '}default-outline-level', '1')
                                cps_style.set('{' + style_uri + '}class', 'chapter')

                                cps_para_props = ET.Element('{' + style_uri + '}paragraph-properties')
                                cps_para_props.set('{' + fo_uri + '}break-before', 'page')
                                cps_style.append(cps_para_props)

                                automatic_styles_collection.append(cps_first_style)
                                automatic_styles_collection.append(cps_style)

                                # Create an automatic style extending TOCEntry with a page break for Revision History
                                toc_pb_name = 'TOCEntry_InlineBreak'
                                auto_pb = ET.Element('{' + style_uri + '}style')
                                auto_pb.set('{' + style_uri + '}name', toc_pb_name)
                                auto_pb.set('{' + style_uri + '}family', 'paragraph')
                                auto_pb.set('{' + style_uri + '}parent-style-name', 'TOCEntry')
                                auto_props = ET.Element('{' + style_uri + '}paragraph-properties')
                                auto_props.set('{' + fo_uri + '}break-before', 'page')
                                auto_pb.append(auto_props)
                                automatic_styles_collection.append(auto_pb)

                                # Apply ContentPageStartFirst to the first H1, and ContentPageStart to the rest
                                first_chapter_found = False
                                for i, h1 in enumerate(h1_headings):
                                    h_text = "".join(h1.itertext()).strip().upper()
                                    sec_filename = heading_to_section.get(h_text, "")
                                    
                                    if '02_revision_history' in sec_filename.lower() or 'REVISION HISTORY' in h_text:
                                        h1.set(text_style_attr, toc_pb_name)
                                        log.info("[Phase3E] Applied TOCEntry + Page Break to REVISION HISTORY heading (section: %s)", sec_filename)
                                    elif not first_chapter_found:
                                        h1.set(text_style_attr, 'ContentPageStartFirst')
                                        log.info("[Phase3E] Applied ContentPageStartFirst (page-number=1) to chapter 1 heading")
                                        first_chapter_found = True
                                    else:
                                        h1.set(text_style_attr, 'ContentPageStart')
                                        log.info("[Phase3E] Applied ContentPageStart to chapter %d heading", i + 1)
                                
                                # Also check paragraphs for REVISION HISTORY (if it's not a heading)
                                text_p_tag = '{' + text_uri + '}p'
                                for p in office_text.findall('.//' + text_p_tag, namespace_map):
                                    p_text = "".join(p.itertext()).strip().upper()
                                    if not p_text:
                                        continue
                                    sec_filename = heading_to_section.get(p_text, "")
                                    if '02_revision_history' in sec_filename.lower() or p_text == 'REVISION HISTORY':
                                        p.set(text_style_attr, toc_pb_name)
                                        log.info("[Phase3E] Applied TOCEntry + Page Break to REVISION HISTORY paragraph")
                                        
                                is_modified = True

                    # 3F. User Field Declarations (content.xml)
                    if document_metadata and office_text is not None:
                        user_field_decls = office_text.find('text:user-field-decls', namespace_map)
                        if user_field_decls is None:
                            user_field_decls = ET.Element('{' + namespace_map['text'] + '}user-field-decls')
                            office_text.insert(0, user_field_decls)

                        for field_name, field_value in document_metadata.items():
                            found = False
                            for decl in user_field_decls.findall('text:user-field-decl', namespace_map):
                                if decl.get('{' + namespace_map['text'] + '}name') == field_name:
                                    decl.set('{' + namespace_map['office'] + '}string-value', field_value)
                                    found = True
                                    break
                            if not found:
                                new_decl = ET.Element('{' + namespace_map['text'] + '}user-field-decl')
                                new_decl.set('{' + namespace_map['text'] + '}name', field_name)
                                new_decl.set('{' + namespace_map['office'] + '}value-type', 'string')
                                new_decl.set('{' + namespace_map['office'] + '}string-value', field_value)
                                user_field_decls.append(new_decl)
                                is_modified = True
                                log.info("[Phase3F] Added user-field-decl '%s' = '%s'", field_name, field_value)
            
            # Save any modifications back to the temporary XML files
            if is_modified:
                xml_tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                log.info("[PostProcess] Saved modified %s", os.path.basename(xml_file_path))
                
        # Re-pack the modified XML files back into the original ODT zip archive layout
        log.info("[PostProcess] Re-packing ODT at %s", odt_file_path)
        with zipfile.ZipFile(odt_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for root_dir, _, files in os.walk(temporary_extract_dir):
                for file in files:
                    full_path = os.path.join(root_dir, file)
                    rel_path = os.path.relpath(full_path, temporary_extract_dir)
                    zip_out.write(full_path, rel_path)
                    
    finally:
        log.info("[PostProcess] Cleanup complete. ODT re-packed to %s", odt_file_path)
        shutil.rmtree(temporary_extract_dir)

def convert_markdown_to_odt(
    markdown_content=None,
    output_odt_file_path=None,
    reference_template_odt_path=None,
    sections=None,
    template_type="srs",
    document_metadata=None,
) -> bool:
    """
    Main entry point for document conversion. Orchestrates cleaning, Pandoc execution, and post-processing.

    Args:
        markdown_content (str, optional): The raw markdown string to convert.
        output_odt_file_path (str): The absolute path where the final .odt file should be saved.
        reference_template_odt_path (str, optional): A path to a reference ODT file providing base styles.
        sections (list[dict], optional): Section metadata with content. Each dict has
            {"section_filename": str, "content": str, ...}. When provided, enables
            section-aware styling instead of positional assumptions.
        template_type (str): Document type, "srs" or "sdd".
        document_metadata (dict, optional): Document ID field values for header.
            Keys: PRJ_ID, PRJ_FG, PRJ_VERSION, TYPE_ID, DOC_TYPE, DOC_VER_MAJOR, DOC_VER_MINOR.

    Returns:
        bool: True if the conversion pipeline executed completely without errors, False otherwise.
    """

    # Fallback to template-specific reference document if not explicitly provided
    if not reference_template_odt_path:
        from system_config import get_reference_document_dir
        cfg = get_template_config(template_type)
        reference_template_odt_path = os.path.join(
            get_reference_document_dir(),
            cfg["reference_document_filename"],
        )

    log.info("[convert] Starting conversion: output=%s template=%s reference=%s sections=%s", output_odt_file_path, template_type, reference_template_odt_path, len(sections) if sections else 0)

    temporary_markdown_file_path = output_odt_file_path + ".temp.md"

    try:
        if sections:
            # Section-aware mode: assemble markdown from section content
            assembled_parts = []
            for sec in sections:
                sec_content = sec.get("content", "").strip()
                if sec_content:
                    assembled_parts.append(sec_content)
            markdown_content = "\n\n".join(assembled_parts)
            log.info("[convert] Section-aware mode: assembled %d sections (%d with content)", len(sections), len(assembled_parts))

        # Step 1: Clean raw markdown to prevent Pandoc numbering conflicts
        cleaned_markdown_content = strip_heading_numbering(markdown_raw_content=markdown_content)
        
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
        log.info("[convert] Running pandoc: %s", " ".join(pandoc_command_arguments))
        subprocess_execution_result = subprocess.run(pandoc_command_arguments, capture_output=True, text=True)
        log.info("[convert] Pandoc exit code: %d", subprocess_execution_result.returncode)
        
        # Step 4: Validate Pandoc exit code and initiate XML Post Processing
        if subprocess_execution_result.returncode == 0:
            log.info("[convert] Pandoc succeeded, starting post-processing")
            post_process_odt(
                output_odt_file_path,
                sections=sections,
                template_type=template_type,
                document_metadata=document_metadata,
                reference_template_odt_path=reference_template_odt_path,
            )
            log.info("[convert] Conversion pipeline complete — success")
            return True
        else:
            log.error("[convert] Pandoc failed (code %d): %s", subprocess_execution_result.returncode, subprocess_execution_result.stderr[:200])
            return False
            
    except Exception as exception_error:
        log.error("[convert] Exception during conversion: %s", exception_error, exc_info=True)
        return False
        
    finally:
        # Step 5: Always clean up the temporary markdown file artifact
        if os.path.exists(temporary_markdown_file_path):
            os.remove(temporary_markdown_file_path)