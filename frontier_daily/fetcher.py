"""前沿文献日报 · 抓取层
OpenAlex(核心) + PubMed + arXiv 补充，指标(被引量/百分位/IF)解析与多入口链接构建。
"""

import json
import os
import random
import re
import ssl
import time
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from .config import DOMAINS, PUBMED_QUERIES, MAX_PER_QUERY, UA, MAILTO

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_UA = UA

_IF_CACHE = None
_IF_STRIPPED = None


def load_impact_factors():
    global _IF_CACHE, _IF_STRIPPED
    if _IF_CACHE is not None:
        return _IF_CACHE, _IF_STRIPPED
    path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "data", "jcr_if.json"))
    try:
        with open(path, encoding="utf-8") as f:
            _IF_CACHE = json.load(f)
    except Exception:
        _IF_CACHE = {}
    _IF_STRIPPED = {}
    for name, val in _IF_CACHE.items():
        s = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
        if s:
            _IF_STRIPPED.setdefault(s, val)
    return _IF_CACHE, _IF_STRIPPED


def get_impact_factor(journal):
    if not journal:
        return None
    mapping, stripped = load_impact_factors()
    j = journal.strip().lower()
    if j in mapping:
        return mapping[j]
    j = re.split(r"\s*[:=|]\s*", j)[0].strip()
    j = re.sub(r"\s*\([^)]*\)\s*", " ", j).strip()
    if j in mapping:
        return mapping[j]
    if j in stripped:
        return stripped[j]
    return None


def _req(url, timeout=45, retries=3):
    """带限流退避的请求。429/403 时读取 Retry-After：短则等待重试，长则直接放弃。"""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            return urllib.request.urlopen(req, timeout=timeout, context=_CTX)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 403, 503, 408):
                retry_after = None
                try:
                    retry_after = int(e.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    retry_after = None
                if retry_after and retry_after >= 120:
                    print(f"    [SKIP] {e.code} 冷却 {retry_after}s，放弃本轮")
                else:
                    wait = (retry_after if retry_after else 4 * (attempt + 1))
                    wait += random.random()
                    print(f"    [RETRY] {e.code} 退避 {wait:.0f}s")
                    time.sleep(wait)
                    continue
            raise
    raise last


def _decode_abstract(inverted_index):
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words.keys()))


def _extract_doi(work):
    doi = (work.get("doi") or "").replace("https://doi.org/", "").strip()
    return doi


def _extract_ids(work):
    ids = work.get("ids") or {}
    openalex_id = (ids.get("openalex") or work.get("id") or "").replace(
        "https://openalex.org/", "")
    pmid = ""
    m = re.search(r"(\d+)", ids.get("pmid") or "")
    if m:
        pmid = m.group(1)
    pmcid = ""
    m = re.search(r"(PMC\d+)", ids.get("pmcid") or "")
    if m:
        pmcid = m.group(1)
    arxiv_id = ""
    loc = work.get("primary_location") or {}
    landing = loc.get("landing_page_url") or ""
    if "arxiv.org" in (landing or ""):
        m = re.search(r"arxiv\.org/(?:abs|pdf)/([^#?]+)", landing)
        if m:
            arxiv_id = m.group(1).strip()
    return {"openalex": openalex_id, "pmid": pmid, "pmcid": pmcid,
            "arxiv": arxiv_id}


