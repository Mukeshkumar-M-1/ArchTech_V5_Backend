**DOCUMENT CONTROL**

| Document Information | Details |
|---------------------|---------|
| Document Title | Software Requirements Specification (SRS) |
| Document Reference | DP-OBC-8184-603-SRS |
| Version Number | 0V01 |
| Version Date | 2026-04-30 |
| Prepared By | Data Patterns (India) Limited |
| Document Review By | [REVIEWER] |
| Technical Review By | [TECHNICAL_REVIEWER] |
| Process Review By | [PROCESS_REVIEWER] |
| Approved By | [APPROVER] |

---

**REVISION HISTORY**

| Version | Date | Author | Description of Changes |
|---------|------|--------|----------------------|
| 0V01 | 2026-04-30 | Data Patterns | Initial Version |
| | | | |
| | | | |

---

# 1. INTRODUCTION

## 1.1 Purpose

This Software Requirements Specification (SRS) document describes the requirements involved in the design and development of the test application software for DP-OBC-8184 processor board, that will be used to test and qualify the hardware available on this board. The software shall enable comprehensive validation of all hardware modules including the Processor Module (SBC), Optical Interface Module, Video Processing Module, SATA Storage Module, Power Supply Module, and communication interfaces.

**Table 1.1: Entities Involved in DP-OBC-8184**

| Topics | Details |
|--------------|------------|
| Identification Number | DP-OBC-8184 |
| Title | Rugged Controller for ADFCR/ DP-OBC-8184 |
| Version Number | 0V01 |
| Abbrevation | SRS (Software Requirement Specification) |

---

## 1.2 Scope

Scope of this document is to capture the functional, operation, interface, performance, safety, and qualification related requirement for the software. The software shall be developed for system-specific requirements and for testing the functionality of DP-OBC-8184 Rugged Controller. The test application shall validate all hardware components including the 9th Generation Intel Xeon Processor, 32GB DDR4 memory, 512GB SATA SSD storage, multiple communication interfaces (RS422, RS485, RS232, USB, CAN, Ethernet), optical interfaces, and the NVIDIA Quadro GPU module. The software shall operate on Ubuntu Linux 22.04 and shall support both manual and automated testing modes for hardware qualification and production testing.

---

## 1.3 Definitions, Acronyms, and Abbreviations

**Table 1.2: List of Definitions, Acronyms, and Abbreviations**

| Term/Acronym | Definition |
|--------------|------------|
| SRS | Software Requirements Specification |
| SDD | Software Design Document |
| HRS | Hardware Requirements Specification |
| SyRS | System Requirements Specification |
| ADFCR | Air Defence Fire Control Radar |
| OBC | On Board Computer |
| VPX | Virtual Path Cross-Connect |
| SBC | Single Board Computer |
| DDR4 | Double Data Rate 4 SDRAM |
| SSD | Solid State Drive |
| SATA | Serial Advanced Technology Attachment |
| USB | Universal Serial Bus |
| CAN | Controller Area Network |
| UART | Universal Asynchronous Receiver Transmitter |
| GPIO | General Purpose Input/Output |
| FPGA | Field Programmable Gate Array |
| XMC | Express Mezzanine Card |
| GPU | Graphics Processing Unit |
| UHD | Ultra High Definition |
| DVI | Digital Visual Interface |
| RS232 | Recommended Standard 232 |
| RS422 | Recommended Standard 422 |
| RS485 | Recommended Standard 485 |
| MODBUS | Industrial communication protocol |
| IP | Ingress Protection |
| EMI | Electro Magnetic Interference |
| EMC | Electro Magnetic Compatibility |
| MIL STD | Military Standard |
| JSS | Japanese Industrial Standard |
| BSP | Board Support Package |
| RTOS | Real Time Operating System |
| KC | Key Characteristics |
| IV&V | Independent Verification and Validation |
| MGT | Multi-Gigabit Transceiver |
| PCIe | Peripheral Component Interconnect Express |
| FPDP | Front Panel Data Port |
| FIFO | First In First Out |
| GPIO | General Purpose Input/Output |
| JTAG | Joint Test Action Group |
| MD5 | Message Digest Algorithm 5 |
| ECC | Error Correction Code |
| NAND | Not AND (Flash memory type) |
| SPI | Serial Peripheral Interface |
| QSPI | Quad Serial Peripheral Interface |
| NOR | Not OR (Flash memory type) |

---

## 1.4 References

**Table 1.3: Reference Documents**

