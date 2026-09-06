---
sub_category: PCIe
parent_category: Hardware Interfaces
total_requirements: 4
---

# PCIe Requirements

## Summary

This sub-category defines the hardware interface specifications for the DP-XMC-5049 module, focusing on the PCIe Gen 3 x8 link architecture and high-speed ARINC 818 video data transmission capabilities.

## Requirements

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| REQ-0006 | Normal | DP-XMC-5049 shall be a XMC PCIe based video converter module which supports STANAG3350 / RGB / VGA, DVI, ARINC818 interfaces. | [REQ-0006.md](../requirements/REQ-0006.md) |
| REQ-0009 | Normal | DP-XMC-5049-HRS-0011 ARINC 818: Three ARINC 818 Transmitter (Tx) for high speed digital video output on XMC Secondary Connector. One output channel shall be interfaced to XMC connector. Two output channels are optional with DVI channel 1. 4.25 Gb/s data rate (max) shall be supported for each Tx channel. Three ARINC 818 Receiver (Rx) for high speed digital video input. All three channels are optional with DVI channel 1. 4.25 Gb/s data rate (max) shall be supported for each Rx channel. | [REQ-0009.md](../requirements/REQ-0009.md) |
| REQ-0015 | Normal | PCIe interface: x8 PCIe interface on FPGA MGT bank; Reference clock from clock generator to FPGA MGT bank shall be used for PCIe. | [REQ-0015.md](../requirements/REQ-0015.md) |
| REQ-0017 | Normal | DP-XMC-5049-HRS-0014 PCIe: 1x x8 PCIe Gen 3 link between XMC Primary Connector and MGT bank of FPGA. | [REQ-0017.md](../requirements/REQ-0017.md) |