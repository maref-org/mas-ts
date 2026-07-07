/*
 * MAS-TS YARA Rules — Date Format Steganography Detection
 *
 * Detects non-standard date format patterns that can be used as
 * steganographic signals (e.g., switching from ISO 2026-07-06 to
 * slash format 2026/07/06 to mark timezone-triggered behavior).
 */

rule Date_Format_Slash_Variant {
    meta:
        description = "Detects slash-format dates (YYYY/MM/DD) — Claude Code pattern"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "high"

    strings:
        // YYYY/MM/DD format (slash separator)
        $slash_date = /\d{4}\/\d{2}\/\d{2}/

    condition:
        $slash_date and filesize < 100KB
}

rule Date_Format_Mixed_Separator {
    meta:
        description = "Detects mixed date separators (- and /) — strong steganography signal"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "critical"

    strings:
        // Mixed separators in same date: 2026-07/06 or 2026/07-06
        $mixed_1 = /\d{4}-\d{2}\/\d{2}/
        $mixed_2 = /\d{4}\/\d{2}-\d{2}/

    condition:
        $mixed_1 or $mixed_2
}

rule Date_Format_Dot_Variant {
    meta:
        description = "Detects dot-format dates (DD.MM.YYYY) — European format"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "medium"

    strings:
        $dot_date = /\d{2}\.\d{2}\.\d{4}/

    condition:
        $dot_date and filesize < 100KB
}

rule Conditional_Date_Logic {
    meta:
        description = "Detects conditional date format logic in source code"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "high"

    strings:
        // Conditional date format switching patterns
        $cond_1 = /if.*date.*format.*\//is nocase
        $cond_2 = /date.*separator.*[\/-]/is nocase
        $cond_3 = /strftime.*%m\/%d/is

    condition:
        any of ($cond_1, $cond_2, $cond_3) and filesize < 500KB
}
