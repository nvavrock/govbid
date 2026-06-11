variable "aws_region" {
  type        = string
  description = "AWS region (e.g. us-east-1)"
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  default     = "govbid"
}

variable "postgres_user" {
  type    = string
  default = "govbid"
}

variable "postgres_password" {
  type        = string
  sensitive   = true
  description = "RDS master password — set in terraform.tfvars (never commit)"
}

variable "postgres_db" {
  type    = string
  default = "govbid"
}

variable "admin_cidr" {
  type        = string
  description = "CIDR allowed to connect to RDS on 5432 (use YOUR.PUBLIC.IP/32)"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}