| S.NO | Document | Reference | Date |
|------|----------|-----------|------|
| 1 | Hardware Requirements Specification | DP-OBC-8184-600-HRS-0V01 | 2024-03-30 |
| 2 | System Requirements Specification | DP-OBC-8184-603-SyRS-0V01 | 2024-03-30 |
| 3 | System Requirements Specification for Air Defence Fire Control Radar | DP-RDR-8227-600-SYRS-xVyz | - |
| 4 | System Requirements Specification for X Band Search RADAR for ADFCR | DP-RDR-8230-600-SYRS-xVyz | - |
| 5 | System Requirements Specification for Ka Band Track RADAR for ADFCR | DP-RDR-8239-600-SYRS-xVyz | - |

---

## 1.5 Document Overview

**Document Organization:**

This Software Requirements Specification (SRS) document is organized as follows:

- **Section 1 (Introduction):** Provides an overview of the document, including its purpose, scope, definitions, and references.

- **Section 2 (Overall Description):** Describes the product perspective, functions, user classes, operating environment, design constraints, and assumptions.

- **Section 3 (External Interface Requirements):** Details the user, hardware, software, and communications interfaces.

- **Section 4 (Functional Requirements):** Specifies the functional requirements organized by application/module type.

- **Section 5 (Software System Attributes):** Covers performance, safety, security requirements, and software quality attributes.

- **Section 6 (Other Requirements):** Addresses any additional requirements not covered elsewhere.

- **Section 7 (Requirements Traceability):** Maps requirements from customer documents to this SRS.

- **Appendices:** Contains KC mapping and supporting information.

---

# 2. OVERALL DESCRIPTION

## 2.1 Product Perspective

The Rugged Controller for ADFCR (DP-OBC-8184) is a mission-critical subsystem designed for the Air Defence Fire Control Radar system. This controller serves as the central processing and communication hub for both X-band search radar and Ka-band track radar vehicles. The software application developed for this controller shall provide comprehensive hardware validation and testing capabilities for all integrated modules.

The system architecture comprises multiple interconnected modules including the Processor Module (DP-VPX-0750), Optical Interface Module (DP-XMC-5010), Video Processing Module (DP-VPX-5797), SATA Storage Module (DP-VPX-4001), Power Supply Module (DP-PSU-8218), and various interface modules. Each module plays a critical role in the overall system functionality, and the test application shall validate the proper operation of each component.

The Processor Module serves as the main computing engine, featuring a 9th Generation Intel Xeon Processor-E with 6 cores operating at 2.0GHz. It provides 32GB of ECC DDR4 SDRAM for reliable data processing and includes extensive I/O capabilities. The test software shall validate processor functionality, memory integrity, and all peripheral interfaces including USB, Ethernet, and serial ports.

The Optical Interface Module (DP-XMC-5010) handles high-speed data acquisition through Front Panel Data Port (FPDP) interfaces. It supports both optical and copper connections with data rates up to 3.6 Gbps. The module includes 256MB DDR2 SDRAM with FIFO buffering for smooth data flow. Testing shall verify optical communication integrity, data throughput, and protocol compliance.

The Video Processing Module (DP-VPX-5797) provides advanced video processing capabilities through a Kintex-7 FPGA and NVIDIA Quadro GPU with 768 CUDA cores. It supports multiple DVI input channels and provides hardware-accelerated video processing. The test application shall validate video input processing, GPU functionality, and frame buffer operations.

The SATA Storage Module (DP-VPX-4001) provides reliable data storage with a 512GB SATA SSD and includes dual CAN channels for additional I/O expansion. The module features advanced data security measures including end-to-end data path protection. Testing shall verify storage read/write operations, data integrity, and CAN communication functionality.

The Power Supply Module (DP-PSU-8218) converts input voltage (18-32V DC) to multiple regulated outputs (+12V, +5V, +3.3V) required by all system modules. It includes comprehensive protection features and health monitoring. The test software shall validate voltage regulation, protection mechanisms, and power good signaling.

The system operates within a ruggedized enclosure meeting JSS 55555 military standards with IP65 ingress protection and MIL-STD-461F EMI/EMC compliance. The conduction-cooled design ensures reliable operation in harsh environmental conditions ranging from -20°C to +60°C.

**Figure 2.1: DP-OBC-8184 Block Diagram**

---

## 2.2 Product Functions

The Rugged Controller test application provides comprehensive hardware validation and testing capabilities for the DP-OBC-8184 system. The primary functions include system initialization, hardware module discovery, interface testing, functional validation, and comprehensive reporting.

**System Initialization and Configuration:** The application shall perform complete system initialization including hardware detection, resource allocation, and interface configuration. During initialization, the software shall enumerate all connected modules, verify their presence through dedicated identification registers, and configure communication interfaces according to system requirements. The initialization process shall establish communication channels with each hardware module and verify basic functionality before proceeding with detailed testing.

