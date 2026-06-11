output "postgres_endpoint" {
  description = "RDS hostname — set POSTGRES_HOST in .env"
  value       = aws_db_instance.postgres.address
}

output "postgres_port" {
  value = aws_db_instance.postgres.port
}

output "postgres_connection_hint" {
  description = "Example psql connection"
  value       = "psql -h ${aws_db_instance.postgres.address} -U ${var.postgres_user} -d ${var.postgres_db}"
}
