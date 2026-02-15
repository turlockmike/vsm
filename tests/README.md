# VSM Test Suite

## Self-Test

Quick validation that all core VSM components are functional.

```bash
python3 tests/selftest.py
```

### What It Tests

- **core/controller.py** - State management, health checks, task gathering
- **core/comm.py** - Email communication module
- **core/memory.py** - Persistent memory system
- **web/server.py** - Dashboard web server
- **Task Queue** - Task directory exists and files are valid JSON
- **State File** - state.json exists with required keys
- **Cron Setup** - VSM cron entries are installed
- **Dashboard** - HTML files exist

### Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

### Example Output

```
======================================================================
VSM SELF-TEST SUMMARY
======================================================================
  ✓ core/controller.py             PASS
  ✓ core/comm.py                   PASS
  ✓ core/memory.py                 PASS
  ✓ web/server.py                  PASS
  ✓ Task Queue                     PASS
  ✓ State File                     PASS
  ✓ Cron Setup                     PASS
  ✓ Dashboard HTML                 PASS
======================================================================
Tests run: 16
Failures: 0
Errors: 0
Skipped: 0

Result: ALL TESTS PASSED
```

## Notes

- Tests run without network calls or LLM invocations
- Fast execution (< 1 second)
- Safe to run repeatedly
- Does not modify any files