**Hardware Module Testing:** The test application shall validate each hardware module independently and as part of the integrated system. Processor module testing includes CPU functionality verification, memory integrity testing (DDR4 ECC validation), and peripheral interface validation. Storage module testing encompasses SSD read/write operations, data integrity verification, and endurance testing. Power supply validation includes output voltage measurement, current consumption monitoring, and protection circuit verification.

**Interface Communication Testing:** All communication interfaces shall be tested for proper functionality including RS232, RS422, RS485, USB, Ethernet, CAN, and optical interfaces. The testing shall verify data transmission integrity, protocol compliance, and performance characteristics. Loopback tests shall be performed where applicable to validate both transmit and receive functionality.

**Video Processing Validation:** The video processing module testing shall validate DVI input channel functionality, GPU processing capabilities, and frame buffer operations. Tests shall verify proper video signal acquisition, processing pipeline functionality, and output rendering. CUDA core functionality shall be validated through computational tests.

**Environmental and Stress Testing:** The application shall support extended operation testing under various conditions to validate system reliability. This includes long-duration operation tests, thermal cycling validation, and stress testing under maximum load conditions.

**Data Logging and Reporting:** All test operations shall be logged with timestamps and detailed results. The application shall generate comprehensive reports including test coverage, pass/fail status, and detailed measurement data. Action logs shall maintain a complete record of all user operations and system events.

**Figure 2.2: DP-OBC-8184 Functionality Diagram**

---

## 2.3 User Classes and Characteristics

The different users of the DP-OBC-8184 test application are:

- **Design Engineers:** Require comprehensive testing capabilities for design validation and verification. They possess in-depth knowledge of the system architecture and require detailed diagnostic information.

- **Production Test Operators:** Need straightforward test execution capabilities for production line testing. They require basic product knowledge and clear pass/fail indicators with minimal technical detail.

- **Quality Assurance Personnel:** Require detailed test reports and compliance verification. They need access to historical data, trend analysis, and certification documentation.

- **Maintenance Technicians:** Need diagnostic capabilities for field troubleshooting. They require moderate system knowledge and access to module-level testing functions.

All users shall have access to role-specific functionality with appropriate security controls. The application shall support user authentication and authorization to ensure proper access control.

---

## 2.4 Operating Environment

The operating environment details of the software are given in the below table.

**Table 2.1: Operating Environment Specifications**

| Environment Category | Specification |
|---------------------|---------------|
| **Hardware Platform** | Intel Xeon Processor-E 2276ML 2.0GHz (6 Cores), 32GB DDR4 ECC RAM, 512GB SATA SSD, NVIDIA Quadro GPU (768 CUDA cores), VPX backplane with 3U form factor |
| **Operating System** | Ubuntu Linux 22.04 LTS (64-bit) |
| **Software Environment** | Board Support Package (BSP) for Ubuntu 22.04, Linux kernel drivers for all interfaces, CUDA toolkit for GPU processing, Qt framework for GUI |
| **Network Environment** | 2x 10/100/1000 Base-T Ethernet ports, RS422/RS485/RS232 serial interfaces, CAN bus (up to 1 Mbit/s), Optical FPDP interfaces (2.5-3.6 Gbps) |

---

## 2.5 Design and Implementation Constraints

- The application shall run exclusively on Ubuntu Linux 22.04 LTS operating system.
- All hardware interface drivers shall be provided through the Board Support Package (BSP).
- The application shall utilize CUDA-supported GPU for video processing tasks.
- Real-time performance requirements shall be met through Linux kernel optimizations.
- All communication protocols shall comply with military standards (MIL-STD-461F).
- The application shall support both manual and automated test execution modes.
- GUI shall be developed using Qt framework for cross-platform compatibility.
- All test results shall be stored in structured format with timestamp and metadata.
- The application shall support remote operation capabilities through network interfaces.
- Security requirements include user authentication and role-based access control.

---

## 2.6 User Documentation

The product shall include the following documents:

- User Manual - Comprehensive guide for test application operation
- Quick Start Guide - Basic operation instructions for production testing
- API Reference - Technical documentation for integration and customization
- Troubleshooting Guide - Diagnostic procedures and error resolution
- Release Notes - Version-specific information and known issues

---

## 2.7 Assumptions and Dependencies

**Assumptions:**
- Assumption 1: All hardware modules are properly installed and powered - if incorrect, test execution will fail with hardware detection errors.
- Assumption 2: Ubuntu Linux 22.04 BSP is correctly installed with all drivers - if incorrect, hardware interfaces may not function properly.
- Assumption 3: Test equipment (power supply, measurement instruments) is available and calibrated - if incorrect, qualification testing cannot be performed.

