---
project_id: Sample_1
total_requirements: 54
extraction_date: 2024-05-20
---

# Project Overview — Sample_1

## Summary

This project defines the requirements for the DP-XMC-5049, a VITA 42 compliant Single-Width Mezzanine Card (XMC) designed as a high-performance video converter module. The system is centered around a Xilinx Kintex Ultrascale+ FPGA, providing extensive video processing capabilities including support for STANAG3350, RGB, VGA, DVI, and ARINC818 standards. The architecture emphasizes high-speed data interfaces such as PCIe Gen3 x8 and MIPI, alongside robust memory subsystems and environmental resilience for harsh operating conditions.

## Requirements by Category

| Category | Count | Requirement IDs |
|----------|-------|-----------------|
| Functional | 3 | FUN-0046, FUN-0050, FUN-0052 |
| Hardware | 32 | HAR-0002, HAR-0003, HAR-0007, HAR-0008, HAR-0010, HAR-0012, HAR-0013, HAR-0020, HAR-0021, HAR-0022, HAR-0025, HAR-0026, HAR-0028, HAR-0029, HAR-0030, HAR-0032, HAR-0033, HAR-0034, HAR-0035, HAR-0036, HAR-0037, HAR-0038, HAR-0039, HAR-0040, HAR-0041, HAR-0042, HAR-0043, HAR-0044, HAR-0047, HAR-0048, HAR-0049, HAR-0054 |
| Hardware/FPGA | 3 | REQ-0001, REQ-0011, REQ-0031 |
| Hardware/Interface | 13 | REQ-0004, REQ-0005, REQ-0006, REQ-0009, REQ-0015, REQ-0017, REQ-0018, REQ-0019, REQ-0023, REQ-0024, REQ-0027, REQ-0045, REQ-0051 |
| Hardware/Memory | 1 | REQ-0016 |
| Software | 2 | SOF-0014, SOF-0053 |

## Requirements by Sub-Category

| Sub-Category | Count | Parent Category | Requirement IDs |
|--------------|-------|-----------------|-----------------|
| Application | 2 | Software | SOF-0014, SOF-0053 |
| DDR | 1 | Hardware/Memory | REQ-0016 |
| Environmental | 3 | Hardware | HAR-0038, HAR-0039, HAR-0040 |
| FPGA | 5 | Hardware/FPGA | REQ-0001, HAR-0002, REQ-0011, HAR-0012, REQ-0031 |
| General | 3 | Functional | FUN-0046, FUN-0050, FUN-0052 |
| I2C | 1 | Hardware/Interface | REQ-0018 |
| Interface | 15 | Hardware | HAR-0003, REQ-0004, REQ-0005, HAR-0007, HAR-0008, HAR-0020, HAR-0021, HAR-0022, REQ-0023, REQ-0024, HAR-0025, HAR-0028, HAR-0036, HAR-0044, HAR-0054 |
| MIPI | 3 | Hardware/Interface | REQ-0027, REQ-0045, REQ-0051 |
| Mechanical | 2 | Hardware | HAR-0037, HAR-0049 |
| Memory | 5 | Hardware | HAR-0035, HAR-0042, HAR-0043, HAR-0047, HAR-0048 |
| PCIe | 4 | Hardware/Interface | REQ-0006, REQ-0009, REQ-0015, REQ-0017 |
| Power | 8 | Hardware | HAR-0010, HAR-0013, HAR-0029, HAR-0030, HAR-0032, HAR-0033, HAR-0034, HAR-0041 |
| Processor | 1 | Hardware | HAR-0026 |
| SPI | 1 | Hardware/Interface | REQ-0019 |

## Individual Requirements Summary

