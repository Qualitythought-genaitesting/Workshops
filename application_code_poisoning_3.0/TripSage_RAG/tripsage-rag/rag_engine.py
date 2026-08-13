"""
TripSage RAG engine — pure Python standard library only.

Pipeline for every question:
  1. Input guardrails  (prompt injection / jailbreak / unsafe / data-leakage / bias)
  2. Retrieve          (TF-IDF cosine over the chunked knowledge base = the "vector database")
  3. Ground / abstain  (answer only from retrieved chunks, else say "I don't know")
  4. Output guardrails (strip indirect injections found in chunks, redact PII)

Every action is written to logs/tripsage.log (human readable) and logs/trace.jsonl
(one JSON record per request) so testers can see exactly what happened behind the scenes.
"""
import os, re, json, math, time, csv, logging
from logging.handlers import RotatingFileHandler

BASE = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE, "kb")
POISON_DIR = os.path.join(BASE, "kb_poison")
LOG_DIR = os.path.join(BASE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ----------------------------------------------------------------------------- logging
logger = logging.getLogger("tripsage")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = RotatingFileHandler(os.path.join(LOG_DIR, "tripsage.log"), maxBytes=1_000_000, backupCount=3)
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-5s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
    logger.addHandler(sh)

TRACE_FILE = os.path.join(LOG_DIR, "trace.jsonl")
JUDGE_FILE = os.path.join(LOG_DIR, "relevance_judgments.csv")
RETRIEVAL_FILE = os.path.join(LOG_DIR, "retrieval_eval.csv")

def write_trace(record):
    record["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def record_judgment(query, chunk_id, doc, verdict, tester):
    new = not os.path.exists(JUDGE_FILE)
    with open(JUDGE_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "tester", "query", "chunk_id", "doc", "verdict"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), tester, query, chunk_id, doc, verdict])
    logger.info("JUDGE   tester=%s chunk=%s verdict=%s  query=%r", tester, chunk_id, verdict, query)

# ----------------------------------------------------------------------------- tokenizer
_word = re.compile(r"[a-z0-9]+")
def tokenize(text):
    return _word.findall(text.lower())

STOP = set(("a an the this that these those is are was were be been being of for to in on at by with from "
            "as and or but if then else than so do does did done i me my we our us you your he she it its "
            "they them their what which who whom whose when where why how can could should would may might "
            "will shall must need needs about into over under between again more most some any all no not "
            "only just very please tell show give list get got have has had").split())

# Minimum fraction of meaningful query terms that must appear in the top retrieved
# chunks for the assistant to answer; below this it abstains (out-of-KB guard).
COVERAGE_MIN = 0.34

# ----------------------------------------------------------------------------- chunking
def _split_markdown(text):
    """Split a markdown doc into (section_title, body) blocks by headings."""
    blocks, title, buf = [], "Overview", []
    for line in text.splitlines():
        if line.startswith("#"):
            if buf:
                blocks.append((title, "\n".join(buf).strip()))
                buf = []
            title = line.lstrip("# ").strip() or title
        else:
            buf.append(line)
    if buf:
        blocks.append((title, "\n".join(buf).strip()))
    return [(t, b) for t, b in blocks if b]

def chunk_document(doc_name, text, max_chars=600):
    """Turn one document into small, retrievable chunks. Logs every chunk."""
    meta = {}
    m = re.search(r"last_updated:\s*(.+)", text)
    if m:
        meta["last_updated"] = m.group(1).strip()
    text = re.sub(r"(?m)^\s*last_updated:.*$", "", text)  # keep metadata out of retrievable text
    chunks = []
    for section, body in _split_markdown(text):
        # further split long sections on blank lines / size
        paras, cur = [], ""
        for para in re.split(r"\n\s*\n", body):
            para = para.strip()
            if not para:
                continue
            if len(cur) + len(para) + 1 <= max_chars:
                cur = (cur + "\n" + para).strip()
            else:
                if cur:
                    paras.append(cur)
                cur = para
        if cur:
            paras.append(cur)
        for i, p in enumerate(paras):
            cid = "%s#%s-%d" % (doc_name, re.sub(r"\W+", "_", section.lower())[:24], i)
            chunks.append({"id": cid, "doc": doc_name, "section": section,
                           "text": p, "last_updated": meta.get("last_updated", "")})
    logger.info("CHUNK   %-26s -> %d chunk(s)", doc_name, len(chunks))
    return chunks

