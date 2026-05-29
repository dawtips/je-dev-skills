You are turning ONE scenario idea into a single, fully-specified evaluation test case.

# Task
{task_description}

# Scenario
{scenario}

# Allowed input keys (CLOSED SET)
You MUST populate exactly these keys — every one of them, and no others:
{allowed_keys}

Descriptions of each input (use these to choose realistic values):
{prompt_inputs_spec}

# Output
Return a JSON object with exactly two fields:
- "prompt_inputs": an object containing every allowed key with a concrete, realistic value for this scenario.
- "solution_criteria": an array of 1 to 4 concise, measurable checks that a correct output MUST satisfy.

# Rules for solution_criteria (READ CAREFULLY)
- Address ONLY the core requirement of the task. Do NOT over-specify.
- Each criterion must be objectively checkable — not a matter of taste or style.
- Fewer, tighter criteria are better than many loose ones.

Worked example — for the task "Summarize an article in one sentence", the IDEAL criteria is a single tight check:
["The summary is one sentence and captures the article's main claim."]

A BAD version over-specifies and drifts into subjective style:
["Is engaging", "Is creative", "Is well formatted", "Is insightful", "Uses active voice"]

Return ONLY the JSON object. No extra fields, no commentary.
