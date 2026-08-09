"""前沿文献日报配置：四大领域 + 检索规则"""

REPORT_TITLE = "前沿文献日报"
SCOPE = "生物医药 · 医疗器械 · 可穿戴设备 · 脑机接口（全球）"

TARGET_TZ_OFFSET = 8  # 北京时间

# 每条文献的入口链接。manual=True 表示需订阅/登录或注意版权，仅在报告中标示不出指标
ENTRY_LINKS = [
    {"key": "DOI", "label": "DOI", "manual": False},
    {"key": "OpenAlex", "label": "OpenAlex", "manual": False},
    {"key": "PubMed", "label": "PubMed", "manual": False},
    {"key": "PMC", "label": "PMC全文", "manual": False},
    {"key": "EuropePMC", "label": "Europe PMC", "manual": False},
    {"key": "arXiv", "label": "arXiv", "manual": False},
    {"key": "OA全文", "label": "OA(Unpaywall)", "manual": False},
    {"key": "Web of Science", "label": "Web of Science", "manual": True,
     "note": "需机构订阅"},
    {"key": "ResearchGate", "label": "ResearchGate", "manual": True,
     "note": "需登录"},
    {"key": "WorldCat", "label": "WorldCat", "manual": True,
     "note": "馆藏检索"},
    {"key": "LibGen", "label": "Library Genesis", "manual": True,
     "note": "注意版权"},
]

# OpenAlex `title_and_abstract.search` 检索词（每个领域多个查询词，跑完后合并去重）
DOMAINS = [
    {
        "name": "生物医药",
        "concept_ids": ["C66782513"],
        "search_queries": [
            "drug delivery", "immunotherapy", "gene therapy",
            "precision medicine", "nanomedicine", "clinical trial",
            "biomarker",
        ],
    },
    {
        "name": "医疗器械",
        "concept_ids": [],
        "search_queries": [
            "medical device", "surgical robot", "implantable device",
            "prosthetic OR pacemaker OR stent", "point-of-care diagnostic",
            "lab-on-a-chip",
        ],
    },
    {
        "name": "可穿戴设备",
        "concept_ids": ["C54290928"],
        "search_queries": [
            "wearable", "electronic skin", "health monitoring",
            "biosensor", "continuous glucose monitoring",
            "flexible sensor",
        ],
    },
    {
        "name": "脑机接口",
        "concept_ids": ["C173201364"],
        "search_queries": [
            "brain-computer interface", "brain machine interface",
            "neural decoding", "ECoG", "intracortical electrode",
            "neuroprosthesis",
        ],
    },
]

# PubMed 关键词（医疗器械/可穿戴/脑机接口 走 PubMed 补充遗漏，按标题/摘要匹配）
PUBMED_QUERIES = {
    "医疗器械": ["medical device", "surgical robot", "implantable",
                 "pacemaker OR stent OR catheter"],
    "可穿戴设备": ["wearable", "e-skin OR electronic skin",
                     "smartwatch OR activity monitor", "continuous glucose monitor"],
    "脑机接口": ["brain-computer interface", "brain machine interface OR BCI",
                "neural decoding OR ECoG", "intracortical OR neuroprosthes"],
}

# 每领域每查询最多取多少篇
MAX_PER_QUERY = 40

# 数据来源水印（README/报告页脚用）
SOURCES_NOTE = ("自动抓取: OpenAlex(聚合 Crossref/Scopus/PubMed/arXiv 等) · PubMed · arXiv；"
                "指标: 被引量/被引百分位来自 OpenAlex，期刊 IF 来自本地 JCR 2024 映射表；"
                "Web of Science / ResearchGate / WorldCat / Library Genesis 仅提供检索入口，"
                "需订阅或人工访问。")

UA = "Frontier-Paper-Daily/1.0 (mailto:frontier-daily@example.com)"
# OpenAlex 礼貌池邮箱参数（提升每日额度）
MAILTO = "frontier-daily@example.com"