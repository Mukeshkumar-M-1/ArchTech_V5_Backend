> \[!IMPORTANT\]
>
> - {{Document-Name}} → Ask to user
> - {{Project-Version}} → Ask to user

**{{Document-Name}} For {{Project-Version}}**

**DOCUMENT CONTROL**

> \[!IMPORTANT\]
>
> - Document Title → Use {{Document-Name}} for {{Project-Version}}
> - Document Reference → {{Project-Board-ID}}-{{FG-Version}}-{{Product-Version}}-{{Type-ID}}-SRS-{{Document-Version}}
> - {{Project-Board-ID}} → Ask to user
> - {{FG-Version}} → Ask to user
> - {{Product-Version}} → Ask to user
> - {{Type-ID}} → Ask to user
> - {{Document-Version}} → Ask to user
> - Version Number → use {{Document-Version}}
> - Version Date → user Current Date for {{Document-Date}}
> - {{Author-Name}} → Ask to user
> - {{Document-Reviewer-Name}} → Ask to user
> - {{Technical-Reviewer-Name}} → Ask to user
> - {{Process-Reviewer-Name}} → Ask to user

| Document Information | Details |
| --- | --- |
| Document Title | {{Document-Name}} for {{Project-Version}} |
| Document Reference | {{Project-Board-ID}}-{{FG-Version}}-{{Product-Version}}-{{Type-ID}}-SRS-{{Document-Version}} |
| Version Number | {{Document-Version}} |
| Version Date | {{Document-Date}} |
| Prepared By | Name: {{Author-Name}} |
| Document Review By | Name: {{Document-Reviewer-Name}} |
| Technical Review By | Name: {{Technical-Reviewer-Name}} |
| Process Review By | Name: {{Process-Reviewer-Name}} |
| Approved By | Name: Design Review Board |

---

**REVISION HISTORY**

> \[!IMPORTANT\]
>
> - {{Document-version}} → use the Project Document version
> - {{Document-Date}} → use the Project Document Date
> - {{Author-Name}} → use the Project Author Name
> - Section Changed → Update the sections based on changes
> - Description of changes → update the changes description

| S.No | Version | Date | Author | Section Changed | Description of Changes |
| --- | --- | --- | --- | --- | --- |
| 1. | {{Document-version}} | {{Document-Date}} | {{Author-Name}} | \- | Initial version |
| … |   |   |   |   |   |

---

# 1. INTRODUCTION

## 1.1 Purpose

> \[!IMPORTANT\]
>
> - Description → Make it as a Paragraph
>
> > \[!CAUTION\]
> >
> > Example → The purpose of this document is to provide the detailed description of the SRS for the development of test application software for &lt; DP-XMC-5049 → replace with the current {{Project-Board-ID}} &gt;. The intended audience for this SRS is Design Review Board (DRB). The expected users of this document are the internal QAC (Quality Assurance and Control) department, HDD (Hardware Design and Development) department and SDG (Software Design Group) department. It aids the designer to test and qualify the hardware through the test software.

**Table 1.1: Entities Involved in Test Application software**

> \[!IMPORTANT\]
>
> - Identification Number→ use {{Project-Board-ID}}-{{FG-Version}}-{{Product-Version}}-{{Type-ID}}-SRS-{{Document-Version}}
> - Title → use {{Document-Name}} for {{Project-Version}}
> - Version Number → use {{Document-Version}}

| Topics | Details |
| --- | --- |
| Identification Number | {{Project-Board-ID}}-{{FG-Version}}-{{Product-Version}}-{{Type-ID}}-SRS-{{Document-Version}} |
| Title | {{Document-Name}} for {{Project-Version}} |
| Version Number | {{Document-Version}} |
| Abbrevation | SRS (Software Requirement Specification) |

---

## 1.2 Scope

> \[!IMPORTANT\]
>
> - Description → Make it as a Paragraph
>
> > \[!CAUTION\]
> >
> > Example → The scope of this document is to bring out all the functional and non-functional software requirements for test application software to qualify &lt; DP-XMC-5049 → replace with the current {{Project-Board-ID}} &gt; hardware. The scope of this software is only to qualify the &lt; DP-XMC-5049 → replace with the current {{Project-Board-ID}} &gt; hardware using the test setup.\*

---

## 1.3 Definitions, Acronyms, and Abbreviations

**Table 1.2: List of Definitions, Acronyms, and Abbreviations**

