# govbid

Federal contract opportunity tooling (SAM.gov bulk download and filtering).

## SAM.gov daily download

```bash
/home/me/govbid/run_download.sh
```

Cron (daily 6 AM): `0 6 * * * /home/me/govbid/run_download.sh`

Output: `data/ContractOpportunitiesFull_YYYYMMDD.csv` (only the latest file is kept).
