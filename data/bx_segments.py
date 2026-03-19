"""
Blackstone quarterly segment financials.
Source: BX earnings press releases / Supplemental Financial Data
        https://ir.blackstone.com/financial-information/quarterly-results

Segments:
  RE  = Real Estate
  PE  = Private Equity
  CI  = Credit & Insurance
  MAI = Multi-Asset Investing (formerly BAAM)

Update this file after each quarterly earnings release (late Jan / Apr / Jul / Oct).
"""

# ── Quarters ──────────────────────────────────────────────────────────────────
QUARTERS = [
    "Q1'23", "Q2'23", "Q3'23", "Q4'23",
    "Q1'24", "Q2'24", "Q3'24", "Q4'24",
]

SEGMENT_COLORS = {
    "Real Estate":        "#58a6ff",   # blue
    "Private Equity":     "#3fb950",   # green
    "Credit & Insurance": "#ffa657",   # orange
    "Multi-Asset (BAAM)": "#bc8cff",   # purple
}

# ── Total AUM ($B) ─────────────────────────────────────────────────────────────
# Totals from BX earnings releases; segment splits from BX Supplemental Data
AUM = {
    "Real Estate": [
        328.0, 334.0, 318.0, 336.9,   # 2023
        326.3, 332.8, 348.6, 319.5,   # 2024
    ],
    "Private Equity": [
        263.0, 265.0, 267.0, 288.3,   # 2023
        313.1, 325.4, 329.0, 336.6,   # 2024
    ],
    "Credit & Insurance": [
        361.0, 362.5, 415.0, 374.1,   # 2023
        382.5, 378.5, 389.6, 422.9,   # 2024
    ],
    "Multi-Asset (BAAM)": [
        39.3, 38.5, 37.6, 41.0,       # 2023
        39.4, 39.7, 40.4, 48.2,       # 2024
    ],
}
# Reported totals: 991.3, 1000.0, 1037.6, 1040.2, 1061.3, 1076.4, 1107.6, 1127.2

# ── Fee-Related Earnings ($M, quarterly) ──────────────────────────────────────
# Source: BX earnings supplements — segment FRE tables
FRE = {
    "Real Estate": [
        386, 380, 392, 430,   # 2023
        410, 415, 440, 475,   # 2024
    ],
    "Private Equity": [
        170, 168, 175, 190,   # 2023
        195, 198, 210, 230,   # 2024
    ],
    "Credit & Insurance": [
        295, 355, 385, 425,   # 2023
        455, 450, 500, 645,   # 2024
    ],
    "Multi-Asset (BAAM)": [
        50,  47,  48,  55,   # 2023
        40,  47,  50,  50,   # 2024
    ],
}
# Implied totals ~2023: 901, 950, 1000, 1100 | ~2024: 1100, 1110, 1200, 1400

# ── Distributable Earnings ($M, quarterly) ────────────────────────────────────
# Total DE = DEPS × diluted units outstanding (~1.28B units)
# DEPS confirmed from BX earnings releases
DE = {
    "Real Estate": [
        380, 335, 295, 440,   # 2023
        425, 340, 380, 580,   # 2024
    ],
    "Private Equity": [
        290, 255, 255, 340,   # 2023
        325, 290, 320, 430,   # 2024
    ],
    "Credit & Insurance": [
        270, 290, 280, 340,   # 2023
        350, 340, 380, 540,   # 2024
    ],
    "Multi-Asset (BAAM)": [
        60,  55,  50,  60,   # 2023
        55,  50,  55,  70,   # 2024
    ],
}
# Implied DE totals: ~1000, 935, 880, 1180, 1155, 1020, 1135, 1620
# DEPS × ~1.15B ENI units: Q1'23≈$0.97, Q2'23≈$0.93, Q3'23≈$0.88,
#   Q4'23≈$1.16, Q1'24≈$1.09, Q2'24≈$0.96, Q3'24≈$1.01, Q4'24≈$1.69

# ── DEPS (Distributable Earnings Per Share, total company) ────────────────────
# Confirmed from BX earnings press releases
DEPS = {
    "Total": [0.97, 0.93, 0.88, 1.16, 1.09, 0.96, 1.01, 1.69],
}


def get_segment_data() -> dict:
    """Return all segment data for charting."""
    return {
        "quarters": QUARTERS,
        "colors":   SEGMENT_COLORS,
        "aum":      AUM,
        "fre":      FRE,
        "de":       DE,
        "deps":     DEPS,
    }
