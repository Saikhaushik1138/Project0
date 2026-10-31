# Contributing

1. Create a branch describing one change.
2. Install locally with `python -m pip install -e .` in a virtual environment.
3. Run `python -m unittest discover -s tests -v` and the README demo.
4. Add regression coverage for security-relevant behavior and document changes to the wire format.
5. Open a pull request describing the problem, change, validation, and remaining limitations.

Keep tests offline and deterministic where possible. Never commit secrets, packet captures containing credentials, or personal flight logs. Do not claim integration, benchmark, or security results without reproducible evidence. Changes to the envelope require versioning and explicit compatibility discussion.
