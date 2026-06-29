import unittest
from unittest.mock import patch

from data import pipeline_audit


class PipelineAuditTests(unittest.TestCase):
    def test_finish_task_run_closes_running_row_when_attempt_number_differs(self):
        config = {
            "database": "NFL_ANALYTICS",
            "schema": "audit",
        }

        with patch.object(pipeline_audit, "execute_audit_write") as audit_write:
            pipeline_audit.finish_task_run(
                run_id="test_run",
                task_name="test_task",
                attempt_number=2,
                task_status="succeeded",
                config=config,
            )

        sql = audit_write.call_args.args[0]

        self.assertIn("attempt_number = %s", sql)
        self.assertIn("OR task_status = 'running'", sql)


if __name__ == "__main__":
    unittest.main()