# ----------------------------------------------------------------------------- vector store (TF-IDF)
class VectorStore:
    """A tiny local 'vector database': TF-IDF vectors + cosine similarity, persisted to disk."""
    def __init__(self):
        self.chunks = []          # list of chunk dicts
        self.vectors = []         # list of {term: weight} normalised
        self.idf = {}

    def build(self, chunks):
        self.chunks = chunks
        N = len(chunks)
        df = {}
        toks_all = []
        for c in chunks:
            # Index the chunk body + its section heading + the document name
            # (underscores -> spaces) so a query naming the place/airline/hotel
            # ranks that document's chunks first (e.g. "best time to visit Tokyo").
            doc_words = c["doc"].replace("POISON_", "").replace("_", " ")
            toks = tokenize(c["text"] + " " + c["section"] + " " + doc_words)
            toks_all.append(toks)
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log((N + 1) / (dfi + 1)) + 1.0 for t, dfi in df.items()}
        self.max_idf = (max(self.idf.values()) + 1.0) if self.idf else 1.0
        self.vectors = [self._vec(toks) for toks in toks_all]
        self._persist()
        logger.info("STORE   built vector index: %d chunks, %d vocabulary terms", N, len(self.idf))

    def _vec(self, toks):
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        v = {t: (1 + math.log(c)) * self.idf.get(t, 0.0) for t, c in tf.items()}
        norm = math.sqrt(sum(w * w for w in v.values())) or 1.0
        return {t: w / norm for t, w in v.items()}

    def query_vec(self, text):
        return self._vec(tokenize(text))

    def search(self, query, top_k):
        qv = self.query_vec(query)
        scored = []
        for i, cv in enumerate(self.vectors):
            # cosine = dot product (both normalised); iterate over smaller dict
            small, big = (qv, cv) if len(qv) < len(cv) else (cv, qv)
            s = sum(w * big.get(t, 0.0) for t, w in small.items())
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        results = []
        for s, i in scored[:top_k]:
            c = dict(self.chunks[i])
            c["score"] = round(s, 4)
            results.append(c)
        return results

    def _persist(self):
        # demonstrates "storing the data in the vector database"
        path = os.path.join(LOG_DIR, "vectorstore.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"chunks": self.chunks, "num_terms": len(self.idf)}, f, ensure_ascii=False, indent=1)
        logger.info("STORE   persisted vector store snapshot -> %s", os.path.relpath(path, BASE))

    # ---- vector database testing helpers ----
    @staticmethod
    def _cos(a, b):
        small, big = (a, b) if len(a) < len(b) else (b, a)
        return sum(w * big.get(t, 0.0) for t, w in small.items())

    def top_terms(self, i, n=6):
        return [t for t, _ in sorted(self.vectors[i].items(), key=lambda kv: kv[1], reverse=True)[:n]]

    def chunk_list(self, max_chars=600):
        out = []
        for i, c in enumerate(self.chunks):
            out.append({"id": c["id"], "doc": c["doc"], "section": c["section"],
                        "chars": len(c["text"]), "terms": len(self.vectors[i]),
                        "top_terms": self.top_terms(i),
                        "oversized": len(c["text"]) > max_chars, "empty": len(c["text"].strip()) == 0})
        return out

    def stats(self, max_chars=600):
        per_doc = {}
        for c in self.chunks:
            per_doc[c["doc"]] = per_doc.get(c["doc"], 0) + 1
        lens = [len(c["text"]) for c in self.chunks] or [0]
        oversized = [c["id"] for c in self.chunks if len(c["text"]) > max_chars]
        empty = [c["id"] for c in self.chunks if not c["text"].strip()]
        return {"num_chunks": len(self.chunks), "vocab": len(self.idf),
                "per_doc": [{"doc": d, "chunks": n} for d, n in sorted(per_doc.items())],
                "avg_chars": round(sum(lens) / len(lens)), "max_chars_chunk": max(lens),
                "oversized": oversized, "empty": empty,
                "duplicates": self.duplicates()}

    def duplicates(self, threshold=0.9):
        pairs = []
        n = len(self.vectors)
        for i in range(n):
            for j in range(i + 1, n):
                s = self._cos(self.vectors[i], self.vectors[j])
                if s >= threshold:
                    pairs.append({"a": self.chunks[i]["id"], "b": self.chunks[j]["id"], "cos": round(s, 3)})
        return sorted(pairs, key=lambda p: p["cos"], reverse=True)[:20]

# ----------------------------------------------------------------------------- guardrails
INJECTION = [
    r"ignore (all|your|the|previous|prior).{0,20}instruction", r"disregard .{0,20}(instruction|rule)",
    r"system prompt", r"reveal your", r"you are now", r"\bdan\b", r"no rules", r"do anything now",
    r"pretend you (are|have no|do not have)", r"developer mode", r"jailbreak", r"act as .{0,20}(unrestricted|no rules)",
    r"follow (this|these).{0,30}(base64|encoded|decode)", r"decode .{0,20}base64",
]
DATA_LEAK = [
    r"api[_ ]?key", r"another (customer|user|traveller|traveler|person)", r"someone else'?s (booking|itinerary|data)",
    r"other (customer|user)s? (booking|data)", r"\bconfig(uration)?\b", r"print your (system )?prompt",
    r"(show|list|give).{0,20}(all )?(users|customers|bookings)", r"passport number of",
]
UNSAFE = [
    r"fake (document|passport|visa|id)", r"forged", r"visa fraud", r"overstay", r"smuggl",
    r"bribe", r"without a visa illegally", r"evade (immigration|customs)", r"undetected",
]
BIAS = [
    r"which nationalit", r"most trouble", r"worst tourists", r"which (race|religion|group).{0,20}(better|worse|dangerous)",
    r"are .{0,20}(people|tourists) (bad|dangerous|criminal)",
]

def _match(patterns, text):
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return p
    return None

def input_guardrail(query):
    """Returns (action, category, reason, pattern). action in {allow, refuse}."""
    for cat, pats in (("prompt_injection", INJECTION), ("data_leakage", DATA_LEAK),
                      ("unsafe_request", UNSAFE), ("bias", BIAS)):
        p = _match(pats, query)
        if p:
            reasons = {
                "prompt_injection": "I can't follow instructions that try to change my rules or reveal my configuration. I can help with travel questions grounded in our knowledge base.",
                "data_leakage":     "I can't share other travellers' data or internal configuration. I can help with your own travel questions.",
                "unsafe_request":   "I can't help with unlawful or unsafe travel requests. I can help with legitimate travel information.",
                "bias":             "I won't generalise about people by nationality or group. I can share factual, sourced travel information for a specific destination.",
            }
            return "refuse", cat, reasons[cat], p
    return "allow", None, None, None

# PII patterns for output redaction
PII = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[redacted-email]"),
    (re.compile(r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"), "[redacted-phone]"),
    (re.compile(r"\b[A-Z]\d{7}\b"), "[redacted-passport]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[redacted-ssn]"),
]
def redact_pii(text):
    flags = []
    for rx, repl in PII:
        if rx.search(text):
            flags.append(repl)
            text = rx.sub(repl, text)
    return text, flags

# indirect injection hidden inside a retrieved chunk
INDIRECT = re.compile(r"(assistant\s*:|ignore .{0,20}instruction|reveal your|system prompt|email .{0,20}@)", re.IGNORECASE)

# ----------------------------------------------------------------------------- engine
class RAGEngine:
    def __init__(self, config):
        self.cfg = config
        self.store = VectorStore()
        self.kb_docs = []
        self.poison = False
        # When True, mitigations are active: indirect-injection instructions found
        # inside retrieved chunks are neutralised and poisoned provenance is flagged.
        # Set False to demonstrate the raw attack (how the poison malfunctions the app).
        self.defenses = bool(config.get("defenses", True))
        self.reindex(poison=config.get("poison_mode", False))

    def _load_docs(self, poison):
        docs = []
        for fn in sorted(os.listdir(KB_DIR)):
            if fn.endswith(".md"):
                with open(os.path.join(KB_DIR, fn), encoding="utf-8") as f:
                    docs.append((fn[:-3], f.read()))
        if poison and os.path.isdir(POISON_DIR):
            for fn in sorted(os.listdir(POISON_DIR)):
                if fn.endswith(".md"):
                    with open(os.path.join(POISON_DIR, fn), encoding="utf-8") as f:
                        docs.append(("POISON_" + fn[:-3], f.read()))
        return docs

    def reindex(self, poison=None):
        if poison is not None:
            self.poison = poison
        logger.info("INGEST  reindexing knowledge base (poison_mode=%s)", self.poison)
        docs = self._load_docs(self.poison)
        self.kb_docs = [d[0] for d in docs]
        all_chunks = []
        for name, text in docs:
            all_chunks.extend(chunk_document(name, text))
        self.store.build(all_chunks)
        return len(all_chunks)

    # ---- vector database testing ----
    def probe(self, query, top_k=None, expected=""):
        """Raw retrieval only (no guardrails / generation) — the vector-DB view.
        If `expected` (a doc name or chunk id) is given, report the rank/hit."""
        top_k = top_k or self.cfg.get("top_k", 4)
        hits = self.store.search(query, top_k=max(top_k, 10))
        rank = None
        exp = (expected or "").strip()
        if exp:
            for idx, h in enumerate(hits, 1):
                if h["id"] == exp or h["doc"] == exp or safe_kb_name(exp) == h["doc"]:
                    rank = idx; break
        verdict = None
        if exp:
            verdict = {"expected": exp, "rank": rank,
                       "hit_at_1": rank == 1, "hit_at_k": rank is not None and rank <= top_k}
        logger.info("PROBE   q='%s' top_k=%d expected=%s rank=%s",
                    query[:60], top_k, exp or "-", rank)
        return {"query": query, "top_k": top_k,
                "hits": [{"id": h["id"], "doc": h["doc"], "section": h["section"],
                          "score": h["score"], "text": h["text"]} for h in hits[:top_k]],
                "verdict": verdict}

    def eval_retrieval(self, cases, top_k=None):
        """Run a labelled query set and score retrieval: Hit@1, Hit@k, MRR."""
        top_k = top_k or self.cfg.get("top_k", 4)
        rows, hit1, hitk, rr = [], 0, 0, 0.0
        for c in cases:
            q = c.get("query", ""); exp = (c.get("expected_doc") or c.get("expected") or "").strip()
            hits = self.store.search(q, top_k=max(top_k, 10))
            rank = None
            for idx, h in enumerate(hits, 1):
                if h["doc"] == exp or h["id"] == exp or safe_kb_name(exp) == h["doc"]:
                    rank = idx; break
            h1 = rank == 1; hk = rank is not None and rank <= top_k
            hit1 += h1; hitk += hk; rr += (1.0 / rank if rank else 0.0)
            rows.append({"id": c.get("id", ""), "query": q, "expected": exp,
                         "rank": rank, "hit_at_1": h1, "hit_at_k": hk,
                         "top": hits[0]["id"] if hits else "-",
                         "top_score": hits[0]["score"] if hits else 0.0})
        n = len(cases) or 1
        summary = {"n": len(cases), "top_k": top_k,
                   "hit_at_1": round(hit1 / n, 3), "hit_at_k": round(hitk / n, 3),
                   "mrr": round(rr / n, 3), "misses": [r["id"] or r["query"][:30] for r in rows if r["rank"] is None]}
        # write evidence CSV
        new = not os.path.exists(RETRIEVAL_FILE)
        with open(RETRIEVAL_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "id", "query", "expected", "rank", "hit@1", "hit@k", "top_chunk", "top_score"])
            for r in rows:
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), r["id"], r["query"], r["expected"],
                            r["rank"], r["hit_at_1"], r["hit_at_k"], r["top"], r["top_score"]])
        logger.info("RETEVAL n=%d Hit@1=%.2f Hit@%d=%.2f MRR=%.2f",
                    summary["n"], summary["hit_at_1"], top_k, summary["hit_at_k"], summary["mrr"])
        return {"summary": summary, "rows": rows}

    def ask(self, query, tester="tester", top_k=None, threshold=None):
        top_k = top_k or self.cfg.get("top_k", 4)
        threshold = threshold if threshold is not None else self.cfg.get("sim_threshold", 0.06)
        t0 = time.time()
        logger.info("QUERY   tester=%s  q=%r", tester, query)
        trace = {"query": query, "tester": tester, "top_k": top_k, "threshold": threshold,
                 "poison_mode": self.poison, "steps": [], "flags": []}

        # 1. input guardrail
        action, cat, reason, pat = input_guardrail(query)
        trace["steps"].append({"stage": "input_guardrail", "action": action, "category": cat, "pattern": pat})
        if action == "refuse":
            logger.info("GUARD   REFUSE (%s) pattern=%r", cat, pat)
            trace["flags"].append("refused:" + cat)
            resp = {"answer": reason, "refused": True, "abstained": False, "category": cat,
                    "chunks": [], "flags": trace["flags"]}
            trace["answer"] = reason; trace["latency_ms"] = int((time.time()-t0)*1000)
            write_trace(trace)
            return resp

        # 2. retrieve
        hits = self.store.search(query, top_k)
        logger.info("RETRIEVE top_k=%d -> %s", top_k,
                    ", ".join("%s(%.3f)" % (h["id"], h["score"]) for h in hits) or "no matches")
        trace["retrieved"] = [{"id": h["id"], "doc": h["doc"], "section": h["section"],
                               "score": h["score"], "text": h["text"]} for h in hits]

        best = hits[0]["score"] if hits else 0.0
        # 3. abstain if nothing relevant — by score OR by query-term coverage.
        #    coverage = fraction of the meaningful query terms that appear in the
        #    top retrieved chunks. This lets real questions through while still
        #    abstaining on out-of-KB topics that happen to score above threshold.
        qterms = [t for t in dict.fromkeys(tokenize(query)) if t not in STOP and len(t) > 2]
        coverage = 1.0
        present = []
        if hits and qterms:
            topk_tokens = set()
            for h in hits[:3]:
                topk_tokens |= set(tokenize(h["text"] + " " + h["section"] + " " + h["doc"]))
            present = [t for t in qterms if t in topk_tokens]
            coverage = len(present) / len(qterms)
            trace["steps"].append({"stage": "coverage", "query_terms": qterms,
                                   "present": present, "coverage": round(coverage, 2),
                                   "min_required": COVERAGE_MIN})
        if not hits or best < threshold or coverage < COVERAGE_MIN:
            msg = ("I don't have that information in my knowledge base. "
                   "Please check official sources or our booking system.")
            logger.info("ABSTAIN best_score=%.3f threshold=%.3f coverage=%.2f",
                        best, threshold, coverage)
            trace["steps"].append({"stage": "grounding", "action": "abstain",
                                   "best_score": best, "coverage": round(coverage, 2)})
            trace["flags"].append("abstained")
            for h in hits:
                h["used"] = False
            trace["answer"] = msg; trace["latency_ms"] = int((time.time()-t0)*1000)
            write_trace(trace)
            return {"answer": msg, "refused": False, "abstained": True, "category": None,
                    "chunks": hits, "flags": trace["flags"]}

        # 4. inspect retrieved chunks for poisoning / indirect injection
        used = []
        for h in hits:
            if h["score"] >= threshold and h["score"] >= best * 0.5:
                clean = h["text"]
                injected = bool(INDIRECT.search(clean))
                if injected:
                    logger.info("GUARD   indirect injection detected in chunk %s (defenses=%s)",
                                h["id"], self.defenses)
                    if self.defenses:
                        trace["flags"].append("indirect_injection_neutralised:" + h["id"])
                        clean = INDIRECT.sub("[instruction-in-source ignored]", clean)
                    else:
                        trace["flags"].append("BREACH_indirect_injection_executed:" + h["id"])
                if h["doc"].startswith("POISON_"):
                    trace["flags"].append("poisoned_source_used:" + h["id"])
                used.append(dict(h, clean=clean, injected=injected))

        # 5. compose a grounded answer from the used chunk(s)
        answer = self._compose(query, used)
        answer, pii = redact_pii(answer)
        if pii:
            trace["flags"] += ["pii_" + p for p in pii]
            logger.info("GUARD   redacted PII: %s", pii)

        for h in hits:
            h["used"] = any(u["id"] == h["id"] for u in used)
        trace["steps"].append({"stage": "grounding", "action": "answer",
                               "used_chunks": [u["id"] for u in used], "best_score": best})
        trace["answer"] = answer; trace["latency_ms"] = int((time.time()-t0)*1000)
        write_trace(trace)
        logger.info("ANSWER  used=%d chunk(s) latency=%dms", len(used), trace["latency_ms"])
        return {"answer": answer, "refused": False, "abstained": False, "category": None,
                "chunks": hits, "flags": trace["flags"]}

    def _compose(self, query, used):
        if not used:
            return "I don't have that information in my knowledge base."
        top = used[0]
        cite = "%s — %s" % (top["doc"], top["section"])
        body = top["clean"].strip()
        # keep the answer concise: first ~3 sentences of the top chunk
        sents = re.split(r"(?<=[.!?])\s+", body)
        snippet = " ".join(sents[:3]).strip()
        parts = ["Based on our knowledge base: " + snippet]
        if top.get("last_updated"):
            parts.append("(Source last updated: %s.)" % top["last_updated"])
        if re.search(r"visa|entry requirement", query, re.IGNORECASE) or "visa" in top["doc"].lower():
            parts.append("Please verify with the official embassy/consulate before you travel.")
        parts.append("[source: %s]" % cite)
        # add a secondary citation if a second distinct doc was used
        if len(used) > 1 and used[1]["doc"] != top["doc"]:
            parts.append("[also see: %s — %s]" % (used[1]["doc"], used[1]["section"]))
        return " ".join(parts)


