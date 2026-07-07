/*
 * MAS-TS YARA Rules — Claude Code 2026-06-30 Backdoor Detection
 *
 * Detects steganographic backdoor patterns used by Claude Code:
 *   - Date format steganography (2026/07/06 vs ISO 2026-07-06)
 *   - Unicode apostrophe variant encoding (U+02BC, U+02B9, U+2019)
 *   - Timezone-based geolocation logic (Asia/Shanghai, Asia/Urumqi)
 *   - Chinese company domain blacklists
 */

rule Claude_Code_Backdoor_DateFormat {
    meta:
        description = "Detects Claude Code 2026-06-30 backdoor date format pattern"
        author = "MAS-TS"
        date = "2026-07-06"
        reference = "Reddit 2026-06-30 disclosure"
        severity = "critical"

    strings:
        // "Today's date is 2026/07/06" with slash separator and any apostrophe variant
        $today_slash_ascii = /Today's?\s+date\s+is\s+\d{4}\/\d{2}\/\d{2}/i
        $today_slash_02bc = /Todayʼs?\s+date\s+is\s+\d{4}\/\d{2}\/\d{2}/i
        $today_slash_02b9 = /Todayʹs?\s+date\s+is\s+\d{4}\/\d{2}\/\d{2}/i
        $today_slash_2019 = /Today’s?\s+date\s+is\s+\d{4}\/\d{2}\/\d{2}/i

        // Slash-format date in code context
        $date_slash_code = /\d{4}\/\d{2}\/\d{2}/

    condition:
        any of ($today_slash_*) or ($date_slash_code and filesize < 100KB)
}

rule Claude_Code_Backdoor_Apostrophe_Variant {
    meta:
        description = "Detects Claude Code apostrophe variant steganography"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "critical"

    strings:
        // Non-ASCII apostrophe variants used for 'hit type' encoding
        $apos_02bc = { CA 02 }    // U+02BC in UTF-8 (ʼ MODIFIER LETTER APOSTROPHE)
        $apos_02b9 = { B9 02 }    // U+02B9 in UTF-8 (ʹ MODIFIER LETTER PRIME)
        $apos_2019 = { 19 20 }    // U+2019 in UTF-8 (’ RIGHT SINGLE QUOTATION MARK)

        // Context: "Today" + non-ASCII apostrophe
        $today_02bc = /Todayʼs?\s*date/i
        $today_02b9 = /Todayʹs?\s*date/i
        $today_2019 = /Today’s?\s*date/i

    condition:
        $today_02bc or $today_02b9 or $today_2019
}

rule Claude_Code_Backdoor_Timezone_Detection {
    meta:
        description = "Detects timezone-based geolocation logic"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "high"

    strings:
        $tz_shanghai = "Asia/Shanghai"
        $tz_urumqi = "Asia/Urumqi"
        $tz_beijing = "Asia/Beijing"
        $tz_env = "/etc/timezone"
        $tz_pattern = /timezone|time_zone|TZ\b/i nocase

    condition:
        any of ($tz_shanghai, $tz_urumqi, $tz_beijing) or
        ($tz_pattern and any of ($tz_shanghai, $tz_urumqi, $tz_env))
}

rule Claude_Code_Backdoor_CN_Domain_Blacklist {
    meta:
        description = "Detects Chinese company domain blacklists"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "critical"

    strings:
        $alibaba = "alibaba" nocase
        $bytedance = "bytedance" nocase
        $baidu = "baidu" nocase
        $tencent = "tencent" nocase
        $moonshot = "moonshot" nocase
        $minimax = "minimax" nocase
        $zhipu = "zhipu" nocase
        $xiaomi = "xiaomi" nocase
        $huawei = "huawei" nocase
        $jd = "jd.com" nocase

    condition:
        // 5+ CN company keywords = likely blacklist
        (5 of ($alibaba, $bytedance, $baidu, $tencent, $moonshot,
                $minimax, $zhipu, $xiaomi, $huawei, $jd))
}
