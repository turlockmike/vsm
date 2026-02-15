#!/usr/bin/env python3
"""
VSM Self-Test Suite

Validates core VSM components are functional without requiring external services.
Run: python3 tests/selftest.py
"""

import sys
import json
import unittest
import subprocess
from pathlib import Path

# Add project root to path for imports
VSM_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(VSM_ROOT / "core"))
sys.path.insert(0, str(VSM_ROOT / "web"))


class TestCoreController(unittest.TestCase):
    """Test core/controller.py"""

    def test_controller_imports(self):
        """Controller module imports successfully"""
        try:
            import controller
            self.assertTrue(hasattr(controller, 'load_state'))
            self.assertTrue(hasattr(controller, 'save_state'))
            self.assertTrue(hasattr(controller, 'check_health'))
            self.assertTrue(hasattr(controller, 'gather_tasks'))
        except ImportError as e:
            self.fail(f"Failed to import controller: {e}")

    def test_controller_state_functions(self):
        """Controller state functions are callable"""
        import controller

        # load_state should return a dict
        state = controller.load_state()
        self.assertIsInstance(state, dict)
        self.assertIn('criticality', state)
        self.assertIn('cycle_count', state)

    def test_controller_health_check(self):
        """Controller health check returns valid data"""
        import controller

        health = controller.check_health()
        self.assertIsInstance(health, dict)
        self.assertIn('disk_free_gb', health)
        self.assertIn('pending_tasks', health)
        self.assertIn('cron_installed', health)


class TestCoreComm(unittest.TestCase):
    """Test core/comm.py"""

    def test_comm_imports(self):
        """Communication module imports successfully"""
        try:
            import comm
            self.assertTrue(hasattr(comm, 'send_email'))
            self.assertTrue(hasattr(comm, 'load_config'))
        except ImportError as e:
            self.fail(f"Failed to import comm: {e}")

    def test_comm_functions_exist(self):
        """Communication functions are callable"""
        import comm

        # send_email should be a function
        self.assertTrue(callable(comm.send_email))

        # load_config should work
        config = comm.load_config()
        self.assertIsInstance(config, dict)


class TestCoreMemory(unittest.TestCase):
    """Test core/memory.py"""

    def test_memory_imports(self):
        """Memory module imports successfully"""
        try:
            import memory
            self.assertTrue(hasattr(memory, 'load_memory'))
            self.assertTrue(hasattr(memory, 'append_to_memory'))
            self.assertTrue(hasattr(memory, 'init_memory_files'))
        except ImportError as e:
            self.fail(f"Failed to import memory: {e}")

    def test_memory_functions_exist(self):
        """Memory functions are callable"""
        import memory

        self.assertTrue(callable(memory.load_memory))
        self.assertTrue(callable(memory.append_to_memory))
        self.assertTrue(callable(memory.init_memory_files))

    def test_memory_load(self):
        """Memory system loads without errors"""
        import memory

        result = memory.load_memory()
        self.assertIsInstance(result, str)


class TestWebServer(unittest.TestCase):
    """Test web/server.py"""

    def test_web_server_imports(self):
        """Web server module imports successfully"""
        try:
            import server
            self.assertTrue(hasattr(server, 'VSMHandler'))
            self.assertTrue(hasattr(server, 'run_server'))
        except ImportError as e:
            self.fail(f"Failed to import server: {e}")


class TestTaskQueue(unittest.TestCase):
    """Test task queue infrastructure"""

    def test_tasks_directory_exists(self):
        """sandbox/tasks/ directory exists"""
        tasks_dir = VSM_ROOT / "sandbox" / "tasks"
        self.assertTrue(tasks_dir.exists(), f"Tasks directory not found: {tasks_dir}")
        self.assertTrue(tasks_dir.is_dir())

    def test_task_files_parseable(self):
        """Existing task files are valid JSON"""
        tasks_dir = VSM_ROOT / "sandbox" / "tasks"

        for task_file in tasks_dir.glob("*.json"):
            # Skip archive directory
            if task_file.parent.name == "archive":
                continue

            with self.subTest(task_file=task_file.name):
                try:
                    with open(task_file, 'r') as f:
                        task_data = json.load(f)

                    # Validate basic task structure
                    self.assertIsInstance(task_data, dict)
                    # Tasks should have at least an id or title
                    self.assertTrue('id' in task_data or 'title' in task_data)
                except json.JSONDecodeError as e:
                    self.fail(f"Invalid JSON in {task_file}: {e}")


class TestStateFile(unittest.TestCase):
    """Test state/state.json"""

    def test_state_file_exists(self):
        """state.json exists"""
        state_file = VSM_ROOT / "state" / "state.json"
        self.assertTrue(state_file.exists(), f"State file not found: {state_file}")

    def test_state_file_valid_json(self):
        """state.json is valid JSON"""
        state_file = VSM_ROOT / "state" / "state.json"

        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)
        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON in state file: {e}")

    def test_state_file_has_required_keys(self):
        """state.json has required keys"""
        state_file = VSM_ROOT / "state" / "state.json"

        with open(state_file, 'r') as f:
            state_data = json.load(f)

        required_keys = ['criticality', 'cycle_count', 'health', 'errors']
        for key in required_keys:
            self.assertIn(key, state_data, f"Missing required key: {key}")


class TestCron(unittest.TestCase):
    """Test cron installation"""

    def test_crontab_has_vsm_entries(self):
        """Crontab contains VSM entries"""
        try:
            result = subprocess.run(
                ['crontab', '-l'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                crontab_content = result.stdout.lower()
                self.assertIn('vsm', crontab_content,
                            "Crontab does not contain VSM entries")
            else:
                self.skipTest("No crontab installed")
        except FileNotFoundError:
            self.skipTest("crontab command not available")
        except subprocess.TimeoutExpired:
            self.fail("crontab command timed out")


class TestDashboard(unittest.TestCase):
    """Test dashboard HTML"""

    def test_dashboard_html_exists(self):
        """Dashboard HTML file exists"""
        # Check both possible locations
        html_file1 = VSM_ROOT / "web" / "index.html"
        html_file2 = VSM_ROOT / "web" / "static" / "dashboard.html"

        exists = html_file1.exists() or html_file2.exists()
        self.assertTrue(exists,
                       f"Dashboard HTML not found at {html_file1} or {html_file2}")


class TestRunner(unittest.TextTestRunner):
    """Custom test runner with summary"""

    def run(self, test):
        """Run tests and print summary"""
        result = super().run(test)

        print("\n" + "="*70)
        print("VSM SELF-TEST SUMMARY")
        print("="*70)

        # Component status
        components = [
            ("core/controller.py", "TestCoreController"),
            ("core/comm.py", "TestCoreComm"),
            ("core/memory.py", "TestCoreMemory"),
            ("web/server.py", "TestWebServer"),
            ("Task Queue", "TestTaskQueue"),
            ("State File", "TestStateFile"),
            ("Cron Setup", "TestCron"),
            ("Dashboard HTML", "TestDashboard"),
        ]

        for component_name, test_class in components:
            # Check if any tests for this component failed
            failed = any(
                test_class in str(test_case[0])
                for test_case in result.failures + result.errors
            )

            status = "FAIL" if failed else "PASS"
            symbol = "✗" if failed else "✓"
            print(f"  {symbol} {component_name:<30} {status}")

        print("="*70)
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Skipped: {len(result.skipped)}")

        if result.wasSuccessful():
            print("\nResult: ALL TESTS PASSED")
            return result
        else:
            print("\nResult: SOME TESTS FAILED")
            return result


def main():
    """Run all tests"""
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])

    runner = TestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with proper code
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
