# Technology catalog provenance

Generated from `src/phased_array_systems/data/technologies.yaml` by
`python -m phased_array_systems.models.rf.technology`. Do not edit by hand.

Values are survey/review ranges or single published data points, each
with the citation that was fetched when the row was written. Ranges
collapse to midpoints in `technology_defaults`. The `pa_class_dbm`
field is a saturated/optimization power class; the TRM hook uses it
as a P1dB default, which is an optimistic upper bound.

For the full published-design landscape rather than class ranges, see
the [ETH IDEAS PA Survey](https://ideas.ethz.ch/Surveys/pa-survey.html)
(v10: 5073 designs, 500 MHz-1.5 THz, CMOS/SiGe/GaN/GaAs/InP/LDMOS) and
the [ETH IDEAS LNA Survey](https://ideas.ethz.ch/Surveys/lna-survey.html)
(v3.0, silicon/SiGe, 500 MHz-300 GHz), both accessed 2026-08-11.

## cmos — Bulk / SOI CMOS

| field | value | units | source | confidence |
|---|---|---|---|---|
| pa_class_dbm | 25.0 | dBm (optimization target, 5G front-end context) | [Watanabe et al., arXiv:2009.07208](https://arxiv.org/abs/2009.07208) (accessed 2026-08-11) | high |
| pa_pae_pct | 30.0 | % (optimization target, same source) | [Watanabe et al., arXiv:2009.07208](https://arxiv.org/abs/2009.07208) (accessed 2026-08-11) | high |
| lna_nf_db | [1.5, 3.0] | dB | [RF Essentials, 'What is an LNA?' technology comparison](https://rfessentials.com/resources/rf-glossary/lna/) (accessed 2026-08-11) | medium |
| lna_iip3_dbm | [-5.0, 5.0] | dBm | [RF Essentials, 'What is an LNA?' technology comparison](https://rfessentials.com/resources/rf-glossary/lna/) (accessed 2026-08-11) | medium |
| cost_class | lowest (consumer volume; RF Essentials LNA guide) | | | |

## gaas — GaAs pHEMT / HBT

| field | value | units | source | confidence |
|---|---|---|---|---|
| pa_psat_w_per_mm | 1.5 | W/mm (about) | [Frenzel, Electronic Design](https://www.electronicdesign.com/communications/what-s-difference-between-gaas-and-gan-rf-power-amplifiers) (accessed 2026-08-11) | medium |
| pa_class_dbm | [30.0, 35.0] | dBm (5G front-end context) | [Watanabe et al., arXiv:2009.07208](https://arxiv.org/abs/2009.07208) (accessed 2026-08-11) | high |
| pa_pae_pct | [20.0, 50.0] | % (handset PA class) | [Frenzel, Electronic Design](https://www.electronicdesign.com/communications/what-s-difference-between-gaas-and-gan-rf-power-amplifiers) (accessed 2026-08-11) | medium |
| single_device_power_w | 5.0 | W (up to, single device) | [Frenzel, Electronic Design](https://www.electronicdesign.com/communications/what-s-difference-between-gaas-and-gan-rf-power-amplifiers) (accessed 2026-08-11) | medium |
| ft_ghz | 150.0 | GHz (typical range) | [Frenzel, Electronic Design](https://www.electronicdesign.com/communications/what-s-difference-between-gaas-and-gan-rf-power-amplifiers) (accessed 2026-08-11) | medium |
| lna_nf_db | [0.3, 0.5] | dB at 2 GHz | [RF Essentials, 'What is an LNA?' technology comparison](https://rfessentials.com/resources/rf-glossary/lna/) (accessed 2026-08-11) | medium |
| lna_iip3_dbm | [-5.0, 5.0] | dBm | [RF Essentials, 'What is an LNA?' technology comparison](https://rfessentials.com/resources/rf-glossary/lna/) (accessed 2026-08-11) | medium |

## gan — GaN HEMT (on SiC)

| field | value | units | source | confidence |
|---|---|---|---|---|
| pa_psat_w_per_mm | [5.0, 12.0] | W/mm | [Frenzel, 'What's the Difference Between GaAs and GaN RF Power Amplifiers?', Electronic Design](https://www.electronicdesign.com/communications/what-s-difference-between-gaas-and-gan-rf-power-amplifiers) (accessed 2026-08-11) | medium |
| pa_psat_w_per_mm_example | 10.6 | W/mm | [Wolfspeed 0.25 um X-band GaN HEMT (sunken field plate), Semiconductor Today, Feb 2022](https://www.semiconductor-today.com/news_items/2022/feb/wolfspeed-170222.shtml) (accessed 2026-08-11) | high |
| pa_class_dbm | 45.0 | dBm (capability floor, 5G front-end context) | [Watanabe et al., 'A Review of 5G Front-End Systems Package Integration', arXiv:2009.07208](https://arxiv.org/abs/2009.07208) (accessed 2026-08-11) | high |
| pa_pae_example_pct | 64.0 | % (3.5 GHz accelerated-life test device) | [Wolfspeed via Semiconductor Today, Feb 2022](https://www.semiconductor-today.com/news_items/2022/feb/wolfspeed-170222.shtml) (accessed 2026-08-11) | high |
| breakdown_v | 80.0 | V (typical commercial process ceiling) | [Frenzel, Electronic Design](https://www.electronicdesign.com/communications/what-s-difference-between-gaas-and-gan-rf-power-amplifiers) (accessed 2026-08-11) | medium |
| supply_v | [28.0, 50.0] | V | [28 V: 'Reliability of 150 nm, 28 V GaN HEMT Process up to Ka-band' (paper title); 50 V: Wolfspeed X-band device rating](https://www.semiconductor-today.com/news_items/2022/feb/wolfspeed-170222.shtml) (accessed 2026-08-11) | high |
| ft_ghz | 200.0 | GHz (up to) | [Frenzel, Electronic Design](https://www.electronicdesign.com/communications/what-s-difference-between-gaas-and-gan-rf-power-amplifiers) (accessed 2026-08-11) | medium |
| lna_nf_db | [1.0, 2.0] | dB | [RF Essentials, 'What is an LNA?' technology comparison](https://rfessentials.com/resources/rf-glossary/lna/) (accessed 2026-08-11) | medium |
| lna_iip3_dbm | [15.0, 25.0] | dBm | [RF Essentials, 'What is an LNA?' technology comparison](https://rfessentials.com/resources/rf-glossary/lna/) (accessed 2026-08-11) | medium |
| tj_max_c | 225.0 | C (junction temperature at which MTTF > 6e7 h was demonstrated) | [Wolfspeed via Semiconductor Today, Feb 2022](https://www.semiconductor-today.com/news_items/2022/feb/wolfspeed-170222.shtml) (accessed 2026-08-11) | high |

## ldmos — Si LDMOS

| field | value | units | source | confidence |
|---|---|---|---|---|
| freq_max_ghz | 4.0 | GHz | [Theeuwen & Qureshi, 'LDMOS Technology for RF Power Amplifiers', IEEE TMTT 60(6):1755-1763, 2012 (Ampleon reprint)](https://www.ampleon.com/documents/published-paper/AMP-PP-2017-0503.pdf.pdf) (accessed 2026-08-11) | high |
| supply_v | [28.0, 50.0] | V (30 V mainstream base station; 50 V broadcast/ISM) | [Theeuwen & Qureshi, IEEE TMTT 2012](https://www.ampleon.com/documents/published-paper/AMP-PP-2017-0503.pdf.pdf) (accessed 2026-08-11) | high |
| breakdown_v | [70.0, 120.0] | V (30-V and 50-V technology respectively) | [Theeuwen & Qureshi, IEEE TMTT 2012](https://www.ampleon.com/documents/published-paper/AMP-PP-2017-0503.pdf.pdf) (accessed 2026-08-11) | high |
| pa_psat_w_per_mm | [1.4, 2.0] | W/mm (on-wafer; 30-V and 50-V technology) | [Theeuwen & Qureshi, IEEE TMTT 2012](https://www.ampleon.com/documents/published-paper/AMP-PP-2017-0503.pdf.pdf) (accessed 2026-08-11) | high |
| peak_drain_eff_pct | [62.0, 72.0] | % (72% max; 68% at 3 GHz; 62% at 4 GHz, class-AB on-wafer) | [Theeuwen & Qureshi, IEEE TMTT 2012](https://www.ampleon.com/documents/published-paper/AMP-PP-2017-0503.pdf.pdf) (accessed 2026-08-11) | high |
| doherty_backoff_eff_pct | 47.0 | % at 7.5 dB back-off (700 W peak, 1.8 GHz, 3-way Doherty) | [Theeuwen & Qureshi, IEEE TMTT 2012](https://www.ampleon.com/documents/published-paper/AMP-PP-2017-0503.pdf.pdf) (accessed 2026-08-11) | high |
| gain_db_at_2ghz | 21.0 | dB (15 dB at 4 GHz, -6 dB/octave) | [Theeuwen & Qureshi, IEEE TMTT 2012](https://www.ampleon.com/documents/published-paper/AMP-PP-2017-0503.pdf.pdf) (accessed 2026-08-11) | high |
| cost_class | low (named alongside high gain, efficiency, reliability as LDMOS strengths; Theeuwen & Qureshi 2012) | | | |

## sige — SiGe BiCMOS (HBT)

| field | value | units | source | confidence |
|---|---|---|---|---|
| pa_class_dbm | 25.0 | dBm (optimization target, 5G front-end context) | [Watanabe et al., arXiv:2009.07208](https://arxiv.org/abs/2009.07208) (accessed 2026-08-11) | high |
| pa_pae_pct | 30.0 | % (optimization target, same source) | [Watanabe et al., arXiv:2009.07208](https://arxiv.org/abs/2009.07208) (accessed 2026-08-11) | high |
| pa_example | 19.7 | dBm Psat at 64 GHz, 3.3 V supply, OP1dB 18 dBm (130 nm SiGe BiCMOS) | ['A V-Band Wideband Power Amplifier with High Gain in a 130 nm SiGe BiCMOS Process', Micromachines 15(9):1077, 2024 (PMC11434341)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11434341/) (accessed 2026-08-11) | high |
| bvceo_v | 1.7 | V (open-base; RF swing can exceed this toward BVCBO) | [Jain et al., 'DC and RF breakdown voltage characteristics of SiGe HBTs for WiFi PA applications', IEEE (document 7738948)](https://ieeexplore.ieee.org/document/7738948/) (accessed 2026-08-11) | medium |
| bvcbo_v | 5.9 | V | [Jain et al., IEEE document 7738948](https://ieeexplore.ieee.org/document/7738948/) (accessed 2026-08-11) | medium |
| lna_nf_db | [0.5, 1.5] | dB at 2 GHz | [RF Essentials, 'What is an LNA?' technology comparison](https://rfessentials.com/resources/rf-glossary/lna/) (accessed 2026-08-11) | medium |
| lna_iip3_dbm | [0.0, 10.0] | dBm | [RF Essentials, 'What is an LNA?' technology comparison](https://rfessentials.com/resources/rf-glossary/lna/) (accessed 2026-08-11) | medium |

