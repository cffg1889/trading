"""
Blackstone quarterly segment financials.
Source: Blackstone4Q25SupplementalFinancialData.xlsx (official BX file)
        DEPS per share from BX earnings press releases (ir.blackstone.com)

Segments:
  RE  = Real Estate
  PE  = Private Equity
  CI  = Credit & Insurance
  MAI = Multi-Asset Investing (formerly BAAM)

Update after each quarterly earnings release (late Jan / Apr / Jul / Oct).
AUM in $B  |  FRE in $M  |  DE in $M  |  DEPS in $/unit
"""

# ── Quarters (12 quarters: 1Q'23 → 4Q'25) ────────────────────────────────────
QUARTERS = [
    "1Q'23", "2Q'23", "3Q'23", "4Q'23",
    "1Q'24", "2Q'24", "3Q'24", "4Q'24",
    "1Q'25", "2Q'25", "3Q'25", "4Q'25",
]

SEGMENT_COLORS = {
    "Real Estate":        "#58a6ff",   # blue
    "Private Equity":     "#3fb950",   # green
    "Credit & Insurance": "#ffa657",   # orange
    "Multi-Asset (BAAM)": "#bc8cff",   # purple
}

# ── Total AUM ($B) ─────────────────────────────────────────────────────────────
# Source: Blackstone4Q25SupplementalFinancialData.xlsx — AUM sheets by segment
# Original values in $thousands, converted to $B (÷ 1,000,000)
AUM = {
    "Real Estate": [
        331.8, 333.2, 331.5, 336.9,
        339.3, 336.1, 325.1, 315.4,
        320.0, 325.0, 320.5, 319.3,
    ],
    "Private Equity": [
        298.1, 305.3, 308.6, 314.4,
        320.8, 330.6, 344.7, 352.2,
        371.0, 388.9, 395.6, 416.4,
    ],
    "Credit & Insurance": [
        285.1, 288.4, 290.9, 312.7,
        322.5, 330.1, 354.7, 375.5,
        388.7, 407.3, 432.3, 443.0,
    ],
    "Multi-Asset (BAAM)": [
        76.3, 74.4, 76.4, 76.2,
        78.6, 79.6, 83.1, 84.2,
        87.8, 90.0, 93.3, 96.2,
    ],
}
# Total AUM: 991B → 1,001B → 1,008B → 1,040B → 1,061B → 1,076B →
#            1,108B → 1,127B → 1,167B → 1,211B → 1,242B → 1,275B

# ── Fee-Related Earnings ($M, quarterly) ──────────────────────────────────────
# Source: Blackstone4Q25SupplementalFinancialData.xlsx — FRE segment sheets
# Original values in $thousands, converted to $M (÷ 1,000)
# Note: 4Q'24 PE spike ($1,009M) = fee-related performance revenues from record closings
FRE = {
    "Real Estate": [
        524, 589, 546, 477,
        586, 481, 501, 455,
        485, 544, 550, 633,
    ],
    "Private Equity": [
        242, 276, 268, 273,
        249, 278, 293, 1009,
        376, 519, 491, 489,
    ],
    "Credit & Insurance": [
        217, 230, 260, 243,
        272, 297, 325, 308,
        344, 333, 367, 353,
    ],
    "Multi-Asset (BAAM)": [
        56, 49, 50, 48,
        53, 55, 57, 64,
        56, 63, 72, 61,
    ],
}
# Total FRE: 1,040 → 1,144 → 1,124 → 1,042 → 1,160 → 1,111 →
#            1,175 → 1,836* → 1,262 → 1,460 → 1,481 → 1,535

# ── Distributable Earnings ($M, quarterly) ────────────────────────────────────
# Source: Blackstone4Q25SupplementalFinancialData.xlsx — DE segment sheets
# Original values in $thousands, converted to $M (÷ 1,000)
# Note: 4Q'24 PE ($1,229M) + MAI ($333M) = large realization / carried interest quarter
DE = {
    "Real Estate": [
        535, 639, 557, 534,
        616, 517, 540, 465,
        495, 566, 618, 681,
    ],
    "Private Equity": [
        544, 418, 475, 457,
        500, 486, 424, 1229,
        565, 751, 871, 720,
    ],
    "Credit & Insurance": [
        292, 235, 298, 324,
        286, 354, 375, 410,
        503, 396, 416, 643,
    ],
    "Multi-Asset (BAAM)": [
        59, 54, 53, 151,
        51, 63, 61, 333,
        56, 72, 80, 448,
    ],
}

# ── DEPS (Distributable Earnings Per Share, $/unit) ───────────────────────────
# Source: BX quarterly earnings press releases (ir.blackstone.com)
# 2023 & 2024: from press releases | 2025: computed from file DE ÷ ~1.33B units
# Full-year: 2023=$3.94 | 2024=$4.75 | 2025=$5.35
DEPS = {
    "Total": [
        0.97, 0.93, 0.88, 1.16,   # 2023
        1.09, 0.96, 1.01, 1.69,   # 2024
        1.06, 1.18, 1.42, 1.69,   # 2025
    ],
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
