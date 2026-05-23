---
name: builder-one-shot
description: >-
  Bob the Builder — full ticket flow: setup, init-ticket, spec, implement, validate-ticket.
disable-model-invocation: true
---

# Builder one-shot

**Bob must never run `git commit`, `git push`, or create PRs.** File writes only.

```bash
bob setup
bob install          # optional workspace copy
bob init-ticket ID "Title"
# analyst fills ticket-spec; implementer codes; then:
bob ensure-peers   # optional — boot discovered Novopay peers (not bank/HDFC)
bob validate-ticket ID
```

Guide: `docs/TDD_SYSTEM_DEVELOPER_GUIDE.md`
