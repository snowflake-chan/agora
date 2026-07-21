import re
import unicodedata


_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)

# This is a high-confidence preflight guard. Ambiguous administrative words are
# left to the contextual classifier so product/community language is not blocked.
_CJK_TERMS = (
    "\u653f\u7b56",
    "\u6cd5\u5f8b",
    "\u6cd5\u89c4",
    "\u6cd5\u898f",
    "\u7acb\u6cd5",
    "\u53f8\u6cd5",
    "\u5baa\u6cd5",
    "\u61b2\u6cd5",
    "\u4eba\u6c11\u653f\u5e9c",
    "\u515a\u59d4",
    "\u9ee8\u59d4",
    "\u515a\u652f\u90e8",
    "\u9ee8\u652f\u90e8",
    "\u4eba\u5927\u4ee3\u8868",
    "\u653f\u534f\u59d4\u5458",
    "\u653f\u5354\u59d4\u54e1",
    "\u516c\u5b89\u673a\u5173",
    "\u516c\u5b89\u6a5f\u95dc",
    "\u7f51\u4fe1\u529e",
    "\u7db2\u4fe1\u8fa6",
    "\u5916\u4ea4\u90e8",
    "\u56fd\u9632\u90e8",
    "\u570b\u9632\u90e8",
    "\u56fd\u53f0\u529e",
    "\u570b\u81fa\u8fa6",
    "\u5ba3\u4f20\u90e8",
    "\u5ba3\u50b3\u90e8",
    "\u7edf\u6218",
    "\u7d71\u6230",
    "\u7eaa\u59d4",
    "\u7d00\u59d4",
    "\u76d1\u5bdf\u59d4",
    "\u76e3\u5bdf\u59d4",
    "\u516c\u52a1\u5458",
    "\u516c\u52d9\u54e1",
    "\u653f\u52a1",
    "\u653f\u52d9",
    "\u6cd5\u6848",
    "\u884c\u653f\u547d\u4ee4",
    "\u4eba\u6743",
    "\u4eba\u6b0a",
    "\u7ef4\u6743",
    "\u7dad\u6b0a",
    "\u516c\u6295",
    "\u5236\u88c1",
    "\u4e60\u8fd1\u5e73",
    "\u6bdb\u6cfd\u4e1c",
    "\u9093\u5c0f\u5e73",
    "\u6c5f\u6cfd\u6c11",
    "\u80e1\u9526\u6d9b",
    "\u674e\u5f3a",
    "\u848b\u4ecb\u77f3",
    "\u8521\u82f1\u6587",
    "\u8d56\u6e05\u5fb7",
    "\u666e\u4eac",
    "\u62dc\u767b",
    "\u7279\u6717\u666e",
    "\u8fde\u4efb",
    "\u9023\u4efb",
    "\u5019\u9009\u4eba",
    "\u5019\u9078\u4eba",
    "政治",
    "政府",
    "政党",
    "政黨",
    "共产党",
    "共產黨",
    "中国共产党",
    "中國共產黨",
    "中共",
    "国家主席",
    "國家主席",
    "总书记",
    "總書記",
    "国务院",
    "國務院",
    "全国人大",
    "全國人大",
    "人民代表大会",
    "人民代表大會",
    "政协",
    "政協",
    "两会",
    "兩會",
    "选举",
    "選舉",
    "官员",
    "官員",
    "领导人",
    "領導人",
    "总统",
    "總統",
    "首相",
    "国会",
    "國會",
    "议会",
    "議會",
    "外交",
    "主权",
    "主權",
    "领土争端",
    "領土爭端",
    "地缘政治",
    "地緣政治",
    "抗议",
    "抗議",
    "示威",
    "政权",
    "政權",
    "意识形态",
    "意識形態",
    "政治审查",
    "政治審查",
    "国家安全法",
    "國家安全法",
    "一国两制",
    "一國兩制",
    "两岸关系",
    "兩岸關係",
    "台湾独立",
    "台灣獨立",
    "香港国安",
    "香港國安",
    "西藏独立",
    "西藏獨立",
    "天安门",
    "天安門",
    "六四",
    "军队",
    "軍隊",
    "军事",
    "軍事",
    "战争",
    "戰爭",
    "選挙",
    "政党",
    "国会",
    "大統領",
    "主権",
    "軍事",
    "戦争",
)

# These words are political only when another term supplies real political
# context. For example, 候選人 is also the faithful translation of a release
# candidate, and 政策 is commonly used for product policy.
_CONTEXTUAL_CJK_TERMS = frozenset(
    {
        "制裁",
        "候选人",
        "候選人",
        "连任",
        "連任",
    }
)

