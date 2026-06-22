# Log verification commands (sample)

Run on the host where application logs are written (`LOGS_DIR` from `bob setup`).

```bash
cd "$LOGS_DIR"
grep -rn --include="*.log" --include="*.out" --include="*.err" "inquireCardEligibility" . | head -50
```

