# Log verification commands (sample)

Run on the host where application logs are written (`LOGS_DIR` from `bob setup`).

```bash
cd "$LOGS_DIR"
rg -n "inquireCardEligibility" . --glob "*.log" | head -50
```
