from checker.result import PASS, SKIP

AI_OFF = "AI checks are turned off."  # the message of run_checks

# The rules that look at the same thing as a question
SAME_POINT = {"status_or_result": "What is the status", "concrete_tasks": "What exactly", "terms_explained": "A reader who", "real_blockers": "Do you have any blockers"}


def points_to_check(questions: list[str], results, edited: bool) -> list[str]:
    """
    The questions and the failed rules, with each point only once.
    """
    points, skipped = list(questions), {}
    for result in results:
        same = [point for point in points if result.rule_id in SAME_POINT and point.startswith(SAME_POINT[result.rule_id])]
        if result.status == PASS and edited:  # the edits answered it
            points = [point for point in points if point not in same]
        elif result.status == SKIP and result.message != AI_OFF:
            skipped.setdefault(result.message, []).append(result.title)
        elif result.status != PASS and result.message != AI_OFF and not same:
            points.append(" ".join(f"{result.title}: {result.message} {result.where}".split()))
    # the same reason for several rules is one point
    return points + [f"{len(titles)} rule{'' if len(titles) == 1 else 's'} not checked. {reason}" for reason, titles in skipped.items()]
