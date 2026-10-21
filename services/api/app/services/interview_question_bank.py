"""
Static question bank backing the HEURISTIC provider only (AI_PROVIDER
unset/"none", and what tests run against). This is NOT the AI Question
Engine itself — it's the deterministic, offline-testable fallback
behind app/ai/providers/heuristic_provider.py. A real AI_PROVIDER
(e.g. "anthropic") never touches this file.

Organized by round -> topic/competency, straight from the spec's
TECHNICAL/MANAGERIAL/HR ROUND sections (see
app/services/round_competencies.py for the canonical topic lists).
Managerial questions are deliberately phrased as scenarios, per the
spec's "use scenario-based questions where appropriate."

One additional technical question TYPE is resume-grounded: if the
candidate's profile lists a skill, `pick_question` may return a
templated question naming it directly ("I see {skill} on your resume
...") — covering the spec's "questions from resume technologies" area
concretely, not just as inspiration passed into an AI prompt.
"""
from app.models.interview_template import InterviewRoundType

_BANK: dict[str, dict[str, list[str]]] = {
    InterviewRoundType.TECHNICAL: {
        "dsa": [
            "How would you find whether a linked list contains a cycle, and what's the time/space complexity of your approach?",
            "When would you reach for a hash map over a balanced binary search tree, and why?",
            "How would you find the k most frequent elements in a large list efficiently?",
        ],
        "algorithms": [
            "Walk me through how you'd approach a problem that looks like it needs brute force — how do you decide whether a better approach exists?",
            "What's the difference between a greedy algorithm and dynamic programming, and how do you decide which fits a given problem?",
            "How would you detect and handle an infinite loop risk in a recursive algorithm you're reviewing?",
        ],
        "oop": [
            "How would you explain the difference between composition and inheritance, and when do you prefer one over the other?",
            "What's the purpose of an interface or abstract class, and can you give an example from something you've built?",
            "How do you decide when a class has taken on too many responsibilities?",
        ],
        "dbms": [
            "What's the difference between an SQL join and a subquery, and when would you use each?",
            "How would you decide whether a column needs an index, and what's the tradeoff?",
            "Can you explain what a database transaction guarantees, and why that matters?",
        ],
        "operating_systems": [
            "How would you explain the difference between a process and a thread?",
            "What happens, at a high level, when a program you're running requests more memory than is currently free?",
            "How do you think about deadlock, and what's one way to avoid it?",
        ],
        "computer_networks": [
            "Can you explain what happens, step by step, when you type a URL into a browser and hit enter?",
            "What's the difference between TCP and UDP, and when would you choose one over the other?",
            "How would you debug a service that's intermittently slow only for some users?",
        ],
    },
    InterviewRoundType.MANAGERIAL: {
        "decision_making": [
            "Imagine you have two viable approaches to a task and no time to fully evaluate both — walk me through how you'd decide.",
        ],
        "ownership": [
            "Describe a situation where something you were responsible for wasn't going well. What did you do?",
        ],
        "teamwork": [
            "Tell me about a time you had to get a task done that depended heavily on someone else's work. How did you handle that dependency?",
        ],
        "conflict_handling": [
            "Imagine you and a teammate strongly disagree about a technical approach a week before a deadline. Walk me through what you'd do.",
        ],
        "leadership": [
            "Describe a time you had to get a group aligned on a direction without formal authority over them.",
        ],
        "problem_solving": [
            "Walk me through how you'd approach a problem where the root cause isn't obvious and the clock is ticking.",
        ],
        "prioritization": [
            "How do you prioritize tasks when everything feels urgent?",
        ],
        "project_understanding": [
            "Pick a project you've worked on — what tradeoffs did the team make, and would you make the same ones again?",
        ],
    },
    InterviewRoundType.HR: {
        "professional_communication": [
            "Tell me about a time you had to explain something technical to someone non-technical. How did you approach it?",
        ],
        "self_awareness": [
            "What would your teammates say is your biggest strength, and where do you think you still have room to grow?",
        ],
        "motivation": [
            "What draws you to this kind of role, specifically?",
        ],
        "career_goals": [
            "Where do you see yourself professionally in a couple of years?",
        ],
        "strengths_weaknesses": [
            "Tell me about a skill you've had to work hard to improve.",
        ],
        "professional_behavior": [
            "Tell me about a time you had to deliver difficult feedback or receive it.",
        ],
        "role_alignment": [
            "What are you looking for in your next role, and why does this one fit?",
        ],
    },
}

_RESUME_SKILL_TEMPLATES = [
    "I see {skill} on your resume — can you walk me through how you've used it?",
    "You've listed {skill} as one of your skills. What's a specific problem you solved with it?",
]


def _topic_order(round_type: str, topics: list[str]) -> list[str]:
    """Preferred topics first (filtered to ones the bank actually has),
    then any remaining bank topics as fallback so a round is never
    starved of questions just because a campaign specified an unknown
    category."""
    bank_topics = list(_BANK.get(round_type, {}).keys())
    ordered = [t for t in topics if t in bank_topics]
    ordered += [t for t in bank_topics if t not in ordered]
    return ordered


def pick_question(
    round_type: str,
    *,
    topics: list[str] | None = None,
    exclude: list[str],
    candidate_profile: dict | None = None,
    question_index: int = 0,
) -> tuple[str, str | None]:
    """
    Returns (question_text, topic). `topics` is the round's ordered
    competency/subject list (see round_competencies.topics_for_round);
    `question_index` (0-based, how many questions already asked this
    round) rotates through topics so a round doesn't ask three DSA
    questions in a row. Falls back to the first available bank
    question if every option is already excluded.
    """
    topics = topics or []

    # Occasionally ask a resume-grounded technical question, if the
    # candidate has any listed skills — covers the spec's "technologies
    # from resume" area with something concrete rather than generic.
    if (
        round_type == InterviewRoundType.TECHNICAL
        and candidate_profile
        and candidate_profile.get("skills")
        and question_index > 0
        and question_index % 3 == 2
    ):
        skill = candidate_profile["skills"][question_index % len(candidate_profile["skills"])]
        template = _RESUME_SKILL_TEMPLATES[question_index % len(_RESUME_SKILL_TEMPLATES)]
        text = template.format(skill=skill)
        if text not in exclude:
            return text, "resume_technologies"

    ordered_topics = _topic_order(round_type, topics)
    if not ordered_topics:
        return "Can you tell me more about your background?", None

    # Rotate the starting topic by question_index so consecutive
    # questions in a round cover different areas.
    rotated = ordered_topics[question_index % len(ordered_topics):] + ordered_topics[
        : question_index % len(ordered_topics)
    ]

    for topic in rotated:
        for q in _BANK[round_type][topic]:
            if q not in exclude:
                return q, topic

    # Every bank question for every topic has been asked already
    # (a long interview, or a very short bank) — fall back to the
    # first question overall rather than raising mid-interview.
    first_topic = ordered_topics[0]
    return _BANK[round_type][first_topic][0], first_topic