def _build_links(paper):
    doi = paper.get("doi") or ""
    pmid = paper.get("pmid") or ""
    pmcid = paper.get("pmcid") or ""
    links = {}
    if doi:
        links["DOI"] = f"https://doi.org/{doi}"
        links["OA全文"] = f"https://unpaywall.org/https://doi.org/{doi}"
    if paper.get("openalex"):
        links["OpenAlex"] = f"https://openalex.org/{paper['openalex']}"
    if pmid:
        links["PubMed"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        links["EuropePMC"] = f"https://europepmc.org/article/MED/{pmid}"
    if pmcid:
        links["PMC"] = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    if paper.get("arxiv"):
        links["arXiv"] = f"https://arxiv.org/abs/{paper['arxiv']}"
    return links


def _manual_links(paper):
    t = urllib.parse.quote(paper.get("title") or "")
    return {
        "Web of Science": "https://www.webofscience.com/",
        "ResearchGate": f"https://www.researchgate.net/search?q={t}",
        "WorldCat": f"https://search.worldcat.org/search?q={t}",
        "LibGen": f"https://libgen.is/?req={t}&column=def",
    }


def _make_paper(domain, title="", doi="", abstract="", publication_date="",
                journal="", authors=None, openalex_id="", pmid="",
                pmcid="", arxiv="", cited_by_count=None,
                cited_percentile=None):
    if authors is None:
        authors = []
    p = {
        "source": "OpenAlex",
        "domain": domain,
        "title": title,
        "doi": doi,
        "abstract": abstract,
        "publication_date": publication_date,
        "journal": journal,
        "impact_factor": get_impact_factor(journal),
        "authors": authors,
        "openalex": openalex_id,
        "pmid": pmid,
        "pmcid": pmcid,
        "arxiv": arxiv,
        "cited_by_count": cited_by_count,
        "cited_percentile": cited_percentile,
    }
    p["links"] = _build_links(p)
    p["manual_links"] = _manual_links(p)
    return p


def _parse_work(work, domain):
    journal = (((work.get("primary_location") or {}).get("source") or {})
               .get("display_name") or "")
    stats = work.get("cited_by_percentile_year") or {}
    pctl = stats.get("max")
    if pctl is not None and pctl <= 0:
        pctl = None
    ids = _extract_ids(work)
    authors = []
    for a in work.get("authorships", []):
        n = (a.get("author") or {}).get("display_name", "")
        if n:
            authors.append(n)
    return _make_paper(
        domain=domain,
        title=work.get("title", ""),
        doi=_extract_doi(work),
        abstract=_decode_abstract(work.get("abstract_inverted_index")),
        publication_date=work.get("publication_date", ""),
        journal=journal,
        authors=authors,
        openalex_id=ids["openalex"],
        pmid=ids["pmid"],
        pmcid=ids["pmcid"],
        arxiv=ids["arxiv"],
        cited_by_count=work.get("cited_by_count"),
        cited_percentile=pctl,
    )


_SELECT = ("id,doi,title,type,publication_date,cited_by_count,"
           "cited_by_percentile_year,authorships,primary_location,ids,"
           "abstract_inverted_index")


# 常规非期刊来源噪声音词（机构库/数据仓储/非评审预印本等）
_VENUE_BLACKLIST = (
    "research square", "ssrn", "zenodo", "figshare", "osf", "digital commons",
    "escholarship", "dspace repository", "preprints.org", "openreview",
    "openalex", "department of ", "repository", "europe pmc", "pubmed central",
    "cureus", "medrxiv", "biorxiv",
)


def _venue_ok(work):
    typ = work.get("type")
    if typ not in ("article", "review", "preprint", "letter", "editorial"):
        return False
    if work.get("is_paratext"):
        return False
    source = (work.get("primary_location") or {}).get("source") or {}
    display = (source.get("display_name") or "") + " " + source.get("type", "")
    low = display.lower()
    if any(b in low for b in _VENUE_BLACKLIST):
        return False
    return True


def _fetch_openalex_domain(domain, date_from, date_to):
    """一个领域的所有检索入口合并，返回论文列表。"""
    papers = []
    base = "https://api.openalex.org/works"
    filter_common = (f"from_publication_date:{date_from},"
                     f"to_publication_date:{date_to}")

    for cid in (domain.get("concept_ids") or []):
        flt = f"{filter_common},concepts.id:{cid}"
        url = (f"{base}?filter={urllib.parse.quote(flt, safe=',:')}"
               f"&sort=cited_by_count:desc&per_page={MAX_PER_QUERY}"
               f"&mailto={MAILTO}&select={_SELECT}")
        try:
            data = json.loads(_req(url).read().decode())
        except Exception as e:
            print(f"    [WARN] OpenAlex concept query error: {e}")
            continue
        for w in data.get("results", []):
            if _venue_ok(w):
                papers.append(_parse_work(w, domain.get("name", "")))
        time.sleep(0.5)

    for query in (domain.get("search_queries") or []):
        url = (f"{base}?filter={urllib.parse.quote(filter_common, safe=',:')}"
               f"&search={urllib.parse.quote(query)}"
               f"&sort=publication_date:desc&per_page={MAX_PER_QUERY}"
               f"&mailto={MAILTO}&select={_SELECT}")
        try:
            data = json.loads(_req(url).read().decode())
        except Exception as e:
            print(f"    [WARN] OpenAlex search query error: {e}")
            continue
        for w in data.get("results", []):
            if _venue_ok(w):
                papers.append(_parse_work(w, domain.get("name", "")))
        time.sleep(0.5)

    print(f"  [OpenAlex:{domain['name']}] {len(papers)} papers")
    return papers


# ── PubMed 补充 ─────────────────────────────────────────────────────

def _fetch_pubmed_domain(domain_name, date_from, date_to):
    df = date_from.replace("-", "/")
    dt = date_to.replace("-", "/")
    parts = PUBMED_QUERIES.get(domain_name) or []
    if not parts:
        return []
    qs = " OR ".join(f"({p})" for p in parts)
    term = f"({qs}) AND ({df}[Date - Publication] : {dt}[Date - Publication])"
    url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
           f"?db=pubmed&term={urllib.parse.quote(term)}"
           f"&retmax={MAX_PER_QUERY}&retmode=json&sort=pub+date")
    try:
        data = json.loads(_req(url).read().decode())
    except Exception as e:
        print(f"    [WARN] PubMed esearch error: {e}")
        return []
    id_list = data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return []
    efetch = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
              f"?db=pubmed&id={','.join(id_list)}&retmode=xml")
    try:
        xml_data = _req(efetch).read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    [WARN] PubMed efetch error: {e}")
        return []

    papers = []
    root = ET.fromstring(xml_data)
    for art in root.findall(".//PubmedArticle"):
        try:
            medline = art.find(".//MedlineCitation")
            if medline is None:
                continue
            article = medline.find(".//Article")
            pmid = medline.findtext("PMID", "")
            title = article.findtext("ArticleTitle", "")
            doi = ""
            for eid in medline.findall(".//ArticleIdList/ArticleId"):
                if eid.get("IdType") == "doi":
                    doi = eid.text or ""
                    break
            abstract = " ".join("".join(x.itertext())
                                for x in art.findall(".//AbstractText"))
            journal = ""
            je = article.find("Journal")
            if je is not None:
                journal = je.findtext("Title", "")
            pub_date = ""
            ji = article.find("Journal/JournalIssue")
            if ji is not None:
                pd = ji.find("PubDate")
                if pd is not None:
                    y = pd.findtext("Year", "")
                    m = pd.findtext("Month", "")
                    d = pd.findtext("Day", "")
                    if y:
                        pub_date = y
                        mm = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04",
                              "May":"05","Jun":"06","Jul":"07","Aug":"08",
                              "Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
                        if m:
                            pub_date += "-" + mm.get(m[:3], m.zfill(2))
                        if d:
                            pub_date += "-" + d.zfill(2)
            authors = []
            for a in article.findall(".//Author"):
                ln = a.findtext("LastName", "")
                fn = a.findtext("ForeName", "")
                if ln:
                    authors.append(f"{fn} {ln}".strip())
            p = _make_paper(
                domain=domain_name, title=title, doi=doi, abstract=abstract,
                publication_date=pub_date, journal=journal, authors=authors,
                pmid=pmid,
            )
            p["source"] = "PubMed"
            papers.append(p)
        except Exception:
            continue
    print(f"  [PubMed] {domain_name} {len(papers)} papers")
    return papers


