import re
from collections import Counter
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from src.models import Theme

THEME_RULES = {
    "Facilitator quality": ["facilitator", "teacher", "explained", "knowledgeable"],
    "Practical activities": ["practical", "exercise", "activity", "hands-on", "practice"],
    "Pacing": ["pace", "pacing", "quick", "fast", "slow", "rushed", "time"],
    "Course relevance": ["relevant", "useful", "work", "role", "applicable"],
    "Technical issues": ["technical", "audio", "login", "platform", "connection", "internet"],
    "Course materials": ["materials", "slides", "resources", "workbook", "notes"],
    "Engagement": ["engaging", "interactive", "discussion", "participation", "engagement"],
    "Examples and case studies": ["example", "examples", "case", "scenario", "industry"],
}
NEGATIVE = re.compile(r"\b(more|improve|too|not|issue|problem|difficult|rushed|fast|slow|less|missing)\b", re.I)

def extract_themes(comments: list[str], max_themes: int = 8) -> list[Theme]:
    clean = [str(c).strip() for c in comments if str(c).strip()]
    if not clean:
        return []
    found: list[Theme] = []
    lower = [c.lower() for c in clean]
    for name, words in THEME_RULES.items():
        idx = [i for i, text in enumerate(lower) if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)]
        if idx:
            negative_count = sum(bool(NEGATIVE.search(clean[i])) for i in idx)
            category = "Improvement" if negative_count > len(idx) / 2 else "Positive"
            ranked_idx = sorted(idx, key=lambda i: bool(NEGATIVE.search(clean[i])), reverse=category == "Improvement")
            evidence = [clean[i] for i in ranked_idx[:3]]
            matched = Counter(w for i in idx for w in words if w in lower[i]).most_common(4)
            found.append(Theme(name, [w for w, _ in matched], len(idx), category, evidence))
    if len(clean) >= 6:
        try:
            vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2, max_features=500)
            matrix = vec.fit_transform(clean)
            n_components = min(3, matrix.shape[0], matrix.shape[1])
            if n_components:
                model = NMF(n_components=n_components, random_state=42, init="nndsvda", max_iter=400).fit(matrix)
                terms = vec.get_feature_names_out()
                for component in model.components_:
                    words = [terms[i] for i in component.argsort()[-4:][::-1]]
                    if any(set(words) & set(theme.keywords) for theme in found):
                        continue
                    idx = [i for i, text in enumerate(lower) if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)]
                    if not idx:
                        continue  # no comment actually matches these terms; not a real theme
                    found.append(Theme("Emerging: " + ", ".join(words[:2]), words, len(idx), "Review", [clean[i] for i in idx[:3]]))
        except ValueError:
            pass
    return sorted(found, key=lambda t: t.frequency, reverse=True)[:max_themes]
