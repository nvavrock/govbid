# GovBid Terraform — AWS RDS

Minimal Terraform for **Phase 1**: PostgreSQL on RDS. Uses the account **default VPC** to keep the first apply small.

## Prerequisites

- AWS CLI + credentials (`aws sts get-caller-identity`)
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5

## Quick start

```bash
cd /home/me/govbid/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit postgres_password and admin_cidr (your public IP/32)

terraform init
terraform plan
terraform apply
```

After apply:

```bash
terraform output -raw postgres_endpoint
```

Set in repo `.env`:

```text
POSTGRES_HOST=<endpoint>
POSTGRES_PORT=5432
```

Run migrations:

```bash
cd /home/me/govbid
bash scripts/apply_migrations.sh
```

## Files

| File | Purpose |
|------|---------|
| `versions.tf` | Provider pin |
| `variables.tf` | Region, passwords, CIDR |
| `rds.tf` | RDS instance + security group |
| `outputs.tf` | Endpoint for `.env` |

## Teardown

```bash
terraform destroy
```

**Warning:** destroys the database unless you snapshot first.
