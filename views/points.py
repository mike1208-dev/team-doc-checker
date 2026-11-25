from checker.result import PASS

AI_OFF = "AI checks are turned off."  # the message of run_checks

# The rules that look at the same thing as a question
SAME_POINT = {"status_or_result": "What is the status", "concrete_tasks": "What exactly", "terms_explained": "A reader who", "real_blockers": "Do you have any blockers"}


def points_to_check(questions: list[str], results, edited: bool) -> list[str]:
    """
    The questions and the failed rules, with each point only once.
    """
    points = list(questions)
    for result in results:
        same = [point for point in points if result.rule_id in SAME_POINT and point.startswith(SAME_POINT[result.rule_id])]
        if result.status == PASS and edited:  # the edits answered it
            points = [point for point in points if point not in same]
        elif result.status != PASS and result.message != AI_OFF and not same:
            points.append(" ".join(f"{result.title}: {result.message} {result.where}".split()))
    return points
