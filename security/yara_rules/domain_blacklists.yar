/*
 * MAS-TS YARA Rules — Hidden Domain Blacklist Detection
 *
 * Detects hidden lists of domains/companies that may be used for
 * covert blocking or differential treatment based on user identity.
 */

rule CN_Company_Blacklist_Pattern {
    meta:
        description = "Detects Chinese company domain lists (potential blacklist)"
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
        $netease = "netease" nocase
        $meituan = "meituan" nocase
        $doubao = "doubao" nocase
        $qwen = "qwen" nocase
        $deepseek = "deepseek" nocase

    condition:
        // 5+ CN company keywords = likely blacklist
        5 of ($alibaba, $bytedance, $baidu, $tencent, $moonshot,
              $minimax, $zhipu, $xiaomi, $huawei, $jd,
              $netease, $meituan, $doubao, $qwen, $deepseek)
}

rule Domain_Block_Logic {
    meta:
        description = "Detects domain blocking logic in source code"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "high"

    strings:
        $block_1 = /block.*domain|domain.*block/is nocase
        $block_2 = /blacklist.*domain|domain.*blacklist/is nocase
        $block_3 = /deny.*domain|domain.*deny/is nocase
        $block_4 = /filter.*domain|domain.*filter/is nocase

    condition:
        any of ($block_1, $block_2, $block_3, $block_4) and filesize < 500KB
}

rule Proxy_Detection_Logic {
    meta:
        description = "Detects proxy/VPN detection logic"
        author = "MAS-TS"
        date = "2026-07-06"
        severity = "high"

    strings:
        $proxy_1 = /proxy.*detect|detect.*proxy/is nocase
        $proxy_2 = /vpn.*detect|detect.*vpn/is nocase
        $proxy_3 = /ANTHROPIC_BASE_URL/is
        $proxy_4 = /base_url.*proxy|proxy.*base_url/is nocase
        $proxy_5 = /HTTP_PROXY|HTTPS_PROXY/is

    condition:
        any of ($proxy_1, $proxy_2, $proxy_3, $proxy_4, $proxy_5) and filesize < 500KB
}
