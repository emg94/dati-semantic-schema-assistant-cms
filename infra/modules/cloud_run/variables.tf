variable "project_id" {
  description = "Google Cloud project id."
  type        = string
}

variable "region" {
  description = "Cloud Run region."
  type        = string
}

variable "environment" {
  description = "Environment name."
  type        = string
}

variable "service_prefix" {
  description = "Prefix shared by Schema Assistant resources."
  type        = string
}

variable "labels" {
  description = "Labels applied to supported resources."
  type        = map(string)
}

variable "agent_image" {
  description = "Agent container image."
  type        = string
}

variable "ingestion_image" {
  description = "Ingestion job container image."
  type        = string
}

variable "agent_service_account_email" {
  description = "Service account used by the agent."
  type        = string
}

variable "ingestion_service_account_email" {
  description = "Service account used by the ingestion job."
  type        = string
}

variable "bucket_name" {
  description = "Application data bucket."
  type        = string
}

variable "firestore_database_name" {
  description = "Firestore database id."
  type        = string
}

variable "developer_invokers" {
  description = "IAM members allowed to invoke dev Cloud Run resources."
  type        = list(string)
}

variable "deletion_protection" {
  description = "Cloud Run deletion protection."
  type        = bool
}
