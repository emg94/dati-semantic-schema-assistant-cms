variable "project_id" {
  description = "Google Cloud project used by the dev environment."
  type        = string
  default     = "istat-ndc-schema-ass-cms-dev"
}

variable "region" {
  description = "Primary Google Cloud region. europe-west8 is Milan."
  type        = string
  default     = "europe-west8"
}

variable "firestore_location" {
  description = "Firestore location. Keep it aligned with the runtime region when possible."
  type        = string
  default     = "europe-west8"
}

variable "environment" {
  description = "Short environment name used in resource names."
  type        = string
  default     = "dev"
}

variable "service_prefix" {
  description = "Prefix shared by the Schema Assistant cloud resources."
  type        = string
  default     = "schema-assistant"
}

variable "developer_invokers" {
  description = "IAM principals allowed to invoke the private dev agent and manual ingestion job."
  type        = list(string)

  validation {
    condition = length(var.developer_invokers) > 0 && alltrue([
      for member in var.developer_invokers :
      can(regex("^(user|group|serviceAccount):", member))
    ])
    error_message = "Use IAM member syntax, for example user:name@example.com."
  }
}

variable "enabled_services" {
  description = "Project APIs managed by Terraform after the one-time Service Usage bootstrap."
  type        = set(string)
  default = [
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "datastore.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ]
}

variable "bucket_name" {
  description = "Optional globally unique bucket name. Empty value derives one from project and environment."
  type        = string
  default     = ""
}

variable "artifact_registry_repository_id" {
  description = "Artifact Registry repository used for the agent and ingestion images."
  type        = string
  default     = "schema-assistant"
}

variable "agent_image" {
  description = "Bootstrap image for the agent. Application deploys update it outside Terraform."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "ingestion_image" {
  description = "Bootstrap image for the ingestion job. Application deploys update it outside Terraform."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/job"
}

variable "force_destroy_bucket" {
  description = "Allows Terraform to delete a non-empty dev bucket. Keep false unless you are intentionally cleaning dev."
  type        = bool
  default     = false
}

variable "firestore_deletion_policy" {
  description = "Terraform behavior on destroy. ABANDON avoids accidental database deletion."
  type        = string
  default     = "ABANDON"

  validation {
    condition     = contains(["ABANDON", "DELETE"], var.firestore_deletion_policy)
    error_message = "Use ABANDON or DELETE."
  }
}

variable "firestore_delete_protection" {
  description = "Firestore delete protection. Dev starts disabled, while Terraform still abandons the database by default."
  type        = bool
  default     = false
}

variable "cloud_run_deletion_protection" {
  description = "Cloud Run deletion protection. Dev starts disabled to keep iteration simple."
  type        = bool
  default     = false
}
