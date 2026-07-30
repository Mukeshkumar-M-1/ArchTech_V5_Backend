import os
from convert import convert_markdown_to_odt


def run_test():
    # Sample markdown to test the specific post-processing logic in convert.py
    # This includes:
    # 1. Document Control & Revision History (should be unnumbered in ODT, but in TOC)
    # 2. Introduction (where the dynamic TOC should be inserted before)
    # 3. Tables (Navy blue for first two, grey for others)
    # 4. Captions (Paragraphs starting with Table/Figure)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    srs_test_path = os.path.join(current_dir, "SRS_TEST_1.md")
    
    with open(srs_test_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    output_path = os.path.join(current_dir, "test_output.odt")
    
    # Optional: If you have a specific reference template, provide its path.
    # If set to None, convert.py will try to use the default path defined inside it.
    reference_template = "/home/devusr/Mukesh/ArchTech_V5_1/Backend/Document_Section/SRS_Reference/DP-VPX-0227-V1-01-SRS-1V00.odt" 

    print("Starting conversion test...")
    success = convert_markdown_to_odt(
        markdown_content=markdown_content,
        output_odt_file_path=output_path,
        reference_template_odt_path=reference_template,
        document_metadata={
            "PRJ_ID": "DP-XMC-5049",
            "PRJ_FG": "000",
            "PRJ_VERSION": "V1",
            "TYPE_ID": "01",
            "DOC_TYPE": "SRS",
            "DOC_VER_MAJOR": "0",
            "DOC_VER_MINOR": "03",
            "DOC_DATE": "2025-04-16",
        },
    )

    if success:
        print(f"\n\nSuccess! ODT file successfully generated at: {output_path}")
        print("You can open this file in Word or LibreOffice to verify the formatting (TOC, Tables, Fonts, Page Breaks, etc.).")
    else:
        print("Conversion failed. Check the console output for errors.")

if __name__ == "__main__":
    run_test()