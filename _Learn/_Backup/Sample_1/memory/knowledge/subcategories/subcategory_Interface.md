---
sub_category: Interface
parent_category: Hardware Requirements
total_requirements: 15
---

# Interface Requirements

## Summary

This sub-category defines the hardware interfaces for video input, output, and high-speed data transmission, including DisplayPort, ARINC 818, PCIe, DVI, and USB connections. It specifies the FPGA's role in managing these interfaces, the required signal conditioning components, and the testing procedures to verify connectivity and data integrity across various video standards and protocols.

## Requirements

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| HAR-0003 | Normal | The module shall support DisplayPort video input from secondary XMC Connector which are electrically translated to the 3 no.s of TMDS level DP++/DVI outputs using DP to DP++/DVI splitter. The DP++ Video splitter shall be interfaced with a 2MB SPI NOR Flash. | [HAR-0003.md](../requirements/HAR-0003.md) |
| REQ-0004 | Normal | The FPGA shall be interfaced with three Video encoder ICs via an RGB parallel data bus interface on an IO bank for Video output from the FPGA to the XMC Secondary Connector. The FPGA shall supply the required reference clock for the Video encoder ICs. The Video encoder ICs shall be configured by the FPGA. | [REQ-0004.md](../requirements/REQ-0004.md) |
| REQ-0005 | Normal | ARINC 818 Interface: ARINC 818 high speed video protocol shall be implemented on FPGA MGT bank; 3x ARINC 818 Video output and input channels shall be implemented. Reference clock from clock generator to FPGA MGT bank shall be used for ARINC 818. | [REQ-0005.md](../requirements/REQ-0005.md) |
| HAR-0007 | Normal | The module shall support high speed communication interface such as PCIe on XMC primary connector for video raw data reception / transmission. The XMC Primary connector interfaces x8 PCIe lines from the carrier module. Module shall optionally support 3x ARINC 818 Transmitter(Tx) and 3x ARINC 818 Receiver(Rx) interfaces from the secondary XMC connector to the MGT bank of FPGA. | [HAR-0007.md](../requirements/HAR-0007.md) |
| HAR-0008 | Normal | The module shall support 1x single link DVI output via DVI equalizer interfaced from either FPGA or DP to DVI splitter to XMC secondary connector. The module shall additionally support 1x single link DVI output from DP to DVI splitter interfaced to the DVI Connector on the Front panel via DVI equalizer. The module shall also support 1x DVI output from DP to DVI splitter interfaced to the XMC secondary connector on the Front panel via DVI equalizer. The module shall support RGBHV / VGA / STANAG 3350 analog video standard output on XMC Secondary connector using Video encoder with recommended front end. | [HAR-0008.md](../requirements/HAR-0008.md) |
| HAR-0020 | Normal | Requirement ID: DP-XMC-5049-HRS-0013; Requirement: STANAG 3350 / VGA Video; Testing Plan: DisplayPort Video input data shall be received on FPGA. Same video data received on FPGA shall be sent out via Video encoder IC which shall be interfaced to standard VGA / PAL display. Software: Refer DP- VPX-5792 test application | [HAR-0020.md](../requirements/HAR-0020.md) |
| HAR-0021 | Normal | Requirement ID: DP-XMC-5049-HRS-0014; Requirement: PCIe; Testing Plan: Standard PCIe enumeration test shall be performed with any standard SBC PCIe root complex; Software: Refer DP-VPX-0750 or DP-VPX-0930 test application | [HAR-0021.md](../requirements/HAR-0021.md) |
| HAR-0022 | Normal | This section shall include required test equipment, test cables (bought out), test cables (fabricated), test jig, test rig, external modules, JTAG, emulators, software environment, and programming file. | [HAR-0022.md](../requirements/HAR-0022.md) |
| REQ-0023 | Normal | The FPGA shall be interfaced with a maximum of 3 DVI/TMDS video inputs. | [REQ-0023.md](../requirements/REQ-0023.md) |
| REQ-0024 | Normal | DVI Video Output: FPGA shall provide 1x DVI video output interfaced to DVI equalizer IC. | [REQ-0024.md](../requirements/REQ-0024.md) |
| HAR-0025 | Normal | Requirement ID: DP-XMC-5049-HRS-0011; Requirement: ARINC 818; Testing Plan: ARINC 818 standard Video data transfer test shall be done using external ARINC 818 to DVI conversion module; Software: Refer DP- VPX-5792 test application | [HAR-0025.md](../requirements/HAR-0025.md) |
| HAR-0028 | Normal | DP-XMC-5049-HRS-0017: XMC Secondary Connector requirements: DVI channel 1 / 2x ARINC818 TX & 3x ARINC818 RX; 1x ARINC818 TX; DVI channel 2 / RGBHV channel 1 RED - BLUE & RGBHV channel 2 RED – BLUE; RGBHV CVBS Green channel 1 & 2; RGBHV channel 3 (Red, Green & Blue); One DisplayPort input channel; One optional USB channel from Micro-controller. | [HAR-0028.md](../requirements/HAR-0028.md) |
| HAR-0036 | Normal | DP-XMC-5049-HRS-0019: Supported OS: Linux / Windows (SBC external module for PCIe enumeration) | [HAR-0036.md](../requirements/HAR-0036.md) |
| HAR-0044 | Normal | Requirement ID: DP-XMC-5049-HRS-0012; Requirement: DP/DP++ Video Input; Testing Plan: DisplayPort source shall be used to send video data and same video shall be sent out via each DVI channel to a DVI monitor; Software: Refer DP- VPX-5792 test application | [HAR-0044.md](../requirements/HAR-0044.md) |
| HAR-0054 | Normal | Requirement ID: DP-XMC-5049-HRS-0016; Requirement: USB2.0; Testing Plan: NA | [HAR-0054.md](../requirements/HAR-0054.md) |