_NON_POLITICAL_CJK_PHRASES = (
    "产品政策",
    "產品政策",
    "隐私政策",
    "隱私政策",
    "退款政策",
    "平台政策",
    "社区政策",
    "社群政策",
    "公司政策",
    "企业政策",
    "企業政策",
    "公司内部政策",
    "公司內部政策",
    "企业内部政策",
    "企業內部政策",
    "团队内部政策",
    "團隊內部政策",
    "部署政策",
    "产品安全政策",
    "產品安全政策",
    "平台安全政策",
    "公司安全政策",
    "产品内容政策",
    "產品內容政策",
    "平台内容政策",
    "平台內容政策",
    "产品使用政策",
    "產品使用政策",
    "数据保留政策",
    "資料保留政策",
    "缓存保留政策",
    "快取保留政策",
)

# Product-policy phrases are safe only when they are not qualified by a public
# jurisdiction. Keep scoped phrases intact so the ordinary political terms
# below still block them before any text is sent to the external provider.
_CJK_POLITICAL_SCOPE_TERMS = (
    "国家",
    "國家",
    "中国",
    "中國",
    "全国",
    "全國",
    "中央",
    "政府",
    "官方",
    "公共部门",
    "公共部門",
    "联邦",
    "聯邦",
    "省级",
    "省級",
    "地方政府",
    "监管",
    "監管",
    "立法",
    "行政机关",
    "行政機關",
)
_CJK_SCOPE_WINDOW = 8


def _strip_unscoped_product_policy_phrases(compact: str) -> str:
    stripped = compact
    for phrase in sorted(_NON_POLITICAL_CJK_PHRASES, key=len, reverse=True):
        search_from = 0
        while True:
            start = stripped.find(phrase, search_from)
            if start < 0:
                break
            end = start + len(phrase)
            context = stripped[
                max(0, start - _CJK_SCOPE_WINDOW) : min(
                    len(stripped), end + _CJK_SCOPE_WINDOW
                )
            ]
            if any(scope in context for scope in _CJK_POLITICAL_SCOPE_TERMS):
                search_from = end
                continue
            stripped = stripped[:start] + stripped[end:]
    return stripped

_ENGLISH_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bpolitic(?:s|al|ian|ians)?\b",
        r"\bgovernment(?:s|al)?\b",
        r"\bpresidential election\b",
        r"\bpresident of (?:the )?[a-z]",
        r"\bprime minister\b",
        r"\bpublic officials?\b",
        r"\belection(?:s|eering)?\b",
        r"\bpolitical part(?:y|ies)\b",
        r"\b(?:congress|parliament|senate)\b",
        r"\blegislat(?:ion|ive|ure)\b",
        r"\b(?:government|public|state|federal|national) regulat(?:ion|ions|ory)\b",
        r"\b(?:eu|european union) regulat(?:ion|ions|ory)\b",
        r"\bconstitutional?(?:ly)?\b",
        r"\bjudiciar(?:y|ies)\b",
        r"\blawmakers?\b",
        r"\b(?:civil|human) rights?\b",
        r"\beconomic sanctions?\b",
        r"\bpublic polic(?:y|ies)\b",
        r"\bsovereignt(?:y|ies)\b",
        r"\bterritorial dispute(?:s)?\b",
        r"\bgeopolitic(?:s|al)?\b",
        r"\bdiplomac(?:y|ies|tic)\b",
        r"\bmilitar(?:y|ies)\b",
        r"\barmed conflict(?:s)?\b",
        r"\bprotest(?:s|er|ers|ing)?\b",
        r"\bpolitical ideolog(?:y|ies)\b",
        r"\bpolitical censorship\b",
        r"\bcommunist part(?:y|ies)\b",
        r"\b(?:ccp|cpc)\b",
        r"\bdemocratic party\b",
        r"\brepublican party\b",
        r"\b(?:xi jinping|mao zedong|deng xiaoping|putin)\b",
        r"\b(?:serve|seek|stand for) another term\b",
        r"\bre-?elect(?:ion|ed|ing)?\b",
        r"\b(?:head|leader) of state\b",
    )
)


def contains_political_signals(text: str) -> bool:
    """Identify high-confidence political text before API egress."""
    normalized = unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)
    compact = "".join(char for char in normalized if char.isalnum())
    political_compact = _strip_unscoped_product_policy_phrases(compact)
    if any(
        term in political_compact
        for term in _CJK_TERMS
        if term not in _CONTEXTUAL_CJK_TERMS
    ):
        return True
    if sum(term in political_compact for term in _CONTEXTUAL_CJK_TERMS) >= 2:
        return True
    return any(pattern.search(normalized) for pattern in _ENGLISH_PATTERNS)