**Dependencies:**
- Dependency 1: Board Support Package (BSP) for hardware abstraction - changes may require application recompilation.
- Dependency 2: Linux kernel version compatibility - major version changes may affect driver functionality.
- Dependency 3: CUDA toolkit version for GPU operations - updates may require application modifications.

---

# 3. EXTERNAL INTERFACE REQUIREMENTS

External interface requirements define the connections between the software product and its external environment, including users, hardware, software, and communications interfaces.

## 3.1 User Interfaces

The application software shall interface with the user through Graphical User Interface (GUI). The user shall communicate with the system using mouse and keyboard.

- Application shall consist of standard GUI layouts such as menu bar, action log, standard buttons and other user-friendly controls.
- All controls shall be available with keyboard shortcuts and shall be tab ordered.
- Pop-up message boxes shall be used to provide warning and error messages to intimate the user about failures or serious events.
- Every user action shall be listed in the action log to monitor previous activities.
- Navigation panel shall be used to assist the user for easy transition in accessing each functionality.
- Test results shall be displayed in tabular format with color-coded pass/fail indicators.
- Real-time status indicators shall show system health and test progress.

---

## 3.2 Hardware Interfaces

**Table 3.1: Hardware Interfaces**

| Sl.No. | Device | Interface | Description |
|--------|--------|-----------|-------------|
| 1 | Processor Module (SBC) | PCIe Gen2, VPX Backplane | Main processing unit with Intel Xeon processor, memory, and I/O interfaces |
| 2 | Optical Interface Module | FPDP/Aurora Protocol (Optical/Copper) | High-speed data acquisition with 256MB DDR2 SDRAM FIFO buffer |
| 3 | Video Processing Module | PCIe, DVI, GPU (MXM) | Video signal processing with Kintex-7 FPGA and NVIDIA Quadro GPU |
| 4 | SATA Storage Module | SATA III, PCIe (CAN) | 512GB SSD storage with dual CAN channel interface |
| 5 | Power Supply Module | VPX Power Backplane | DC-DC conversion (18-32V input to +12V/+5V/+3.3V outputs) |
| 6 | EMI Filter Module | VPX Power Input | EMI filtering and input protection |
| 7 | Backplane Module | VPX P1/P2/P3 Connectors | 3U VPX 4-slot backplane with PCIe Gen2 routing |
| 8 | Circular Connector Module | MIL STD 38999 Series III | External field interface connectors |
| 9 | RS422/RS485 Ports | Serial Interface | Communication with IFF, Gimbal controllers, VFD |
| 10 | Ethernet Ports | 10/100/1000 Base-T | Network communication with other subsystems |
| 11 | USB Ports | USB 2.0 | Peripheral connectivity and data transfer |
| 12 | CAN Ports | CAN 2.0 A/B | Controller area network communication |

---

## 3.3 Software Interfaces

The application shall interface with the following software components:

- **Board Support Package (BSP):** Provides hardware abstraction layer for all device drivers.
- **Linux Kernel:** Version 5.15 or later for Ubuntu 22.04 compatibility.
- **CUDA Runtime:** For GPU-accelerated video processing operations.
- **Qt Framework:** Version 5.15 or later for GUI development.
- **Database System:** SQLite for test result storage and retrieval.
- **Communication Libraries:** libserial for serial ports, libusb for USB, socket libraries for Ethernet.

---

## 3.4 Communications Interfaces

**Table 3.2: Communications Interfaces**

| Sl.No. | Interface | Protocol | Description |
|--------|-----------|----------|-------------|
| 1 | RS422 | Differential Serial | Communication with IFF Module, Radar Gimbal Controller |
| 2 | RS485 | MODBUS | Variable frequency driver module communication |
| 3 | RS232 | Serial | Debug and configuration interfaces |
| 4 | Ethernet | TCP/IP | Network communication with other subsystems |
| 5 | FPDP | Aurora Protocol | High-speed optical data transfer (2.5-3.6 Gbps) |
| 6 | CAN | CAN 2.0 A/B | Controller area network (up to 1 Mbit/s) |
| 7 | USB | USB 2.0 | Peripheral connectivity |

---

# 4. FUNCTIONAL REQUIREMENTS

**Table 4.1: DP-OBC-8184 Board Validation Test Requirement IDs**

