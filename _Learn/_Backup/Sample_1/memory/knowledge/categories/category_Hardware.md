---
category: Hardware
total_requirements: 32
related_categories: [Software, Mechanical, Environmental]
---

# Hardware Requirements

## Summary

This category defines the physical and electrical architecture of the DP-XMC-5049 video converter module, centered around a Xilinx Kintex Ultrascale FPGA. It specifies the integration of high-speed interfaces (PCIe, ARINC 818, DisplayPort, DVI, VGA), memory subsystems (DDR4, SPI NOR Flash), and power delivery systems compliant with VITA 42 standards. The requirements also cover environmental tolerances, mechanical form factors, and testing protocols for validation.

## Requirements by Sub-Category

| Sub-Category | Count |
|-------------|-------|
| Interface | 11 |
| Power | 8 |
| Memory | 5 |
| Environmental | 3 |
| FPGA | 2 |
| Mechanical | 2 |
| Processor | 1 |

## Detailed Requirements

### Interface

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0002 | High | XMC PCIe based video converter module using XILINX Kintex Ultrascale FPGA supporting STANAG3350/RGB/VGA, DVI, ARINC818, PCIe. | [HAR-0002.md](../requirements/HAR-0002.md) |
| HAR-0003 | High | Support DisplayPort video input from secondary XMC Connector translated to 3 TMDS level DP++/DVI outputs using splitter. | [HAR-0003.md](../requirements/HAR-0003.md) |
| HAR-0007 | High | Support high speed PCIe on XMC primary connector for video data; optionally support 3x ARINC 818 Tx/Rx on secondary connector. | [HAR-0007.md](../requirements/HAR-0007.md) |
| HAR-0008 | High | Support 1x single link DVI output via equalizer to XMC secondary or front panel; support RGBHV/VGA/STANAG 3350 analog output. | [HAR-0008.md](../requirements/HAR-0008.md) |
| HAR-0013 | Normal | XMC Primary Connector requirements: 5V/3.3V/3.3V-AUX supply, JTAG, PCIe REFCLK, 1x x8 PCIe Gen 3 link from FPGA MGT bank. | [HAR-0013.md](../requirements/HAR-0013.md) |
| HAR-0020 | High | STANAG 3350/VGA Video: DisplayPort input received on FPGA, sent via Video encoder IC to standard VGA/PAL display. | [HAR-0020.md](../requirements/HAR-0020.md) |
| HAR-0021 | High | PCIe: Standard PCIe enumeration test with standard SBC PCIe root complex. | [HAR-0021.md](../requirements/HAR-0021.md) |
| HAR-0025 | High | ARINC 818: Standard Video data transfer test using external ARINC 818 to DVI conversion module. | [HAR-0025.md](../requirements/HAR-0025.md) |
| HAR-0028 | Normal | XMC Secondary Connector: DVI channels, ARINC818 TX/RX, RGBHV channels, DisplayPort input, optional USB from Micro-controller. | [HAR-0028.md](../requirements/HAR-0028.md) |
| HAR-0044 | High | DP/DP++ Video Input: DisplayPort source video sent out via each DVI channel to a DVI monitor. | [HAR-0044.md](../requirements/HAR-0044.md) |
| HAR-0054 | Normal | USB2.0 support. | [HAR-0054.md](../requirements/HAR-0054.md) |

### Power

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0010 | High | On board clock and power supply generation; powered by 5V, 3.3V, 3.3V-AUX via XMC Connector per VITA 42 standard. | [HAR-0010.md](../requirements/HAR-0010.md) |
| HAR-0029 | Normal | Voltage Module supply rails: +5V, +3.3V, +3.3V-AUX. | [HAR-0029.md](../requirements/HAR-0029.md) |
| HAR-0030 | Normal | Current: 5V @ 2.99 A, 3V @ 3.18 A, 3.3V-AUX @ 0.002 A (TYP). | [HAR-0030.md](../requirements/HAR-0030.md) |
| HAR-0032 | High | Supply current shall be measured by power analysis of module components. | [HAR-0032.md](../requirements/HAR-0032.md) |
| HAR-0033 | Normal | Power Dissipation: 15 W (TYP). | [HAR-0033.md](../requirements/HAR-0033.md) |
| HAR-0034 | High | Power dissipation shall be measured by power analysis of module components. | [HAR-0034.md](../requirements/HAR-0034.md) |
| HAR-0041 | High | All voltages measured by multi-meter; un-sequenced voltages monitored through voltage monitor section. | [HAR-0041.md](../requirements/HAR-0041.md) |
| HAR-0022 | High | Include required test equipment, cables, jigs, emulators, software environment, and programming file for testing. | [HAR-0022.md](../requirements/HAR-0022.md) |

### Memory

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0035 | Normal | SDRAM: 64-bit 4GB DDR4. | [HAR-0035.md](../requirements/HAR-0035.md) |
| HAR-0042 | High | DDR4 full memory test shall be performed. | [HAR-0042.md](../requirements/HAR-0042.md) |
| HAR-0047 | Normal | Configuration Flash Memory: 64MB. | [HAR-0047.md](../requirements/HAR-0047.md) |
| HAR-0048 | Normal | Storage Flash Memory: 256MB. | [HAR-0048.md](../requirements/HAR-0048.md) |
| HAR-0043 | High | Storage Flash Memory: Full memory test and memory read/write performed as per standard procedure. | [HAR-0043.md](../requirements/HAR-0043.md) |

### Environmental

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0038 | Normal | Operating Temperature: -40°C to +71°C (Card Edge). | [HAR-0038.md](../requirements/HAR-0038.md) |
| HAR-0039 | Normal | Storage Temperature: -55°C to +95°C. | [HAR-0039.md](../requirements/HAR-0039.md) |
| HAR-0040 | Normal | Relative Humidity: 95% RH. | [HAR-0040.md](../requirements/HAR-0040.md) |

### FPGA

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0012 | Normal | FPGA: Kintex Ultrascale XCKU035-2FBVA676I, 444,343 logic cells, 16 GTH Transceivers, PCIe Gen3 x8. | [HAR-0012.md](../requirements/HAR-0012.md) |
| HAR-0002 | High | Module Kintex Ultrascale FPGA interfaced with two 32-bit 4GB DDR4 SDRAM controllers and SPI NOR Flash. | [HAR-0002.md](../requirements/HAR-0002.md) |

### Mechanical

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0037 | Normal | Dimension (LxBxH): 143.74×74×13.46 mm. | [HAR-0037.md](../requirements/HAR-0037.md) |
| HAR-0049 | Normal | Weight: <800g. | [HAR-0049.md](../requirements/HAR-0049.md) |

### Processor

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0026 | Normal | Micro-controller: SAM D5x/E5x ATSAMD51G19A, 32-bit Arm Cortex-M4F, 512KB Flash, 192KB SRAM. | [HAR-0026.md](../requirements/HAR-0026.md) |