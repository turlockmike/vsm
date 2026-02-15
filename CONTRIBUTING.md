# Contributing to VSM

Thanks for your interest in improving the Viable System Machine.

## Reporting Bugs

Found a bug? Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Relevant logs from `state/logs/`

## Submitting Code

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes following existing code patterns
4. Test by running at least one VSM cycle: `python3 core/controller.py`
5. Commit with a clear message
6. Push to your fork and open a pull request

## Code Style

- Follow existing patterns in the codebase
- Keep functions focused and single-purpose
- Use descriptive variable names
- Add comments for non-obvious logic
- Python: follow PEP 8 conventions

## Testing

Before submitting a PR:
- Run `python3 core/controller.py` to ensure the controller works
- Check that your changes don't break existing functionality
- If adding a new feature, test it in isolation first

## Questions?

Not sure about something? Open an issue to discuss before coding.
