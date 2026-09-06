---
project_id: Sample_1
total_requirements: 54
total_links: 15
---

# Requirement Relationships Index

## Link Summary

Total requirements: 54
Total unique links: 15

## Links by Theme

### PCIe Interface & FPGA Connectivity

| Requirement A | File Path | ↔ | Requirement B | File Path | Reason |
|--------------|-----------|---|--------------|-----------|--------|
| REQ-0001 | [requirements/REQ-0001.md](requirements/REQ-0001.md) | ↔ | HAR-0002 | [requirements/HAR-0002.md](requirements/HAR-0002.md) | Both define FPGA interface capabilities including PCIe and video standards |
| REQ-0006 | [requirements/REQ-0006.md](requirements/REQ-0006.md) | ↔ | HAR-0007 | [requirements/HAR-0007.md](requirements/HAR-0007.md) | Both specify PCIe high-speed communication on XMC primary connector |
| REQ-0011 | [requirements/REQ-0011.md](requirements/REQ-0011.md) | ↔ | HAR-0012 | [requirements/HAR-0012.md](requirements/HAR-0012.md) | REQ-0011 lists PCIe Gen 3 link; HAR-0012 defines FPGA transceivers required for PCIe |
| REQ-0015 | [requirements/REQ-0015.md](requirements/REQ-0015.md) | ↔ | REQ-0017 | [requirements/REQ-0017.md](requirements/REQ-0017.md) | Both define PCIe interface specifications and reference clock requirements |
| HAR-0021 | [requirements/HAR-0021.md](requirements/HAR-0021.md) | ↔ | HAR-0036 | [requirements/HAR-0036.md](requirements/HAR-0036.md) | HAR-0021 requires PCIe enumeration test; HAR-0036 specifies OS support for this test |

### Video Interface & Signal Processing

| Requirement A | File Path | ↔ | Requirement B | File Path | Reason |
|--------------|-----------|---|--------------|-----------|--------|
| REQ-0004 | [requirements/REQ-0004.md](requirements/REQ-0004.md) | ↔ | HAR-0008 | [requirements/HAR-0008.md](requirements/HAR-0008.md) | Both define DVI/VGA output paths via FPGA and video encoders |
| REQ-0005 | [requirements/REQ-0005.md](requirements/REQ-0005.md) | ↔ | REQ-0009 | [requirements/REQ-0009.md](requirements/REQ-0009.md) | Both specify ARINC 818 high-speed video protocol implementation on FPGA MGT bank |
| REQ-0023 | [requirements/REQ-0023.md](requirements/REQ-0023.md) | ↔ | REQ-0024 | [requirements/REQ-0024.md](requirements/REQ-0024.md) | Both define DVI video input/output logic within the FPGA |
| REQ-0027 | [requirements/REQ-0027.md](requirements/REQ-0027.md) | ↔ | HAR-0020 | [requirements/HAR-0020.md](requirements/HAR-0020.md) | Both specify STANAG 3350 / VGA video output via FPGA and encoders |
| REQ-0045 | [requirements/REQ-0045.md](requirements/REQ-0045.md) | ↔ | HAR-0028 | [requirements/HAR-0028.md](requirements/HAR-0028.md) | Both define DVI and ARINC818 channel mapping on XMC secondary connector |

### Memory Architecture & Testing

| Requirement A | File Path | ↔ | Requirement B | File Path | Reason |
|--------------|-----------|---|--------------|-----------|--------|
| HAR-0035 | [requirements/HAR-0035.md](requirements/HAR-0035.md) | ↔ | REQ-0016 | [requirements/REQ-0016.md](requirements/REQ-0016.md) | HAR-0035 defines DDR4 SDRAM specs; REQ-0016 defines FPGA controller IP for DDR4 |
| HAR-0042 | [requirements/HAR-0042.md](requirements/HAR-0042.md) | ↔ | HAR-0035 | [requirements/HAR-0035.md](requirements/HAR-0035.md) | HAR-0042 requires full memory test for the DDR4 defined in HAR-0035 |
| HAR-0043 | [requirements/HAR-0043.md](requirements/HAR-0043.md) | ↔ | HAR-0048 | [requirements/HAR-0048.md](requirements/HAR-0048.md) | HAR-0043 requires memory test for storage flash defined in HAR-0048 |
| HAR-0043 | [requirements/HAR-0043.md](requirements/HAR-0043.md) | ↔ | HAR-0012 | [requirements/HAR-0012.md](requirements/HAR-0012.md) | Flash memory test logic is implemented in the FPGA defined in HAR-0012 |

