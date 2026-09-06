---
sub_category: MIPI
parent_category: Hardware Interfaces
total_requirements: 3
---

# MIPI Requirements

## Summary

This sub-category defines the video input and output capabilities of the system, focusing on DisplayPort, DVI, and STANAG 3350/VGA standards. It specifies the physical connectors, signal types, and optional dependencies between video channels and other interface signals like ARINC818.

## Requirements

| ID | Priority | Description Preview | Link |
|----|----------|---------------------|------|
| REQ-0027 | Normal | DP-XMC-5049-HRS-0013 STANAG 3350 / VGA: Three STANAG 3350 / VGA / RGBHV / RGB Video output on XMC Secondary Connector. RED and BLUE of two channels are optional with DVI channel 2. | [REQ-0027.md](../requirements/REQ-0027.md) |
| REQ-0045 | Normal | DP-XMC-5049-HRS-0010 DVI Video Output: Two single link DVI video outputs on XMC Secondary Connector. One channel is optional with two ARINC818 outputs and three ARINC818 inputs. One channel is optional with RED and BLUE signals of RGBHV channel 1 and 2. One single link DVI Video output on DVI Connector at Front Panel (optional). | [REQ-0045.md](../requirements/REQ-0045.md) |
| REQ-0051 | Normal | DP-XMC-5049-HRS-0012 DP/DP++ Input: One DP/DP++ Input from XMC Secondary Connector. | [REQ-0051.md](../requirements/REQ-0051.md) |