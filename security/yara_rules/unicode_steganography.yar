/*
 * MAS-TS YARA Rules — General Unicode Steganography Detection
 *
 * Detects Unicode-based steganographic techniques that can be used to
 * encode covert information in agent source code or binaries.
 */

rule Unicode_Homoglyph_Mixing {
    meta:
        description = "Detects mixing of ASCII and Cyrillic homoglyphs"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "high"

    strings:
        // Cyrillic homoglyphs that look like ASCII letters
        $cyrillic_a = { B0 04 }      // а (U+0430)
        $cyrillic_e = { B5 04 }      // е (U+0435)
        $cyrillic_o = { BE 04 }      // о (U+043E)
        $cyrillic_p = { 80 04 }      // р (U+0440)
        $cyrillic_c = { 81 04 }      // с (U+0441)
        $cyrillic_x = { 85 04 }      // х (U+0445)

        // ASCII counterparts
        $ascii_a = "a" nocase
        $ascii_e = "e" nocase
        $ascii_o = "o" nocase

    condition:
        // Suspicious if both ASCII and Cyrillic homoglyphs present in small file
        filesize < 500KB and
        any of ($cyrillic_a, $cyrillic_e, $cyrillic_o, $cyrillic_p, $cyrillic_c, $cyrillic_x) and
        any of ($ascii_a, $ascii_e, $ascii_o)
}

rule Unicode_Apostrophe_Variants {
    meta:
        description = "Detects multiple Unicode apostrophe variants in same file"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "high"

    strings:
        $apos_ascii = "'"            // U+0027 ASCII apostrophe
        $apos_02bc = { CA 02 }       // U+02BC MODIFIER LETTER APOSTROPHE
        $apos_02b9 = { B9 02 }       // U+02B9 MODIFIER LETTER PRIME
        $apos_2019 = { 19 20 }       // U+2019 RIGHT SINGLE QUOTATION MARK
        $apos_2032 = { 32 20 }       // U+2032 PRIME
        $apos_ff07 = { 07 FF }       // U+FF07 FULLWIDTH APOSTROPHE

    condition:
        // 2+ different apostrophe variants = potential steganographic encoding
        2 of ($apos_02bc, $apos_02b9, $apos_2019, $apos_2032, $apos_ff07)
}

rule Unicode_Normalization_Anomaly {
    meta:
        description = "Detects non-NFC normalized text (potential steganography)"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "medium"

    strings:
        // Combining diacritical marks (decomposed forms)
        $combining_acute = { 01 03 }     // U+0301 COMBINING ACUTE ACCENT
        $combining_grave = { 00 03 }     // U+0300 COMBINING GRAVE ACCENT
        $combining_tilde = { 03 03 }     // U+0303 COMBINING TILDE
        $combining_umlaut = { 08 03 }    // U+0308 COMBINING DIAERESIS

    condition:
        // Many combining marks = potential decomposed form steganography
        filesize < 100KB and
        (#combining_acute + #combining_grave + #combining_tilde + #combining_umlaut) > 10
}