# ── arXiv 补充 ──────────────────────────────────────────────────────

ARXIV_CATS = ["cs.HC", "cs.AI", "cs.LG", "cs.NE", "eess.SP", "eess.IV",
              "q-bio.BM", "q-bio.NC", "physics.med-ph", "cs.RO", "cs.CV"]


def _fetch_arxiv(date_from, date_to):
    df = date_from.replace("-", "")
    dt = date_to.replace("-", "")
    cat_q = "+OR+".join(f"cat:{c}" for c in ARXIV_CATS)
    query = (f"({cat_q})+AND+submittedDate:[{df}0000+TO+{dt}2359]"
             "+AND+(brain-computer+OR+wearable+OR+medical+device+OR+neural)")
    url = (f"https://export.arxiv.org/api/query?search_query={query}"
           f"&max_results=60&sortBy=submittedDate&sortOrder=descending")
    try:
        xml_data = _req(url, timeout=60).read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    [WARN] arXiv API error: {e}")
        return []
    ns = {"a": "http://www.w3.org/2005/Atom",
          "ar": "http://arxiv.org/schemas/atom"}
    papers = []
    root = ET.fromstring(xml_data)
    for entry in root.findall("a:entry", ns):
        try:
            title = entry.findtext("a:title", "", ns).replace("\n", " ").strip()
            summary = entry.findtext("a:summary", "", ns).replace("\n", " ").strip()
            arxiv_id = ""
            for link in entry.findall("a:link", ns):
                if link.get("rel") == "alternate":
                    arxiv_id = link.get("href", "")
                    break
            doi = ""
            for link in entry.findall("a:link", ns):
                if "doi.org" in link.get("href", ""):
                    doi = link.get("href", "").split("doi.org/")[-1]
                    break
            authors = [e.findtext("a:name", "", ns)
                       for e in entry.findall("a:author", ns) if e.findtext("a:name", "", ns)]
            p = _make_paper(
                domain="", title=title, doi=doi, abstract=summary,
                publication_date=entry.findtext("a:published", "", ns)[:10],
                journal="arXiv", authors=authors, arxiv=arxiv_id,
            )
            p["domain"] = "arXiv"
            p["source"] = "arXiv"
            papers.append(p)
        except Exception:
            continue
    print(f"  [arXiv] {len(papers)} papers")
    return papers


