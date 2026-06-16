# Scoring prompt (Node 5)

MUST CONTAIN: instructions for the reasoning model to score the suite across the
quality dimensions, returning STRICT JSON only (score + reason + recommended action
per dimension). State that missing data => "insufficient evidence", never a guess.
Include the dimension list and the score scale (e.g. 0-10).