### Power, Thermal & Environmental

| Requirement A | File Path | ↔ | Requirement B | File Path | Reason |
|--------------|-----------|---|--------------|-----------|--------|
| HAR-0033 | [requirements/HAR-0033.md](requirements/HAR-0033.md) | ↔ | HAR-0034 | [requirements/HAR-0034.md](requirements/HAR-0034.md) | HAR-0033 specifies power dissipation value; HAR-0034 specifies measurement method |
| HAR-0038 | [requirements/HAR-0038.md](requirements/HAR-0038.md) | ↔ | HAR-0035 | [requirements/HAR-0035.md](requirements/HAR-0035.md) | Operating temperature range affects DDR4 memory reliability and operation |
| HAR-0039 | [requirements/HAR-0039.md](requirements/HAR-0039.md) | ↔ | HAR-0034 | [requirements/HAR-0034.md](requirements/HAR-0034.md) | Storage temperature limits impact power component and module component survival |

### Micro-controller & Configuration

| Requirement A | File Path | ↔ | Requirement B | File Path | Reason |
|--------------|-----------|---|--------------|-----------|--------|
| SOF-0014 | [requirements/SOF-0014.md](requirements/SOF-0014.md) | ↔ | HAR-0026 | [requirements/HAR-0026.md](requirements/HAR-0026.md) | SOF-0014 defines GUI configuration of micro-controller peripherals; HAR-0026 defines the MCU hardware |
| HAR-0048 | [requirements/HAR-0048.md](requirements/HAR-0048.md) | ↔ | HAR-0026 | [requirements/HAR-0026.md](requirements/HAR-0026.md) | Storage flash is managed/configured by the micro-controller defined in HAR-0026 |

## Explicit Links Reference

| Source ID | File Path | ↔ | Target ID | File Path | Linked Via |
|-----------|-----------|---|-----------|-----------|------------|
| HAR-0021 | [requirements/HAR-0021.md](requirements/HAR-0021.md) | ↔ | HAR-0008 | [requirements/HAR-0008.md](requirements/HAR-0008.md) | related_ids (source data) |
| HAR-0038 | [requirements/HAR-0038.md](requirements/HAR-0038.md) | ↔ | HAR-0035 | [requirements/HAR-0035.md](requirements/HAR-0035.md) | related_ids (source data) |
| HAR-0039 | [requirements/HAR-0039.md](requirements/HAR-0039.md) | ↔ | HAR-0034 | [requirements/HAR-0034.md](requirements/HAR-0034.md) | related_ids (source data) |
| HAR-0042 | [requirements/HAR-0042.md](requirements/HAR-0042.md) | ↔ | HAR-0008 | [requirements/HAR-0008.md](requirements/HAR-0008.md) | related_ids (source data) |
| HAR-0043 | [requirements/HAR-0043.md](requirements/HAR-0043.md) | ↔ | HAR-0012 | [requirements/HAR-0012.md](requirements/HAR-0012.md) | related_ids (source data) |
| HAR-0043 | [requirements/HAR-0043.md](requirements/HAR-0043.md) | ↔ | HAR-0022 | [requirements/HAR-0022.md](requirements/HAR-0022.md) | related_ids (source data) |
| HAR-0048 | [requirements/HAR-0048.md](requirements/HAR-0048.md) | ↔ | HAR-0026 | [requirements/HAR-0026.md](requirements/HAR-0026.md) | related_ids (source data) |

## Agent Quick Reference

Use this index to load related requirement files together:
- **Same theme group:** Load all requirements in a theme row together for coherent document sections
- **Explicit links:** Always load explicitly linked pairs (from source related_ids)
- **File path format:** requirements/<req_id>.md — always use this format when reading individual requirements