# ── 去重 ────────────────────────────────────────────────────────────

def _deduplicate(papers):
    seen_dois, seen_titles = set(), set()
    unique = []
    for p in papers:
        doi = (p.get("doi") or "").strip().lower()
        if doi:
            if doi in seen_dois:
                continue
            seen_dois.add(doi)
            unique.append(p)
            continue
        title = (p.get("title") or "").strip().lower().replace(" ", "")
        if title:
            if title in seen_titles:
                continue
            seen_titles.add(title)
        unique.append(p)
    return unique


# ── 入口 ───────────────────────────────────────────────────────────

def _enrich_semantic_scholar(papers, max_batch=500):
    """Semantic Scholar 交叉校验（尽力而为），失败自动跳过。"""
    dois = [p.get("doi") for p in papers if p.get("doi")]
    if not dois:
        return
    try:
        body = json.dumps({"ids": dois[:max_batch]}).encode()
        req = urllib.request.Request(
            "https://api.semanticscholar.org/graph/v1/paper/batch"
            "?fields=citationCount,title,externalIds,url",
            data=body,
            headers={"User-Agent": _UA, "Content-Type": "application/json"},
            method="POST",
        )
        data = json.loads(urllib.request.urlopen(req, timeout=60,
                           context=_CTX).read().decode())
        s2 = {}
        for row in data:
            if not row:
                continue
            doi = (row.get("externalIds") or {}).get("DOI", "")
            if doi:
                s2[doi.lower()] = row.get("citationCount")
        for p in papers:
            key = (p.get("doi") or "").strip().lower()
            v = s2.get(key)
            if v:
                p["s2_citations"] = v
        n = sum(1 for p in papers if p.get("s2_citations") is not None)
        print(f"  [Semantic Scholar] enriched {n} papers")
    except Exception as e:
        print(f"  [WARN] Semantic Scholar enrichment skipped: {e}")


def fetch_papers(date_from, date_to, include_pubmed=True):
    all_papers = []
    for domain in DOMAINS:
        all_papers += _fetch_openalex_domain(domain, date_from, date_to)
        if include_pubmed:
            try:
                all_papers += _fetch_pubmed_domain(domain["name"], date_from, date_to)
            except Exception as e:
                print(f"    [WARN] PubMed {domain['name']} failed: {e}")
        time.sleep(0.3)

    try:
        all_papers += _fetch_arxiv(date_from, date_to)
    except Exception as e:
        print(f"    [WARN] arXiv failed: {e}")

    before = len(all_papers)
    all_papers = _deduplicate(all_papers)
    if before - len(all_papers):
        print(f"  [Dedup] removed {before - len(all_papers)} duplicates")
    _enrich_semantic_scholar(all_papers)
    print(f"[TOTAL] {len(all_papers)} papers")
    return all_papers