| Sl.No. | Requirement ID | Requirement Name | Reference Requirement ID |
|--------|----------------|------------------|-------------------------|
| 1 | DP_OBC_8184_HOST_01 | Host Application | DP-OBC-8184-600-SyRS-SDG-002 |
| 2 | DP_OBC_8184_TARGET_02 | Target Application | DP-OBC-8184-600-SyRS-SDG-002 |
| 3 | DP_OBC_8184_SBC_03 | SBC Processor Module Test | Derived |
| 4 | DP_OBC_8184_STOR_04 | Storage Module Test | Derived |
| 5 | DP_OBC_8184_VIDEO_05 | Video Processing Test | Derived |
| 6 | DP_OBC_8184_PWR_06 | Power Supply Test | Derived |
| 7 | DP_OBC_8184_INT_07 | Interface Test | DP-OBC-8184-600-SyRS-EXT-001 |
| 8 | DP_OBC_8184_OPT_08 | Optical Interface Test | DP-OBC-8184-600-SyRS-EXT-002 |

---

## 4.1 Host Application

**Description:**
The host application is a GUI application that runs on the test PC/server for controlling hardware validation, receiving test data, and managing test operations.

**Table 4.1: Host Application Test Requirement**

| Sl.No | Requirement ID | Requirement Name |
|-------|----------------|------------------|
| 1 | DP_OBC_8184_HOST_01 | Host Application |

**Table 4.2: Host Application Test Sub Requirements**

| Sl.No | Sub Requirement ID | Requirement Name |
|-------|-------------------|------------------|
| 1 | DP_OBC_8184_HOST_USR_AUTH_01_01 | User Authentication |
| 2 | DP_OBC_8184_HOST_INIT_01_02 | Initialization |
| 3 | DP_OBC_8184_HOST_USR_MGMT_01_03 | User Management |
| 4 | DP_OBC_8184_HOST_TEST_EXEC_01_04 | Test Execution |
| 5 | DP_OBC_8184_HOST_REPORT_01_05 | Report Generation |
| 6 | DP_OBC_8184_HOST_LOG_01_06 | Action Logging |

---

### 4.1.1 User Authentication

**Description:**
The user authentication module shall ensure that only authorized users are allowed to access the software. The module shall collect the user name and password from the user. Then it shall evaluate the user name and password entered by the user and allows the user to proceed if both are valid. Any invalid input shall lead to the display of an error message and prompt for the user to re-enter the details.

**Table 4.3: User Authentication**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_HOST_USR_AUTH_01_01 | **Description:** The system shall authenticate users before granting access to test functions. Invalid login attempts shall be logged and limited to prevent unauthorized access. |

---

### 4.1.2 Initialization

**Description:**
This module shall ensure that the initialization of communication interfaces between host and target components is established successfully. This module shall enable or disable the connection between host application and target hardware through device drivers based on software control.

**Table 4.4: Initialization**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_HOST_INIT_01_02 | **Description:** The initialization module shall detect all hardware modules, configure communication interfaces, and verify system readiness before test execution. |

---

### 4.1.3 User Management

**Description:**
This module shall provide an option to change the password for the user name and manage user access levels. Different user classes shall have appropriate access to test functions based on their role.

**Table 4.5: User Management**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_HOST_USR_MGMT_01_03 | **Description:** User management shall support multiple access levels including Administrator, Engineer, Operator, and Viewer with appropriate permissions. |

---

### 4.1.4 Test Execution

**Description:**
The test execution module shall control the running of all hardware validation tests. Users shall be able to select individual tests or run complete test suites in manual or automatic mode.

**Table 4.6: Test Execution**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_HOST_TEST_EXEC_01_04 | **Description:** Test execution shall support manual selection, sequential execution, and automated test sequences with configurable parameters. |

---

### 4.1.5 Report Generation

**Description:**
The report generation module shall create comprehensive test reports including test coverage, results, and measurement data. Reports shall be exportable in multiple formats.

**Table 4.7: Report Generation**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_HOST_REPORT_01_05 | **Description:** Reports shall include test summary, detailed results, timestamps, operator information, and be exportable as PDF, CSV, and XML formats. |

---

### 4.1.6 Action Logging

**Description:**
The action logging module shall record all user operations and system events for audit and troubleshooting purposes.

**Table 4.8: Action Logging**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_HOST_LOG_01_06 | **Description:** All user actions, test events, errors, and system status changes shall be logged with timestamps and stored for historical analysis. |

---

## 4.2 Target Application

**Description:**
The target application runs in the SBC/Processing Unit which accesses and controls FPGA/Processor devices in the DP-OBC-8184 module as master/controller.

**Table 4.9: Target Application Test Requirement**

| Sl.No | Requirement ID | Requirement Description |
|-------|----------------|------------------------|
| 1 | DP_OBC_8184_TARGET_02 | Target Application |

**Table 4.10: Target Application Test Sub Requirements**

