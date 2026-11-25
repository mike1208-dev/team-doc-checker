"""
Finds the statuses that plain notes give to PRs, issues and tasks. It only says whether a status of the AI is supported;
it never chooses one itself.
"""

import re
from dataclasses import dataclass, field
from difflib import get_close_matches

WORDS = {
    "Merged": r"\bmerged\b|マージ(?:済|した|しました|完了|されました)",
    "In review": r"\b(?:waiting for|awaiting|under|pending) (?:\w+ )?review\b|\breview\b|レビュー(?:中|待ち)",
    "In progress": r"\bin progress\b|\bwip\b|\bongoing\b|\bworking on\b|\binvestigating\b|\bunfinished\b|\bstarted\b|\bstill (?:on|doing|open)\b|\bci is running\b"
    r"|\bnot (?:finished|done|complete)\b|\bnot merged\b|進行中|対応中|作業中",
    "Draft": r"\bdraft\b|ドラフト",
    "Closed": r"\bclosed\b|クローズ",
    "Open": r"\b(?:re)?open(?:ed)?\b",
    "Done": r"\b(?:done|finished|completed?|fixed|deployed|shipped|released|passed|pass|solved|resolved|verified)\b|\bit work(?:s|ed)\b|\bworks (?:now|well|fine)\b|\blooks? (?:ok|good)\b"
    r"|✅|完了|修正した|修正しました|対応済|問題なし",
}
PR_STATUSES = {"Merged", "In review", "Draft", "Closed", "Open"}
FINISHED = {"Merged", "Done"}
NOT = r"\b(?:not|never|no|cannot|without)\b|n['’]t\b|\b(?:isnt|wasnt|havent|hasnt|didnt)\b"
NOT_YET = r"\b(?:will|would|gonna|going to|to be|after|until|once|when|if|ask(?:ing)? for|ready for|almost|nearly|half|only|should|want to|need(?:s)? to)\b"
NUMBER = re.compile(r"(?:\bprs?|\bpull requests?|\bissues?|\btickets?|\bmr|#|/pull/|/issues/)[\s-]*#?\s*(\d+)", re.IGNORECASE)
TYPOS = ("merged", "review", "finished", "completed")
NOT_TYPOS = {"merge", "merges", "merging", "emerged", "reviews", "reviewed", "reviewer", "preview", "previews", "finish", "finishes", "complete", "completes", "unfinished"}


@dataclass
class Evidence:
    said: set[str] = field(default_factory=set)
    denied: set[str] = field(default_factory=set)

    def add(self, other: "Evidence"):
        self.said |= other.said
        self.denied |= other.denied


def sentences(notes: str) -> list[str]:
    return [part for part in re.split(r"[\n;。]|(?<=[.!?])\s+", notes) if part.strip()]


def _fix_typos(text: str) -> str:
    def fix(match):
        word = match[0].lower()
        close = [] if word in NOT_TYPOS else get_close_matches(word, TYPOS, n=1, cutoff=0.83)
        return close[0] if close else match[0]

    return re.sub(r"\b[A-Za-z]{5,10}\b", fix, text)


def _find(text: str) -> list[tuple[int, str, bool]]:
    """
    (position, status, whether it's denied) of each status in the text. "will be merged" is neither said nor denied.
    """
    found = []
    for status, pattern in WORDS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            before = " ".join(text[: match.start()].split()[-3:])
            if re.search(NOT, before, re.IGNORECASE):
                found.append((match.start(), status, True))
            elif not re.search(NOT_YET, before, re.IGNORECASE):
                found.append((match.start(), status, False))
        if status == "Merged" and re.search(r"マージ(?:されて|して)い?(?:ない|ません)", text):
            found.append((0, status, True))
    return found


def _evidence(found) -> Evidence:
    return Evidence({status for _, status, denied in found if not denied}, {status for _, status, denied in found if denied})


def by_number(notes: str) -> dict[str, Evidence]:
    """
    The statuses the notes give to each PR or issue number.
    """
    result: dict[str, Evidence] = {}
    for sentence in sentences(_fix_typos(notes)):
        active: list[str] = []
        for clause in re.split(r",|、|\bbut\b|\s/\s", sentence):
            numbers = [(match.start(), match[1]) for match in NUMBER.finditer(clause)]
            found = _find(clause)
            if numbers:
                active = [number for _, number in numbers]
                for item in found:  # a status belongs to the number before it, or to the first one after it
                    before = [number for position, number in numbers if position < item[0]]
                    result.setdefault(before[-1] if before else active[0], Evidence()).add(_evidence([item]))
            elif active:
                for number in active:
                    result.setdefault(number, Evidence()).add(_evidence(found))
            for number in active:
                result.setdefault(number, Evidence())
        if not active:
            for number in result:
                result[number].said |= _of_all(sentence)
    return result


def _of_all(sentence: str) -> set[str]:
    """
    The statuses of a sentence such as "both merged".
    """
    is_for_all = re.match(r"\W*(?:\w+\s+)?(?:both|all|everything)\b(?!\s+(?:tests?|checks?|pass))", sentence, re.IGNORECASE)
    return _evidence(_find(sentence)).said if is_for_all else set()


def words(text: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]{4,}", re.sub(r"https?://\S+", " ", text.lower())))


def same_words(text: str, other: str) -> set[str]:
    """
    The words of the text that are in the other one too. "fixing" and "fixed" are the same, and so is a word with a typo.
    """
    others = words(other)
    starts = {word[:4] for word in others}
    return {word for word in words(text) if word[:4] in starts or get_close_matches(word, others, n=1, cutoff=0.8)}


def _of_task(task: str, notes: str) -> Evidence:
    """
    The statuses in the sentence that is most like the task, or in a short one after it.
    """
    parts = sentences(_fix_typos(notes))
    if not parts:
        return Evidence()
    scores = [len(same_words(task, part)) for part in parts]
    best = scores.index(max(scores))
    if not scores[best]:
        return Evidence()
    text = parts[best]
    after = parts[best + 1] if best + 1 < len(parts) else ""
    if after and len(after.split()) <= 5 and not NUMBER.search(after) and not re.match(r"\W*(?:today|tomorrow|next|plan|no block|block)", after, re.IGNORECASE):
        text += ", " + after
    evidence = _evidence(_find(text))
    for part in parts[best + 1 :]:
        evidence.said |= _of_all(part)
    return evidence


def check(status: str, numbers: list[str], task: str, notes: str, known: dict[str, Evidence] | None = None) -> str:
    """
    "ok" if the notes support the status, "conflict" if they say that the work is finished and that it isn't, or "".
    """
    known = by_number(notes) if known is None else known
    given = Evidence()
    for number in numbers:
        given.add(known.get(number, Evidence()))
    if given.said & FINISHED and given.denied & FINISHED and not given.said & (PR_STATUSES - {"Merged"}):
        return "conflict"
    if status in given.denied:
        return ""
    if status in given.said:
        return "ok"
    if given.said & PR_STATUSES:  # the notes give another one
        return ""
    of_task = _of_task(task, notes)
    return "ok" if status in of_task.said and status not in of_task.denied else ""
