data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_db_subnet_group" "govbid" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Project = var.project_name
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds"
  description = "GovBid RDS PostgreSQL"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "PostgreSQL from admin CIDR"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = var.project_name
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = var.postgres_db
  username = var.postgres_user
  password = var.postgres_password

  db_subnet_group_name   = aws_db_subnet_group.govbid.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible = true
  skip_final_snapshot = true

  backup_retention_period = 7

  tags = {
    Project = var.project_name
  }
}
