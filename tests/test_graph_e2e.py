"""
End-to-end: run the full graph on the sample_data/ suite, auto-answering the 3 HITL
interrupts, and assert the four outputs are produced and the audit_log is complete.

Also assert the run reproduces sample_data/expected_findings.json (the golden set):
the near-duplicate cluster, the flaky test (test_checkout_total), the slow test
(test_payment_gateway), and the AC-3 coverage gap. This is regression coverage on
the agent's analysis quality, not just that it ran without crashing.
"""
