# je-dev-skills

## Prompt Evaluation Framework

LLM-graded prompt/agent evaluation: generate a diverse test dataset from a
plain-English task, run your prompt-under-test against it, and grade each output
with an LLM judge into a scored report.

- **Spec & setup guide:** [docs/PROMPT_EVAL_FRAMEWORK_SPEC.md](docs/PROMPT_EVAL_FRAMEWORK_SPEC.md)
- **Reference implementation (Python):** [evals/](evals/) — see [evals/README.md](evals/README.md)

Verify offline (no API key needed):

```bash
python -m unittest discover -s evals/tests -t .
python -m evals.examples.smoke_test
```