| Sl.No | Sub Requirement ID | Requirement Description |
|-------|-------------------|------------------------|
| 1 | DP_OBC_8184_TARGET_BRD_DETAILS_02_01 | Get Board Details |
| 2 | DP_OBC_8184_TARGET_SBC_TEST_02_02 | SBC Processor Test |
| 3 | DP_OBC_8184_TARGET_DDR_02_03 | DDR Memory Test |
| 4 | DP_OBC_8184_TARGET_STORAGE_02_04 | Storage Test |
| 5 | DP_OBC_8184_TARGET_TEMP_02_05 | Temperature Test |
| 6 | DP_OBC_8184_TARGET_INT_02_06 | Interface Test |
| 7 | DP_OBC_8184_TARGET_VIDEO_02_07 | Video Processing Test |
| 8 | DP_OBC_8184_TARGET_OPT_02_08 | Optical Interface Test |

---

### 4.2.1 Get Board Details

**Description:**
The DP-OBC-8184 has read-only registers for reading board details such as board ID, board version, and type ID. On selecting this test, interface read operations shall be performed on these registers and displayed in the console.

**Table 4.11: Get Board Details**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_TARGET_BRD_DETAILS_02_01 | **Description:** The system shall read and display board identification information including board ID, version number, manufacturer, and hardware revision. |

---

### 4.2.2 SBC Processor Test

**Description:**
This test shall validate the Intel Xeon Processor functionality including CPU operation, instruction execution, and performance characteristics.

**Table 4.12: SBC Processor Test**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_TARGET_SBC_TEST_02_02 | **Description:** Processor testing shall verify core functionality, cache operation, and instruction set compliance through computational tests. |

---

### 4.2.3 DDR Memory Test

**Description:**
The DDR4 memory test shall validate the 32GB ECC SDRAM for data integrity and reliability.

**Table 4.13: DDR Memory Test**

| Sl.No | Requirement ID | Requirement Description |
|-------|----------------|------------------------|
| 1 | DP_OBC_8184_TARGET_DDR_02_03 | DDR Memory Test |

**Table 4.14: DDR Memory Test Sub Requirements**

| Sl.No | Sub Requirement ID | Requirement Description |
|-------|-------------------|------------------------|
| 1 | DP_OBC_8184_TARGET_DDR_FULL_02_03_01 | DDR Full Memory Test |
| 2 | DP_OBC_8184_TARGET_DDR_DATA_02_03_02 | DDR Data Bus Test |
| 3 | DP_OBC_8184_TARGET_DDR_ADDR_02_03_03 | DDR Address Bus Test |
| 4 | DP_OBC_8184_TARGET_DDR_ECC_02_03_04 | DDR ECC Validation |

---

#### 4.2.3.1 DDR Full Memory Test

**Description:**
The DP-OBC-8184 DDR full memory test shall be performed by writing and reading predefined pattern data and anti-pattern data in each location of all memory banks.

**Table 4.15: DDR Full Memory Test**

| Sub Requirement ID | Requirement Description |
|-------------------|------------------------|
| DP_OBC_8184_TARGET_DDR_FULL_02_03_01 | **Description:** Full memory test shall write and verify multiple patterns (0x00, 0xFF, 0xAA, 0x55, walking 1/0) across all 32GB of DDR4 memory. |

---

#### 4.2.3.2 DDR Data Bus Test

**Description:**
This test shall validate the 64-bit data lines in the DDR memory by performing walking 1's and walking 0's tests.

**Table 4.16: DDR Data Bus Test**

| Sub Requirement ID | Requirement Description |
|-------------------|------------------------|
| DP_OBC_8184_TARGET_DDR_DATA_02_03_02 | **Description:** Data bus testing shall verify each data bit line through walking pattern tests to detect stuck-at or shorted lines. |

---

#### 4.2.3.3 DDR Address Bus Test

**Description:**
This test shall validate the address lines in the DDR memory by writing known pattern and anti-pattern data to verify address decoding.

**Table 4.17: DDR Address Bus Test**

| Sub Requirement ID | Requirement Description |
|-------------------|------------------------|
| DP_OBC_8184_TARGET_DDR_ADDR_02_03_03 | **Description:** Address bus testing shall verify each address line through pattern tests to ensure proper memory location addressing. |

---

#### 4.2.3.4 DDR ECC Validation

**Description:**
This test shall validate the Error Correction Code functionality of the DDR4 memory system.

**Table 4.18: DDR ECC Validation**

| Sub Requirement ID | Requirement Description |
|-------------------|------------------------|
| DP_OBC_8184_TARGET_DDR_ECC_02_03_04 | **Description:** ECC validation shall verify single-bit error correction and multi-bit error detection capabilities of the memory system. |

---

### 4.2.4 Storage Test