def load_config():
    path = os.path.join(BASE, "config.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------
# Knowledge-base management (add / list / delete documents at runtime)
# All operations are confined to KB_DIR; the poison folder is never
# writable from here. Every change is logged and the caller re-indexes.
# ------------------------------------------------------------------
def safe_kb_name(name):
    """Slugify to a safe .md basename inside kb/ (no path traversal)."""
    base = os.path.splitext(os.path.basename(str(name or "")))[0]
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_").lower()
    return slug[:60]


def list_kb():
    items = []
    for fn in sorted(os.listdir(KB_DIR)):
        if fn.endswith(".md"):
            p = os.path.join(KB_DIR, fn)
            items.append({"name": fn[:-3], "bytes": os.path.getsize(p)})
    return items


def add_kb_doc(name, content):
    slug = safe_kb_name(name)
    if not slug:
        return {"ok": False, "error": "Please provide a valid document name."}
    content = str(content or "").strip()
    if not content:
        return {"ok": False, "error": "The document content is empty."}
    if len(content) > 200_000:
        return {"ok": False, "error": "Document too large (200 KB max)."}
    path = os.path.join(KB_DIR, slug + ".md")
    existed = os.path.exists(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    logger.info("KBADD   %s kb/%s.md (%d bytes)", "updated" if existed else "added", slug, len(content))
    return {"ok": True, "name": slug, "updated": existed}


def delete_kb_doc(name):
    slug = safe_kb_name(name)
    path = os.path.abspath(os.path.join(KB_DIR, slug + ".md"))
    if not (slug and os.path.isfile(path) and path.startswith(os.path.abspath(KB_DIR) + os.sep)):
        return {"ok": False, "error": "Document not found."}
    os.remove(path)
    logger.info("KBDEL   removed kb/%s.md", slug)
    return {"ok": True, "name": slug}


def build_destination_md(name, best_time="", attractions="", safety="", notes=""):
    """Turn a guided 'add destination' form into a well-structured markdown doc."""
    title = str(name or "").strip()
    out = ["last_updated: %s" % time.strftime("%Y-%m-%d"), "", "# %s" % title, ""]
    if str(best_time).strip():
        out += ["## Best time to visit", str(best_time).strip(), ""]
    if str(attractions).strip():
        out += ["## Top attractions"]
        for a in [x.strip() for x in re.split(r"[\n,]", str(attractions)) if x.strip()]:
            out.append("- " + a)
        out += [""]
    if str(safety).strip():
        out += ["## Safety notes", str(safety).strip(), ""]
    if str(notes).strip():
        out += ["## Good to know", str(notes).strip(), ""]
    return "\n".join(out)