> \[!IMPORTANT\]
>
> - Term/Acronym → Abbreviation Terms used in the documents
> - Definition → Acronyms Definition
>
> > \[!CAUTION\]
> >
> > All the Acronyms are order in alphabetic ordered
> >
> > Example :
> >
> > - ARINC818 → Aeronautical Radio Incorporated
> > - DVI → Digital Visual Interface
> > - DDR4 → Double Data Rate
> > - FPGA → Field Programmable Gate Array
> > - GPIO → General Purpose Input/Output
> > - I2C → Inter-Integrated Circuit
> > - UART → Universal Asynchronous Receiver Transmitter

| Term/Acronym | Definition |
| --- | --- |
|   |   |

---

## 1.4 References

**Table 1.3: Internal Documents**

> \[!IMPORTANT\]
>
> - [S.No](http://s.no) → Refers the serial no of the row in the table
> - Document Type → Refer example
>
> > \[!CAUTION\]
> >
> > Document Type : HRS, SyRS
> >
> > Example:
> >
> > - HRS → Hardware Requirements Specification
> > - SyRS → System Requirements Specification
>
> - Reference → Refer example
>
> > \[!CAUTION\]
> >
> > Reference : DP-XMC-5049-000-HRS-0V04
> >
> > Example :
> >
> > - HRS → DP-XMC-5049-000-HRS-0V04
>
> - Date → Refers the reference document Date

| S.No | Document | Reference | Date |
| --- | --- | --- | --- |
|   |   |   |   |

---

## 1.5 Document Overview

> \[!IMPORTANT\]
>
> Don’t change this section.

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

> \[!NOTE\]\
> Describe as a paragraph and also use sub-paragraph - (Detailed)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > DP-XMC-5049 shall be a XMC PCIe based video converter module using XILINX Kintex Ultrascale FPGA Supporting STANAG3350 / RGB / VGA, DVI, ARINC818 and PCIe Interfaces. It is a Single-Width Mezzanine Card with the primary XMC connector occupying connector location P15 and secondary XMC connector occupying connector location P16. Module Kintex Ultrascale FPGA is interfaced with two 32-bit 4GB DDR4 SDRAM controllers, 64MB SPI NOR configuration Flash & 256MB SPI NOR storage flash.
> >
> > The module supports DisplayPort video input from secondary XMC Connector which are electrically translated to the 3 no.s of TMDS level DP++/DVI outputs using DP to DP++/DVI splitter. The DP++ Video splitter shall be interfaced with a 2MB SPI NOR Flash.
> >
> > The module supports high speed communication interface such as PCIe on XMC primary connector for video raw data reception / transmission. The XMC Primary connector interfaces x8 PCIe lines from the carrier module. Module shall optionally support 3x ARINC 818 Transmitter(Tx) & 3x ARINC 818 Receiver(Rx) interfaces from the secondary XMC connector to the MGT bank of FPGA.
> >
> > The module support 1x single link DVI output via DVI equalizer interfaced from either FPGA or DP to DVI splitter to XMC secondary connector. The module shall additionally support 1x single link DVI output from DP to DVI splitter interfaced to the DVI Connector on the Front panel via DVI equalizer. Module shall also support 1x DVI output from DP to DVI splitter interfaced to the XMC secondary connector on the Front panel via DVI equalizer. Module shall support RGBHV / VGA / STANAG 3350 analog video standard output on XMC Secondary connector using Video encoder with recommended front end.
> >
> > Note: ARINC818, DVI & RGBHV/VGA are having FG mount options. Refer block diagram Figure 2.1 & FG configuration sheet for more details.
> >
> > \
> > Module shall support on board clock generation & power supply generation as per design requirements. Module shall be powered by 5V,3.3V & 3.3V-AUX via XMC Connector as per VITA 42 standard.

**Figure 2.1: Block Diagram**

> \[!NOTE\]
>
> Use NA

---

## 2.2 Product Functions

> \[!NOTE\]
>
> Describe as a paragraph and also use sub-paragraph - (Detailed)
>
> > \[!CAUTION\]
> >
> > Example: \
> > The DP-XMC-5049 module shall receive video through ARINC-818 RX channels and transmit processed video through ARINC-818 TX channels from the FPGA. The module shall transmit analog video in STANAG 3350B format through video encoder chips which is processed and transmitted by FPGA
> >
> > The module has a KTM5030 chip as 1:3 video splitter for transmitting digital video which is displayed through DVI ports and a micro-HDMI connector which will be displayed in a monitor. Configuring the KTM5030, EEPROM and DVI re-timer chips from on-board ARM based MCU(ATSAMD51) through I2C channels. EDID data written in EEPROM from MCU is read by KTM5030 as I2C master. The MCU shall be interfaced with host application(GUI) through USB for command, control and communication. The MCU has the provision to communicate with FPGA through QSPI.
> >
> > The module has temperature sensor for monitoring temperature to protect the modules from high or low temperature.

---

## 2.3 User Classes and Characteristics

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example: \
> > The different users of DP-XMC-5049 test application area Data patterns – SDG, HDD, production, QA team. The users are expected to test the product functionality of module.

---

## 2.4 Operating Environment

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The DP-XMC-5049 module testing has three software modules such as target application (DPXMC-5049), host application (Test PC) and firmware applications (ATSAMD51). The development and operating environment of each software modules are detailed in the below sections.

### 2.4.1 Target Application

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The target application shall be executed in DP-VPX-0750 for accessing DP-XMC-5049 FPGA. The development and environment of target application are detailed below.

**Table 2.1: Development Environment for Target Application**

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Parameter → Refers the Example
>
> > \[!CAUTION\]
> >
> > Parameter → Example :
> >
> > - OS
> > - Kernel
> > - Processor Architecture
> > - Compiler
> > - Programming Language
> > - RAM
> > - SATA NAND
>
> - Size / Details → Refer the Example
>
> > \[!CAUTION\]
> >
> > Size / Details → Example :
> >
> > - Fedora 22 Linux
> > - 4.0.4-301.fc22.x86_64
> > - x86_64
> > - GCC
> > - C Language
> > - 32 GB DDR4
> > - 64 GB

| S.NO | Parameter | Size / Details |
| --- | --- | --- |
|   |   |   |
|   |   |   |

**Table 2.2: Operating Environment for Target Application**

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Parameter → Refers the Example
>
> > \[!CAUTION\]
> >
> > Parameter → Example :
> >
> > - OS
> > - Kernel
> > - Processor Architecture
> > - Compiler
> > - Programming Language
> > - RAM
> > - SATA NAND
>
> - Size / Details → Refer the Example
>
> > \[!CAUTION\]
> >
> > Size / Details → Example :
> >
> > - Fedora 22 Linux
> > - 4.0.4-301.fc22.x86_64
> > - x86_64
> > - GCC
> > - C Language
> > - 32 GB DDR4
> > - 64 GB

| [S.No](http://S.NO) | Parameter | Size / Details |
| --- | --- | --- |
|   |   |   |
|   |   |   |

### 2.4.2 Host Application

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > It is a GUI based application shall be executed in test PC for establishing USB communication with MCU for command processing.

**Table 2.3: Development Environment for Host Application**

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Parameter → Refers the Example
>
> > \[!CAUTION\]
> >
> > Parameter → Example :
> >
> > - OS
> > - Processor Architecture
> > - Programming Language
> > - IDE
>
> - Size / Details → Refer the Example
>
> > \[!CAUTION\]
> >
> > Size / Details → Example :
> >
> > - Windows 10
> > - x86
> > - C / C++ Language
> > - QT 5.14

| [S.No](http://S.NO) | Parameter | Size / Details |
| --- | --- | --- |
|   |   |   |
|   |   |   |

**Table 2.4: Operating Environment for Host Application**

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Parameter → Refers the Example
>
> > \[!CAUTION\]
> >
> > Parameter → Example :
> >
> > - OS
> > - Processor Architecture
> > - Programming Language
> > - IDE
>
> - Size / Details → Refer the Example
>
> > \[!CAUTION\]
> >
> > Size / Details → Example :
> >
> > - Windows 10
> > - x86
> > - C / C++ Language
> > - QT 5.14

| [S.No](http://S.NO) | Parameter | Size / Details |
| --- | --- | --- |
|   |   |   |
|   |   |   |

---

## 2.5 Design and Implementation Constraints

> \[!IMPORTANT\]
>
> Content should be present like Example, Mention it as NA
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The design and Implementation constraints are detailed in the section
> >
> > 1. Driver (.ko) and shared object (.so) of DP-XMC-5049 is required for implementation of target application.
> >
> >
> > 2) The software packages are detailed in the **Table 2.5** are required for implementation firmware application.
> >
> > 3) The driver and library (.dll) of QSerialPort is required for implementation host application.

---

## 2.6 User Documentation

> \[!IMPORTANT\]
>
> Content should be present like Example, Otherwise Mention it as NA
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The following document shall be prepared for DP-XMC-5049 test application as part Software Development Life Cycle
> >
> > 1. DP-XMC-5049 Software Requirement Specification (SRS)
> >
> > 2. DP-XMC-5049 Software Design Document (SDD)
> >
> > 3. DP-XMC-5049 Version Definition Document (VDD)

---

## 2.7 Assumptions and Dependencies

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The design and development of the software depends on the hardware requirement document. Any changes in the requirement document will affect the design of software

### 2.7.1 Assumptions

> \[!NOTE\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA

### 2.7.2 Dependencies

> \[!NOTE\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA/

---

# 3. EXTERNAL INTERFACE REQUIREMENTS

> \[!NOTE\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The external interface requirements such as the user, hardware, software and communication interfaces are detailed in this section.

## 3.1 User Interfaces

> \[!IMPORTANT\]
>
> Make it as a bullet list with description (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > - The firmware application software shall be interfaced with user through USB host application. User shall be able to choose the test case to be performed by clicking the options in GUI application.
> >
> > - The user has provision to provide inputs for EEPROM EDID write operation, DVI re-timer configuration, KTM5030 configuration and QSPI communication with FPGA.
> >
> > - Application shall consist of standard GUI layouts such as menu bar, action log, standard
> >
> >   buttons and other user-friendly controls.
> >
> > - Pop up message boxes shall be used to provide warning and error information to intimate the
> >
> >   user about the failures or other serious events.

---

## 3.2 Hardware Interfaces

> \[!NOTE\]
>
> Describe as a paragraph (1- 2 lines)
>
> > \[!CAUTION\]
> >
> > Example: The hardware interface in the DP-XMC-5049 module are listed in the below **Table 3.1**.

**Table 3.1 : Hardware Interfaces**

> \[!IMPORTANT\]
>
> - [S.No](http://S.No) → Refers the serial no of the row.
> - Device → Refers the Example
>
> > \[!CAUTION\]
> >
> > Device → Example:
> >
> > - ARINC818
> > - FPGA
> > - Micro-controller
> > - Temperature Sensor
> > - Storage Flash
> > - DVI Re-Timer
> > - Micro HDMI Connector
> > - Configuration Flash
> > - KTM5030
>
> - Interface → Refers the Example
>
> > \[!CAUTION\]
> >
> > Interface → Example:
> >
> > - FO
> > - PCIe
> > - USB 2.0
> > - I2C
> > - SPI
> > - HDMI
> > - SPI
> > - DP
>
> - Description → Refers the Example
>
> > \[!CAUTION\]
> >
> > Description → Describe it as (2-3 Lines)
> >
> > Example:
> >
> > Fibre optic cables are interface to transmit and receive the digital ARINC818 video data.

| S.No | Device | Interface | Description |
| --- | --- | --- | --- |
| 1 | \[Device Name\] | \[Interface\] | \[Description for the device\] |
|   |   |   |   |

---

## 3.3 Software Interfaces

> \[!NOTE\]
>
> Describe as a paragraph (1- 2 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The software interface in the DP-XMC-5049 test application are detailed in the below sub-sections.

### 3.3.1 Software interface in Target Application

> \[!IMPORTANT\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA

### 3.3.2 Software Interface in Host Application

> \[!IMPORTANT\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA

### 3.3.3 Software Interface in Firmware Application

> \[!IMPORTANT\]
>
> Make it as a bullet list with description (2- 3 lines),Otherwise Mention it as NA

---

## 3.4 Communications Interfaces

> Refer example for content formation
>
> Example:
>
> The communication interfaces in the DP-VPX-0750 test application are detailed below:
>
> - PCIe shall be used for establishing communication between the SBC (DP-VPX-0750) and the FPGA (Xilinx Kintex Ultrascale).
>
> - USB is used for establishing communication between the MCU and the Test PC.
>
> - KTM5030 establishes communication with the Test PC through the I2C / UART / AUX interface.


---

# 4. FUNCTIONAL REQUIREMENTS

> \[!IMPORTANT\]
>
> Describe as a paragraph (1- 2 lines)
>
> Example:
>
> The major functional requirements of DP-XMC-5049 Board validation test software are given in the below **Table 4.1**.

**Table 4.1: {{Project-Board-ID}} Board Validation Test Requirement IDs**

> \[!IMPORTANT\]
>
> Refer the Example Table:
>
> | [**Si.No**](http://Si.No)**.** | **Requirement ID** | **Requirement Name** | **Reference Requirement ID** |
>
> | 1 | DPXMC5049_HOST_01 | Host Application | N.A |
>
> | 2 | DPXMC5049_TARGET_02 | Target Application | N.A |
>
> | 3 | DPXMC5049_FW_03 | MCU Firmware | N.A |
>
> | 4 | DPXMC5049_KTM_04 | Video Splitter Test | N.A |

| Si.No. | Requirement ID | Requirement Name | Reference Requirement ID |
| --- | --- | --- | --- |
|   |   |   |   |

**Table 4.{{NO}}: {{Board ID}} Board Validation Test Sub-Requirement IDs**

> \[!IMPORTANT\]
>
> | [**Si.No**](http://Si.No)**.** | **Requirement ID** | **Sub - Requirement Name** | **Reference Requirement ID** |
>
> | 1 | DPXMC5049_HOST_USR_AUTH_01_01 | User Authentication | N.A |
>
> | 2 | DPXMC5049_HOST_INIT_01_02 | Initialization | N.A |
>
> | 3 | DPXMC5049_HOST_USR_MGMT_01_03 | User Management | N.A |
>
> | 4 | DPXMC5049_TARGET_BRD_DETAILS_02_01 | Get Board Details | N.A |
>
> | 5 | DPXMC5049_TARGET_FPGA_RDWR_02_02 | FPGA Read & Write | N.A |
>
> | 6 | DPXMC5049_TARGET_DDR_02_03 | DDR Test | N.A |
>
> | 7 | DPXMC5049_TARGET_TEMP_02_04 | Temperature Test | N.A |
>
> | 8 | DPXMC5049_TARGET_ARINC818_02_05 | ARINC 818 Test | N.A |
>
> | 9 | DPXMC5049_TARGET_VIO_ENC_02_06 | Video Encoder Test | N.A |
>
> | 10 | DPXMC5049_TARGET_USR_FLASH_02_07 | User Flash Test | N.A |
>
> | 11 | DPXMC5049_FW_USB_INIT_03_01 | USB Initialization | N.A |
>
> | 12 | DPXMC5049_FW_RD_GA_03_02 | Read Geographical Address | N.A |
>
> | 13 | DPXMC5049_FW_EEPROM_03_03 | EEPROM Test | N.A |
>
> | 14 | DPXMC5049_FW_QSPI_03_04 | QSPI Communication Test | N.A |
>
> | 15 | DPXMC5049_FW_DVI_03_05 | DVI Test | N.A |

| Si.No. | Requirement ID | Sub - Requirement Name | Reference Requirement ID |
| --- | --- | --- | --- |
|   |   |   |   |

---

> \[!IMPORTANT\]
>
> {{**No**}} → Auto incremented based on the sequence
>
> {{**Requirement Name**}} → choose from the Requirement Table

## 4.{{No}} {{**Requirement Name}}**

> \[!IMPORTANT\]
>
> Describe as a paragraph (2- 3 lines)
>
> > \[!CAUTION\]
> >
> > Example:
> >
> > The host application is a GUI based windows application which runs in the test PC for transmitting command to MCU through USB protocol. The GUI receives response packet from MCU with the test status by performing test cases corresponding to test specified in the command packet.

> \[!CAUTION\]
>
> {{**No**}} → Auto incremented based on the sequence
>
> {{**Requirement Name**}} → choose from the Requirement Table

**Table 4.{{No}} {{Requirement Name}} Test Requirement**

> \[!IMPORTANT\]
>
> Refer the example for table format
>
> Example:
>
> | [**S.No**](http://Si.No) | **Requirement ID** | **Requirement Name** |
>
> | 1 | DPXMC5049_HOST_01 | Host Application |

| S.No | Requirement ID | Requirement Name |
| --- | --- | --- |
|   |   |   |

> \[!CAUTION\]
>
> {{**No**}} → Auto incremented based on the sequence
>
> {{**Requirement Name**}} → choose from the Requirement Table

**Table 4.{{No}} {{Requirement Name}} Test Sub Requirement**

> \[!IMPORTANT\]
>
> Refer the example for Table Format
>
> Example:
>
> | [**S.No**](http://Si.No) | **Sub - Requirement ID** | **Sub - Requirement Name** |
>
> | 1 | DPXMC5049_HOST_USR_AUTH_01_01 | User Authentication |
>
> | 2 | DPXMC5049_HOST_INIT_01_02 | Initialization |
>
> | 3 | DPXMC5049_HOST_USR_MGMT_01_03 | User Management |

| [S.No](http://S.No) | **Sub -** Requirement ID | Sub - Requirement Name |
| --- | --- | --- |
|   |   |   |

> \[!CAUTION\]
>
> {{**No**}} → Auto incremented based on the sequence
>
> {{**sub Requirement Name**}} → choose from the Sub Requirement Table

### 4.{{No}}.{{No}} {{Sub - Requirement Name}}

> \[!CAUTION\]
>
> {{**No**}} → Auto incremented based on the sequence

**Table 4.{{No}} {{Sub - Requirement Name}}**

> \[!IMPORTANT\]
>
> Refer the example for Table Format
>
> Example →
>
> - Requirement ID → DPXMC5049_HOST_USR_AUTH_01_01
> - Requirement Description → The user authentication module shall ensure that only authorized users are allowed to access the software. The module shall get the user name and password from user. Then it shall evaluate the user name and password entered by the user and allows the user to proceed if both are valid. Any invalid input shall lead to the display of an error message and prompt for the user to re-enter the details. This helps in restricting the application to be accessible for unauthorized users.

| sub - Requirement ID | Requirement Description |
| --- | --- |
|   |   |
|   |   |


---

# 5. SOFTWARE SYSTEM ATTRIBUTES

> \[!IMPORTANT\]
>
> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA
>
> Example:
>
> The other non-functional requirements, including the performance, safety and security requirements are dealt in this section

## 5.1 Performance Requirements

> \[!IMPORTANT\]
>
> Make it as Number list with description (2- 3 lines), Otherwise Mention it as NA
>
> Example:
>
> - All Test plan shall be carried out, only if all the hardware modules are present in the system.

## 5.2 Safety Requirements

> \[!IMPORTANT\]
>
> Make it as Number list with description (2- 3 lines), Otherwise Mention it as NA
>
> Example:
>
> The safety requirements are addressed in the software by following methods
>
> 1. The test software application shall be exited while testing.
>
> 2. Functional operations shall be restricted when any of the hardware modules are not detected.
>
> 3. Warning / error messages shall be printed from the test application.

## 5.3 Security Requirements

> \[!IMPORTANT\]
>
> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA\
> Example:
>
> The user shall have an authentication process to access this application. The system shall be protected from anonymous users as it has confidential information and other important functions. Only authorized user shall be able to access this software.

## 5.4 Software Quality Attributes

> \[!IMPORTANT\]
>
> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA\
> Example:
>
> The application software quality attributes, including the maintainability and re-usability details are dealt in this section

## 5.5 Business Rules

> \[!IMPORTANT\]
>
> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA

---

# 6. OTHER REQUIREMENTS

> \[!IMPORTANT\]
>
> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA
>
> Example:
>
> The KTM5030 video splitter chip in the DP-XMC-5049 module shall operate after loading its driver and firmware through Dedi programmer in the KTM5030 flash memory. Then after power-ON chip shall be initialize with loaded firmware. Refer **Figure 3.1** for the diagrammatic description.
>
> The ATSAMD51 MCU in the module shall be loaded with the DP-XMC-5049 operational requirement firmware for performing the configuration, communication test requirements.

---

# 7. REQUIREMENTS TRACEABILITY

**Table 7.1 : Requirements Traceability Matrix**

> \[!IMPORTANT\]
>
> The requirement IDs in SRS document are mapped with the requirements in HRS document in the below **Table 7.1**.
>
> Refer the Example Table Format:
>
> | [**S.No**](http://Si.No)**.** | **Requirement ID in SRS** | **Requirement ID in HRS** | **Section in SRS** |
>
> | 1 | DPXMC5049_TARGET_BRD_DETAILS_02_01 | DP-XMC- 5049-HRS-0014, | 4.2.1 |
>
> | 2 | DPXMC5049_TARGET_FPGA_RDWR_02_02 | DP-XMC- 5049-HRS-002 | 4.2.2 |
>
> | 3 | DPXMC5049_TARGET_DDR_02_03, | DP-XMC- 5049-HRS-007 | 4.2.3,**4.2.3.1,** |
>
> | 4 | DPXMC5049_TARGET_TEMP_02_04, | DP-XMC- 5049-HRS-0015 | 4.2.4, **4.2.4.1, 4.2.4.2** |

| S.No | Requirement ID in SRS | Requirement ID in HRS | Section in SRS |
| --- | --- | --- | --- |
|   |   |   |   |

---

# APPENDIX A: MAPPING KC

> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA

---

# APPENDIX B: SUPPORTING INFORMATION

> Describe as a paragraph (2- 3 lines), Otherwise Mention it as NA

---