**Description:**
The SATA SSD storage module test shall validate read/write operations, data integrity, and storage functionality.

**Table 4.19: Storage Test Requirement**

| Sl.No | Requirement ID | Requirement Description |
|-------|----------------|------------------------|
| 1 | DP_OBC_8184_TARGET_STORAGE_02_04 | Storage Test |

**Table 4.20: Storage Test Sub Requirements**

| Sl.No | Sub Requirement ID | Requirement Description |
|-------|-------------------|------------------------|
| 1 | DP_OBC_8184_TARGET_STOR_READ_02_04_01 | SSD Read Test |
| 2 | DP_OBC_8184_TARGET_STOR_WRITE_02_04_02 | SSD Write Test |
| 3 | DP_OBC_8184_TARGET_STOR_INTEG_02_04_03 | Data Integrity Test |
| 4 | DP_OBC_8184_TARGET_STOR_PERF_02_04_04 | Performance Test |

---

### 4.2.5 Temperature Test

**Description:**
The temperature monitoring test shall validate thermal sensors and health monitoring functionality.

**Table 4.21: Temperature Test Requirement**

| Sl.No | Requirement ID | Requirement Description |
|-------|----------------|------------------------|
| 1 | DP_OBC_8184_TARGET_TEMP_02_05 | Temperature Test |

**Table 4.22: Temperature Test Sub Requirements**

| Sl.No | Sub Requirement ID | Requirement Description |
|-------|-------------------|------------------------|
| 1 | DP_OBC_8184_TARGET_TEMP_LOCAL_02_05_01 | Read Local Temperature |
| 2 | DP_OBC_8184_TARGET_TEMP_REMOTE_02_05_02 | Read Remote Temperature |

---

#### 4.2.5.1 Local Temperature Read

**Description:**
This test case shall be selected for reading local temperature value from the dedicated register through the system management interface.

**Table 4.23: Local Temperature Read Test**

| Sub Requirement ID | Requirement Description |
|-------------------|------------------------|
| DP_OBC_8184_TARGET_TEMP_LOCAL_02_05_01 | **Description:** Local temperature reading shall monitor the SBC processor and power supply thermal sensors. |

---

#### 4.2.5.2 Remote Temperature Read

**Description:**
This test case shall be selected for reading remote temperature values from distributed thermal sensors across the system.

**Table 4.24: Remote Temperature Read Test**

| Sub Requirement ID | Requirement Description |
|-------------------|------------------------|
| DP_OBC_8184_TARGET_TEMP_REMOTE_02_05_02 | **Description:** Remote temperature reading shall monitor thermal sensors on video processing module, storage module, and other components. |

---

### 4.2.6 Interface Test

**Description:**
The interface test shall validate all communication ports including RS232, RS422, RS485, USB, Ethernet, and CAN interfaces.

**Table 4.25: Interface Test Requirement**

| Sl.No | Requirement ID | Requirement Description |
|-------|----------------|------------------------|
| 1 | DP_OBC_8184_TARGET_INT_02_06 | Interface Test |

**Table 4.26: Interface Test Sub Requirements**

| Sl.No | Sub Requirement ID | Requirement Description |
|-------|-------------------|------------------------|
| 1 | DP_OBC_8184_TARGET_INT_RS232_02_06_01 | RS232 Test |
| 2 | DP_OBC_8184_TARGET_INT_RS422_02_06_02 | RS422 Test |
| 3 | DP_OBC_8184_TARGET_INT_RS485_02_06_03 | RS485 Test |
| 4 | DP_OBC_8184_TARGET_INT_USB_02_06_04 | USB Test |
| 5 | DP_OBC_8184_TARGET_INT_ETH_02_06_05 | Ethernet Test |
| 6 | DP_OBC_8184_TARGET_INT_CAN_02_06_06 | CAN Test |

---

### 4.2.7 Video Processing Test

**Description:**
The video processing module test shall validate DVI inputs, GPU functionality, and video processing capabilities.

**Table 4.27: Video Processing Test**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_TARGET_VIDEO_02_07 | **Description:** Video testing shall validate all 4 DVI input channels, GPU CUDA cores, frame buffer operations, and video processing pipeline functionality. |

---

### 4.2.8 Optical Interface Test

**Description:**
The optical interface test shall validate the FPDP module functionality including optical transceivers and high-speed data transfer.

**Table 4.28: Optical Interface Test**

| Requirement ID | Requirement Description |
|----------------|------------------------|
| DP_OBC_8184_TARGET_OPT_02_08 | **Description:** Optical interface testing shall verify FPDP protocol operation, data throughput, and optical link integrity for both transmit and receive paths. |

---

# 5. SOFTWARE SYSTEM ATTRIBUTES