| ID | Title | Priority | Category | Sub-Category | Explanation |
|----|-------|----------|----------|--------------|-------------|
| REQ-0001 | Kintex Ultrascale+ FPGA shall support STANAG3350 / RGB / VGA | High | Hardware/FPGA | FPGA | The specified FPGA chip must be capable of handling multiple video and data transmission standards simultaneously. |
| HAR-0002 | DP-XMC-5049 shall be a XMC PCIe based video converter module | High | Hardware | FPGA | The module is a hardware card that converts video signals, built around a specific high-performance FPGA chip. It connects to a carrier board via two specific XMC connector locations and includes dedicated memory components for configuration and data storage. |
| HAR-0003 | The module shall support DisplayPort video input from second | High | Hardware | Interface | The module takes DisplayPort video input from the secondary connector and converts it into three separate DVI or DP++ outputs. This conversion process uses a splitter component, which is managed by its own small flash memory chip. |
| REQ-0004 | The FPGA shall be interfaced with three Video encoder ICs vi | High | Hardware/Interface | Interface | The FPGA sends video data to three Video encoder ICs using an RGB parallel data bus. The FPGA provides the necessary reference clock to these ICs and controls their configuration. The output is routed to the XMC Secondary Connector. |
| REQ-0005 | ARINC 818 Interface: ARINC 818 high speed video protocol sha | High | Hardware/Interface | Interface | The FPGA implements the ARINC 818 high-speed video protocol using its MGT (Multi-Gigabit Transceiver) bank. It handles three ARINC 818 channels for both video input and output. The reference clock for this protocol is supplied from a clock generator to the FPGA MGT bank. |
| REQ-0006 | DP-XMC-5049 shall be a XMC PCIe based video converter module | High | Hardware/Interface | PCIe | The DP-XMC-5049 is a hardware module that converts video signals. It uses the XMC form factor and connects via the PCIe bus. It must support the same set of video and data interfaces as the FPGA. |
| HAR-0007 | The module shall support high speed communication interface | High | Hardware | Interface | The module uses the primary XMC connector for high-speed data transfer via PCIe lines to send or receive raw video data. It also optionally supports ARINC 818 interfaces on the secondary connector, connecting them to the FPGA's high-speed transceiver bank. |
| HAR-0008 | The module shall support 1x single link DVI output via DVI e | High | Hardware | Interface | The module provides multiple analog and digital video outputs. It supports single-link DVI outputs routed through equalizers to either the XMC secondary connector or a front panel connector. It also supports analog video standards (RGBHV/VGA/STANAG 3350) on the XMC secondary connector using a video encoder. |
| REQ-0009 | DP-XMC-5049-HRS-0011 ARINC 818: Three ARINC 818 Transmitter | High | Hardware/Interface | PCIe | The system requires specific ARINC 818 transmitter and receiver channels for high-speed digital video, with defined data rates and optional configurations. |
| HAR-0010 | Module shall support on board clock generation and power sup | High | Hardware | Power | The module generates its own necessary clock and power signals internally. It receives its main power supply from the XMC connector, adhering to a specific industry standard for voltage levels. |
| REQ-0011 | 2.1 Features VITA 42 Compliant XMC Module; Kintex Ultrascale | Normal | Hardware/FPGA | FPGA | This requirement describes a VITA 42 compliant XMC module built around a Kintex Ultrascale series FPGA. It details the module's memory, connectivity, and configurable video/data output capabilities. |
| HAR-0012 | DP-XMC-5049-HRS-002 FPGA • Family: Kintex Ultrascale • Devic | Normal | Hardware | FPGA | This requirement specifies the exact FPGA model and its detailed internal resources, such as logic capacity, memory, and high-speed interfaces. |
| HAR-0013 | DP-XMC-5049-HRS-0017: XMC Primary Connector requirements: 5V | Normal | Hardware | Power | The primary connector on the module requires specific power supplies, a debugging interface, a clock signal, and a high-speed data link from the FPGA. |
| SOF-0014 | Requirement ID: DP-XMC-5049-HRS-003; Requirement: A micro-co | High | Software | Application | A software application with a graphical user interface must be created to run on a micro-controller. This application allows users to configure external hardware components connected via SPI and I2C protocols. The testing for this requirement involves updating the test application using the same USB-based GUI. |
| REQ-0015 | PCIe interface: x8 PCIe interface on FPGA MGT bank; Referenc | High | Hardware/Interface | PCIe | The system requires a high-speed PCIe connection using eight lanes, with its timing signal provided by a dedicated clock generator. |
| REQ-0016 | DDR4/L SDRAM Interface: One 64 bit DDR4 SDRAM controller IP | High | Hardware/Memory | DDR | The FPGA must include a specific memory controller for DDR4 SDRAM, powered by a reference clock from a generator. |
| REQ-0017 | DP-XMC-5049-HRS-0014 PCIe: 1x x8 PCIe Gen 3 link between XMC | Normal | Hardware/Interface | PCIe | There is a PCIe Gen 3 x8 link connecting the XMC Primary Connector to the FPGA's MGT bank. |
| REQ-0018 | The FPGA shall read the temperature sensor via the I2C inter | High | Hardware/Interface | I2C | The FPGA reads temperature data from a sensor using the I2C communication protocol on an IO bank. |
| REQ-0019 | SPI Flash memory interface: FPGA shall implement logic to wr | High | Hardware/Interface | SPI | The FPGA implements logic to read from and write to external SPI Flash memory using the SPI protocol on an IO bank. |
| HAR-0020 | Requirement ID: DP-XMC-5049-HRS-0013; Requirement: STANAG 33 | High | Hardware | Interface | Video data received on the FPGA must be processed by a video encoder and displayed on a standard VGA or PAL monitor. |
| HAR-0021 | Requirement ID: DP-XMC-5049-HRS-0014; Requirement: PCIe; Tes | High | Hardware | Interface | The system's PCIe connection must be verified by performing a standard enumeration test using a standard Single Board Computer. |
| HAR-0022 | This section shall include required test equipment, test cab | High | Hardware | Interface | This section must list all the physical tools, hardware accessories, and software environments needed to perform testing. |
| REQ-0023 | The FPGA shall be interfaced with a maximum of 3 DVI/TMDS vi | High | Hardware/Interface | Interface | The FPGA connection is limited to accepting no more than three DVI or TMDS video signals as inputs. |
| REQ-0024 | DVI Video Output: FPGA shall provide 1x DVI video output int | High | Hardware/Interface | Interface | The FPGA provides one DVI video output signal, which is connected to a DVI equalizer IC to condition the signal. |
| HAR-0025 | Requirement ID: DP-XMC-5049-HRS-0011; Requirement: ARINC 818 | High | Hardware | Interface | The system must successfully transfer video data using the ARINC 818 standard, verified by converting the signal to DVI for testing. |
| HAR-0026 | DP-XMC-5049-HRS-003 Micro-controller • Family: SAM D5x/E5x • | Normal | Hardware | Processor | The system includes a microcontroller based on the Arm Cortex-M4F core with specific memory sizes for program storage and data processing. |
| REQ-0027 | DP-XMC-5049-HRS-0013 STANAG 3350 / VGA: Three STANAG 3350 / | Normal | Hardware/Interface | MIPI | The system provides three STANAG 3350 / VGA / RGBHV / RGB video outputs on the XMC Secondary Connector, with some channels optionally linked to DVI channel 2. |
| HAR-0028 | DP-XMC-5049-HRS-0017: XMC Secondary Connector requirements: | Normal | Hardware | Interface | The secondary connector supports a complex mix of video outputs, data links, and an optional USB connection, including specific color channels for RGBHV signals. |
| HAR-0029 | DP-XMC-5049-HRS-004 Voltage Module supply rails: • +5V • +3. | Normal | Hardware | Power | The module requires three distinct power supply voltages to operate its different internal circuits. |
| HAR-0030 | DP-XMC-5049-HRS-005 Current • 5V @ 2.99 A (TYP) • 3V @ 3.18 | Normal | Hardware | Power | This specifies the typical current draw for each of the power supply rails, indicating how much electrical current the module consumes. |
| REQ-0031 | The Kintex Ultrascale XCKU035 series FPGA shall be used in t | High | Hardware/FPGA | FPGA | The module must use a specific model of FPGA from the Kintex Ultrascale XCKU035 series, ensuring it has enough input/output pins to meet the design's needs. |
| HAR-0032 | Requirement ID: DP-XMC-5049-HRS-005; Requirement: The supply | High | Hardware | Power | The electrical current drawn by the module must be determined by analyzing the power consumption of its individual components. |
| HAR-0033 | DP-XMC-5049-HRS-006 Power Dissipation • 15 W (TYP) | Normal | Hardware | Power | The module dissipates a typical amount of heat power during operation, which is important for thermal management and cooling design. |
| HAR-0034 | DP-XMC-5049-HRS-006 Power dissipation shall be measured by p | High | Hardware | Power | The total heat generated (power dissipation) by the module must be calculated by analyzing the power consumption of its individual components. |
| HAR-0035 | DP-XMC-5049-HRS-007 SDRAM • 64-bit 4GB DDR4 | Normal | Hardware | Memory | The system uses a large capacity DDR4 SDRAM for high-speed data storage and processing. |
| HAR-0036 | DP-XMC-5049-HRS-0019: Supported OS: Linux / Windows (SBC ext | Normal | Hardware | Interface | The module is compatible with both Linux and Windows operating systems, using an external Single Board Computer (SBC) to handle the detection and setup of the PCIe connection. |
| HAR-0037 | DP-XMC-5049-HRS-0021: Dimension (LxBxH): 143.74×74×13.46 mm | Normal | Hardware | Mechanical | The physical size of the module is strictly defined by its length, width, and height. |
| HAR-0038 | DP-XMC-5049-HRS-0015: Operating Temperature: -40°C to +71°C | Normal | Hardware | Environmental | The module is designed to function correctly within a specific temperature range at its connection edge. |
| HAR-0039 | DP-XMC-5049-HRS-0023: Storage Temperature: -55°C to +95°C | Normal | Hardware | Environmental | The module can be stored safely within a wider temperature range than its operating range, without being powered on. |
| HAR-0040 | DP-XMC-5049-HRS-0024: Relative Humidity: 95% RH | Normal | Hardware | Environmental | The module must withstand high levels of moisture without damage. |
| HAR-0041 | DP-XMC-5049-HRS-004: All voltages shall be measured by the m | High | Hardware | Power | All power supply voltages must be checked using a multi-meter. Additionally, any voltages that do not follow a specific startup sequence must be continuously monitored by a dedicated voltage monitoring circuit. |
| HAR-0042 | Requirement ID: DP-XMC-5049-HRS-007; Requirement: DDR4 full | High | Hardware | Memory | A complete test of the DDR4 memory must be executed to ensure it is functioning correctly. |
| HAR-0043 | Requirement ID: DP-XMC-5049-HRS-009; Requirement: Storage Fl | High | Hardware | Memory | The system's flash memory must undergo a complete verification process to ensure data integrity through standard read and write operations. |
| HAR-0044 | Requirement ID: DP-XMC-5049-HRS-0012; Requirement: DP/DP++ V | High | Hardware | Interface | Video input received via DisplayPort must be correctly routed and output through every DVI channel to a monitor for verification. |
| REQ-0045 | DP-XMC-5049-HRS-0010 DVI Video Output: Two single link DVI v | Normal | Hardware/Interface | MIPI | The system provides two single-link DVI video outputs on the XMC Secondary Connector, with specific optional dependencies, plus an optional front-panel DVI output. |
| FUN-0046 | DP-XMC-5049-HRS-0016: One optional USB2.0 interface from Mic | Normal | Functional | General | There is an optional connection using USB 2.0 technology that links the main micro-controller to a secondary connector on the module. |
| HAR-0047 | DP-XMC-5049-HRS-008 Configuration Flash Memory • 64MB | Normal | Hardware | Memory | The module includes a flash memory chip used for storing configuration data or firmware. |
| HAR-0048 | DP-XMC-5049-HRS-009 Storage Flash Memory • 256MB | Normal | Hardware | Memory | The module includes a flash memory chip used for general data storage. |
| HAR-0049 | DP-XMC-5049-HRS-0022: Weight: <800g | Normal | Hardware | Mechanical | The total weight of the module must be less than 800 grams. |
| FUN-0050 | DP-XMC-5049-HRS-001 Type • XMC Module (VITA42) • Single-Widt | Normal | Functional | General | The hardware is a specific type of expansion card that fits into a standard chassis slot. |
| REQ-0051 | DP-XMC-5049-HRS-0012 DP/DP++ Input: One DP/DP++ Input from X | Normal | Hardware/Interface | MIPI | The system must include one DisplayPort or DisplayPort++ input connected to the XMC Secondary Connector. |
| FUN-0052 | This section shall be provided with test setup, interconnect | High | Functional | General | This section must describe how the test setup is arranged, including how components are connected and how equipment links together. |
| SOF-0053 | DP-XMC-5049-HRS-0018: Application GUI via USB | Normal | Software | Application | The application software includes a graphical user interface (GUI) that can be accessed or controlled via a USB connection. |
| HAR-0054 | Requirement ID: DP-XMC-5049-HRS-0016; Requirement: USB2.0; T | Normal | Hardware | Interface | The system must support the USB 2.0 standard for connectivity. |

## Knowledge Files Index

### Requirements
- [REQ-0001.md](requirements/REQ-0001.md) — Kintex Ultrascale+ FPGA shall support STANAG3350 / RGB / VGA
- [HAR-0002.md](requirements/HAR-0002.md) — DP-XMC-5049 shall be a XMC PCIe based video converter module
- [HAR-0003.md](requirements/HAR-0003.md) — The module shall support DisplayPort video input from second
- [REQ-0004.md](requirements/REQ-0004.md) — The FPGA shall be interfaced with three Video encoder ICs vi
- [REQ-0005.md](requirements/REQ-0005.md) — ARINC 818 Interface: ARINC 818 high speed video protocol sha
- [REQ-0006.md](requirements/REQ-0006.md) — DP-XMC-5049 shall be a XMC PCIe based video converter module
- [HAR-0007.md](requirements/HAR-0007.md) — The module shall support high speed communication interface
- [HAR-0008.md](requirements/HAR-0008.md) — The module shall support 1x single link DVI output via DVI e
- [REQ-0009.md](requirements/REQ-0009.md) — DP-XMC-5049-HRS-0011 ARINC 818: Three ARINC 818 Transmitter
- [HAR-0010.md](requirements/HAR-0010.md) — Module shall support on board clock generation and power sup
- [REQ-0011.md](requirements/REQ-0011.md) — 2.1 Features VITA 42 Compliant XMC Module; Kintex Ultrascale
- [HAR-0012.md](requirements/HAR-0012.md) — DP-XMC-5049-HRS-002 FPGA • Family: Kintex Ultrascale • Devic
- [HAR-0013.md](requirements/HAR-0013.md) — DP-XMC-5049-HRS-0017: XMC Primary Connector requirements: 5V
- [SOF-0014.md](requirements/SOF-0014.md) — Requirement ID: DP-XMC-5049-HRS-003; Requirement: A micro-co
- [REQ-0015.md](requirements/REQ-0015.md) — PCIe interface: x8 PCIe interface on FPGA MGT bank; Referenc
- [REQ-0016.md](requirements/REQ-0016.md) — DDR4/L SDRAM Interface: One 64 bit DDR4 SDRAM controller IP
- [REQ-0017.md](requirements/REQ-0017.md) — DP-XMC-5049-HRS-0014 PCIe: 1x x8 PCIe Gen 3 link between XMC
- [REQ-0018.md](requirements/REQ-0018.md) — The FPGA shall read the temperature sensor via the I2C inter
- [REQ-0019.md](requirements/REQ-0019.md) — SPI Flash memory interface: FPGA shall implement logic to wr
- [HAR-0020.md](requirements/HAR-0020.md) — Requirement ID: DP-XMC-5049-HRS-0013; Requirement: STANAG 33
- [HAR-0021.md](requirements/HAR-0021.md) — Requirement ID: DP-XMC-5049-HRS-0014; Requirement: PCIe; Tes
- [HAR-0022.md](requirements/HAR-0022.md) — This section shall include required test equipment, test cab
- [REQ-0023.md](requirements/REQ-0023.md) — The FPGA shall be interfaced with a maximum of 3 DVI/TMDS vi
- [REQ-0024.md](requirements/REQ-0024.md) — DVI Video Output: FPGA shall provide 1x DVI video output int
- [HAR-0025.md](requirements/HAR-0025.md) — Requirement ID: DP-XMC-5049-HRS-0011; Requirement: ARINC 818
- [HAR-0026.md](requirements/HAR-0026.md) — DP-XMC-5049-HRS-003 Micro-controller • Family: SAM D5x/E5x •
- [REQ-0027.md](requirements/REQ-0027.md) — DP-XMC-5049-HRS-0013 STANAG 3350 / VGA: Three STANAG 3350 /
- [HAR-0028.md](requirements/HAR-0028.md) — DP-XMC-5049-HRS-0017: XMC Secondary Connector requirements:
- [HAR-0029.md](requirements/HAR-0029.md) — DP-XMC-5049-HRS-004 Voltage Module supply rails: • +5V • +3.
- [HAR-0030.md](requirements/HAR-0030.md) — DP-XMC-5049-HRS-005 Current • 5V @ 2.99 A (TYP) • 3V @ 3.18
- [REQ-0031.md](requirements/REQ-0031.md) — The Kintex Ultrascale XCKU035 series FPGA shall be used in t
- [HAR-0032.md](requirements/HAR-0032.md) — Requirement ID: DP-XMC-5049-HRS-005; Requirement: The supply
- [HAR-0033.md](requirements/HAR-0033.md) — DP-XMC-5049-HRS-006 Power Dissipation • 15 W (TYP)
- [HAR-0034.md](requirements/HAR-0034.md) — DP-XMC-5049-HRS-006 Power dissipation shall be measured by p
- [HAR-0035.md](requirements/HAR-0035.md) — DP-XMC-5049-HRS-007 SDRAM • 64-bit 4GB DDR4
- [HAR-0036.md](requirements/HAR-0036.md) — DP-XMC-5049-HRS-0019: Supported OS: Linux / Windows (SBC ext
- [HAR-0037.md](requirements/HAR-0037.md) — DP-XMC-5049-HRS-0021: Dimension (LxBxH): 143.74×74×13.46 mm
- [HAR-0038.md](requirements/HAR-0038.md) — DP-XMC-5049-HRS-0015: Operating Temperature: -40°C to +71°C
- [HAR-0039.md](requirements/HAR-0039.md) — DP-XMC-5049-HRS-0023: Storage Temperature: -55°C to +95°C
- [HAR-0040.md](requirements/HAR-0040.md) — DP-XMC-5049-HRS-0024: Relative Humidity: 95% RH
- [HAR-0041.md](requirements/HAR-0041.md) — DP-XMC-5049-HRS-004: All voltages shall be measured by the m
- [HAR-0042.md](requirements/HAR-0042.md) — Requirement ID: DP-XMC-5049-HRS-007; Requirement: DDR4 full
- [HAR-0043.md](requirements/HAR-0043.md) — Requirement ID: DP-XMC-5049-HRS-009; Requirement: Storage Fl
- [HAR-0044.md](requirements/HAR-0044.md) — Requirement ID: DP-XMC-5049-HRS-0012; Requirement: DP/DP++ V
- [REQ-0045.md](requirements/REQ-0045.md) — DP-XMC-5049-HRS-0010 DVI Video Output: Two single link DVI v
- [FUN-0046.md](requirements/FUN-0046.md) — DP-XMC-5049-HRS-0016: One optional USB2.0 interface from Mic
- [HAR-0047.md](requirements/HAR-0047.md) — DP-XMC-5049-HRS-008 Configuration Flash Memory • 64MB
- [HAR-0048.md](requirements/HAR-0048.md) — DP-XMC-5049-HRS-009 Storage Flash Memory • 256MB
- [HAR-0049.md](requirements/HAR-0049.md) — DP-XMC-5049-HRS-0022: Weight: <800g
- [FUN-0050.md](requirements/FUN-0050.md) — DP-XMC-5049-HRS-001 Type • XMC Module (VITA42) • Single-Widt
- [REQ-0051.md](requirements/REQ-0051.md) — DP-XMC-5049-HRS-0012 DP/DP++ Input: One DP/DP++ Input from X
- [FUN-0052.md](requirements/FUN-0052.md) — This section shall be provided with test setup, interconnect
- [SOF-0053.md](requirements/SOF-0053.md) — DP-XMC-5049-HRS-0018: Application GUI via USB
- [HAR-0054.md](requirements/HAR-0054.md) — Requirement ID: DP-XMC-5049-HRS-0016; Requirement: USB2.0; T

### Category Groupings
- [category_Functional.md](categories/category_Functional.md)
- [category_Hardware.md](categories/category_Hardware.md)
- [category_Hardware/FPGA.md](categories/category_Hardware/FPGA.md)
- [category_Hardware/Interface.md](categories/category_Hardware/Interface.md)
- [category_Hardware/Memory.md](categories/category_Hardware/Memory.md)
- [category_Software.md](categories/category_Software.md)

### Sub-Category Groupings
- [subcategory_Application.md](subcategories/subcategory_Application.md)
- [subcategory_DDR.md](subcategories/subcategory_DDR.md)
- [subcategory_Environmental.md](subcategories/subcategory_Environmental.md)
- [subcategory_FPGA.md](subcategories/subcategory_FPGA.md)
- [subcategory_General.md](subcategories/subcategory_General.md)
- [subcategory_I2C.md](subcategories/subcategory_I2C.md)
- [subcategory_Interface.md](subcategories/subcategory_Interface.md)
- [subcategory_MIPI.md](subcategories/subcategory_MIPI.md)
- [subcategory_Mechanical.md](subcategories/subcategory_Mechanical.md)
- [subcategory_Memory.md](subcategories/subcategory_Memory.md)
- [subcategory_PCIe.md](subcategories/subcategory_PCIe.md)
- [subcategory_Power.md](subcategories/subcategory_Power.md)
- [subcategory_Processor.md](subcategories/subcategory_Processor.md)
- [subcategory_SPI.md](subcategories/subcategory_SPI.md)

### Master Index
- [MEMORY.md](../MEMORY.md) — Complete file listing
- [relationships.md](relationships.md) — Inter-requirement dependency graph