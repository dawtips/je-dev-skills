You are designing a diverse evaluation dataset for the task below.

# Task
{task_description}

# Allowed input variables
The prompt under test consumes exactly these inputs (keys) and no others:
{prompt_inputs_spec}

# Your job
Produce {num_cases} short, DISTINCT scenario ideas. Each will later become one test case.

Each idea MUST be:
- clearly distinct from the others (maximize diversity of situation, edge cases, and input combinations);
- directly relevant to the task;
- specific enough to drive a single concrete test case;
- quick to solve (no multi-step arithmetic or external research);
- solvable within a small output budget (about 400 tokens).

Return a JSON array of exactly {num_cases} strings. Each string is one scenario idea in a single sentence. Do not wrap it in an object and do not add extra fields.

Example shape (illustrative only):
["A wrestler cutting weight the week before a meet", "A vegan endurance runner in peak marathon training"]
