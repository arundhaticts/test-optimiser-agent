"""
The retry/degrade wrapper — every external call goes through here (Blocker #3).

MUST CONTAIN:
- call_tool(fn, *args, retries, backoff): try with exponential backoff on
  TransientError; no retry on FatalError; return {'ok': bool, 'data'/'error'}.
- A place to append failures to state['tool_errors'] so the report can show them.
Ensures one failed dependency degrades gracefully instead of crashing the graph.
"""