Software system attributes define the quality characteristics and non-functional requirements for the software product.

## 5.1 Performance Requirements

- Both the host and target application shall run simultaneously. After sending the command to the target hardware, the host shall wait for the response from the target and then display the test status in GUI.
- All test plans shall be carried out only if all hardware modules are present in the system.
- Auto Mode test report and action logging shall be done up to the last executed point if the system hangs/closes abnormally.
- Memory test shall complete within specified time limits based on memory size.
- Interface throughput shall meet minimum data rate requirements (Ethernet ≥ 100 Mbps, FPDP ≥ 2.5 Gbps).
- Test execution shall provide real-time status updates with latency less than 1 second.
- Report generation shall complete within 30 seconds for full test suite results.

---

## 5.2 Safety Requirements

**Safety Requirements Implementation:**

- **System integrity protection:** The application shall prevent unauthorized modifications to test configurations and results.
- **Data loss prevention:** All test results shall be automatically saved at regular intervals and upon test completion.
- **Recovery procedures:** The application shall support resume-from-checkpoint for interrupted test sequences.
- **Fail-safe operations:** Hardware interfaces shall be safely disabled on application crash or system error.
- **Emergency shutdown procedures:** The application shall provide controlled shutdown capability to prevent hardware damage.

---

## 5.3 Security Requirements

**Security Requirements:**

- **Authentication mechanisms:** User login with username/password authentication shall be required for application access.
- **Authorization controls:** Role-based access control shall limit functionality based on user class.
- **Data encryption standards:** Sensitive data shall be encrypted at rest and in transit.
- **Audit logging requirements:** All user actions and system events shall be logged for audit purposes.
- **Network security measures:** Network communications shall use secure protocols where applicable.
- **Data privacy protections:** Test results shall be protected from unauthorized access or modification.

---

## 5.4 Software Quality Attributes

The application software quality attributes, including maintainability and reusability details, are dealt in this section.

### 5.4.1 Maintainability

The software shall be maintained with version details and program checksum. The modular architecture shall enable easy updates to individual test modules without affecting overall system functionality. Code shall follow DP coding guidelines with comprehensive Doxygen documentation.

### 5.4.2 Reusability

Files generated by the test application software shall be timestamped with date for future references. Test modules shall be designed for reuse across different hardware configurations. Common functionality shall be implemented as reusable libraries.

---

## 5.5 Business Rules

- Test results shall be immutable once finalized and signed off.
- Production testing shall require operator authentication and test session logging.
- Quality assurance personnel shall have authority to approve/reject test results.
- Design engineers shall have access to diagnostic and debug functionality.
- Test configurations shall be version-controlled and traceable.

---

# 6. OTHER REQUIREMENTS

The test application shall support future expansion for additional hardware modules and test capabilities. The architecture shall accommodate new interface types and testing protocols without major redesign.

---

# 7. REQUIREMENTS TRACEABILITY

Requirements traceability provides a systematic method for tracing requirements through all stages of the development lifecycle, ensuring that all requirements are implemented and verified.

**Table 7.1: Requirements Traceability Matrix**

| Requirement ID in SRS | Section / Section ID in SyRS |
|----------------------|------------------------------|
| DP_OBC_8184_HOST_01 | 3.2 Software Requirements Specification |
| DP_OBC_8184_TARGET_02 | 3.2 Software Requirements Specification |
| DP_OBC_8184_SBC_03 | 4.2 Processor Module (SBC) Specifications |
| DP_OBC_8184_STOR_04 | 4.5 Storage and CAN IO Module Specifications |
| DP_OBC_8184_VIDEO_05 | 4.3 Video Processing Module Specifications |
| DP_OBC_8184_PWR_06 | 4.1 DC-DC Converter Specifications |
| DP_OBC_8184_INT_07 | 3.3 External Interface Requirements Specification |
| DP_OBC_8184_OPT_08 | 3.3 External Interface Requirements Specification |
| DP_OBC_8184_HOST_INIT_01_02 | 3.2 Software Requirements Specification |
| DP_OBC_8184_TARGET_DDR_02_03 | 4.2 Processor Module (SBC) Specifications |
| DP_OBC_8184_TARGET_STORAGE_02_04 | 4.5 Storage and CAN IO Module Specifications |

---

# APPENDIX A: MAPPING KC

Not Applicable (NA)

---

# APPENDIX B: SUPPORTING INFORMATION

**Test Setup Requirements:**

- 18-32V DC Power Supply
- Test PC with Ubuntu Linux 22.04
- USB to RS232/RS422 isolated interface board (DP-SPL-4258-300)
- Test JIG for hardware connectivity
- Measurement instruments for validation testing

---
